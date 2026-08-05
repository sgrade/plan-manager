# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""SQLite -> YAML backup exporter."""

from __future__ import annotations

import contextlib
import fcntl
import json
import shutil
import uuid
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from plan_manager.io.file_mirror import render_with_front_matter
from plan_manager.storage.backup_manifest import (
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    compute_tree_content_hash,
)
from plan_manager.storage.codecs import loads_json
from plan_manager.storage.db import DB_FILENAME
from plan_manager.storage.uow import unit_of_work

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterator

LEGACY_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ExportReport:
    out_dir: str
    plans: int
    stories: int
    tasks: int
    events: int
    seq_min: int | None
    seq_max: int | None
    content_hash: str


def export_tree(
    *,
    db_dir: str | Path,
    out_dir: str | Path,
    plan_id: str | None = None,
) -> ExportReport:
    db_path = Path(db_dir) / DB_FILENAME
    if not db_path.exists():
        raise RuntimeError(f"Database not found: {db_path}")

    out_path = Path(out_dir)
    parent = out_path.parent if out_path.parent != Path() else Path.cwd()
    parent.mkdir(parents=True, exist_ok=True)
    temp_path = parent / f"{out_path.name}.tmp.{uuid.uuid4().hex}"

    # Serialize concurrent exports to the same target: the safety check and
    # the publish must be atomic with respect to other export processes
    # (U7 re-review residual finding: check-then-publish TOCTOU).
    with hold_target_lock(out_path):
        if plan_id is not None:
            _assert_scoped_target_is_safe(out_path=out_path, plan_id=plan_id)
        temp_path.mkdir(parents=True, exist_ok=True)
        try:
            snapshot = _read_snapshot(db_path=db_path, plan_id=plan_id)
            _write_snapshot(temp_path, snapshot)
            content_hash = compute_tree_content_hash(temp_path)
            manifest = _build_manifest(snapshot, content_hash=content_hash)
            _write_json(temp_path / MANIFEST_FILENAME, manifest)
            _publish_tree(temp_path=temp_path, out_path=out_path)
        finally:
            if temp_path.exists():
                shutil.rmtree(temp_path, ignore_errors=True)

    return ExportReport(
        out_dir=str(out_path),
        plans=len(snapshot["plans"]),
        stories=sum(plan["counts"]["stories"] for plan in snapshot["plans"]),
        tasks=sum(plan["counts"]["tasks"] for plan in snapshot["plans"]),
        events=sum(plan["counts"]["events"] for plan in snapshot["plans"]),
        seq_min=snapshot["seq_min"],
        seq_max=snapshot["seq_max"],
        content_hash=content_hash,
    )


def _read_snapshot(*, db_path: Path, plan_id: str | None) -> dict[str, Any]:
    # Use one explicit transaction for the entire export read to guarantee
    # one WAL snapshot across all SELECT statements.
    with unit_of_work(db_path, write=True) as conn:
        # Anchor the transaction before any domain reads.
        conn.execute("SELECT 1 FROM plans LIMIT 1").fetchone()
        plan_rows = _load_plan_rows(conn, plan_id)
        if plan_id is not None and not plan_rows:
            raise RuntimeError(f"Plan '{plan_id}' was not found.")
        plans = [_load_plan_snapshot(conn, row) for row in plan_rows]

    all_seqs: list[int] = [
        int(event["seq"])
        for plan in plans
        for event in plan["events"]
        if event.get("seq") is not None
    ]
    return {
        "plans": plans,
        "seq_min": min(all_seqs) if all_seqs else None,
        "seq_max": max(all_seqs) if all_seqs else None,
    }


def _load_plan_rows(conn: sqlite3.Connection, plan_id: str | None) -> list[sqlite3.Row]:
    if plan_id is None:
        return conn.execute(
            "SELECT id, title, description, status, priority, creation_time, completion_time, ord, extra "
            "FROM plans ORDER BY ord, id"
        ).fetchall()
    return conn.execute(
        "SELECT id, title, description, status, priority, creation_time, completion_time, ord, extra "
        "FROM plans WHERE id = ?",
        (plan_id,),
    ).fetchall()


