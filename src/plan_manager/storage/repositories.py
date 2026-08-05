# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""SQLite repository primitives operating on caller-managed connections."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Iterable

from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.storage.codecs import dumps_json, loads_json, serialize_steps
from plan_manager.storage.uow import canonical_utc_timestamp

UNSET = object()


class StorageConflictError(RuntimeError):
    """Raised when a guarded storage mutation conflicts with current state."""


@dataclass(frozen=True)
class TaskStatusTransitionConflictError(StorageConflictError):
    """Raised when a guarded status transition loses a race."""

    plan_id: str
    story_id: str
    local_id: str
    expected_status: Status
    next_status: Status

    def __str__(self) -> str:
        return (
            "Task status transition conflict for "
            f"'{self.story_id}:{self.local_id}' in plan '{self.plan_id}': "
            f"expected {self.expected_status.value}, attempted {self.next_status.value}."
        )


@dataclass(frozen=True)
class PlanStateRecord:
    plan_id: str
    current_story_id: str | None
    current_task_story_id: str | None
    current_task_local_id: str | None

    @property
    def current_task_id(self) -> str | None:
        if self.current_task_story_id is None or self.current_task_local_id is None:
            return None
        return f"{self.current_task_story_id}:{self.current_task_local_id}"


@dataclass(frozen=True)
class EventRecord:
    seq: int
    plan_id: str
    legacy_id: str | None
    ts: str
    event_type: str
    scope: dict[str, Any]
    data: dict[str, Any] | None


def get_meta_value(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    if row is None:
        return None
    return str(row["value"])


def set_meta_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def delete_meta_value(conn: sqlite3.Connection, key: str) -> None:
    conn.execute("DELETE FROM meta WHERE key = ?", (key,))


def create_plan(
    conn: sqlite3.Connection,
    *,
    base_id: str,
    title: str,
    description: str | None,
    status: Status,
    priority: int | None,
    creation_time: datetime | str | None = None,
    completion_time: datetime | str | None = None,
    ord_value: int = 0,
    extra: dict[str, Any] | None = None,
    max_id_attempts: int = 32,
) -> str:
    """Create a plan row and return the allocated ID."""
    created = _to_timestamp(creation_time) or canonical_utc_timestamp()
    completed = _to_timestamp(completion_time)
    return _insert_with_unique_suffix(
        base_id=base_id,
        max_attempts=max_id_attempts,
        inserter=lambda candidate: conn.execute(
            "INSERT INTO plans(id, title, description, status, priority, creation_time, completion_time, ord, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                candidate,
                title,
                description,
                status.value,
                priority,
                created,
                completed,
                ord_value,
                dumps_json(extra),
            ),
        ),
        id_constraint_tokens=("plans.id",),
    )


def get_plan(conn: sqlite3.Connection, plan_id: str) -> Plan | None:
    row = conn.execute(
        "SELECT id, title, description, status, priority, creation_time, completion_time "
        "FROM plans WHERE id = ?",
        (plan_id,),
    ).fetchone()
    if row is None:
        return None
    return Plan(
        id=str(row["id"]),
        title=str(row["title"]),
        description=row["description"],
        status=Status(str(row["status"])),
        priority=row["priority"],
        creation_time=_parse_required_timestamp(str(row["creation_time"])),
        completion_time=_parse_timestamp(row["completion_time"]),
        stories=[],
    )


def list_plans(conn: sqlite3.Connection) -> list[Plan]:
    rows = conn.execute(
        "SELECT id, title, description, status, priority, creation_time, completion_time "
        "FROM plans ORDER BY ord, id"
    ).fetchall()
    return [
        Plan(
            id=str(row["id"]),
            title=str(row["title"]),
            description=row["description"],
            status=Status(str(row["status"])),
            priority=row["priority"],
            creation_time=_parse_required_timestamp(str(row["creation_time"])),
            completion_time=_parse_timestamp(row["completion_time"]),
            stories=[],
        )
        for row in rows
    ]


