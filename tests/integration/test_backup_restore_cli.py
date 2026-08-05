# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from __future__ import annotations

import filecmp
import json
import shutil
import sqlite3
import threading
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

import pytest
import yaml

from plan_manager import __main__ as pm_cli
from plan_manager.domain.models import Status
from plan_manager.storage.backup_manifest import compute_tree_content_hash
from plan_manager.storage.db import DB_FILENAME, bootstrap
from plan_manager.storage.exporter import export_tree
from plan_manager.storage.importer import (
    LegacyImportError,
    import_legacy_tree,
    replace_plan_from_tree,
)
from plan_manager.storage.offline_guard import (
    LiveServerDetectedError,
    hold_server_lock,
    require_offline,
)
from plan_manager.storage.repositories import (
    append_event,
    create_plan,
    create_story,
    create_task,
    delete_plan,
)
from plan_manager.storage.uow import unit_of_work

if TYPE_CHECKING:
    from pathlib import Path


def _seed_plan(db_path: Path, plan_id: str, *, with_event: bool = True) -> None:
    with unit_of_work(db_path, write=True) as conn:
        create_plan(
            conn,
            base_id=plan_id,
            title=f"Plan {plan_id}",
            description="desc",
            status=Status.TODO,
            priority=1,
            ord_value=0,
        )
        create_story(
            conn,
            plan_id=plan_id,
            base_id="story",
            title="Story",
            description="story",
            status=Status.TODO,
            priority=1,
            acceptance_criteria=["done"],
            depends_on=[],
            ord_value=0,
            body="story body",
        )
        create_task(
            conn,
            plan_id=plan_id,
            story_id="story",
            base_local_id="task",
            title="Task",
            description="task",
            status=Status.TODO,
            priority=1,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            ord_value=0,
            body="task body",
        )
        if with_event:
            append_event(
                conn,
                plan_id=plan_id,
                event_type="task_created",
                scope={"task_id": "story:task"},
                data={"plan": plan_id},
            )


def _assert_trees_equal(left: Path, right: Path) -> None:
    comparison = filecmp.dircmp(left, right)
    assert comparison.left_only == []
    assert comparison.right_only == []
    assert comparison.funny_files == []
    _matches, mismatch, errors = filecmp.cmpfiles(
        left, right, comparison.common_files, shallow=False
    )
    assert mismatch == []
    assert errors == []
    for child in comparison.common_dirs:
        _assert_trees_equal(left / child, right / child)


def _read_event_seqs(db_path: Path) -> list[tuple[str, int]]:
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT plan_id, seq FROM events ORDER BY seq").fetchall()
    return [(str(row[0]), int(row[1])) for row in rows]


def _story_title(db_path: Path, plan_id: str) -> str:
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT title FROM stories WHERE plan_id = ? AND id = 'story'",
            (plan_id,),
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_round_trip_export_import_export_is_stable_and_preserves_seq(
    tmp_path: Path,
) -> None:
    source_db_dir = tmp_path / "db-source"
    source_db_path = bootstrap(source_db_dir)
    _seed_plan(source_db_path, "alpha")

    # Create/deleting a throwaway plan creates seq gaps that prove manifest restore fidelity.
    _seed_plan(source_db_path, "throwaway")
    with unit_of_work(source_db_path, write=True) as conn:
        delete_plan(conn, "throwaway")
    with unit_of_work(source_db_path, write=True) as conn:
        append_event(
            conn,
            plan_id="alpha",
            event_type="story_saved",
            scope={"story_id": "story"},
        )

    export_a = tmp_path / "export-a"
    export_tree(db_dir=source_db_dir, out_dir=export_a)
    original_seqs = _read_event_seqs(source_db_path)

    restored_db_dir = tmp_path / "db-restored"
    report = import_legacy_tree(todo_dir=export_a, db_dir=restored_db_dir)
    assert report.ok
    restored_seqs = _read_event_seqs(restored_db_dir / DB_FILENAME)
    assert restored_seqs == original_seqs

    export_b = tmp_path / "export-b"
    export_tree(db_dir=restored_db_dir, out_dir=export_b)
    _assert_trees_equal(export_a, export_b)


