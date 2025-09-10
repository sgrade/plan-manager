from typing import List, Optional

from plan_manager.services.task_service import (
    create_task as svc_create_task,
    get_task as svc_get_task,
    update_task as svc_update_task,
    delete_task as svc_delete_task,
    list_tasks as svc_list_tasks,
    explain_task_blockers as svc_explain_task_blockers,
    submit_for_code_review as svc_submit_for_code_review,
    propose_steps as svc_propose_steps,
)
from plan_manager.schemas.inputs import (
    ListTasksIn,
    CreateTaskIn, GetTaskIn, UpdateTaskIn, DeleteTaskIn,
    SetCurrentTaskIn,
    ExplainTaskBlockersIn,
    SubmitForReviewIn,
    ProposeStepsIn,
)
from plan_manager.schemas.outputs import TaskOut, TaskListItem, OperationResult, TaskBlockersOut
from plan_manager.services.state_repository import get_current_story_id, set_current_task_id, get_current_task_id


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
    mcp_instance.tool()(explain_task_blockers)


def create_task(payload: CreateTaskIn) -> TaskOut:
    """Create a task under a story."""
    data = svc_create_task(payload.story_id, payload.title,
                           payload.priority, payload.depends_on, payload.description)
    return TaskOut(**data)


def get_task(payload: Optional[GetTaskIn] = None) -> TaskOut:
    """Fetch a task by ID (local or FQ). Defaults to current task of current story."""
    if payload:
        story_id = payload.story_id
        task_id = payload.task_id
    else:
        story_id = get_current_story_id()
        if not story_id:
            raise ValueError(
                "No current story set. Call set_current_story or provide story_id.")
        task_id = get_current_task_id()
        if not task_id:
            raise ValueError(
                "No current task set. Call set_current_task or provide task_id.")
    data = svc_get_task(story_id, task_id)
    return TaskOut(**data)


def update_task(payload: UpdateTaskIn) -> TaskOut:
    """Update mutable fields of a task."""
    data = svc_update_task(payload.story_id, payload.task_id, payload.title,
                           payload.description, payload.depends_on, payload.priority, payload.status)
    return TaskOut(**data)


def delete_task(payload: DeleteTaskIn) -> OperationResult:
    """Delete a task by ID (fails if other items depend on it)."""
    data = svc_delete_task(payload.story_id, payload.task_id)
    return OperationResult(**data)


def list_tasks(payload: Optional[ListTasksIn] = None) -> List[TaskListItem]:
    """List tasks, optionally filtering by status set and story."""
    statuses = payload.statuses if payload else None
    story_id = payload.story_id if payload else get_current_story_id()
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
    if payload:
        start = max(0, payload.offset or 0)
        end = None if payload.limit is None else start + max(0, payload.limit)
        return items[start:end]
    return items


def explain_task_blockers(payload: ExplainTaskBlockersIn) -> TaskBlockersOut:
    """Explain why a task is blocked based on its dependencies."""
    data = svc_explain_task_blockers(payload.story_id, payload.task_id)
    return TaskBlockersOut(**data)


def set_current_task(payload: SetCurrentTaskIn) -> OperationResult:
    """Set the current task for the current story."""
    set_current_task_id(payload.task_id)
    return OperationResult(success=True, message=f"Current task set to '{payload.task_id}'")


def submit_for_review(payload: SubmitForReviewIn) -> TaskOut:
    """Submits a task for code review, moving it to PENDING_REVIEW status."""
    data = svc_submit_for_code_review(
        story_id=payload.story_id,
        task_id=payload.task_id,
        summary_text=payload.summary
    )
    return TaskOut(**data)


def propose_task_steps(payload: ProposeStepsIn) -> TaskOut:
    """Proposes an implementation plan for a task, moving it to a reviewable state."""
    data = svc_propose_steps(
        story_id=payload.story_id,
        task_id=payload.task_id,
        plan_text=payload.plan
    )
    return TaskOut(**data)