def update_plan(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    title: str | object = UNSET,
    description: str | None | object = UNSET,
    status: Status | object = UNSET,
    priority: int | None | object = UNSET,
    completion_time: datetime | str | None | object = UNSET,
    ord_value: int | object = UNSET,
    extra: dict[str, Any] | None | object = UNSET,
) -> bool:
    assignments: list[str] = []
    values: list[Any] = []

    if title is not UNSET:
        assignments.append("title = ?")
        values.append(title)
    if description is not UNSET:
        assignments.append("description = ?")
        values.append(description)
    if status is not UNSET:
        assert isinstance(status, Status)
        assignments.append("status = ?")
        values.append(status.value)
    if priority is not UNSET:
        assignments.append("priority = ?")
        values.append(priority)
    if completion_time is not UNSET:
        assignments.append("completion_time = ?")
        values.append(_to_timestamp(completion_time))
    if ord_value is not UNSET:
        assignments.append("ord = ?")
        values.append(ord_value)
    if extra is not UNSET:
        assignments.append("extra = ?")
        values.append(dumps_json(extra))

    if not assignments:
        return False
    values.append(plan_id)
    result = conn.execute(
        f"UPDATE plans SET {', '.join(assignments)} WHERE id = ?",  # noqa: S608
        tuple(values),
    )
    return result.rowcount > 0


def delete_plan(conn: sqlite3.Connection, plan_id: str) -> bool:
    return conn.execute("DELETE FROM plans WHERE id = ?", (plan_id,)).rowcount > 0


def create_story(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    base_id: str,
    title: str,
    description: str | None,
    status: Status,
    priority: int | None,
    acceptance_criteria: list[str] | None,
    depends_on: list[str] | None,
    creation_time: datetime | str | None = None,
    completion_time: datetime | str | None = None,
    ord_value: int = 0,
    body: str = "",
    extra: dict[str, Any] | None = None,
    max_id_attempts: int = 32,
) -> str:
    created = _to_timestamp(creation_time) or canonical_utc_timestamp()
    completed = _to_timestamp(completion_time)
    return _insert_with_unique_suffix(
        base_id=base_id,
        max_attempts=max_id_attempts,
        inserter=lambda candidate: conn.execute(
            "INSERT INTO stories(plan_id, id, title, status, priority, description, acceptance_criteria, depends_on, body, creation_time, completion_time, ord, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                plan_id,
                candidate,
                title,
                status.value,
                priority,
                description,
                dumps_json(acceptance_criteria),
                dumps_json(depends_on),
                body,
                created,
                completed,
                ord_value,
                dumps_json(extra),
            ),
        ),
        id_constraint_tokens=("stories.plan_id, stories.id",),
    )


def get_story(conn: sqlite3.Connection, plan_id: str, story_id: str) -> Story | None:
    row = conn.execute(
        "SELECT id, title, description, status, priority, acceptance_criteria, depends_on, creation_time, completion_time "
        "FROM stories WHERE plan_id = ? AND id = ?",
        (plan_id, story_id),
    ).fetchone()
    if row is None:
        return None
    return Story(
        id=str(row["id"]),
        title=str(row["title"]),
        description=row["description"],
        status=Status(str(row["status"])),
        priority=row["priority"],
        acceptance_criteria=loads_json(row["acceptance_criteria"]),
        depends_on=loads_json(row["depends_on"]) or [],
        creation_time=_parse_required_timestamp(str(row["creation_time"])),
        completion_time=_parse_timestamp(row["completion_time"]),
        tasks=[],
    )


def list_stories(
    conn: sqlite3.Connection,
    plan_id: str,
    *,
    statuses: Iterable[Status] | None = None,
    unblocked: bool = False,
) -> list[Story]:
    rows = conn.execute(
        "SELECT id, title, description, status, priority, acceptance_criteria, depends_on, creation_time, completion_time "
        "FROM stories WHERE plan_id = ? ORDER BY ord, id",
        (plan_id,),
    ).fetchall()
    stories = [
        Story(
            id=str(row["id"]),
            title=str(row["title"]),
            description=row["description"],
            status=Status(str(row["status"])),
            priority=row["priority"],
            acceptance_criteria=loads_json(row["acceptance_criteria"]),
            depends_on=loads_json(row["depends_on"]) or [],
            creation_time=_parse_required_timestamp(str(row["creation_time"])),
            completion_time=_parse_timestamp(row["completion_time"]),
            tasks=[],
        )
        for row in rows
    ]
    return _sort_and_filter_stories(stories, statuses=statuses, unblocked=unblocked)


