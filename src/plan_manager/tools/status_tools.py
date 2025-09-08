from plan_manager.services import status_service


def register_status_tools(mcp_instance) -> None:
    """Register status tools with the MCP instance."""
    mcp_instance.tool()(status)

# This is a placeholder. In a real MCP server, this would be registered as a tool.


def status(payload: None = None) -> str:
    """
    Provides a dynamic, contextual overview of the current state.
    The output changes based on the status of the current task.
    """
    try:
        return status_service.get_status_report()
    except Exception as e:
        # Log the full exception for debugging
        # logger.exception("An unexpected error occurred while generating the status report.")
        return f"An unexpected error occurred while generating the status report: {e}"
