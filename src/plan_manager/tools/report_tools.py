from plan_manager.services import report_service
from plan_manager.schemas.outputs import ReportOut
from plan_manager.schemas.inputs import ReportIn
import logging

logger = logging.getLogger(__name__)


def register_report_tools(mcp_instance) -> None:
    """Register report tools with the MCP instance."""
    mcp_instance.tool()(report)

# This is a placeholder. In a real MCP server, this would be registered as a tool.


def report(payload: ReportIn | None = None) -> ReportOut:
    """
    Provides a dynamic, contextual overview of the current state.
    The output changes based on the report of the current task.
    """
    scope = payload.scope if payload else "story"
    logger.debug(f"report tool called with scope: {scope!r}")
    try:
        report_str = report_service.get_report(scope=scope)
        return ReportOut(report=report_str)
    except Exception as e:
        logger.exception("Error generating report")
        # Provide a user-friendly error message
        return ReportOut(report=f"Error: Could not generate report. {e}")