def update_story(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    title: str | object = UNSET,
    description: str | None | object = UNSET,
    status: Status | object = UNSET,
    priority: int | None | object = UNSET,
    acceptance_criteria: list[str] | None | object = UNSET,
    depends_on: list[str] | None | object = UNSET,
    completion_time: datetime | str | None | object = UNSET,
    body: str | object = UNSET,
    extra: dict[str, Any] | None | object = UNSET,
) -> bool:
    if depends_on is not UNSET:
        depends_on_list = cast("list[str] | None", depends_on)
        _ensure_story_dependency_acyclic(
            conn,
            plan_id=plan_id,
            story_id=story_id,
            next_depends_on=depends_on_list,
        )

    assignments: list[str] = []
    values: list[Any] = []
    if title is not UNSET:
        assignments.append("title = ?")
        values.append(title)
    if description is not UNSET:
        assignments.append("description = ?")
        values.append(description)
    if status is not UNSET:
        assert isinstance(status, Status)
        assignments.append("status = ?")
        values.append(status.value)
    if priority is not UNSET:
        assignments.append("priority = ?")
        values.append(priority)
    if acceptance_criteria is not UNSET:
        assignments.append("acceptance_criteria = ?")
        values.append(dumps_json(acceptance_criteria))
    if depends_on is not UNSET:
        assignments.append("depends_on = ?")
        values.append(dumps_json(depends_on))
    if completion_time is not UNSET:
        assignments.append("completion_time = ?")
        values.append(_to_timestamp(completion_time))
    if body is not UNSET:
        assignments.append("body = ?")
        values.append(body)
    if extra is not UNSET:
        assignments.append("extra = ?")
        values.append(dumps_json(extra))

    if not assignments:
        return False
    values.extend([plan_id, story_id])
    result = conn.execute(
        f"UPDATE stories SET {', '.join(assignments)} WHERE plan_id = ? AND id = ?",  # noqa: S608
        tuple(values),
    )
    return result.rowcount > 0


def delete_story(conn: sqlite3.Connection, plan_id: str, story_id: str) -> bool:
    conn.execute(
        "UPDATE plan_state SET current_story_id = NULL, current_task_story_id = NULL, current_task_local_id = NULL "
        "WHERE plan_id = ? AND (current_story_id = ? OR current_task_story_id = ?)",
        (plan_id, story_id, story_id),
    )
    return (
        conn.execute(
            "DELETE FROM stories WHERE plan_id = ? AND id = ?",
            (plan_id, story_id),
        ).rowcount
        > 0
    )


def create_task(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    base_local_id: str,
    title: str,
    description: str | None,
    status: Status,
    priority: int | None,
    depends_on: list[str] | None,
    steps: list[Task.Step] | None,
    changes: list[str] | None,
    review_feedback: list[Task.ReviewFeedback] | None,
    rework_count: int = 0,
    creation_time: datetime | str | None = None,
    completion_time: datetime | str | None = None,
    ord_value: int = 0,
    body: str = "",
    extra: dict[str, Any] | None = None,
    max_id_attempts: int = 32,
) -> str:
    created = _to_timestamp(creation_time) or canonical_utc_timestamp()
    completed = _to_timestamp(completion_time)
    return _insert_with_unique_suffix(
        base_id=base_local_id,
        max_attempts=max_id_attempts,
        inserter=lambda candidate: conn.execute(
            "INSERT INTO tasks(plan_id, story_id, local_id, title, status, priority, description, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                plan_id,
                story_id,
                candidate,
                title,
                status.value,
                priority,
                description,
                dumps_json(depends_on),
                dumps_json(serialize_steps(steps)),
                dumps_json(changes),
                dumps_json(
                    [feedback.model_dump(mode="json") for feedback in review_feedback]
                    if review_feedback is not None
                    else []
                ),
                rework_count,
                body,
                created,
                completed,
                ord_value,
                dumps_json(extra),
            ),
        ),
        id_constraint_tokens=("tasks.plan_id, tasks.story_id, tasks.local_id",),
    )


def get_task(
    conn: sqlite3.Connection,
    plan_id: str,
    story_id: str,
    local_id: str,
) -> Task | None:
    row = conn.execute(
        "SELECT story_id, local_id, title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, creation_time, completion_time "
        "FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
        (plan_id, story_id, local_id),
    ).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def list_tasks(
    conn: sqlite3.Connection,
    plan_id: str,
    *,
    statuses: Iterable[Status] | None = None,
    story_id: str | None = None,
) -> list[Task]:
    rows = conn.execute(
        "SELECT story_id, local_id, title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, creation_time, completion_time "
        "FROM tasks WHERE plan_id = ? AND (? IS NULL OR story_id = ?)",
        (plan_id, story_id, story_id),
    ).fetchall()
    tasks = [_row_to_task(row) for row in rows]
    if statuses:
        allowed = {status.value for status in statuses}
        tasks = [task for task in tasks if task.status.value in allowed]

    tasks.sort(
        key=lambda task: (
            task.priority if task.priority is not None else 6,
            (
                task.creation_time is None,
                task.creation_time.isoformat() if task.creation_time else "9999",
            ),
            task.id,
        )
    )
    return tasks


