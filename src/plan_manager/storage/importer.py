# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Strict legacy YAML -> SQLite importer."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from plan_manager.domain.models import Plan, Story, Task
from plan_manager.io.file_mirror import split_front_matter
from plan_manager.io.paths import slugify
from plan_manager.storage.codecs import dumps_json, loads_json, serialize_steps
from plan_manager.storage.schema import (
    IMPORT_STATE_DONE,
    IMPORT_STATE_KEY,
    IMPORT_STATE_PENDING,
    apply_migrations,
)
from plan_manager.storage.uow import canonical_utc_timestamp

LEGACY_SCHEMA_VERSION = 1
PUBLISHED_DB_FILENAME = "plan_manager.sqlite3"
_SLUG_RE = r"^[a-z0-9_]+$"


@dataclass(frozen=True)
class ImportProblem:
    """Single import error with a stable location and cause."""

    path: str
    cause: str


@dataclass
class ImportReport:
    """Import summary returned for dry-runs and successful imports."""

    dry_run: bool
    published: bool
    plans: int
    stories: int
    tasks: int
    events: int
    problems: list[ImportProblem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


class LegacyImportError(RuntimeError):
    """Raised when strict import validation fails."""

    def __init__(self, report: ImportReport):
        self.report = report
        details = "\n".join(
            f"- {problem.path}: {problem.cause}" for problem in report.problems
        )
        super().__init__(
            f"Legacy import failed with {len(report.problems)} issue(s):\n{details}"
        )


@dataclass
class _LegacyTask:
    model: Task
    body: str
    extra: dict[str, Any]
    order: int


@dataclass
class _LegacyStory:
    model: Story
    body: str
    extra: dict[str, Any]
    order: int
    tasks: list[_LegacyTask]


@dataclass
class _LegacyEvent:
    legacy_id: str
    ts: str
    event_type: str
    scope: dict[str, Any]
    data: dict[str, Any] | None


@dataclass
class _LegacyPlan:
    model: Plan
    order: int
    extra: dict[str, Any]
    stories: list[_LegacyStory]
    current_story_id: str | None
    current_task_story_id: str | None
    current_task_local_id: str | None
    events: list[_LegacyEvent]


@dataclass
class _LegacyTree:
    plans: list[_LegacyPlan]


def import_legacy_tree(
    todo_dir: str | Path,
    db_dir: str | Path,
    dry_run: bool = False,
) -> ImportReport:
    """Strictly import legacy YAML plan tree into SQLite."""
    todo_root = Path(todo_dir)
    db_root = Path(db_dir)
    db_root.mkdir(parents=True, exist_ok=True)
    _sweep_orphaned_import_temp_dbs(db_root)

    tree = _parse_legacy_tree(todo_root)
    temp_db_path = db_root / f"{PUBLISHED_DB_FILENAME}.import.{uuid.uuid4().hex}.tmp"
    published_db_path = db_root / PUBLISHED_DB_FILENAME
    published = False

    try:
        _build_temp_db(tree, temp_db_path)
        _assert_semantic_equivalence(tree, temp_db_path)
        if not dry_run:
            _cleanup_sqlite_sidecars(published_db_path)
            temp_db_path.replace(published_db_path)
            published = True
    finally:
        _cleanup_sqlite_artifacts(temp_db_path)

    return ImportReport(
        dry_run=dry_run,
        published=published,
        plans=len(tree.plans),
        stories=sum(len(plan.stories) for plan in tree.plans),
        tasks=sum(len(story.tasks) for plan in tree.plans for story in plan.stories),
        events=sum(len(plan.events) for plan in tree.plans),
    )


def _parse_legacy_tree(todo_root: Path) -> _LegacyTree:
    errors: list[ImportProblem] = []
    index_path = todo_root / "plans" / "index.yaml"
    index_data = _load_yaml_mapping(index_path, errors)
    plan_entries = _extract_plan_entries(index_data, index_path, errors)

    indexed_plan_ids = {plan_id for plan_id, _entry in plan_entries}
    plan_dirs = {
        child.name
        for child in todo_root.iterdir()
        if child.is_dir() and child.name != "plans"
    }
    errors.extend(
        ImportProblem(
            path=str(todo_root / plan_id),
            cause="unindexed plan directory",
        )
        for plan_id in sorted(plan_dirs - indexed_plan_ids)
    )
    errors.extend(
        ImportProblem(
            path=str(index_path),
            cause=f"dangling manifest reference to missing plan directory '{plan_id}'",
        )
        for plan_id in sorted(indexed_plan_ids - plan_dirs)
    )

    legacy_plans: list[_LegacyPlan] = []
    for order, (plan_id, _entry) in enumerate(plan_entries):
        plan = _parse_plan(todo_root, plan_id, order, errors)
        if plan is not None:
            legacy_plans.append(plan)

    _raise_if_errors(errors)
    return _LegacyTree(plans=legacy_plans)


def _parse_plan(
    todo_root: Path,
    plan_id: str,
    order: int,
    errors: list[ImportProblem],
) -> _LegacyPlan | None:
    plan_dir = todo_root / plan_id
    manifest_path = plan_dir / "plan.yaml"
    manifest = _load_yaml_mapping(manifest_path, errors)
    if manifest is None:
        return None

    _validate_schema_version(manifest, manifest_path, errors)
    if manifest.get("id") != plan_id:
        errors.append(
            ImportProblem(
                path=str(manifest_path),
                cause=f"plan id mismatch: index '{plan_id}' != manifest '{manifest.get('id')}'",
            )
        )

    _validate_slug_id(plan_id, manifest.get("title"), manifest_path, "plan", errors)
    story_ids = _extract_str_list(manifest, "stories", manifest_path, errors)
    _collect_duplicate_ids(
        values=story_ids,
        source_path=manifest_path,
        field_name="stories",
        item_label="story id",
        errors=errors,
    )
    story_id_set = set(story_ids)

    child_story_dirs = {
        child.name
        for child in plan_dir.iterdir()
        if child.is_dir() and child.name != "tasks"
    }
    errors.extend(
        ImportProblem(
            path=str(plan_dir / orphan_story),
            cause="orphan story directory not referenced by plan manifest",
        )
        for orphan_story in sorted(child_story_dirs - story_id_set)
    )

    stories: list[_LegacyStory] = []
    for story_order, story_id in enumerate(story_ids):
        story = _parse_story(
            plan_dir=plan_dir,
            story_id=story_id,
            order=story_order,
            errors=errors,
        )
        if story is not None:
            stories.append(story)

    plan_payload = dict(manifest)
    plan_payload["stories"] = [
        _story_model_for_plan_validation(story.model, story.tasks) for story in stories
    ]
    plan_model = _validate_plan(plan_payload, manifest_path, errors)
    if plan_model is None:
        return None

    _validate_story_cycles(stories, manifest_path, errors)
    _validate_task_cycles(stories, manifest_path, errors)

    events = _parse_activity_events(plan_dir / "activity.yaml", errors)
    current_story_id, current_task_story_id, current_task_local_id = _parse_state(
        plan_dir / "state.yaml", stories, errors
    )
    extra = _extract_extra_fields(manifest, _plan_known_fields())

    return _LegacyPlan(
        model=plan_model,
        order=order,
        extra=extra,
        stories=stories,
        current_story_id=current_story_id,
        current_task_story_id=current_task_story_id,
        current_task_local_id=current_task_local_id,
        events=events,
    )


def _story_model_for_plan_validation(story: Story, tasks: list[_LegacyTask]) -> Story:
    return Story.model_validate(
        {
            **story.model_dump(mode="python"),
            "tasks": [task.model.model_dump(mode="python") for task in tasks],
        }
    )


def _parse_story(
    *,
    plan_dir: Path,
    story_id: str,
    order: int,
    errors: list[ImportProblem],
) -> _LegacyStory | None:
    story_path = plan_dir / story_id / "story.md"
    if not story_path.exists():
        errors.append(
            ImportProblem(
                path=str(plan_dir / "plan.yaml"),
                cause=f"dangling manifest reference to missing story '{story_id}'",
            )
        )
        return None

    frontmatter, body = _load_markdown_frontmatter(story_path, errors)
    if frontmatter is None:
        return None

    _validate_schema_version(frontmatter, story_path, errors)
    if frontmatter.get("id") != story_id:
        errors.append(
            ImportProblem(
                path=str(story_path),
                cause=f"story id mismatch: manifest '{story_id}' != file '{frontmatter.get('id')}'",
            )
        )
    _validate_slug_id(story_id, frontmatter.get("title"), story_path, "story", errors)

    task_ids = _extract_str_list(frontmatter, "tasks", story_path, errors)
    _collect_duplicate_ids(
        values=task_ids,
        source_path=story_path,
        field_name="tasks",
        item_label="task id",
        errors=errors,
    )
    task_id_set = set(task_ids)

    tasks_dir = plan_dir / story_id / "tasks"
    child_task_files: set[str] = set()
    if tasks_dir.exists():
        child_task_files = {item.stem for item in tasks_dir.iterdir() if item.is_file()}
    errors.extend(
        ImportProblem(
            path=str(tasks_dir / f"{orphan_task}.md"),
            cause="orphan task file not referenced by story frontmatter",
        )
        for orphan_task in sorted(child_task_files - task_id_set)
    )

    tasks: list[_LegacyTask] = []
    for task_order, local_task_id in enumerate(task_ids):
        task = _parse_task(
            tasks_dir=tasks_dir,
            story_id=story_id,
            local_id=local_task_id,
            order=task_order,
            errors=errors,
        )
        if task is not None:
            tasks.append(task)

    story_payload = dict(frontmatter)
    story_payload["tasks"] = [task.model.model_dump(mode="python") for task in tasks]
    story_model = _validate_story(story_payload, story_path, errors)
    if story_model is None:
        return None
    story_model.creation_time = _normalize_datetime(story_model.creation_time)
    if story_model.completion_time is not None:
        story_model.completion_time = _normalize_datetime(story_model.completion_time)

    return _LegacyStory(
        model=story_model,
        body=body,
        extra=_extract_extra_fields(frontmatter, _story_known_fields()),
        order=order,
        tasks=tasks,
    )


def _parse_task(
    *,
    tasks_dir: Path,
    story_id: str,
    local_id: str,
    order: int,
    errors: list[ImportProblem],
) -> _LegacyTask | None:
    task_path = tasks_dir / f"{local_id}.md"
    if not task_path.exists():
        errors.append(
            ImportProblem(
                path=str(tasks_dir.parent / "story.md"),
                cause=f"dangling manifest reference to missing task '{local_id}'",
            )
        )
        return None

    frontmatter, body = _load_markdown_frontmatter(task_path, errors)
    if frontmatter is None:
        return None

    _validate_schema_version(frontmatter, task_path, errors)
    task_id = frontmatter.get("id")
    if task_id != f"{story_id}:{local_id}":
        errors.append(
            ImportProblem(
                path=str(task_path),
                cause=(
                    "task id mismatch: expected "
                    f"'{story_id}:{local_id}', got '{task_id}'"
                ),
            )
        )
    if frontmatter.get("story_id") not in (None, story_id):
        errors.append(
            ImportProblem(
                path=str(task_path),
                cause=(
                    "task story_id mismatch: expected "
                    f"'{story_id}', got '{frontmatter.get('story_id')}'"
                ),
            )
        )
    if frontmatter.get("local_id") not in (None, local_id):
        errors.append(
            ImportProblem(
                path=str(task_path),
                cause=(
                    f"task local_id mismatch: expected '{local_id}', "
                    f"got '{frontmatter.get('local_id')}'"
                ),
            )
        )

    _validate_slug_id(local_id, frontmatter.get("title"), task_path, "task", errors)

    task_model = _validate_task(frontmatter, task_path, errors)
    if task_model is None:
        return None

    if task_model.story_id not in (None, story_id):
        errors.append(
            ImportProblem(
                path=str(task_path),
                cause=f"task validates with mismatched story_id '{task_model.story_id}'",
            )
        )
    if task_model.local_id not in (None, local_id):
        errors.append(
            ImportProblem(
                path=str(task_path),
                cause=f"task validates with mismatched local_id '{task_model.local_id}'",
            )
        )

    task_model.story_id = story_id
    task_model.local_id = local_id
    task_model.id = f"{story_id}:{local_id}"
    task_model.creation_time = _normalize_datetime(task_model.creation_time)
    if task_model.completion_time is not None:
        task_model.completion_time = _normalize_datetime(task_model.completion_time)

    return _LegacyTask(
        model=task_model,
        body=body,
        extra=_extract_extra_fields(frontmatter, _task_known_fields()),
        order=order,
    )


def _build_temp_db(tree: _LegacyTree, temp_db_path: Path) -> None:
    conn = sqlite3.connect(temp_db_path)
    try:
        _set_wal(conn)
        apply_migrations(conn)
        _set_import_state(conn, IMPORT_STATE_PENDING)
        with conn:
            for plan in tree.plans:
                conn.execute(
                    "INSERT INTO plans(id, title, description, status, priority, creation_time, completion_time, ord, extra) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        plan.model.id,
                        plan.model.title,
                        plan.model.description,
                        plan.model.status.value,
                        plan.model.priority,
                        canonical_utc_timestamp(plan.model.creation_time),
                        (
                            canonical_utc_timestamp(plan.model.completion_time)
                            if plan.model.completion_time
                            else None
                        ),
                        plan.order,
                        dumps_json(plan.extra),
                    ),
                )
                for story in plan.stories:
                    conn.execute(
                        "INSERT INTO stories(plan_id, id, title, status, priority, description, acceptance_criteria, depends_on, body, creation_time, completion_time, ord, extra) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            plan.model.id,
                            story.model.id,
                            story.model.title,
                            story.model.status.value,
                            story.model.priority,
                            story.model.description,
                            dumps_json(story.model.acceptance_criteria),
                            dumps_json(story.model.depends_on),
                            story.body,
                            canonical_utc_timestamp(story.model.creation_time),
                            (
                                canonical_utc_timestamp(story.model.completion_time)
                                if story.model.completion_time
                                else None
                            ),
                            story.order,
                            dumps_json(story.extra),
                        ),
                    )
                    for task in story.tasks:
                        conn.execute(
                            "INSERT INTO tasks(plan_id, story_id, local_id, title, status, priority, description, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                plan.model.id,
                                story.model.id,
                                task.model.local_id,
                                task.model.title,
                                task.model.status.value,
                                task.model.priority,
                                task.model.description,
                                dumps_json(task.model.depends_on),
                                dumps_json(serialize_steps(task.model.steps)),
                                dumps_json(task.model.changes),
                                dumps_json(
                                    [
                                        feedback.model_dump(mode="json")
                                        for feedback in task.model.review_feedback
                                    ]
                                ),
                                task.model.rework_count,
                                task.body,
                                canonical_utc_timestamp(task.model.creation_time),
                                (
                                    canonical_utc_timestamp(task.model.completion_time)
                                    if task.model.completion_time
                                    else None
                                ),
                                task.order,
                                dumps_json(task.extra),
                            ),
                        )
                if any(
                    [
                        plan.current_story_id is not None,
                        plan.current_task_story_id is not None,
                        plan.current_task_local_id is not None,
                    ]
                ):
                    conn.execute(
                        "INSERT INTO plan_state(plan_id, current_story_id, current_task_story_id, current_task_local_id) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            plan.model.id,
                            plan.current_story_id,
                            plan.current_task_story_id,
                            plan.current_task_local_id,
                        ),
                    )
                for event in plan.events:
                    conn.execute(
                        "INSERT INTO events(plan_id, legacy_id, ts, type, scope, data) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            plan.model.id,
                            event.legacy_id,
                            event.ts,
                            event.event_type,
                            json.dumps(event.scope, sort_keys=True),
                            (
                                json.dumps(event.data, sort_keys=True)
                                if event.data is not None
                                else None
                            ),
                        ),
                    )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        _set_import_state(conn, IMPORT_STATE_DONE)
    finally:
        conn.close()


