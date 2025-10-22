from datetime import datetime, timezone
from typing import Protocol

from plan_manager.domain.models import Status


class HasStatus(Protocol):
    """Protocol for models that expose a status and completion_time."""

    status: Status
    completion_time: datetime | None


def apply_status_change(item: HasStatus, new_status: Status) -> None:
    """Apply a status change and update completion_time accordingly.

    Args:
        item: The item whose status is being changed
        new_status: The new status to apply
    """
    old = item.status.value if isinstance(item.status, Status) else item.status
    item.status = new_status
    if new_status == Status.DONE and old != Status.DONE.value:
        item.completion_time = datetime.now(timezone.utc)
    elif new_status != Status.DONE and old == Status.DONE.value:
        item.completion_time = None


def rollup_story_status(task_statuses: list[Status | str]) -> Status:
    """Derive a story status from its task statuses.

    Logic:
    - DONE if all tasks are DONE
    - IN_PROGRESS if any task is IN_PROGRESS, PENDING_REVIEW, or if there's a mix of DONE and TODO
    - TODO if all tasks are TODO (or BLOCKED/DEFERRED)

    This ensures that a story shows as IN_PROGRESS when work has started but isn't complete,
    even if no task is currently actively being worked on.

    Args:
        task_statuses: List of task statuses to roll up

    Returns:
        Status: The derived story status
    """
    values = [s.value if isinstance(s, Status) else s for s in task_statuses]
    if not values:
        return Status.TODO

    # All done → story is done
    if all(v == "DONE" for v in values):
        return Status.DONE

    # Any active work → story is in progress
    if any(v in ("IN_PROGRESS", "PENDING_REVIEW") for v in values):
        return Status.IN_PROGRESS

    # Mix of DONE and not-started → story is in progress (work has been done)
    has_done = any(v == "DONE" for v in values)
    has_not_started = any(v in ("TODO", "BLOCKED", "DEFERRED") for v in values)
    if has_done and has_not_started:
        return Status.IN_PROGRESS

    # All tasks are TODO/BLOCKED/DEFERRED → story is todo
    return Status.TODO


def rollup_plan_status(story_statuses: list[Status | str]) -> Status:
    """Derive a plan status from its story statuses.

    Uses the same logic as rollup_story_status:
    - DONE if all stories are DONE
    - IN_PROGRESS if any story is IN_PROGRESS, PENDING_REVIEW, or if there's a mix of DONE and TODO
    - TODO if all stories are TODO (or BLOCKED/DEFERRED)

    Args:
        story_statuses: List of story statuses to roll up

    Returns:
        Status: The derived plan status
    """
    values = [s.value if isinstance(s, Status) else s for s in story_statuses]
    if not values:
        return Status.TODO

    # All done → plan is done
    if all(v == "DONE" for v in values):
        return Status.DONE

    # Any active work → plan is in progress
    if any(v in ("IN_PROGRESS", "PENDING_REVIEW") for v in values):
        return Status.IN_PROGRESS

    # Mix of DONE and not-started → plan is in progress (work has been done)
    has_done = any(v == "DONE" for v in values)
    has_not_started = any(v in ("TODO", "BLOCKED", "DEFERRED") for v in values)
    if has_done and has_not_started:
        return Status.IN_PROGRESS

    # All stories are TODO/BLOCKED/DEFERRED → plan is todo
    return Status.TODO