def update_task(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    local_id: str,
    title: str | object = UNSET,
    description: str | None | object = UNSET,
    status: Status | object = UNSET,
    priority: int | None | object = UNSET,
    depends_on: list[str] | None | object = UNSET,
    steps: list[Task.Step] | None | object = UNSET,
    changes: list[str] | None | object = UNSET,
    review_feedback: list[Task.ReviewFeedback] | None | object = UNSET,
    rework_count: int | object = UNSET,
    completion_time: datetime | str | None | object = UNSET,
    body: str | object = UNSET,
    extra: dict[str, Any] | None | object = UNSET,
    rollup_story_status: Status | object = UNSET,
    rollup_plan_status: Status | object = UNSET,
) -> bool:
    if depends_on is not UNSET:
        depends_on_list = cast("list[str] | None", depends_on)
        _ensure_task_dependency_acyclic(
            conn,
            plan_id=plan_id,
            story_id=story_id,
            local_id=local_id,
            next_depends_on=depends_on_list,
        )

    assignments: list[str] = []
    values: list[Any] = []
    if title is not UNSET:
        assignments.append("title = ?")
        values.append(title)
    if description is not UNSET:
        assignments.append("description = ?")
        values.append(description)
    if status is not UNSET:
        assert isinstance(status, Status)
        assignments.append("status = ?")
        values.append(status.value)
    if priority is not UNSET:
        assignments.append("priority = ?")
        values.append(priority)
    if depends_on is not UNSET:
        assignments.append("depends_on = ?")
        values.append(dumps_json(depends_on))
    if steps is not UNSET:
        steps_value = cast("list[Task.Step] | None", steps)
        assignments.append("steps = ?")
        values.append(dumps_json(serialize_steps(steps_value)))
    if changes is not UNSET:
        assignments.append("changes = ?")
        values.append(dumps_json(changes))
    if review_feedback is not UNSET:
        feedback_value = cast("list[Task.ReviewFeedback] | None", review_feedback)
        assignments.append("review_feedback = ?")
        values.append(
            dumps_json(
                [feedback.model_dump(mode="json") for feedback in feedback_value]
                if feedback_value is not None
                else []
            )
        )
    if rework_count is not UNSET:
        assignments.append("rework_count = ?")
        values.append(rework_count)
    if completion_time is not UNSET:
        assignments.append("completion_time = ?")
        values.append(_to_timestamp(completion_time))
    if body is not UNSET:
        assignments.append("body = ?")
        values.append(body)
    if extra is not UNSET:
        assignments.append("extra = ?")
        values.append(dumps_json(extra))

    updated = False
    if assignments:
        values.extend([plan_id, story_id, local_id])
        updated = (
            conn.execute(
                (
                    f"UPDATE tasks SET {', '.join(assignments)} "  # noqa: S608
                    "WHERE plan_id = ? AND story_id = ? AND local_id = ?"
                ),
                tuple(values),
            ).rowcount
            > 0
        )

    if rollup_story_status is not UNSET:
        assert isinstance(rollup_story_status, Status)
        conn.execute(
            "UPDATE stories SET status = ? WHERE plan_id = ? AND id = ?",
            (rollup_story_status.value, plan_id, story_id),
        )
    if rollup_plan_status is not UNSET:
        assert isinstance(rollup_plan_status, Status)
        conn.execute(
            "UPDATE plans SET status = ? WHERE id = ?",
            (rollup_plan_status.value, plan_id),
        )
    return updated


def delete_task(
    conn: sqlite3.Connection,
    plan_id: str,
    story_id: str,
    local_id: str,
) -> bool:
    conn.execute(
        "UPDATE plan_state SET current_task_story_id = NULL, current_task_local_id = NULL "
        "WHERE plan_id = ? AND current_task_story_id = ? AND current_task_local_id = ?",
        (plan_id, story_id, local_id),
    )
    return (
        conn.execute(
            "DELETE FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            (plan_id, story_id, local_id),
        ).rowcount
        > 0
    )


