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
    - IN_PROGRESS if any task is IN_PROGRESS
    - TODO otherwise (BLOCKED/DEFERRED are not rolled up here)

    Args:
        task_statuses: List of task statuses to roll up

    Returns:
        Status: The derived story status
    """
    values = [s.value if isinstance(s, Status) else s for s in task_statuses]
    if not values:
        return Status.TODO
    if all(v == "DONE" for v in values):
        return Status.DONE
    if any(v == "IN_PROGRESS" for v in values):
        return Status.IN_PROGRESS
    return Status.TODO


def rollup_plan_status(story_statuses: list[Status | str]) -> Status:
    """Derive a plan status from its story statuses.

    Uses the same logic as rollup_story_status:
    - DONE if all stories are DONE
    - IN_PROGRESS if any story is IN_PROGRESS
    - TODO otherwise

    Args:
        story_statuses: List of story statuses to roll up

    Returns:
        Status: The derived plan status
    """
    values = [s.value if isinstance(s, Status) else s for s in story_statuses]
    if not values:
        return Status.TODO
    if all(v == "DONE" for v in values):
        return Status.DONE
    if any(v == "IN_PROGRESS" for v in values):
        return Status.IN_PROGRESS
    return Status.TODO
