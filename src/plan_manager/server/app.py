# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""MCP Server for the plan-manager (Streamable HTTP, stateless).

Exposes story, plan, and archive tools over a single MCP endpoint using
Streamable HTTP in stateless mode with JSON responses: each request gets a
fresh transport, no session state is held between requests, and no SSE
streams are opened (no tool relies on server-initiated streaming).
"""

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from jinja2 import (  # type: ignore[import-not-found]
    Environment,
    FileSystemLoader,
    select_autoescape,
)
from markdown_it import MarkdownIt  # type: ignore[import-not-found]
from markupsafe import Markup  # type: ignore[import-not-found]
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from plan_manager.config import (
    ALLOWED_HOSTS,
    ALLOWED_ORIGINS,
    ENABLE_DNS_REBINDING_PROTECTION,
    PLAN_MANAGER_ENABLE_UI,
)
from plan_manager.logging_context import set_correlation_id
from plan_manager.prompts.prompt_register import register_prompts
from plan_manager.resources.usage_resources import register_usage_resources
from plan_manager.services.shared import service_uow
from plan_manager.storage import repositories
from plan_manager.tools.changelog_tools import register_changelog_tools
from plan_manager.tools.context_tools import register_context_tools
from plan_manager.tools.plan_tools import register_plan_tools
from plan_manager.tools.report_tools import register_report_tools
from plan_manager.tools.story_tools import register_story_tools
from plan_manager.tools.task_tools import register_task_tools

logger = logging.getLogger(__name__)
CORRELATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
UI_CSP = "default-src 'none'; style-src 'self'"
_MARKDOWN = MarkdownIt("commonmark", {"html": False})

_ALLOWED_LINK_SCHEMES = ("http://", "https://", "mailto:")


def _validate_link(url: str) -> bool:
    """Allowlist link schemes (defense in depth beyond CSP).

    markdown-it can emit entity-obfuscated schemes (e.g. jav&#x09;ascript:)
    as live hrefs (U8 review, finding L-1); relative links stay allowed.
    """
    lowered = url.strip().lower()
    if ":" not in lowered.split("/", 1)[0] and not lowered.startswith("//"):
        return True  # relative link, no scheme
    return lowered.startswith(_ALLOWED_LINK_SCHEMES)


_MARKDOWN.validateLink = _validate_link


class CorrelationIdASGIMiddleware:
    """ASGI middleware adding/propagating x-correlation-id per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-correlation-id")
        corr_id = (
            incoming
            if incoming is not None and CORRELATION_ID_PATTERN.fullmatch(incoming)
            else str(uuid.uuid4())
        )
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


class UiSecurityHeadersMiddleware:
    """Apply strict headers to all /ui responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        async def send_with_ui_headers(message: Message) -> None:
            if message["type"] == "http.response.start" and path.startswith("/ui"):
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = UI_CSP
                headers["X-Content-Type-Options"] = "nosniff"
            await send(message)

        await self.app(scope, receive, send_with_ui_headers)


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
    server_dir = Path(__file__).resolve().parent
    templates = Jinja2Templates(
        env=Environment(
            loader=FileSystemLoader(str(server_dir / "templates")),
            autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        )
    )

    def _render_markdown(text: str) -> Markup:
        # markdown-it-py renders with raw HTML disabled (`html=False`).
        return Markup(_MARKDOWN.render(text))  # noqa: S704

    def _render_not_found(
        request: Request,
        *,
        entity: str,
        identifier: str,
    ) -> Response:
        return templates.TemplateResponse(
            request=request,
            name="ui/not_found.html",
            context={"entity": entity, "identifier": identifier},
            status_code=404,
        )

    def _ensure_ui_enabled() -> None:
        if not PLAN_MANAGER_ENABLE_UI:
            raise HTTPException(status_code=404, detail="Not Found")

    async def health_endpoint(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    app.add_route("/health", health_endpoint, methods=["GET"], name="health")
    app.add_route(
        "/",
        lambda _: RedirectResponse(url="/ui"),
        methods=["GET"],
        name="root_to_ui",
    )

    async def ui_index(request: Request) -> Response:
        _ensure_ui_enabled()
        with service_uow(write=False, operation="ui_list_plans") as conn:
            plans = repositories.list_plans(conn)
        return templates.TemplateResponse(
            request=request,
            name="ui/plans.html",
            context={"plans": plans},
        )

    async def ui_plan(request: Request) -> Response:
        _ensure_ui_enabled()
        plan_id = request.path_params["plan_id"]
        with service_uow(
            write=False,
            operation="ui_plan_overview",
            plan_id=plan_id,
        ) as conn:
            plan = repositories.get_plan(conn, plan_id)
            if plan is None:
                return _render_not_found(request, entity="Plan", identifier=plan_id)
            stories = repositories.list_stories(conn, plan_id)
            state = repositories.get_plan_state(conn, plan_id)
            events = repositories.list_events(conn, plan_id)
        recent_events = list(reversed(events[-50:]))
        return templates.TemplateResponse(
            request=request,
            name="ui/plan_detail.html",
            context={
                "plan": plan,
                "stories": stories,
                "state": state,
                "events": recent_events,
            },
        )

    async def ui_story(request: Request) -> Response:
        _ensure_ui_enabled()
        plan_id = request.path_params["plan_id"]
        story_id = request.path_params["story_id"]
        with service_uow(
            write=False,
            operation="ui_story_tasks",
            plan_id=plan_id,
        ) as conn:
            plan = repositories.get_plan(conn, plan_id)
            if plan is None:
                return _render_not_found(request, entity="Plan", identifier=plan_id)
            story = repositories.get_story(conn, plan_id, story_id)
            if story is None:
                return _render_not_found(request, entity="Story", identifier=story_id)
            story_body_row = conn.execute(
                "SELECT body FROM stories WHERE plan_id = ? AND id = ?",
                (plan_id, story_id),
            ).fetchone()
            task_rows = conn.execute(
                "SELECT local_id, title, status, priority, description, body "
                "FROM tasks WHERE plan_id = ? AND story_id = ? ORDER BY ord, local_id",
                (plan_id, story_id),
            ).fetchall()

        story_body = ""
        if story_body_row is not None and story_body_row["body"] is not None:
            story_body = str(story_body_row["body"])
        rendered_tasks: list[dict[str, Any]] = []
        for row in task_rows:
            body = str(row["body"]) if row["body"] is not None else ""
            rendered_tasks.append(
                {
                    "id": f"{story_id}:{row['local_id']}",
                    "title": str(row["title"]),
                    "status": str(row["status"]),
                    "priority": row["priority"],
                    "description": row["description"],
                    "body_html": _render_markdown(body),
                }
            )

        return templates.TemplateResponse(
            request=request,
            name="ui/story_detail.html",
            context={
                "plan": plan,
                "story": story,
                "story_body_html": _render_markdown(story_body),
                "tasks": rendered_tasks,
            },
        )

    if PLAN_MANAGER_ENABLE_UI:
        app.mount(
            "/ui/static",
            StaticFiles(directory=str(server_dir / "static")),
            name="ui_static",
        )

    app.add_route("/ui", ui_index, methods=["GET"], name="ui_plans")
    app.add_route("/ui/{plan_id}", ui_plan, methods=["GET"], name="ui_plan")
    app.add_route(
        "/ui/{plan_id}/{story_id}",
        ui_story,
        methods=["GET"],
        name="ui_story",
    )

    app.add_middleware(UiSecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdASGIMiddleware)

    return app