def transition_task_status_guarded(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    local_id: str,
    expected_status: Status,
    next_status: Status,
    completion_time: datetime | str | None | object = UNSET,
    raise_on_conflict: bool = True,
) -> bool:
    fields = ["status = ?"]
    values: list[Any] = [next_status.value]
    if completion_time is not UNSET:
        fields.append("completion_time = ?")
        values.append(_to_timestamp(completion_time))
    values.extend([plan_id, story_id, local_id, expected_status.value])
    result = conn.execute(
        (
            f"UPDATE tasks SET {', '.join(fields)} "  # noqa: S608
            "WHERE plan_id = ? AND story_id = ? AND local_id = ? AND status = ?"
        ),
        tuple(values),
    )
    if result.rowcount == 1:
        return True
    if raise_on_conflict:
        raise TaskStatusTransitionConflictError(
            plan_id=plan_id,
            story_id=story_id,
            local_id=local_id,
            expected_status=expected_status,
            next_status=next_status,
        )
    return False


def transition_story_status_guarded(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    expected_status: Status,
    next_status: Status,
    completion_time: datetime | str | None | object = UNSET,
    raise_on_conflict: bool = True,
) -> bool:
    fields = ["status = ?"]
    values: list[Any] = [next_status.value]
    if completion_time is not UNSET:
        fields.append("completion_time = ?")
        values.append(_to_timestamp(completion_time))
    values.extend([plan_id, story_id, expected_status.value])
    result = conn.execute(
        (
            f"UPDATE stories SET {', '.join(fields)} "  # noqa: S608
            "WHERE plan_id = ? AND id = ? AND status = ?"
        ),
        tuple(values),
    )
    if result.rowcount == 1:
        return True
    if raise_on_conflict:
        raise StorageConflictError(
            "Story status transition conflict for "
            f"'{story_id}' in plan '{plan_id}': expected "
            f"{expected_status.value}, attempted {next_status.value}."
        )
    return False


def transition_plan_status_guarded(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    expected_status: Status,
    next_status: Status,
    completion_time: datetime | str | None | object = UNSET,
    raise_on_conflict: bool = True,
) -> bool:
    fields = ["status = ?"]
    values: list[Any] = [next_status.value]
    if completion_time is not UNSET:
        fields.append("completion_time = ?")
        values.append(_to_timestamp(completion_time))
    values.extend([plan_id, expected_status.value])
    result = conn.execute(
        (
            f"UPDATE plans SET {', '.join(fields)} "  # noqa: S608
            "WHERE id = ? AND status = ?"
        ),
        tuple(values),
    )
    if result.rowcount == 1:
        return True
    if raise_on_conflict:
        raise StorageConflictError(
            "Plan status transition conflict for "
            f"'{plan_id}': expected {expected_status.value}, "
            f"attempted {next_status.value}."
        )
    return False


def get_plan_state(conn: sqlite3.Connection, plan_id: str) -> PlanStateRecord:
    row = conn.execute(
        "SELECT current_story_id, current_task_story_id, current_task_local_id "
        "FROM plan_state WHERE plan_id = ?",
        (plan_id,),
    ).fetchone()
    if row is None:
        return PlanStateRecord(
            plan_id=plan_id,
            current_story_id=None,
            current_task_story_id=None,
            current_task_local_id=None,
        )
    return PlanStateRecord(
        plan_id=plan_id,
        current_story_id=row["current_story_id"],
        current_task_story_id=row["current_task_story_id"],
        current_task_local_id=row["current_task_local_id"],
    )


def set_current_story(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    current_story_id: str | None,
) -> None:
    conn.execute(
        "INSERT INTO plan_state(plan_id, current_story_id, current_task_story_id, current_task_local_id) "
        "VALUES (?, ?, NULL, NULL) "
        "ON CONFLICT(plan_id) DO UPDATE SET current_story_id = excluded.current_story_id, current_task_story_id = NULL, current_task_local_id = NULL",
        (plan_id, current_story_id),
    )


def set_current_task(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    current_task_story_id: str | None,
    current_task_local_id: str | None,
) -> None:
    if (current_task_story_id is None) != (current_task_local_id is None):
        raise ValueError(
            "Task pointer requires both story_id and local_id, or neither."
        )
    conn.execute(
        "INSERT INTO plan_state(plan_id, current_story_id, current_task_story_id, current_task_local_id) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(plan_id) DO UPDATE SET current_story_id = excluded.current_story_id, current_task_story_id = excluded.current_task_story_id, current_task_local_id = excluded.current_task_local_id",
        (
            plan_id,
            current_task_story_id,
            current_task_story_id,
            current_task_local_id,
        ),
    )


