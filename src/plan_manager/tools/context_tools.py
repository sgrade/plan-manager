from typing import Optional

from plan_manager.schemas.outputs import CurrentContextOut, TaskOut, StoryOut, OperationResult
from plan_manager.services.plan_repository import get_current_plan_id
from plan_manager.services.state_repository import (
    get_current_story_id,
    set_current_story_id,
    get_current_task_id,
    set_current_task_id,
)
from plan_manager.services import plan_repository as plan_repo
from plan_manager.services.story_service import get_story as svc_get_story
from plan_manager.services.task_service import get_task as svc_get_task, list_tasks as svc_list_tasks
from plan_manager.domain.models import Status


def register_context_tools(mcp_instance) -> None:
    """Register context tools with the MCP instance."""
    mcp_instance.tool()(current_context)
    mcp_instance.tool()(select_first_story)
    mcp_instance.tool()(select_first_unblocked_task)
    mcp_instance.tool()(advance_to_next_task)


def current_context() -> CurrentContextOut:
    """Get the current context of the current plan."""
    pid = get_current_plan_id()
    return CurrentContextOut(
        plan_id=pid,
        current_story_id=get_current_story_id(pid),
        current_task_id=get_current_task_id(pid),
    )


def select_first_story() -> StoryOut:
    """Select the first story in the current plan."""
    plan = plan_repo.load_current()
    if not plan.stories:
        raise ValueError("No stories in current plan. Create a story first.")
    first = plan.stories[0]
    set_current_story_id(first.id, plan.id)
    return StoryOut(**first.model_dump(mode='json', exclude_none=True))


def select_first_unblocked_task() -> TaskOut:
    """Select the first unblocked task in the current story."""
    pid = get_current_plan_id()
    sid = get_current_story_id(pid)
    if not sid:
        raise ValueError(
            "No current story set. Call select_first_story or set_current_story.")
    tasks = svc_list_tasks(statuses=None, story_id=sid)
    for t in tasks:
        if t.status in (Status.TODO, Status.IN_PROGRESS):
            set_current_task_id(t.id, pid)
            return TaskOut(**t.model_dump(mode='json', exclude_none=True))
    raise ValueError("No unblocked tasks found in current story.")


def advance_to_next_task() -> TaskOut:
    """Advance to the next task in the current story."""
    pid = get_current_plan_id()
    sid = get_current_story_id(pid)
    if not sid:
        raise ValueError(
            "No current story set. Call select_first_story or set_current_story.")
    current_tid = get_current_task_id(pid)
    tasks = svc_list_tasks(statuses=None, story_id=sid)
    if not tasks:
        raise ValueError("Current story has no tasks.")
    # Find current index
    idx = -1
    if current_tid:
        for i, t in enumerate(tasks):
            if t.id == current_tid:
                idx = i
                break
    next_i = 0 if idx == -1 else (idx + 1)
    if next_i >= len(tasks):
        raise ValueError("Already at last task; no next task to advance to.")
    nxt = tasks[next_i]
    set_current_task_id(nxt.id, pid)
    return TaskOut(**nxt.model_dump(mode='json', exclude_none=True))
