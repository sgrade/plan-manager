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
    """Get the current context of the current plan: plan_id, current_story_id, current_task_id.

    Answers the question "Where am I?"
    """
    pid = get_current_plan_id()
    return CurrentContextOut(
        plan_id=pid,
        current_story_id=get_current_story_id(pid),
        current_task_id=get_current_task_id(pid),
    )
