# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""MCP Server for the plan-manager (Streamable HTTP, stateless).

Exposes story, plan, and archive tools over a single MCP endpoint using
Streamable HTTP in stateless mode with JSON responses: each request gets a
fresh transport, no session state is held between requests, and no SSE
streams are opened (no tool relies on server-initiated streaming).
"""

import logging
import uuid

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from plan_manager.config import (
    ALLOWED_HOSTS,
    ALLOWED_ORIGINS,
    ENABLE_BROWSER,
    ENABLE_DNS_REBINDING_PROTECTION,
)
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


class CorrelationIdASGIMiddleware:
    """ASGI middleware adding/propagating x-correlation-id per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-correlation-id")
        corr_id = incoming or str(uuid.uuid4())
        set_correlation_id(corr_id)

        async def send_with_correlation_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                # Reflect header for downstream debugging.
                headers["x-correlation-id"] = corr_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        finally:
            # Clear at end of request.
            set_correlation_id(None)


def _read_quickstart_instructions() -> str:
    """Load Quickstart instructions for InitializeResult from markdown file."""
    return "Plan Manager coordinates AI agents around a plan. See diagrams in resource://plan-manager/project_workflow.md and details in resource://plan-manager/usage_guide_agents.md."


def starlette_app() -> Starlette:
    """Create a Starlette application for the MCP server."""

    logger.info("Initializing FastMCP.")

    # Explicitly configure DNS rebinding protection. FastMCP only auto-enables it
    # for loopback binds and allowlists loopback hosts, which rejects sibling
    # containers connecting via `host.docker.internal` (HTTP 421). See config.py.
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=ENABLE_DNS_REBINDING_PROTECTION,
        allowed_hosts=ALLOWED_HOSTS,
        allowed_origins=ALLOWED_ORIGINS,
    )

    mcp = FastMCP(
        name="Plan Manager",
        instructions=_read_quickstart_instructions(),
        transport_security=transport_security,
        stateless_http=True,
        json_response=True,
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

    async def health_endpoint(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.add_route("/health", health_endpoint, methods=["GET"], name="health")

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

    app.add_middleware(CorrelationIdASGIMiddleware)

    return app
