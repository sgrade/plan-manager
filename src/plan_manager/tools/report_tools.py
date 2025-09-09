from plan_manager.services import report_service


def register_report_tools(mcp_instance) -> None:
    """Register report tools with the MCP instance."""
    mcp_instance.tool()(report)

# This is a placeholder. In a real MCP server, this would be registered as a tool.


def report(payload: None = None) -> str:
    """
    Provides a dynamic, contextual overview of the current state.
    The output changes based on the report of the current task.
    """
    try:
        return report_service.get_report()
    except Exception as e:
        # Log the full exception for debugging
        # logger.exception("An unexpected error occurred while generating the report.")
        return f"An unexpected error occurred while generating the report: {e}"
