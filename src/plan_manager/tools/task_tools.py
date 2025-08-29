from typing import Optional
from plan_manager.services.task_service import (
    create_task as svc_create_task,
    get_task as svc_get_task,
    update_task as svc_update_task,
    delete_task as svc_delete_task,
    list_tasks as svc_list_tasks,
    explain_task_blockers as svc_explain_task_blockers,
)


def register_task_tools(mcp_instance) -> None:
    mcp_instance.tool()(create_task)
    mcp_instance.tool()(get_task)
    mcp_instance.tool()(update_task)
    mcp_instance.tool()(delete_task)
    mcp_instance.tool()(list_tasks)
    mcp_instance.tool()(explain_task_blockers)


def create_task(story_id: str, title: str, priority: str, depends_on: str, notes: str) -> dict:
    return svc_create_task(story_id, title, priority, depends_on, notes)


def get_task(story_id: str, task_id: str) -> dict:
    return svc_get_task(story_id, task_id)


def update_task(
    story_id: str,
    task_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    depends_on: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    return svc_update_task(story_id, task_id, title, notes, depends_on, priority, status)


def delete_task(story_id: str, task_id: str) -> dict:
    return svc_delete_task(story_id, task_id)


def list_tasks(statuses: str, story_id: Optional[str] = None) -> list[dict]:
    return svc_list_tasks(statuses, story_id)


def explain_task_blockers(story_id: str, task_id: str) -> dict:
    return svc_explain_task_blockers(story_id, task_id)
