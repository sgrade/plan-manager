# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from plan_manager.config import PLAN_MANAGER_DB_DIR, PLAN_MANAGER_DB_PATH, TODO_DIR
from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.io.paths import slugify
from plan_manager.storage import db as storage_db
from plan_manager.storage import repositories
from plan_manager.storage.uow import StorageBusyError, unit_of_work

logger = logging.getLogger(__name__)

CURRENT_PLAN_META_KEY = "current_plan_id"
# Transitional global current pointer. This shim is intentionally temporary and
# removed in U6b when all tool contracts carry explicit plan_id.
TRANSITIONAL_CURRENT_PLAN_COMMENT = "transitional-global-current"


def generate_slug(title: str) -> str:
    """Generate a URL-safe slug from a title.

    Args:
        title: The title to convert into a slug

    Returns:
        str: The slugified title
    """
    return slugify(title)


def ensure_unique_id_from_set(base_id: str, existing_ids: list[str] | set[str]) -> str:
    """Ensure a unique ID by appending -2, -3, ... if base_id is taken.

    The caller provides the set/list of existing IDs in the relevant scope
    (plans index, plan.stories, or story-local task IDs).
    """
    taken = set(existing_ids)
    if base_id not in taken:
        return base_id
    counter = 2
    while True:
        candidate = f"{base_id}-{counter}"
        if candidate not in taken:
            return candidate
        counter += 1


def db_path() -> str:
    env_db_dir = os.getenv("PLAN_MANAGER_DB_DIR")
    if env_db_dir:
        return str(Path(env_db_dir) / "plan_manager.sqlite3")
    return PLAN_MANAGER_DB_PATH


def db_dir() -> str:
    env_db_dir = os.getenv("PLAN_MANAGER_DB_DIR")
    if env_db_dir:
        return env_db_dir
    return PLAN_MANAGER_DB_DIR


def ensure_storage_ready() -> None:
    storage_db.startup_storage(TODO_DIR, db_dir())


@contextmanager
def service_uow(
    *,
    write: bool,
    operation: str,
    plan_id: str | None = None,
) -> Iterator[Any]:
    ensure_storage_ready()
    try:
        with unit_of_work(db_path(), write=write) as conn:
            yield conn
    except StorageBusyError as exc:
        exc.operation = operation
        exc.plan_id = plan_id
        raise


def get_current_plan_id() -> str:
    with service_uow(write=False, operation="get_current_plan_id") as conn:
        current_plan_id = repositories.get_meta_value(conn, CURRENT_PLAN_META_KEY)
        if current_plan_id and repositories.get_plan(conn, current_plan_id):
            return current_plan_id
        plans = repositories.list_plans(conn)

    if not plans:
        raise ValueError("No active plan. Please create a plan first.")

    fallback_plan_id = plans[0].id
    with service_uow(
        write=True, operation="set_current_plan_id", plan_id=fallback_plan_id
    ) as conn:
        repositories.set_meta_value(conn, CURRENT_PLAN_META_KEY, fallback_plan_id)
    return fallback_plan_id


def set_current_plan_id(plan_id: str | None) -> None:
    with service_uow(
        write=True, operation="set_current_plan_id", plan_id=plan_id
    ) as conn:
        if plan_id is None:
            repositories.delete_meta_value(conn, CURRENT_PLAN_META_KEY)
            return
        if repositories.get_plan(conn, plan_id) is None:
            raise ValueError(f"Plan '{plan_id}' not found.")
        repositories.set_meta_value(conn, CURRENT_PLAN_META_KEY, plan_id)


def get_current_story_id(plan_id: Optional[str] = None) -> Optional[str]:
    try:
        resolved_plan_id = plan_id or get_current_plan_id()
    except ValueError:
        return None
    with service_uow(
        write=False,
        operation="get_current_story_id",
        plan_id=resolved_plan_id,
    ) as conn:
        return repositories.get_plan_state(conn, resolved_plan_id).current_story_id


def set_current_story_id(
    story_id: Optional[str], plan_id: Optional[str] = None
) -> None:
    if plan_id is None and story_id is None:
        try:
            resolved_plan_id = get_current_plan_id()
        except ValueError:
            return
    else:
        resolved_plan_id = plan_id or get_current_plan_id()
    with service_uow(
        write=True,
        operation="set_current_story_id",
        plan_id=resolved_plan_id,
    ) as conn:
        if (
            story_id is not None
            and repositories.get_story(conn, resolved_plan_id, story_id) is None
        ):
            raise KeyError(f"story with ID '{story_id}' not found.")
        repositories.set_current_story(
            conn,
            plan_id=resolved_plan_id,
            current_story_id=story_id,
        )


def get_current_task_id(plan_id: Optional[str] = None) -> Optional[str]:
    try:
        resolved_plan_id = plan_id or get_current_plan_id()
    except ValueError:
        return None
    with service_uow(
        write=False,
        operation="get_current_task_id",
        plan_id=resolved_plan_id,
    ) as conn:
        return repositories.get_plan_state(conn, resolved_plan_id).current_task_id


def set_current_task_id(task_id: Optional[str], plan_id: Optional[str] = None) -> None:
    if plan_id is None and task_id is None:
        try:
            resolved_plan_id = get_current_plan_id()
        except ValueError:
            return
    else:
        resolved_plan_id = plan_id or get_current_plan_id()
    with service_uow(
        write=True,
        operation="set_current_task_id",
        plan_id=resolved_plan_id,
    ) as conn:
        if task_id is None:
            repositories.set_current_task(
                conn,
                plan_id=resolved_plan_id,
                current_task_story_id=None,
                current_task_local_id=None,
            )
            return
        story_id, local_task_id = resolve_task_id(
            task_id, story_id=None, plan_id=resolved_plan_id, conn=conn
        )
        if (
            repositories.get_task(conn, resolved_plan_id, story_id, local_task_id)
            is None
        ):
            raise KeyError(f"task with ID '{story_id}:{local_task_id}' not found.")
        repositories.set_current_task(
            conn,
            plan_id=resolved_plan_id,
            current_task_story_id=story_id,
            current_task_local_id=local_task_id,
        )


