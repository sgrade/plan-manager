"""MCP Server for the plan-manager (Streamable HTTP).

Exposes story, plan, and archive tools over a single MCP endpoint using
Streamable HTTP. Supports server-initiated streaming via SSE per spec.
"""

import logging
from plan_manager.io.files import read_markdown
from plan_manager.config import QUICKSTART_REL_PATH
from mcp.server.fastmcp import FastMCP

from starlette.applications import Starlette

from plan_manager.tools.story_tools import register_story_tools
from plan_manager.tools.task_tools import register_task_tools
from plan_manager.tools.plan_tools import register_plan_tools
from plan_manager.tools.context_tools import register_context_tools
from plan_manager.tools.changelog_tools import register_changelog_tools
from plan_manager.tools.approval_tools import register_approval_tools
from plan_manager.tools.report_tools import register_report_tools
from plan_manager.prompts.prompt_register import register_prompts
from plan_manager.resources.usage_resources import register_usage_resources

logger = logging.getLogger(__name__)


def _read_quickstart_instructions() -> str:
    """Load Quickstart instructions for InitializeResult from markdown file."""
    try:
        return read_markdown(QUICKSTART_REL_PATH)
    except Exception:
        return "Plan Manager: Quickstart not found. See resource://plan-manager/usage_guide_agents.md or project docs."


def starlette_app() -> Starlette:
    """Create a Starlette application for the MCP server."""

    logger.info("Initializing FastMCP.")

    mcp = FastMCP(
        name="Plan Manager",
        instructions=_read_quickstart_instructions(),
    )

    register_context_tools(mcp)
    register_plan_tools(mcp)
    register_story_tools(mcp)
    register_task_tools(mcp)
    register_approval_tools(mcp)
    register_report_tools(mcp)
    register_changelog_tools(mcp)
    register_prompts(mcp)
    register_usage_resources(mcp)

    app = mcp.streamable_http_app()

    return app
