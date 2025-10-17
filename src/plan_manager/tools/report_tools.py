import logging
from typing import TYPE_CHECKING

from plan_manager.schemas.outputs import ReportOut
from plan_manager.services import report_service

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_report_tools(mcp_instance: "FastMCP") -> None:
    """Register report tools with the MCP instance."""
    mcp_instance.tool()(report)


# This is a placeholder. In a real MCP server, this would be registered as a tool.


def report(scope: str | None = None) -> ReportOut:
    """Generate a contextual report of the current plan state.

    Provides an overview of plans, stories, and tasks based on the specified scope.
    Defaults to story scope if no scope is provided.

    Args:
        scope: The scope for the report ("plan", "story", or None for default story scope)

    Returns:
        ReportOut: A structured report containing the current state overview
    """
    scope = scope or "story"
    logger.debug(f"report tool called with scope: {scope!r}")
    try:
        report_str = report_service.get_report(scope=scope)
        return ReportOut(report=report_str)
    except Exception as e:
        logger.exception("Error generating report")
        # Provide a user-friendly error message
        return ReportOut(report=f"Error: Could not generate report. {e}")