def _assert_semantic_equivalence(tree: _LegacyTree, temp_db_path: Path) -> None:
    source_view = _source_semantic_view(tree)
    db_view = _db_semantic_view(temp_db_path)
    if source_view != db_view:
        report = ImportReport(
            dry_run=False,
            published=False,
            plans=len(tree.plans),
            stories=sum(len(plan.stories) for plan in tree.plans),
            tasks=sum(
                len(story.tasks) for plan in tree.plans for story in plan.stories
            ),
            events=sum(len(plan.events) for plan in tree.plans),
            problems=[
                ImportProblem(
                    path=str(temp_db_path),
                    cause="semantic comparison failed between parsed source and temp database",
                )
            ],
        )
        raise LegacyImportError(report)


def _source_semantic_view(tree: _LegacyTree) -> dict[str, Any]:
    plans: list[dict[str, Any]] = []
    for plan in tree.plans:
        plan_view: dict[str, Any] = {
            "id": plan.model.id,
            "title": plan.model.title,
            "description": plan.model.description,
            "status": plan.model.status.value,
            "priority": plan.model.priority,
            "creation_time": canonical_utc_timestamp(plan.model.creation_time),
            "completion_time": (
                canonical_utc_timestamp(plan.model.completion_time)
                if plan.model.completion_time
                else None
            ),
            "ord": plan.order,
            "extra": plan.extra,
            "stories": [],
            "plan_state": {
                "current_story_id": plan.current_story_id,
                "current_task_story_id": plan.current_task_story_id,
                "current_task_local_id": plan.current_task_local_id,
            },
            "events": [
                {
                    "legacy_id": event.legacy_id,
                    "ts": event.ts,
                    "type": event.event_type,
                    "scope": event.scope,
                    "data": event.data,
                }
                for event in plan.events
            ],
        }
        for story in plan.stories:
            story_view: dict[str, Any] = {
                "id": story.model.id,
                "title": story.model.title,
                "description": story.model.description,
                "status": story.model.status.value,
                "priority": story.model.priority,
                "acceptance_criteria": story.model.acceptance_criteria,
                "depends_on": story.model.depends_on,
                "body": story.body,
                "creation_time": canonical_utc_timestamp(story.model.creation_time),
                "completion_time": (
                    canonical_utc_timestamp(story.model.completion_time)
                    if story.model.completion_time
                    else None
                ),
                "ord": story.order,
                "extra": story.extra,
                "tasks": [],
            }
            for task in story.tasks:
                story_view["tasks"].append(
                    {
                        "local_id": task.model.local_id,
                        "title": task.model.title,
                        "description": task.model.description,
                        "status": task.model.status.value,
                        "priority": task.model.priority,
                        "depends_on": task.model.depends_on,
                        "steps": serialize_steps(task.model.steps),
                        "changes": task.model.changes,
                        "review_feedback": [
                            feedback.model_dump(mode="json")
                            for feedback in task.model.review_feedback
                        ],
                        "rework_count": task.model.rework_count,
                        "body": task.body,
                        "creation_time": canonical_utc_timestamp(
                            task.model.creation_time
                        ),
                        "completion_time": (
                            canonical_utc_timestamp(task.model.completion_time)
                            if task.model.completion_time
                            else None
                        ),
                        "ord": task.order,
                        "extra": task.extra,
                    }
                )
            plan_view["stories"].append(story_view)
        plans.append(plan_view)
    return {"plans": plans}


