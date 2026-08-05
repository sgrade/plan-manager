# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from __future__ import annotations

import json
import pathlib
import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from plan_manager.storage import (
    DB_FILENAME,
    LegacyImportError,
    StartupAction,
    canonical_utc_timestamp,
    decide_startup_action,
    import_legacy_tree,
    startup_storage,
)

if TYPE_CHECKING:
    from pathlib import Path


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_markdown(path: Path, frontmatter: dict[str, Any], body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(frontmatter, sort_keys=False).rstrip()
    path.write_text(f"---\n{front}\n---\n\n{body}", encoding="utf-8")


def _create_valid_tree(todo_dir: Path) -> None:
    _write_yaml(
        todo_dir / "plans" / "index.yaml",
        {
            "current": "default",
            "plans": [
                {"id": "default", "title": "Default", "status": "TODO"},
                {"id": "samep", "title": "Same P", "status": "TODO"},
            ],
        },
    )
    _write_yaml(
        todo_dir / "default" / "plan.yaml",
        {
            "id": "default",
            "title": "Default",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00",
            "stories": ["s"],
            "plan_extra": {"note": "default-extra"},
        },
    )
    _write_markdown(
        todo_dir / "default" / "s" / "story.md",
        {
            "id": "s",
            "title": "Setup",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "tasks": ["t"],
            "story_extra": "story-default",
            "schema_version": 1,
        },
        body="default story body",
    )
    _write_markdown(
        todo_dir / "default" / "s" / "tasks" / "t.md",
        {
            "id": "s:t",
            "title": "Task",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00.111111+00:00",
            "story_id": "s",
            "local_id": "t",
            "steps": [],
            "changes": [],
            "review_feedback": [],
            "rework_count": 0,
            "task_extra": {"nested": True},
            "schema_version": 1,
        },
        body="default task body",
    )
    _write_yaml(
        todo_dir / "default" / "state.yaml",
        {"current_story_id": "s", "current_task_id": "s:t"},
    )
    _write_yaml(
        todo_dir / "default" / "activity.yaml",
        [
            {
                "id": "1",
                "ts": "2026-08-04T10:00:00Z",
                "type": "story_saved",
                "scope": {"story_id": "s"},
                "data": {"source": "legacy"},
            }
        ],
    )

    _write_yaml(
        todo_dir / "samep" / "plan.yaml",
        {
            "id": "samep",
            "title": "Same P",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:01+00:00",
            "stories": ["s"],
        },
    )
    _write_markdown(
        todo_dir / "samep" / "s" / "story.md",
        {
            "id": "s",
            "title": "Setup2",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:01Z",
            "tasks": ["t"],
            "schema_version": 1,
        },
        body="samep story body",
    )
    _write_markdown(
        todo_dir / "samep" / "s" / "tasks" / "t.md",
        {
            "id": "s:t",
            "title": "Task2",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:02Z",
            "story_id": "s",
            "local_id": "t",
            "steps": None,
            "changes": [],
            "review_feedback": [],
            "rework_count": 0,
            "schema_version": 1,
        },
        body="samep task body",
    )


def _problem_messages(exc: LegacyImportError) -> list[str]:
    return [f"{problem.path}: {problem.cause}" for problem in exc.report.problems]


def test_f3_silent_drop_inputs_now_fail_loudly(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)

    _write_yaml(
        todo_dir / "samep" / "plan.yaml",
        {
            "id": "samep",
            "title": "Same P",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:01+00:00",
            "stories": ["missing_story"],
        },
    )
    (todo_dir / "unindexed").mkdir(parents=True, exist_ok=True)
    (todo_dir / "default" / "orphan_story").mkdir(parents=True, exist_ok=True)
    (todo_dir / "default" / "s" / "tasks" / "orphan.md").write_text(
        "---\nid: s:orphan\ntitle: orphan\n---\n",
        encoding="utf-8",
    )

    with pytest.raises(LegacyImportError) as exc:
        import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    messages = _problem_messages(exc.value)

    assert any("unindexed plan directory" in message for message in messages)
    assert any("dangling manifest reference" in message for message in messages)
    assert any("orphan story directory" in message for message in messages)
    assert any("orphan task file" in message for message in messages)


def test_f3_crash_mid_import_leaves_no_published_db_and_reruns_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)

    monkeypatch.setattr(
        pathlib.Path,
        "replace",
        lambda _self, _dst: (_ for _ in ()).throw(RuntimeError("crash")),
    )
    with pytest.raises(RuntimeError, match="crash"):
        import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert not (db_dir / DB_FILENAME).exists()

    monkeypatch.undo()
    report = import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert report.ok
    assert report.published