def append_event(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    event_type: str,
    scope: dict[str, Any],
    data: dict[str, Any] | None = None,
    ts: datetime | str | None = None,
    legacy_id: str | None = None,
) -> EventRecord:
    timestamp = _to_timestamp(ts) or canonical_utc_timestamp()
    cursor = conn.execute(
        "INSERT INTO events(plan_id, legacy_id, ts, type, scope, data) VALUES (?, ?, ?, ?, ?, ?)",
        (
            plan_id,
            legacy_id,
            timestamp,
            event_type,
            dumps_json(scope),
            dumps_json(data),
        ),
    )
    if cursor.lastrowid is None:
        raise RuntimeError("SQLite did not return a rowid for event insert.")
    seq = int(cursor.lastrowid)
    return EventRecord(
        seq=seq,
        plan_id=plan_id,
        legacy_id=legacy_id,
        ts=timestamp,
        event_type=event_type,
        scope=scope,
        data=data,
    )


def list_events(
    conn: sqlite3.Connection,
    plan_id: str,
    *,
    since_seq: int | None = None,
) -> list[EventRecord]:
    query = (
        "SELECT seq, plan_id, legacy_id, ts, type, scope, data FROM events "
        "WHERE plan_id = ?"
    )
    values: list[Any] = [plan_id]
    if since_seq is not None:
        query += " AND seq > ?"
        values.append(since_seq)
    query += " ORDER BY seq"
    rows = conn.execute(query, tuple(values)).fetchall()
    return [
        EventRecord(
            seq=int(row["seq"]),
            plan_id=str(row["plan_id"]),
            legacy_id=row["legacy_id"],
            ts=str(row["ts"]),
            event_type=str(row["type"]),
            scope=loads_json(row["scope"]) or {},
            data=loads_json(row["data"]),
        )
        for row in rows
    ]


def _insert_with_unique_suffix(
    *,
    base_id: str,
    max_attempts: int,
    inserter: Any,
    id_constraint_tokens: tuple[str, ...],
) -> str:
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    candidate = base_id
    for attempt in range(1, max_attempts + 1):
        try:
            inserter(candidate)
            return candidate
        except sqlite3.IntegrityError as exc:  # noqa: PERF203
            if not _is_retryable_id_conflict(exc, id_constraint_tokens):
                raise
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Unable to allocate unique ID for base '{base_id}' after {max_attempts} attempts."
                ) from exc
            candidate = f"{base_id}-{attempt + 1}"
    raise AssertionError("unreachable")


def _is_retryable_id_conflict(
    exc: sqlite3.IntegrityError, id_constraint_tokens: tuple[str, ...]
) -> bool:
    code = getattr(exc, "sqlite_errorcode", None)
    if code is None or (int(code) & 0xFF) != sqlite3.SQLITE_CONSTRAINT:
        return False
    message = str(exc)
    return "UNIQUE constraint failed" in message and any(
        token in message for token in id_constraint_tokens
    )


def _to_timestamp(value: datetime | str | None | object) -> str | None:
    if value is UNSET:
        return None
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        raise TypeError(
            f"Expected datetime or str timestamp, got {type(value).__name__}"
        )
    return canonical_utc_timestamp(value)


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _parse_required_timestamp(value: Any) -> datetime:
    parsed = _parse_timestamp(value)
    if parsed is None:
        raise ValueError("Missing required timestamp value.")
    return parsed


def _row_to_task(row: sqlite3.Row) -> Task:
    steps_json = loads_json(row["steps"])
    review_feedback_json = loads_json(row["review_feedback"]) or []
    return Task(
        id=f"{row['story_id']}:{row['local_id']}",
        story_id=str(row["story_id"]),
        local_id=str(row["local_id"]),
        title=str(row["title"]),
        description=row["description"],
        status=Status(str(row["status"])),
        priority=row["priority"],
        depends_on=loads_json(row["depends_on"]) or [],
        steps=(
            [Task.Step.model_validate(step) for step in steps_json]
            if steps_json is not None
            else None
        ),
        changes=loads_json(row["changes"]) or [],
        review_feedback=[
            Task.ReviewFeedback.model_validate(item) for item in review_feedback_json
        ],
        rework_count=int(row["rework_count"]),
        creation_time=_parse_required_timestamp(str(row["creation_time"])),
        completion_time=_parse_timestamp(row["completion_time"]),
    )


