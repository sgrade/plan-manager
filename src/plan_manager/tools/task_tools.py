from typing import List

from plan_manager.services.task_service import (
    create_task as svc_create_task,
    get_task as svc_get_task,
    update_task as svc_update_task,
    delete_task as svc_delete_task,
    list_tasks as svc_list_tasks,
    explain_task_blockers as svc_explain_task_blockers,
)
from plan_manager.schemas.inputs import (
    CreateTaskIn, GetTaskIn, UpdateTaskIn, DeleteTaskIn, ListTasksIn, ExplainTaskBlockersIn,
)
from plan_manager.schemas.outputs import TaskOut, TaskListItem, OperationResult, TaskBlockersOut


def register_task_tools(mcp_instance) -> None:
    mcp_instance.tool()(create_task)
    mcp_instance.tool()(get_task)
    mcp_instance.tool()(update_task)
    mcp_instance.tool()(delete_task)
    mcp_instance.tool()(list_tasks)
    mcp_instance.tool()(explain_task_blockers)


def create_task(payload: CreateTaskIn) -> TaskOut:
    """Create a task under a story."""
    data = svc_create_task(payload.story_id, payload.title,
                           payload.priority, payload.depends_on, payload.notes)
    return TaskOut(**data)


def get_task(payload: GetTaskIn) -> TaskOut:
    """Fetch a task by ID (local or FQ) within a story."""
    data = svc_get_task(payload.story_id, payload.task_id)
    return TaskOut(**data)


def update_task(payload: UpdateTaskIn) -> TaskOut:
    """Update mutable fields of a task."""
    data = svc_update_task(payload.story_id, payload.task_id, payload.title,
                           payload.notes, payload.depends_on, payload.priority, payload.status)
    return TaskOut(**data)


def delete_task(payload: DeleteTaskIn) -> OperationResult:
    """Delete a task by ID (fails if other items depend on it)."""
    data = svc_delete_task(payload.story_id, payload.task_id)
    return OperationResult(**data)


def list_tasks(payload: ListTasksIn) -> List[TaskListItem]:
    """List tasks, optionally filtering by status set and story."""
    tasks = svc_list_tasks(payload.statuses, payload.story_id)
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
    return items


def explain_task_blockers(payload: ExplainTaskBlockersIn) -> TaskBlockersOut:
    """Explain why a task is blocked based on its dependencies."""
    data = svc_explain_task_blockers(payload.story_id, payload.task_id)
    return TaskBlockersOut(**data)