def resolve_task_id(
    task_id: str,
    story_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    conn: Any | None = None,
) -> tuple[str, str]:
    """Resolve a task ID into a (story_id, local_task_id) tuple.

    - If task_id is fully-qualified ('story:task'), it is parsed.
    - If task_id is local, story_id must be provided or available in the current context.
    - Rejects ambiguous inputs and ensures a valid, usable pair is returned.
    """
    if ":" in task_id:
        try:
            parsed_story_id, local_task_id = task_id.split(":", 1)
            if story_id and story_id != parsed_story_id:
                raise ValueError(
                    f"Mismatched story_id: provided '{story_id}' but task has '{parsed_story_id}'."
                )
            return parsed_story_id, local_task_id
        except ValueError as e:
            raise ValueError(
                f"Invalid fully-qualified task ID '{task_id}'. Expected 'story_id:task_id'."
            ) from e
    else:
        # Local ID: require story context
        s_id: str | None
        if story_id:
            s_id = story_id
        elif conn is not None and plan_id is not None:
            s_id = repositories.get_plan_state(conn, plan_id).current_story_id
        else:
            s_id = get_current_story_id(plan_id)
        if not s_id:
            raise ValueError(
                "Cannot use a local task ID without a current story. Call `set_current_story` or provide a fully-qualified ID ('story:task')."
            )
        return s_id, task_id


def parse_status(value: Optional[str | Status]) -> Optional[Status]:
    """Parse a status input string."""
    if value is None:
        return None
    if isinstance(value, Status):
        return value
    token = value.strip().upper()
    if not token:
        return None
    try:
        return Status(token)
    except Exception as e:
        raise ValueError(
            f"Invalid status '{value}'. Allowed: {', '.join([s.value for s in Status])}"
        ) from e


def parse_priority_input(priority: str) -> Optional[int]:
    """Parse a priority input string."""
    if priority == "6":
        return None
    if priority == "":
        raise ValueError("Priority string cannot be empty. Use '6' for no priority.")
    try:
        return int(priority)
    except ValueError as e:
        raise ValueError(
            f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' for no priority."
        ) from e


def parse_csv_list(csv: str) -> list[str]:
    """Parse a CSV list of strings."""
    if not csv:
        return []
    return [t.strip() for t in csv.split(",") if t.strip()]


def find_dependents(plan: Plan, target_id: str) -> list[str]:
    """Return IDs that depend on the target story or task.

    - If target is a story ID (no ':'), returns stories and tasks that list it in depends_on.
    - If target is a task ID (story_id:local_id), returns tasks that list it; also considers
      local references (just local_id) within the same story.
    """
    dependents: list[str] = []
    is_task = ":" in target_id
    target_story_id: Optional[str] = None
    target_local: Optional[str] = None
    if is_task:
        target_story_id, target_local = target_id.split(":", 1)

    # Story dependents: other stories that depend on the story
    if not is_task:
        for s in plan.stories:
            dependents.extend(s.id for dep in (s.depends_on or []) if dep == target_id)

    # Task dependents: tasks depending on the target
    for s in plan.stories:
        for t in s.tasks or []:
            for dep in t.depends_on or []:
                if dep == target_id:
                    dependents.append(t.id)
                    continue
                if is_task and s.id == target_story_id and dep == target_local:
                    dependents.append(t.id)
                if not is_task and dep == target_id:
                    # tasks depending on a story ID
                    dependents.append(t.id)
    return sorted(set(dependents))


def is_unblocked(item: Story | Task, plan: Plan) -> bool:
    """Check if a story or task is unblocked by checking the status of its dependencies."""
    if not item.depends_on:
        return True

    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: t for s in plan.stories for t in (s.tasks or [])}

    for dep_id in item.depends_on:
        # Normalize to fully-qualified ID for lookup if it's a task
        fq_dep_id = (
            f"{getattr(item, 'story_id', '')}:{dep_id}"
            if isinstance(item, Task) and ":" not in dep_id
            else dep_id
        )

        if fq_dep_id in task_index:
            if task_index[fq_dep_id].status != Status.DONE:
                return False
        elif dep_id in story_index:
            if story_index[dep_id].status != Status.DONE:
                return False
        else:
            # Dependency not found, assume it's a blocker
            return False

    return True


def status_to_wire(status: Status) -> Status:
    return status


def datetime_to_wire(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def plan_to_dict(plan: Plan) -> dict[str, Any]:
    payload = plan.model_dump(mode="python", exclude_none=True)
    payload["creation_time"] = datetime_to_wire(plan.creation_time)
    payload["completion_time"] = datetime_to_wire(plan.completion_time)
    return payload


def story_to_dict(story: Story) -> dict[str, Any]:
    payload = story.model_dump(mode="python", exclude_none=True)
    payload["creation_time"] = datetime_to_wire(story.creation_time)
    payload["completion_time"] = datetime_to_wire(story.completion_time)
    return payload


def task_to_dict(task: Task) -> dict[str, Any]:
    payload = task.model_dump(mode="python", exclude_none=True)
    payload["creation_time"] = datetime_to_wire(task.creation_time)
    payload["completion_time"] = datetime_to_wire(task.completion_time)
    return payload