def _sort_and_filter_stories(
    stories: list[Story],
    *,
    statuses: Iterable[Status] | None,
    unblocked: bool,
) -> list[Story]:
    if not stories:
        return []

    by_id = {story.id: story for story in stories}
    in_deg: dict[str, int] = {}
    children: dict[str, list[str]] = {}
    for story in stories:
        in_deg.setdefault(story.id, 0)
        for dep in story.depends_on or []:
            if dep in by_id:
                children.setdefault(dep, []).append(story.id)
                in_deg[story.id] = in_deg.get(story.id, 0) + 1

    def _story_sort_key(story: Story) -> tuple[int, tuple[bool, str], str]:
        prio = story.priority if story.priority is not None else 6
        ctime = story.creation_time.isoformat() if story.creation_time else "9999"
        return (prio, (story.creation_time is None, ctime), story.id)

    queue = [by_id[sid] for sid, degree in in_deg.items() if degree == 0]
    ordered: list[Story] = []
    while queue:
        queue.sort(key=_story_sort_key)
        current = queue.pop(0)
        ordered.append(current)
        for child_id in children.get(current.id, []):
            in_deg[child_id] -= 1
            if in_deg[child_id] == 0:
                queue.append(by_id[child_id])

    if len(ordered) != len(stories):
        missing_ids = [sid for sid in by_id if sid not in {s.id for s in ordered}]
        missing = [by_id[sid] for sid in sorted(missing_ids)]
        ordered.extend(missing)

    allowed = set(statuses) if statuses else None
    result: list[Story] = []
    for story in ordered:
        if allowed is not None and story.status not in allowed:
            continue
        if unblocked:
            if story.status != Status.TODO:
                continue
            deps_done = all(
                dep_id in by_id and by_id[dep_id].status == Status.DONE
                for dep_id in (story.depends_on or [])
            )
            if not deps_done:
                continue
        result.append(story)
    return result


def _ensure_story_dependency_acyclic(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    next_depends_on: list[str] | None,
) -> None:
    edges = {
        str(row["id"]): loads_json(row["depends_on"]) or []
        for row in conn.execute(
            "SELECT id, depends_on FROM stories WHERE plan_id = ?",
            (plan_id,),
        ).fetchall()
    }
    edges[story_id] = list(next_depends_on or [])
    _raise_on_cycle(edges, "story dependencies")


def _ensure_task_dependency_acyclic(
    conn: sqlite3.Connection,
    *,
    plan_id: str,
    story_id: str,
    local_id: str,
    next_depends_on: list[str] | None,
) -> None:
    rows = conn.execute(
        "SELECT story_id, local_id, depends_on FROM tasks WHERE plan_id = ?",
        (plan_id,),
    ).fetchall()
    all_ids = {f"{row['story_id']}:{row['local_id']}" for row in rows}
    current_id = f"{story_id}:{local_id}"
    all_ids.add(current_id)
    edges: dict[str, list[str]] = {}
    for row in rows:
        fq_id = f"{row['story_id']}:{row['local_id']}"
        deps = _normalize_task_deps(
            story_id=str(row["story_id"]),
            depends_on=loads_json(row["depends_on"]) or [],
            known_ids=all_ids,
        )
        edges[fq_id] = deps
    edges[current_id] = _normalize_task_deps(
        story_id=story_id,
        depends_on=next_depends_on or [],
        known_ids=all_ids,
    )
    _raise_on_cycle(edges, "task dependencies")


def _normalize_task_deps(
    *, story_id: str, depends_on: list[str], known_ids: set[str]
) -> list[str]:
    resolved: list[str] = []
    for dep in depends_on:
        fq = dep if ":" in dep else f"{story_id}:{dep}"
        if fq in known_ids:
            resolved.append(fq)
    return resolved


def _raise_on_cycle(graph: dict[str, list[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        visiting.add(node)
        for neighbor in graph.get(node, []):
            if neighbor in visiting:
                return True
            if neighbor in visited:
                continue
            if dfs(neighbor):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for key in graph:
        if key in visited:
            continue
        if dfs(key):
            raise ValueError(f"Dependency cycle detected in {label}.")