def test_manifest_tamper_or_invalid_manifest_is_refused(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    export_dir = tmp_path / "export"
    export_tree(db_dir=db_dir, out_dir=export_dir)

    tampered = tmp_path / "tampered"
    shutil.copytree(export_dir, tampered)
    (tampered / "alpha" / "plan.yaml").write_text("id: alpha\n", encoding="utf-8")
    with pytest.raises(LegacyImportError, match="content_hash mismatch"):
        import_legacy_tree(todo_dir=tampered, db_dir=tmp_path / "db-tampered")

    broken = tmp_path / "broken"
    shutil.copytree(export_dir, broken)
    (broken / "MANIFEST").write_text("{not-json", encoding="utf-8")
    with pytest.raises(LegacyImportError, match="invalid MANIFEST"):
        import_legacy_tree(todo_dir=broken, db_dir=tmp_path / "db-broken")


def test_export_replaces_target_and_removes_deleted_plan_dirs(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    _seed_plan(db_path, "ghost")
    out_dir = tmp_path / "backup"
    export_tree(db_dir=db_dir, out_dir=out_dir)
    assert (out_dir / "ghost").exists()

    with unit_of_work(db_path, write=True) as conn:
        delete_plan(conn, "ghost")
    export_tree(db_dir=db_dir, out_dir=out_dir)
    assert not (out_dir / "ghost").exists()


def test_scoped_export_refuses_multi_plan_target_and_keeps_tree(
    tmp_path: Path,
) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    _seed_plan(db_path, "beta")
    out_dir = tmp_path / "backup"
    export_tree(db_dir=db_dir, out_dir=out_dir)
    manifest_before = (out_dir / "MANIFEST").read_text(encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing scoped export into multi-plan"):
        export_tree(db_dir=db_dir, out_dir=out_dir, plan_id="alpha")

    assert (out_dir / "alpha").exists()
    assert (out_dir / "beta").exists()
    assert (out_dir / "MANIFEST").read_text(encoding="utf-8") == manifest_before


def test_legacy_tree_without_manifest_uses_fresh_seq_behavior(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    _seed_plan(db_path, "temp")
    with unit_of_work(db_path, write=True) as conn:
        delete_plan(conn, "temp")
    with unit_of_work(db_path, write=True) as conn:
        append_event(conn, plan_id="alpha", event_type="another", scope={"ok": True})
    export_dir = tmp_path / "export"
    export_tree(db_dir=db_dir, out_dir=export_dir)

    source_seqs = [seq for _plan_id, seq in _read_event_seqs(db_path)]
    assert min(source_seqs) >= 1

    # Remove MANIFEST to force legacy semantics on import.
    (export_dir / "MANIFEST").unlink()
    imported_dir = tmp_path / "db-imported"
    import_legacy_tree(todo_dir=export_dir, db_dir=imported_dir)
    legacy_seqs = [
        seq for _plan_id, seq in _read_event_seqs(imported_dir / DB_FILENAME)
    ]
    assert legacy_seqs != source_seqs


def test_offline_guard_refuses_when_server_lock_held(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    with hold_server_lock(db_dir):
        with pytest.raises(LiveServerDetectedError):
            require_offline(db_dir)


def test_cli_import_refuses_without_replace_flag_and_replace_is_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    _seed_plan(db_path, "other")
    src_dir = tmp_path / "export"
    export_tree(db_dir=db_dir, out_dir=src_dir, plan_id="alpha")

    monkeypatch.setattr(pm_cli.config, "PLAN_MANAGER_DB_DIR", str(db_dir))
    monkeypatch.setattr(pm_cli.config, "TODO_DIR", str(src_dir))

    with pytest.raises(SystemExit) as exc:
        pm_cli.main(["import", "--from", str(src_dir)])
    assert exc.value.code == 1
    assert "Refusing to overwrite existing plans" in capsys.readouterr().err

    # Create a seq collision in another plan to force replace rollback.
    with unit_of_work(db_path, write=True) as conn:
        collision = append_event(
            conn, plan_id="other", event_type="collision", scope={"x": 1}
        )
    activity_path = src_dir / "alpha" / "activity.yaml"
    payload = yaml.safe_load(activity_path.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert payload
    payload[0]["seq"] = collision.seq
    activity_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    manifest_path = src_dir / "MANIFEST"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["event_seq_range"] = {"min": collision.seq, "max": collision.seq}
    manifest["content_hash"] = compute_tree_content_hash(src_dir)
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    before = _read_event_seqs(db_path)
    with pytest.raises(SystemExit) as replace_exc:
        pm_cli.main(["import", "--replace-plan", "alpha", "--from", str(src_dir)])
    assert replace_exc.value.code == 1
    after = _read_event_seqs(db_path)
    assert after == before


def test_replace_plan_happy_path_updates_target_only(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    _seed_plan(db_path, "beta")

    src_dir = tmp_path / "replace-tree"
    export_tree(db_dir=db_dir, out_dir=src_dir, plan_id="alpha")
    story_path = src_dir / "alpha" / "story" / "story.md"
    story_text = story_path.read_text(encoding="utf-8").replace(
        "title: Story", "title: Story Updated"
    )
    story_path.write_text(story_text, encoding="utf-8")
    manifest = json.loads((src_dir / "MANIFEST").read_text(encoding="utf-8"))
    manifest["content_hash"] = compute_tree_content_hash(src_dir)
    (src_dir / "MANIFEST").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    report = replace_plan_from_tree(
        todo_dir=src_dir,
        db_path=db_path,
        replace_plan_id="alpha",
    )
    assert report.ok
    assert _story_title(db_path, "alpha") == "Story Updated"
    assert _story_title(db_path, "beta") == "Story"


def test_replace_plan_identical_content_succeeds(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    _seed_plan(db_path, "beta")
    src_dir = tmp_path / "replace-identical"
    export_tree(db_dir=db_dir, out_dir=src_dir, plan_id="alpha")

    report = replace_plan_from_tree(
        todo_dir=src_dir,
        db_path=db_path,
        replace_plan_id="alpha",
    )
    assert report.ok
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE plan_id IN ('alpha', 'beta')"
        ).fetchone()
    assert row is not None
    assert int(row[0]) == 2


def test_export_snapshot_is_stable_across_concurrent_write(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    out_dir = tmp_path / "backup"
    started = threading.Event()
    release = threading.Event()

    from plan_manager.storage import exporter as exporter_module

    real_unit_of_work = exporter_module.unit_of_work

    @contextmanager
    def wrapped_unit_of_work(*args, **kwargs):
        with real_unit_of_work(*args, **kwargs) as conn:
            started.set()
            release.wait(timeout=2.0)
            yield conn

    exporter_module.unit_of_work = wrapped_unit_of_work
    try:
        export_errors: list[RuntimeError] = []
        writer_done = threading.Event()

        def run_export() -> None:
            try:
                export_tree(db_dir=db_dir, out_dir=out_dir)
            except RuntimeError as exc:
                export_errors.append(exc)

        def run_writer() -> None:
            with unit_of_work(db_path, write=True) as conn:
                create_plan(
                    conn,
                    base_id="beta",
                    title="Plan beta",
                    description="desc",
                    status=Status.TODO,
                    priority=1,
                    ord_value=1,
                )
            writer_done.set()

        export_thread = threading.Thread(target=run_export)
        export_thread.start()
        assert started.wait(timeout=1.0)
        writer = threading.Thread(target=run_writer)
        writer.start()
        release.set()
        export_thread.join(timeout=2.0)
        writer.join(timeout=2.0)
        assert not export_errors
        assert writer_done.is_set()
    finally:
        exporter_module.unit_of_work = real_unit_of_work

    index_data = yaml.safe_load(
        (out_dir / "plans" / "index.yaml").read_text(encoding="utf-8")
    )
    plan_ids = [entry["id"] for entry in index_data["plans"]]
    assert plan_ids == ["alpha"]
    with closing(sqlite3.connect(db_path)) as conn:
        db_plan_ids = [
            str(row[0])
            for row in conn.execute("SELECT id FROM plans ORDER BY ord, id").fetchall()
        ]
    assert db_plan_ids == ["alpha", "beta"]


def test_concurrent_exports_fail_cleanly_without_oserror(tmp_path: Path) -> None:
    db_dir = tmp_path / "db"
    db_path = bootstrap(db_dir)
    _seed_plan(db_path, "alpha")
    out_dir = tmp_path / "backup"
    errors: list[RuntimeError | OSError] = []

    def run_export() -> None:
        try:
            export_tree(db_dir=db_dir, out_dir=out_dir)
        except (RuntimeError, OSError) as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run_export) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)

    assert all(not isinstance(err, OSError) for err in errors)
    assert all(isinstance(err, RuntimeError) for err in errors)
    import_legacy_tree(todo_dir=out_dir, db_dir=tmp_path / "restored", dry_run=True)


def test_cli_dry_run_import_publishes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source_db_dir = tmp_path / "db-source"
    source_db_path = bootstrap(source_db_dir)
    _seed_plan(source_db_path, "alpha")
    source_tree = tmp_path / "tree"
    export_tree(db_dir=source_db_dir, out_dir=source_tree)

    target_db_dir = tmp_path / "db-target"
    monkeypatch.setattr(pm_cli.config, "PLAN_MANAGER_DB_DIR", str(target_db_dir))
    monkeypatch.setattr(pm_cli.config, "TODO_DIR", str(source_tree))

    with pytest.raises(SystemExit) as exc:
        pm_cli.main(["import", "--dry-run", "--from", str(source_tree)])
    assert exc.value.code == 0
    assert not (target_db_dir / DB_FILENAME).exists()
    assert '"published": false' in capsys.readouterr().out.lower()


def test_export_target_lock_serializes_concurrent_exports(tmp_path):
    """U7 re-review residual: check+publish must be atomic across processes.

    Holds the target lock manually and asserts a concurrent export blocks
    until release rather than racing past the safety check.
    """
    import threading
    import time

    from plan_manager.storage import exporter as exp

    out_dir = tmp_path / "backup"
    started = threading.Event()
    finished = threading.Event()

    def blocked_export() -> None:
        started.set()
        with exp.hold_target_lock(out_dir):
            pass
        finished.set()

    with exp.hold_target_lock(out_dir):
        worker = threading.Thread(target=blocked_export)
        worker.start()
        started.wait(timeout=2.0)
        time.sleep(0.2)
        assert not finished.is_set(), "second export acquired the lock while held"
    worker.join(timeout=2.0)
    assert finished.is_set()
