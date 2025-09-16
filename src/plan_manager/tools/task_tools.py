from typing import List, Optional

from plan_manager.services.task_service import (
    create_task as svc_create_task,
    get_task as svc_get_task,
    update_task as svc_update_task,
    delete_task as svc_delete_task,
    list_tasks as svc_list_tasks,
    submit_for_code_review as svc_submit_for_code_review,
    create_steps as svc_create_steps,
)
from plan_manager.schemas.outputs import TaskOut, TaskListItem, OperationResult
from plan_manager.tools.util import coerce_optional_int
from plan_manager.services.state_repository import get_current_story_id, set_current_task_id, get_current_task_id
from plan_manager.domain.models import Status


def register_task_tools(mcp_instance) -> None:
    """Register task tools with the MCP instance."""
    mcp_instance.tool()(list_tasks)
    mcp_instance.tool()(create_task)
    mcp_instance.tool()(get_task)
    mcp_instance.tool()(update_task)
    mcp_instance.tool()(delete_task)
    mcp_instance.tool()(set_current_task)
    mcp_instance.tool()(create_task_steps)
    mcp_instance.tool()(submit_for_review)


def create_task(story_id: str, title: str, priority: Optional[float] = None, depends_on: Optional[list[str]] = None, description: Optional[str] = None) -> TaskOut:
    """Create a task under a story."""
    coerced_priority = coerce_optional_int(priority, 'priority')
    data = svc_create_task(story_id, title,
                           coerced_priority, depends_on or [], description)
    return TaskOut(**data)


def get_task(story_id: Optional[str] = None, task_id: Optional[str] = None) -> TaskOut:
    """Fetch a task by ID (local or FQ). Defaults to current task of current story."""
    story_id = story_id or get_current_story_id()
    if not story_id:
        raise ValueError(
            "No current story set. Call set_current_story or provide story_id.")
    task_id = task_id or get_current_task_id()
    if not task_id:
        raise ValueError(
            "No current task set. Call set_current_task or provide task_id.")
    data = svc_get_task(story_id, task_id)
    return TaskOut(**data)


def update_task(
    story_id: str,
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[float] = None,
    depends_on: Optional[list[str]] = None,
    status: Optional[str] = None,
    steps: Optional[list[dict]] = None
) -> TaskOut:
    """Update mutable fields of a task."""
    # If steps are provided here, forward them via status/utils path by calling create_steps first
    if steps is not None:
        svc_create_steps(story_id=story_id, task_id=task_id, steps=steps)
    coerced_priority = coerce_optional_int(priority, 'priority')
    # Coerce status string to Status enum if provided
    coerced_status = None
    if status is not None:
        if isinstance(status, Status):
            coerced_status = status
        elif isinstance(status, str):
            try:
                coerced_status = Status(status.upper())
            except Exception as e:
                raise ValueError(
                    f"Invalid value for parameter 'status': {status!r}. Allowed: {', '.join([s.value for s in Status])}"
                ) from e
        else:
            raise ValueError(
                f"Invalid type for parameter 'status': expected string or null, got {type(status).__name__}."
            )

    data = svc_update_task(story_id, task_id, title,
                           description, depends_on, coerced_priority, coerced_status)
    return TaskOut(**data)


def delete_task(story_id: str, task_id: str) -> OperationResult:
    """Delete a task by ID (fails if other items depend on it)."""
    try:
        data = svc_delete_task(story_id, task_id)
        return OperationResult(**data)
    except (ValueError, KeyError) as e:
        return OperationResult(success=False, message=str(e))


def list_tasks(statuses: Optional[List[Status]] = None, story_id: Optional[str] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> List[TaskListItem]:
    """List tasks, optionally filtering by statuses and story with pagination."""
    story_id = story_id or get_current_story_id()
    tasks = svc_list_tasks(statuses, story_id)
    items: List[TaskListItem] = []
    for t in tasks:
        items.append(
            TaskListItem(
                id=t.id,
                title=t.title,
                status=t.status,
                priority=t.priority,
                creation_time=t.creation_time.isoformat() if t.creation_time else None,
            )
        )
    start = max(0, offset or 0)
    end = None if limit is None else start + max(0, limit)
    return items[start:end]


def set_current_task(task_id: Optional[str] = None) -> OperationResult | List[TaskListItem]:
    """Set the current task for the current story. If no ID is provided, lists available tasks."""
    if task_id:
        set_current_task_id(task_id)
        return OperationResult(success=True, message=f"Current task set to '{task_id}'")
    return list_tasks()


def submit_for_review(story_id: str, task_id: str, summary: str) -> TaskOut:
    """Submits a task for code review, moving it to PENDING_REVIEW status.

    On success, clients SHOULD immediately surface the returned execution_summary
    to the user for review and present clear next actions:
    - approve_task (accept and finish), or
    - request_changes(feedback) (reopen; revise, then submit_for_review again)
    """
    data = svc_submit_for_code_review(
        story_id=story_id,
        task_id=task_id,
        summary_text=summary
    )
    return TaskOut(**data)


def create_task_steps(story_id: str, task_id: str, steps: List[dict]) -> TaskOut:
    """Proposes implementation steps for a task, moving it to a reviewable state.

    Expects a list of step objects with 'title' and optional 'description'.
    """
    data = svc_create_steps(
        story_id=story_id, task_id=task_id, steps=steps)
    return TaskOut(**data)