def _db_semantic_view(db_path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        result_plans: list[dict[str, Any]] = []
        plan_rows = conn.execute(
            "SELECT id, title, description, status, priority, creation_time, completion_time, ord, extra FROM plans ORDER BY ord"
        ).fetchall()
        for plan_row in plan_rows:
            plan_id = str(plan_row["id"])
            story_rows = conn.execute(
                "SELECT id, title, description, status, priority, acceptance_criteria, depends_on, body, creation_time, completion_time, ord, extra "
                "FROM stories WHERE plan_id = ? ORDER BY ord",
                (plan_id,),
            ).fetchall()
            stories_view: list[dict[str, Any]] = []
            for story_row in story_rows:
                task_rows = conn.execute(
                    "SELECT local_id, title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra "
                    "FROM tasks WHERE plan_id = ? AND story_id = ? ORDER BY ord",
                    (plan_id, str(story_row["id"])),
                ).fetchall()
                stories_view.append(
                    {
                        "id": str(story_row["id"]),
                        "title": str(story_row["title"]),
                        "description": story_row["description"],
                        "status": str(story_row["status"]),
                        "priority": story_row["priority"],
                        "acceptance_criteria": loads_json(
                            story_row["acceptance_criteria"]
                        ),
                        "depends_on": loads_json(story_row["depends_on"]),
                        "body": story_row["body"]
                        if story_row["body"] is not None
                        else "",
                        "creation_time": str(story_row["creation_time"]),
                        "completion_time": story_row["completion_time"],
                        "ord": int(story_row["ord"]),
                        "extra": loads_json(story_row["extra"]) or {},
                        "tasks": [
                            {
                                "local_id": str(task_row["local_id"]),
                                "title": str(task_row["title"]),
                                "description": task_row["description"],
                                "status": str(task_row["status"]),
                                "priority": task_row["priority"],
                                "depends_on": loads_json(task_row["depends_on"]),
                                "steps": loads_json(task_row["steps"]),
                                "changes": loads_json(task_row["changes"]),
                                "review_feedback": loads_json(
                                    task_row["review_feedback"]
                                ),
                                "rework_count": int(task_row["rework_count"]),
                                "body": task_row["body"]
                                if task_row["body"] is not None
                                else "",
                                "creation_time": str(task_row["creation_time"]),
                                "completion_time": task_row["completion_time"],
                                "ord": int(task_row["ord"]),
                                "extra": loads_json(task_row["extra"]) or {},
                            }
                            for task_row in task_rows
                        ],
                    }
                )
            state_row = conn.execute(
                "SELECT current_story_id, current_task_story_id, current_task_local_id FROM plan_state WHERE plan_id = ?",
                (plan_id,),
            ).fetchone()
            event_rows = conn.execute(
                "SELECT legacy_id, ts, type, scope, data FROM events WHERE plan_id = ? ORDER BY seq",
                (plan_id,),
            ).fetchall()
            result_plans.append(
                {
                    "id": plan_id,
                    "title": str(plan_row["title"]),
                    "description": plan_row["description"],
                    "status": str(plan_row["status"]),
                    "priority": plan_row["priority"],
                    "creation_time": str(plan_row["creation_time"]),
                    "completion_time": plan_row["completion_time"],
                    "ord": int(plan_row["ord"]),
                    "extra": loads_json(plan_row["extra"]) or {},
                    "stories": stories_view,
                    "plan_state": {
                        "current_story_id": (
                            str(state_row["current_story_id"]) if state_row else None
                        ),
                        "current_task_story_id": (
                            str(state_row["current_task_story_id"])
                            if state_row
                            else None
                        ),
                        "current_task_local_id": (
                            str(state_row["current_task_local_id"])
                            if state_row
                            else None
                        ),
                    },
                    "events": [
                        {
                            "legacy_id": str(event_row["legacy_id"]),
                            "ts": str(event_row["ts"]),
                            "type": str(event_row["type"]),
                            "scope": loads_json(event_row["scope"]),
                            "data": loads_json(event_row["data"]),
                        }
                        for event_row in event_rows
                    ],
                }
            )
        return {"plans": result_plans}
    finally:
        conn.close()


def _extract_plan_entries(
    index_data: dict[str, Any] | None,
    index_path: Path,
    errors: list[ImportProblem],
) -> list[tuple[str, dict[str, Any]]]:
    if index_data is None:
        return []
    plans_data = index_data.get("plans")
    if not isinstance(plans_data, list):
        errors.append(
            ImportProblem(path=str(index_path), cause="index is missing a 'plans' list")
        )
        return []

    entries: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, entry in enumerate(plans_data):
        entry_path = f"{index_path}#plans[{index}]"
        if not isinstance(entry, dict):
            errors.append(
                ImportProblem(
                    path=entry_path, cause="plan index entry must be a mapping"
                )
            )
            continue
        plan_id = entry.get("id")
        if not isinstance(plan_id, str) or not plan_id.strip():
            errors.append(
                ImportProblem(
                    path=entry_path, cause="plan index entry has empty/invalid id"
                )
            )
            continue
        if plan_id in seen:
            errors.append(
                ImportProblem(
                    path=entry_path, cause=f"duplicate plan id '{plan_id}' in index"
                )
            )
            continue
        seen.add(plan_id)
        entries.append((plan_id, entry))
    return entries


def _parse_activity_events(
    activity_path: Path, errors: list[ImportProblem]
) -> list[_LegacyEvent]:
    if not activity_path.exists():
        return []
    data = _load_yaml_value(activity_path, errors)
    if data is None:
        return []
    if not isinstance(data, list):
        errors.append(
            ImportProblem(
                path=str(activity_path), cause="activity file must be a YAML list"
            )
        )
        return []
    events: list[_LegacyEvent] = []
    for index, item in enumerate(data):
        item_path = f"{activity_path}#{index}"
        if not isinstance(item, dict):
            errors.append(
                ImportProblem(path=item_path, cause="event must be a mapping")
            )
            continue
        legacy_id = item.get("id")
        event_type = item.get("type")
        scope = item.get("scope")
        ts = item.get("ts")
        data_field = item.get("data")
        if legacy_id is None:
            errors.append(ImportProblem(path=item_path, cause="event.id is required"))
            continue
        if not isinstance(event_type, str) or not event_type.strip():
            errors.append(
                ImportProblem(path=item_path, cause="event.type must be a string")
            )
            continue
        if not isinstance(scope, dict):
            errors.append(
                ImportProblem(path=item_path, cause="event.scope must be a mapping")
            )
            continue
        if data_field is not None and not isinstance(data_field, dict):
            errors.append(
                ImportProblem(
                    path=item_path, cause="event.data must be a mapping when present"
                )
            )
            continue
        normalized_ts = _parse_and_normalize_timestamp(ts, item_path, errors)
        if normalized_ts is None:
            continue
        events.append(
            _LegacyEvent(
                legacy_id=str(legacy_id),
                ts=normalized_ts,
                event_type=event_type,
                scope=scope,
                data=data_field,
            )
        )
    return events


def _parse_state(
    state_path: Path,
    stories: list[_LegacyStory],
    errors: list[ImportProblem],
) -> tuple[str | None, str | None, str | None]:
    if not state_path.exists():
        return None, None, None
    state = _load_yaml_mapping(state_path, errors)
    if state is None:
        return None, None, None

    known_story_ids = {story.model.id for story in stories}
    known_task_ids = {
        f"{story.model.id}:{task.model.local_id}"
        for story in stories
        for task in story.tasks
        if task.model.local_id
    }

    current_story_id = state.get("current_story_id")
    current_task_id = state.get("current_task_id")

    if current_story_id is not None and not isinstance(current_story_id, str):
        errors.append(
            ImportProblem(
                path=str(state_path),
                cause="state.current_story_id must be a string when present",
            )
        )
        current_story_id = None
    if current_task_id is not None and not isinstance(current_task_id, str):
        errors.append(
            ImportProblem(
                path=str(state_path),
                cause="state.current_task_id must be a string when present",
            )
        )
        current_task_id = None

    if isinstance(current_story_id, str) and current_story_id not in known_story_ids:
        errors.append(
            ImportProblem(
                path=str(state_path),
                cause=f"invalid state pointer: unknown story '{current_story_id}'",
            )
        )
        current_story_id = None

    current_task_story_id: str | None = None
    current_task_local_id: str | None = None
    if isinstance(current_task_id, str):
        if ":" not in current_task_id:
            errors.append(
                ImportProblem(
                    path=str(state_path),
                    cause=f"invalid state pointer: task id '{current_task_id}' must be story:task",
                )
            )
        elif current_task_id not in known_task_ids:
            errors.append(
                ImportProblem(
                    path=str(state_path),
                    cause=f"invalid state pointer: unknown task '{current_task_id}'",
                )
            )
        else:
            current_task_story_id, current_task_local_id = current_task_id.split(":", 1)
            if (
                current_story_id is not None
                and current_story_id != current_task_story_id
            ):
                errors.append(
                    ImportProblem(
                        path=str(state_path),
                        cause=(
                            "invalid state pointers: current_story_id does not match "
                            "current_task_id story segment"
                        ),
                    )
                )
                current_task_story_id = None
                current_task_local_id = None
    return current_story_id, current_task_story_id, current_task_local_id


def _validate_story_cycles(
    stories: list[_LegacyStory], manifest_path: Path, errors: list[ImportProblem]
) -> None:
    graph = {story.model.id: list(story.model.depends_on or []) for story in stories}
    cycle = _find_cycle(graph)
    if cycle:
        errors.append(
            ImportProblem(
                path=str(manifest_path),
                cause=f"dependency cycle detected across stories: {' -> '.join(cycle)}",
            )
        )


def _validate_task_cycles(
    stories: list[_LegacyStory], manifest_path: Path, errors: list[ImportProblem]
) -> None:
    task_ids = {
        f"{story.model.id}:{task.model.local_id}"
        for story in stories
        for task in story.tasks
        if task.model.local_id
    }
    graph: dict[str, list[str]] = {}
    for story in stories:
        for task in story.tasks:
            if task.model.local_id is None:
                continue
            task_id = f"{story.model.id}:{task.model.local_id}"
            deps: list[str] = []
            for dependency in task.model.depends_on or []:
                if ":" in dependency:
                    dep_id = dependency
                else:
                    dep_id = f"{story.model.id}:{dependency}"
                if dep_id not in task_ids:
                    errors.append(
                        ImportProblem(
                            path=str(manifest_path),
                            cause=f"task '{task_id}' depends on unknown task '{dependency}'",
                        )
                    )
                    continue
                deps.append(dep_id)
            graph[task_id] = deps

    cycle = _find_cycle(graph)
    if cycle:
        errors.append(
            ImportProblem(
                path=str(manifest_path),
                cause=f"dependency cycle detected across tasks: {' -> '.join(cycle)}",
            )
        )


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def dfs(node: str) -> list[str] | None:
        visiting.add(node)
        stack.append(node)
        for neighbor in graph.get(node, []):
            if neighbor in visiting:
                cycle_start = stack.index(neighbor)
                return [*stack[cycle_start:], neighbor]
            if neighbor in visited:
                continue
            cycle = dfs(neighbor)
            if cycle:
                return cycle
        visiting.remove(node)
        visited.add(node)
        stack.pop()
        return None

    for key in graph:
        if key in visited:
            continue
        cycle = dfs(key)
        if cycle:
            return cycle
    return None


def _validate_plan(
    payload: dict[str, Any], path: Path, errors: list[ImportProblem]
) -> Plan | None:
    try:
        plan = Plan.model_validate(payload)
    except ValidationError as exc:
        errors.append(
            ImportProblem(path=str(path), cause=f"plan validation failed: {exc}")
        )
        return None
    plan.creation_time = _normalize_datetime(plan.creation_time)
    if plan.completion_time is not None:
        plan.completion_time = _normalize_datetime(plan.completion_time)
    return plan


def _validate_story(
    payload: dict[str, Any], path: Path, errors: list[ImportProblem]
) -> Story | None:
    try:
        return Story.model_validate(payload)
    except ValidationError as exc:
        errors.append(
            ImportProblem(path=str(path), cause=f"story validation failed: {exc}")
        )
        return None


def _validate_task(
    payload: dict[str, Any], path: Path, errors: list[ImportProblem]
) -> Task | None:
    try:
        return Task.model_validate(payload)
    except ValidationError as exc:
        errors.append(
            ImportProblem(path=str(path), cause=f"task validation failed: {exc}")
        )
        return None


def _extract_str_list(
    data: dict[str, Any], key: str, source_path: Path, errors: list[ImportProblem]
) -> list[str]:
    raw = data.get(key, [])
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append(
            ImportProblem(
                path=str(source_path), cause=f"'{key}' must be a list of strings"
            )
        )
        return []
    values: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, str) or not item.strip():
            errors.append(
                ImportProblem(
                    path=f"{source_path}#{key}[{index}]",
                    cause="list entry must be a non-empty string",
                )
            )
            continue
        values.append(item.strip())
    return values


