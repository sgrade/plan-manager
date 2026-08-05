# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

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


def report(plan_id: str, scope: str | None = None) -> ReportOut:
    """Generate a contextual report of a plan state.

    Provides an overview of plans, stories, and tasks based on the specified scope.
    Defaults to story scope if no scope is provided.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        scope: The scope for the report ("plan", "story", or None for default story scope)

    Returns:
        ReportOut: A structured report containing the current state overview
    """
    scope = scope or "story"
    logger.debug("report tool called with plan_id=%r scope=%r", plan_id, scope)
    try:
        report_str = report_service.get_report(plan_id=plan_id, scope=scope)
        return ReportOut(plan_id=plan_id, report=report_str)
    except Exception as e:
        logger.exception("Error generating report")
        # Provide a user-friendly error message
        return ReportOut(
            plan_id=plan_id, report=f"Error: Could not generate report. {e}"
        )
