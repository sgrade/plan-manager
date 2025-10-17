"""MCP Server for the plan-manager (Streamable HTTP).

Exposes story, plan, and archive tools over a single MCP endpoint using
Streamable HTTP. Supports server-initiated streaming via SSE per spec.
"""

import logging
import uuid
from typing import TYPE_CHECKING

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

from plan_manager.config import ENABLE_BROWSER
from plan_manager.logging_context import set_correlation_id
from plan_manager.prompts.prompt_register import register_prompts
from plan_manager.resources.usage_resources import register_usage_resources
from plan_manager.server.browser import browse_endpoint
from plan_manager.tools.changelog_tools import register_changelog_tools
from plan_manager.tools.context_tools import register_context_tools
from plan_manager.tools.plan_tools import register_plan_tools
from plan_manager.tools.report_tools import register_report_tools
from plan_manager.tools.story_tools import register_story_tools
from plan_manager.tools.task_tools import register_task_tools

logger = logging.getLogger(__name__)


def _read_quickstart_instructions() -> str:
    """Load Quickstart instructions for InitializeResult from markdown file."""
    return "Plan Manager coordinates AI agents around a plan. See diagrams in resource://plan-manager/project_workflow.md and details in resource://plan-manager/usage_guide_agents.md."


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
    register_report_tools(mcp)
    register_changelog_tools(mcp)
    register_prompts(mcp)
    register_usage_resources(mcp)

    app = mcp.streamable_http_app()

    # Add routes for the file browser if enabled
    if ENABLE_BROWSER:
        # Add this to starlette_app() function before returning app
        app.add_route(
            "/",
            lambda _: RedirectResponse(url="/browse/"),
            name="browse_redirect",
        )
        app.add_route(
            "/browse",
            lambda _: RedirectResponse(url="/browse/"),
            name="browse_redirect",
        )
        app.add_route("/browse/", browse_endpoint, name="browse_root")
        app.add_route("/browse/{path:path}", browse_endpoint, name="browse")

    class CorrelationIdMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
        async def dispatch(
            self,
            request: Request,
            call_next: "Callable[[Request], Awaitable[Response]]",
        ) -> Response:
            try:
                incoming = request.headers.get("x-correlation-id")
                corr_id = incoming or str(uuid.uuid4())
                set_correlation_id(corr_id)
                response = await call_next(request)
                # reflect header for downstream debugging
                response.headers["x-correlation-id"] = corr_id
                return response
            finally:
                # Clear at end of request
                set_correlation_id(None)

    app.add_middleware(CorrelationIdMiddleware)

    return app
