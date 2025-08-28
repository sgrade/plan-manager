"""MCP Server for the plan-manager (Streamable HTTP).

Exposes story, plan, and archive tools over a single MCP endpoint using
Streamable HTTP. Supports server-initiated streaming via SSE per spec.
"""

import logging
from mcp.server.fastmcp import FastMCP

from starlette.applications import Starlette

from plan_manager.tools.story_tools import register_story_tools
from plan_manager.stories import register_stories_tools
from plan_manager.archive import register_archive_tools
from plan_manager.tools.task_tools import register_task_tools

logger = logging.getLogger(__name__)

def starlette_app() -> Starlette:
    
    logger.info("Initializing FastMCP.")

    mcp = FastMCP(
        name="plan-manager",
            instructions="Manages stories defined in the project's plan."
        )
        
    register_story_tools(mcp)
    register_stories_tools(mcp)
    register_archive_tools(mcp)
    register_task_tools(mcp)

    app = mcp.streamable_http_app()

    return app