def test_f3_both_present_does_not_reimport(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)

    empty_todo = tmp_path / "empty"
    action = startup_storage(todo_dir=empty_todo, db_dir=db_dir)
    assert action.action == StartupAction.INITIALIZE_EMPTY

    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        conn.execute(
            "INSERT INTO plans(id, title, status, creation_time, ord) VALUES (?, ?, ?, ?, ?)",
            ("existing", "Existing", "TODO", canonical_utc_timestamp(), 0),
        )
        conn.commit()

    second = startup_storage(todo_dir=todo_dir, db_dir=db_dir)
    assert second.action == StartupAction.SERVE_DB

    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        plans = conn.execute("SELECT id FROM plans ORDER BY id").fetchall()
    assert [row[0] for row in plans] == ["existing"]


def test_duplicate_story_and_task_ids_within_plan_are_reported_cleanly(
    tmp_path: Path,
) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    _write_yaml(
        todo_dir / "default" / "plan.yaml",
        {
            "id": "default",
            "title": "Default",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00",
            "stories": ["s", "s"],
        },
    )
    _write_markdown(
        todo_dir / "default" / "s" / "story.md",
        {
            "id": "s",
            "title": "Setup",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "tasks": ["t", "t"],
            "schema_version": 1,
        },
        body="default story body",
    )

    with pytest.raises(LegacyImportError) as exc:
        import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    messages = _problem_messages(exc.value)
    assert any("duplicate story id 's' in stories list" in msg for msg in messages)
    assert any("duplicate task id 't' in tasks list" in msg for msg in messages)


