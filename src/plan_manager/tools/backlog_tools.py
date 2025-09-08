from typing import Optional, List, Dict, Any

from plan_manager.services import backlog_service
from plan_manager.services.backlog_service import NoContextError


def register_backlog_tools(mcp_instance) -> None:
    """Register backlog tools with the MCP instance."""
    mcp_instance.tool()(backlog)

# This is a placeholder. In a real MCP server, this would be registered as a tool.


def backlog(description: Optional[str] = None) -> List[Dict[str, Any]] | Dict[str, Any] | str:
    """
    Contextual command for planning and reviewing work items (Backlog Refinement).

    - If a description is provided, creates a new story in the current plan.
      The first line of the description is used as the title.
    - If no description is provided, reviews the current context:
      - Shows tasks if a story is selected.
      - Shows stories if a plan is selected.
    """
    if description:
        try:
            lines = description.strip().split('\n')
            title = lines[0]
            desc_body = '\n'.join(lines[1:]) if len(lines) > 1 else ""
            return backlog_service.create_story_in_current_plan(title=title, description=desc_body)
        except NoContextError as e:
            # As per the rule "If there is no context, ask the user."
            return f"Error: {e} Please select a plan before creating a story."
        except Exception as e:
            return f"An unexpected error occurred: {e}"
    else:
        try:
            return backlog_service.review_backlog()
        except NoContextError as e:
            return f"Error: {e}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"