def _collect_duplicate_ids(
    *,
    values: list[str],
    source_path: Path,
    field_name: str,
    item_label: str,
    errors: list[ImportProblem],
) -> None:
    seen: set[str] = set()
    for index, value in enumerate(values):
        if value in seen:
            errors.append(
                ImportProblem(
                    path=f"{source_path}#{field_name}[{index}]",
                    cause=f"duplicate {item_label} '{value}' in {field_name} list",
                )
            )
            continue
        seen.add(value)


def _load_markdown_frontmatter(
    path: Path, errors: list[ImportProblem]
) -> tuple[dict[str, Any] | None, str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(ImportProblem(path=str(path), cause=f"read failed: {exc}"))
        return None, ""
    if not raw.startswith("---"):
        errors.append(
            ImportProblem(path=str(path), cause="missing YAML frontmatter delimiter")
        )
        return None, ""

    lines = raw.splitlines()
    end_index: int | None = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index is None:
        errors.append(
            ImportProblem(path=str(path), cause="unterminated YAML frontmatter block")
        )
        return None, ""
    yaml_block = "\n".join(lines[1:end_index])
    try:
        parsed = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError as exc:
        errors.append(ImportProblem(path=str(path), cause=f"unparseable YAML: {exc}"))
        return None, ""
    if not isinstance(parsed, dict):
        errors.append(
            ImportProblem(
                path=str(path), cause="frontmatter must deserialize to a mapping"
            )
        )
        return None, ""
    _, body = split_front_matter(raw)
    return parsed, body


def _load_yaml_mapping(
    path: Path, errors: list[ImportProblem]
) -> dict[str, Any] | None:
    data = _load_yaml_value(path, errors)
    if data is None:
        return None
    if not isinstance(data, dict):
        errors.append(
            ImportProblem(path=str(path), cause="YAML document must be a mapping")
        )
        return None
    return data


def _load_yaml_value(path: Path, errors: list[ImportProblem]) -> Any:
    if not path.exists():
        errors.append(ImportProblem(path=str(path), cause="file not found"))
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(ImportProblem(path=str(path), cause=f"read failed: {exc}"))
        return None
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        errors.append(ImportProblem(path=str(path), cause=f"unparseable YAML: {exc}"))
        return None


def _validate_schema_version(
    payload: dict[str, Any], source_path: Path, errors: list[ImportProblem]
) -> None:
    if "schema_version" not in payload:
        return
    if payload.get("schema_version") != LEGACY_SCHEMA_VERSION:
        errors.append(
            ImportProblem(
                path=str(source_path),
                cause=(
                    "unknown schema_version "
                    f"'{payload.get('schema_version')}' (expected {LEGACY_SCHEMA_VERSION})"
                ),
            )
        )


def _validate_slug_id(
    item_id: str,
    title: Any,
    source_path: Path,
    item_kind: str,
    errors: list[ImportProblem],
) -> None:
    if not isinstance(item_id, str) or not item_id.strip():
        errors.append(
            ImportProblem(
                path=str(source_path), cause=f"{item_kind} id is empty/invalid"
            )
        )
        return
    if not _is_valid_slug(item_id):
        errors.append(
            ImportProblem(
                path=str(source_path),
                cause=f"{item_kind} id '{item_id}' is not a valid slug",
            )
        )
    if not isinstance(title, str) or not title.strip():
        errors.append(
            ImportProblem(path=str(source_path), cause=f"{item_kind} title is required")
        )
        return
    generated = slugify(title)
    if not generated:
        errors.append(
            ImportProblem(
                path=str(source_path),
                cause=f"{item_kind} title '{title}' slugifies to an empty id",
            )
        )


def _is_valid_slug(value: str) -> bool:
    import re

    return bool(re.match(_SLUG_RE, value))


def _parse_and_normalize_timestamp(
    value: Any, source_path: str, errors: list[ImportProblem]
) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(
            ImportProblem(
                path=source_path, cause="timestamp must be a non-empty string"
            )
        )
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(
            ImportProblem(path=source_path, cause=f"invalid timestamp '{value}'")
        )
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return canonical_utc_timestamp(parsed.astimezone(timezone.utc))


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _extract_extra_fields(
    payload: dict[str, Any], known_fields: set[str]
) -> dict[str, Any]:
    extra = {k: v for k, v in payload.items() if k not in known_fields}
    return dict(extra)


def _plan_known_fields() -> set[str]:
    return {
        "id",
        "title",
        "description",
        "priority",
        "depends_on",
        "status",
        "creation_time",
        "completion_time",
        "stories",
        "schema_version",
    }


def _story_known_fields() -> set[str]:
    return {
        "id",
        "title",
        "description",
        "priority",
        "depends_on",
        "status",
        "creation_time",
        "completion_time",
        "acceptance_criteria",
        "tasks",
        "schema_version",
        "file_path",
    }


def _task_known_fields() -> set[str]:
    return {
        "id",
        "title",
        "description",
        "priority",
        "depends_on",
        "status",
        "creation_time",
        "completion_time",
        "story_id",
        "local_id",
        "steps",
        "changes",
        "review_feedback",
        "rework_count",
        "schema_version",
        "file_path",
    }


def _set_import_state(conn: sqlite3.Connection, state: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (IMPORT_STATE_KEY, state),
    )
    conn.commit()


def _set_wal(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    mode = str(row[0]).lower() if row else ""
    if mode != "wal":
        raise RuntimeError("WAL bootstrap failed during import temp-db creation.")


def _sweep_orphaned_import_temp_dbs(db_dir: Path) -> None:
    for temp_file in db_dir.glob(f"{PUBLISHED_DB_FILENAME}.import.*.tmp"):
        _cleanup_sqlite_artifacts(temp_file)


def _cleanup_sqlite_sidecars(db_path: Path) -> None:
    for candidate in (Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        _safe_unlink(candidate)


def _cleanup_sqlite_artifacts(db_path: Path) -> None:
    _safe_unlink(db_path)
    _cleanup_sqlite_sidecars(db_path)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def _raise_if_errors(errors: list[ImportProblem]) -> None:
    if not errors:
        return
    report = ImportReport(
        dry_run=False,
        published=False,
        plans=0,
        stories=0,
        tasks=0,
        events=0,
        problems=errors,
    )
    raise LegacyImportError(report)