def test_sweeps_orphaned_temp_db_files_before_import(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    orphan = db_dir / f"{DB_FILENAME}.import.orphan.tmp"
    orphan.write_text("stale", encoding="utf-8")
    assert orphan.exists()

    report = import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert report.ok
    assert report.published
    assert not orphan.exists()


def test_f13_unknown_schema_version_refused(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    _write_markdown(
        todo_dir / "default" / "s" / "story.md",
        {
            "id": "s",
            "title": "Setup",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "tasks": ["t"],
            "schema_version": 999,
        },
        body="body",
    )

    with pytest.raises(LegacyImportError) as exc:
        import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert any("unknown schema_version" in msg for msg in _problem_messages(exc.value))


def test_f15_mixed_timestamp_formats_normalized_and_ordering_restored(
    tmp_path: Path,
) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    _write_yaml(
        todo_dir / "default" / "activity.yaml",
        [
            {
                "id": "1",
                "ts": "2026-08-04T10:00:00Z",
                "type": "event_a",
                "scope": {"story_id": "s"},
            },
            {
                "id": "2",
                "ts": "2026-08-04T10:00:00.100000+00:00",
                "type": "event_b",
                "scope": {"story_id": "s"},
            },
        ],
    )

    report = import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert report.ok

    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        rows = conn.execute(
            "SELECT legacy_id, ts FROM events WHERE plan_id = ? ORDER BY ts",
            ("default",),
        ).fetchall()
    assert [row[0] for row in rows] == ["1", "2"]
    assert rows[0][1].endswith(".000Z")
    assert rows[1][1].endswith(".100Z")


def test_f17_dependency_cycle_detected_loudly(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    _write_yaml(
        todo_dir / "default" / "plan.yaml",
        {
            "id": "default",
            "title": "Default",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "stories": ["s", "x"],
        },
    )
    _write_markdown(
        todo_dir / "default" / "s" / "story.md",
        {
            "id": "s",
            "title": "Setup",
            "depends_on": ["x"],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "tasks": ["t"],
            "schema_version": 1,
        },
    )
    _write_markdown(
        todo_dir / "default" / "x" / "story.md",
        {
            "id": "x",
            "title": "X",
            "depends_on": ["s"],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "tasks": [],
            "schema_version": 1,
        },
    )
    _write_markdown(
        todo_dir / "default" / "s" / "tasks" / "t.md",
        {
            "id": "s:t",
            "title": "Task",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "story_id": "s",
            "local_id": "t",
            "steps": [],
            "changes": [],
            "review_feedback": [],
            "rework_count": 0,
            "schema_version": 1,
        },
    )

    with pytest.raises(LegacyImportError) as exc:
        import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert any(
        "dependency cycle detected" in msg for msg in _problem_messages(exc.value)
    )


def test_f18_empty_slug_refused(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    _write_markdown(
        todo_dir / "default" / "s" / "story.md",
        {
            "id": "s",
            "title": "你好",
            "depends_on": [],
            "status": "TODO",
            "creation_time": "2026-08-04T10:00:00Z",
            "tasks": ["t"],
            "schema_version": 1,
        },
    )

    with pytest.raises(LegacyImportError) as exc:
        import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert any(
        "slugifies to an empty id" in msg for msg in _problem_messages(exc.value)
    )


def test_duplicate_story_ids_across_plans_import_with_composite_keys(
    tmp_path: Path,
) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)

    report = import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert report.ok
    assert report.plans == 2
    assert report.stories == 2
    assert report.tasks == 2

    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        rows = conn.execute(
            "SELECT plan_id, id FROM stories WHERE id = 's' ORDER BY plan_id"
        ).fetchall()
    assert rows == [("default", "s"), ("samep", "s")]


def test_bodies_and_extra_keys_round_trip(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)

    report = import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir)
    assert report.ok

    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        row = conn.execute(
            "SELECT body, extra FROM stories WHERE plan_id = ? AND id = ?",
            ("default", "s"),
        ).fetchone()
        task_row = conn.execute(
            "SELECT body, extra FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            ("default", "s", "t"),
        ).fetchone()
        default_steps = conn.execute(
            "SELECT steps FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            ("default", "s", "t"),
        ).fetchone()
        samep_steps = conn.execute(
            "SELECT steps FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            ("samep", "s", "t"),
        ).fetchone()
    assert row is not None
    assert task_row is not None
    assert default_steps is not None
    assert samep_steps is not None
    assert row[0] == "default story body"
    assert task_row[0] == "default task body"
    assert json.loads(str(row[1])) == {"story_extra": "story-default"}
    assert json.loads(str(task_row[1])) == {"task_extra": {"nested": True}}
    assert str(default_steps[0]) == "[]"
    assert samep_steps[0] is None


def test_dry_run_publishes_nothing(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)

    report = import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir, dry_run=True)
    assert report.ok
    assert not report.published
    assert not (db_dir / DB_FILENAME).exists()


def test_decide_startup_action_uses_done_marker_not_file_presence(
    tmp_path: Path,
) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    db_dir.mkdir(parents=True, exist_ok=True)
    (db_dir / DB_FILENAME).write_text("not-a-db", encoding="utf-8")

    decision = decide_startup_action(todo_dir=todo_dir, db_dir=db_dir)
    assert decision.action == StartupAction.IMPORT_LEGACY


def test_startup_reimports_when_db_marker_pending(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _create_valid_tree(todo_dir)
    startup_storage(todo_dir=tmp_path / "empty", db_dir=db_dir)

    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        conn.execute(
            "UPDATE meta SET value = ? WHERE key = ?",
            ("pending", "import_state"),
        )
        conn.execute("DELETE FROM plans")
        conn.commit()

    decision = startup_storage(todo_dir=todo_dir, db_dir=db_dir)
    assert decision.action == StartupAction.IMPORT_LEGACY
    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        marker = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            ("import_state",),
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()
    assert marker is not None
    assert marker[0] == "done"
    assert count is not None
    assert int(count[0]) == 2


def test_startup_imports_empty_plans_index(tmp_path: Path) -> None:
    todo_dir = tmp_path / "todo"
    db_dir = tmp_path / "db"
    _write_yaml(
        todo_dir / "plans" / "index.yaml",
        {
            "current": None,
            "plans": [],
        },
    )

    decision = startup_storage(todo_dir=todo_dir, db_dir=db_dir)
    assert decision.action == StartupAction.IMPORT_LEGACY
    with closing(sqlite3.connect(db_dir / DB_FILENAME)) as conn:
        marker = conn.execute(
            "SELECT value FROM meta WHERE key = ?",
            ("import_state",),
        ).fetchone()
        count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()
    assert marker is not None
    assert marker[0] == "done"
    assert count is not None
    assert int(count[0]) == 0
