from plan_manager.schemas.outputs import (
    CurrentContextOut,
)
from plan_manager.services.plan_repository import get_current_plan_id
from plan_manager.services.state_repository import (
    get_current_story_id,
    get_current_task_id,
)


def register_context_tools(mcp_instance) -> None:
    """Register context tools with the MCP instance."""
    mcp_instance.tool()(get_current)


def get_current() -> CurrentContextOut:
    """Get the current context including plan, story, and task IDs.

    Returns the current plan ID, current story ID (if any), and current task ID (if any).
    This helps answer "Where am I?" in the plan hierarchy.

    Returns:
        CurrentContextOut: The current context with plan_id, current_story_id, and current_task_id
    """
    pid = get_current_plan_id()
    return CurrentContextOut(
        plan_id=pid,
        current_story_id=get_current_story_id(pid),
        current_task_id=get_current_task_id(pid),
    )
