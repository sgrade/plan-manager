from datetime import datetime, timezone
from typing import Protocol

from plan_manager.domain import Status


class HasStatus(Protocol):
    """Protocol for models that expose a status and completion_time."""
    status: Status
    completion_time: datetime | None


def apply_status_change(item: HasStatus, new_status: Status) -> None:
    """Apply a status change and update completion_time accordingly."""
    old = item.status.value if isinstance(item.status, Status) else item.status
    item.status = new_status
    if new_status == Status.DONE and old != Status.DONE.value:
        item.completion_time = datetime.now(timezone.utc)
    elif new_status != Status.DONE and old == Status.DONE.value:
        item.completion_time = None


def rollup_story_status(task_statuses: list[Status | str]) -> Status:
    """Derive a story status from its task statuses.

    DONE if all tasks DONE;
    IN_PROGRESS if any task IN_PROGRESS;
    otherwise TODO (BLOCKED/DEFERRED are not rolled-up here).
    """
    values = [s.value if isinstance(s, Status) else s for s in task_statuses]
    if not values:
        return Status.TODO
    if all(v == 'DONE' for v in values):
        return Status.DONE
    if any(v == 'IN_PROGRESS' for v in values):
        return Status.IN_PROGRESS
    return Status.TODO