def _load_plan_snapshot(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    plan_id = str(row["id"])
    stories_rows = conn.execute(
        "SELECT id, title, description, status, priority, acceptance_criteria, depends_on, body, creation_time, completion_time, ord, extra "
        "FROM stories WHERE plan_id = ? ORDER BY ord, id",
        (plan_id,),
    ).fetchall()
    stories = [
        _load_story_snapshot(conn, plan_id, story_row) for story_row in stories_rows
    ]
    state = conn.execute(
        "SELECT current_story_id, current_task_story_id, current_task_local_id "
        "FROM plan_state WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()
    events_rows = conn.execute(
        "SELECT seq, legacy_id, ts, type, scope, data FROM events WHERE plan_id = ? ORDER BY seq",
        (plan_id,),
    ).fetchall()
    events = [
        {
            "seq": int(event_row["seq"]),
            "legacy_id": event_row["legacy_id"],
            "id": (
                str(event_row["legacy_id"])
                if event_row["legacy_id"] is not None
                else str(event_row["seq"])
            ),
            "ts": str(event_row["ts"]),
            "type": str(event_row["type"]),
            "scope": loads_json(event_row["scope"]) or {},
            "data": loads_json(event_row["data"]),
        }
        for event_row in events_rows
    ]
    return {
        "id": plan_id,
        "frontmatter": _render_plan_frontmatter(row=row, stories=stories),
        "stories": stories,
        "state": {
            "current_story_id": (
                str(state["current_story_id"])
                if state is not None and state["current_story_id"] is not None
                else None
            ),
            "current_task_id": (
                f"{state['current_task_story_id']}:{state['current_task_local_id']}"
                if (
                    state is not None
                    and state["current_task_story_id"] is not None
                    and state["current_task_local_id"] is not None
                )
                else None
            ),
        },
        "events": events,
        "counts": {
            "stories": len(stories),
            "tasks": sum(len(story["tasks"]) for story in stories),
            "events": len(events),
        },
    }


def _load_story_snapshot(
    conn: sqlite3.Connection, plan_id: str, row: sqlite3.Row
) -> dict[str, Any]:
    story_id = str(row["id"])
    task_rows = conn.execute(
        "SELECT local_id, title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra "
        "FROM tasks WHERE plan_id = ? AND story_id = ? ORDER BY ord, local_id",
        (plan_id, story_id),
    ).fetchall()
    tasks = [_load_task_snapshot(story_id, task_row) for task_row in task_rows]
    return {
        "id": story_id,
        "frontmatter": _render_story_frontmatter(row=row, tasks=tasks),
        "body": row["body"] if row["body"] is not None else "",
        "tasks": tasks,
    }


def _load_task_snapshot(story_id: str, row: sqlite3.Row) -> dict[str, Any]:
    local_id = str(row["local_id"])
    return {
        "id": local_id,
        "frontmatter": _render_task_frontmatter(
            story_id=story_id, local_id=local_id, row=row
        ),
        "body": row["body"] if row["body"] is not None else "",
    }


def _render_plan_frontmatter(
    *, row: sqlite3.Row, stories: list[dict[str, Any]]
) -> dict[str, Any]:
    front = _coerce_extra(row["extra"])
    front.update(
        {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "description": row["description"],
            "priority": row["priority"],
            "depends_on": [],
            "status": str(row["status"]),
            "creation_time": str(row["creation_time"]),
            "completion_time": row["completion_time"],
            "stories": [story["id"] for story in stories],
            "schema_version": LEGACY_SCHEMA_VERSION,
        }
    )
    return front


def _render_story_frontmatter(
    *, row: sqlite3.Row, tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    front = _coerce_extra(row["extra"])
    front.update(
        {
            "id": str(row["id"]),
            "title": str(row["title"]),
            "description": row["description"],
            "priority": row["priority"],
            "depends_on": loads_json(row["depends_on"]) or [],
            "status": str(row["status"]),
            "creation_time": str(row["creation_time"]),
            "completion_time": row["completion_time"],
            "acceptance_criteria": loads_json(row["acceptance_criteria"]),
            "tasks": [task["id"] for task in tasks],
            "schema_version": LEGACY_SCHEMA_VERSION,
        }
    )
    return front


def _render_task_frontmatter(
    *, story_id: str, local_id: str, row: sqlite3.Row
) -> dict[str, Any]:
    front = _coerce_extra(row["extra"])
    front.update(
        {
            "id": f"{story_id}:{local_id}",
            "title": str(row["title"]),
            "description": row["description"],
            "priority": row["priority"],
            "depends_on": loads_json(row["depends_on"]) or [],
            "status": str(row["status"]),
            "creation_time": str(row["creation_time"]),
            "completion_time": row["completion_time"],
            "story_id": story_id,
            "local_id": local_id,
            "steps": loads_json(row["steps"]),
            "changes": loads_json(row["changes"]) or [],
            "review_feedback": loads_json(row["review_feedback"]) or [],
            "rework_count": int(row["rework_count"]),
            "schema_version": LEGACY_SCHEMA_VERSION,
        }
    )
    return front


def _coerce_extra(raw: Any) -> dict[str, Any]:
    extra = loads_json(raw)
    if not isinstance(extra, dict):
        return {}
    return dict(extra)


def _write_snapshot(root: Path, snapshot: dict[str, Any]) -> None:
    plans_index = {
        "current": snapshot["plans"][0]["id"] if snapshot["plans"] else None,
        "plans": [
            {
                "id": plan["id"],
                "title": plan["frontmatter"]["title"],
                "status": plan["frontmatter"]["status"],
            }
            for plan in snapshot["plans"]
        ],
    }
    _write_yaml(root / "plans" / "index.yaml", plans_index)

    for plan in snapshot["plans"]:
        plan_root = root / plan["id"]
        _write_yaml(plan_root / "plan.yaml", plan["frontmatter"])
        for story in plan["stories"]:
            story_root = plan_root / story["id"]
            story_body = render_with_front_matter(story["frontmatter"], story["body"])
            _write_text(story_root / "story.md", story_body)
            for task in story["tasks"]:
                task_body = render_with_front_matter(task["frontmatter"], task["body"])
                _write_text(story_root / "tasks" / f"{task['id']}.md", task_body)
        _write_yaml(plan_root / "state.yaml", plan["state"])
        _write_yaml(plan_root / "activity.yaml", plan["events"])


def _build_manifest(snapshot: dict[str, Any], *, content_hash: str) -> dict[str, Any]:
    return {
        "format_version": MANIFEST_VERSION,
        "tool_version": _tool_version(),
        "plans": [plan["id"] for plan in snapshot["plans"]],
        "counts": {
            plan["id"]: {
                "stories": plan["counts"]["stories"],
                "tasks": plan["counts"]["tasks"],
                "events": plan["counts"]["events"],
            }
            for plan in snapshot["plans"]
        },
        "event_seq_range": {"min": snapshot["seq_min"], "max": snapshot["seq_max"]},
        "content_hash": content_hash,
    }


def _tool_version() -> str:
    try:
        return metadata.version("plan-manager")
    except metadata.PackageNotFoundError:
        return "0.0.0+dev"


def _assert_scoped_target_is_safe(*, out_path: Path, plan_id: str) -> None:
    if not out_path.exists():
        return
    if not out_path.is_dir():
        raise RuntimeError(f"Scoped export target must be a directory: {out_path}")
    # Empty directories are safe for scoped-only exports.
    if not any(out_path.iterdir()):
        return
    manifest_path = out_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        raise RuntimeError(
            "Refusing scoped export into a non-empty directory without MANIFEST. "
            "Use an empty output directory or run a full export."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Invalid existing MANIFEST at {manifest_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        manifest = {}
    if manifest.get("format_version") != MANIFEST_VERSION:
        raise RuntimeError(
            "Refusing scoped export into backup with unsupported MANIFEST format."
        )
    expected_hash = manifest.get("content_hash")
    if not isinstance(expected_hash, str) or not expected_hash:
        raise RuntimeError(
            "Refusing scoped export: existing MANIFEST lacks content_hash."
        )
    actual_hash = compute_tree_content_hash(out_path)
    if actual_hash != expected_hash:
        raise RuntimeError(
            "Refusing scoped export into a torn or modified backup tree "
            f"(expected hash {expected_hash}, got {actual_hash})."
        )
    plans = manifest.get("plans")
    if not isinstance(plans, list) or not all(isinstance(item, str) for item in plans):
        raise RuntimeError(
            "Refusing scoped export: existing MANIFEST plans list is invalid."
        )
    sibling_plans = sorted({item for item in plans if item != plan_id})
    if sibling_plans:
        raise RuntimeError(
            "Refusing scoped export into multi-plan backup target. "
            f"Target currently includes: {', '.join(sibling_plans)}. "
            "Use a dedicated output directory for --plan exports, or run full export."
        )


@contextlib.contextmanager
def hold_target_lock(out_path: Path) -> Iterator[None]:
    """Hold an exclusive advisory lock for one export target directory.

    Blocking by design: a second export to the same target waits for the
    first to finish, then re-evaluates the (now current) target state.
    """
    lock_file = out_path.parent / f".{out_path.name}.export.lock"
    with lock_file.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _publish_tree(*, temp_path: Path, out_path: Path) -> None:
    old_path = out_path.parent / f"{out_path.name}.old.{uuid.uuid4().hex}"
    try:
        if out_path.exists():
            out_path.replace(old_path)
        temp_path.replace(out_path)
    except OSError as exc:
        if old_path.exists() and not out_path.exists():
            old_path.replace(out_path)
        raise RuntimeError(
            f"Failed to publish export tree at {out_path}: {exc}"
        ) from exc
    finally:
        if old_path.exists():
            shutil.rmtree(old_path, ignore_errors=True)


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
