from typing import List, Optional

from plan_manager.services.task_service import (
    create_task as svc_create_task,
    get_task as svc_get_task,
    update_task as svc_update_task,
    delete_task as svc_delete_task,
    list_tasks as svc_list_tasks,
    submit_for_code_review as svc_submit_for_code_review,
    propose_steps as svc_propose_steps,
)
from plan_manager.schemas.outputs import TaskOut, TaskListItem, OperationResult
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
    mcp_instance.tool()(propose_task_steps)
    mcp_instance.tool()(submit_for_review)


def create_task(story_id: str, title: str, priority: Optional[int] = None, depends_on: Optional[list[str]] = None, description: Optional[str] = None) -> TaskOut:
    """Create a task under a story."""
    try:
        data = svc_create_task(story_id, title,
                               priority, depends_on or [], description)
        return TaskOut(**data)
    except (ValueError, KeyError) as e:
        return TaskOut(id=None, error=str(e))


def get_task(story_id: Optional[str] = None, task_id: Optional[str] = None) -> TaskOut:
    """Fetch a task by ID (local or FQ). Defaults to current task of current story."""
    try:
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
    except (ValueError, KeyError) as e:
        return TaskOut(id=None, error=str(e))


def update_task(story_id: str, task_id: str, title: Optional[str] = None, description: Optional[str] = None, depends_on: Optional[list[str]] = None, priority: Optional[int] = None, status: Optional[str] = None) -> TaskOut:
    """Update mutable fields of a task."""
    try:
        data = svc_update_task(story_id, task_id, title,
                               description, depends_on, priority, status)
        return TaskOut(**data)
    except (ValueError, KeyError) as e:
        return TaskOut(id=None, error=str(e))


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
    """Submits a task for code review, moving it to PENDING_REVIEW status."""
    try:
        data = svc_submit_for_code_review(
            story_id=story_id,
            task_id=task_id,
            summary_text=summary
        )
        return TaskOut(**data)
    except (ValueError, KeyError) as e:
        return TaskOut(id=None, error=str(e))


def propose_task_steps(story_id: str, task_id: str, plan: str) -> TaskOut:
    """Proposes an implementation plan for a task, moving it to a reviewable state."""
    try:
        data = svc_propose_steps(
            story_id=story_id,
            task_id=task_id,
            plan_text=plan
        )
        return TaskOut(**data)
    except (ValueError, KeyError) as e:
        return TaskOut(id=None, error=str(e))
