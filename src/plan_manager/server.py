"""MCP Server for the plan-manager (Streamable HTTP).

Exposes story, plan, and archive tools over a single MCP endpoint using
Streamable HTTP. Supports server-initiated streaming via SSE per spec.
"""

import logging
from mcp.server.fastmcp import FastMCP

from starlette.applications import Starlette

from plan_manager.tools.story_tools import register_story_tools
from plan_manager.tools.task_tools import register_task_tools
from plan_manager.tools.plan_tools import register_plan_tools
from plan_manager.tools.context_tools import register_context_tools
from plan_manager.tools.changelog_tools import register_changelog_tools
from plan_manager.tools.approval_tools import register_approval_tools
from plan_manager.tools.report_tools import register_report_tools
from plan_manager.prompts.workflow_prompts import register_workflow_prompts
from plan_manager.prompts.propose_prompts import register_propose_prompts

logger = logging.getLogger(__name__)


def starlette_app() -> Starlette:
    """Create a Starlette application for the MCP server."""

    logger.info("Initializing FastMCP.")

    mcp = FastMCP(
        name="Plan Manager",
        instructions="Manages stories defined in the project's plan.",
    )

    register_context_tools(mcp)
    register_plan_tools(mcp)
    register_story_tools(mcp)
    register_task_tools(mcp)
    register_approval_tools(mcp)
    register_report_tools(mcp)
    register_changelog_tools(mcp)
    register_workflow_prompts(mcp)
    register_propose_prompts(mcp)

    app = mcp.streamable_http_app()

    return app
