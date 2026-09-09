# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from plan_manager.config import (
    PROJECT_WORKFLOW_OVERRIDE_PATH,
    PROJECT_WORKFLOW_REL_PATH,
    USAGE_GUIDE_OVERRIDE_PATH,
    USAGE_GUIDE_REL_PATH,
)
from plan_manager.identity import build_identity_json
from plan_manager.io.files import read_markdown

logger = logging.getLogger(__name__)


def _degraded_guide(title: str, env_name: str) -> str:
    return (
        f"# Plan Manager — {title}\n\n"
        f"Guide content is unavailable. Check or unset {env_name} "
        "and restart Plan Manager.\n"
    )


def _read_guide(
    *,
    filename: str,
    development_path: str,
    override_path: str | None,
    env_name: str,
    title: str,
) -> str:
    try:
        if override_path is not None:
            return read_markdown(override_path)
        try:
            return (
                files("plan_manager")
                .joinpath("docs", filename)
                .read_text(encoding="utf-8")
            )
        except (FileNotFoundError, OSError):
            return read_markdown(development_path)
    except (FileNotFoundError, OSError) as exc:
        logger.warning("%s guide content is unavailable: %s", filename, exc)
        return _degraded_guide(title, env_name)


def register_usage_resources(mcp_instance: "FastMCP") -> None:
    """Register the extended usage guide as an MCP resource.

    The content is loaded from docs/usage_guide_agents.md so it can be edited easily.
    """

    @mcp_instance.resource(
        uri="resource://plan-manager/usage_guide_agents.md",
        name="usage_guide_agents.md",
        title="Plan Manager Usage Guide for Agents",
        description="Extended usage guide for agents using the Plan Manager MCP server.",
        mime_type="text/markdown",
    )
    def usage_guide_resource() -> str:
        return _read_guide(
            filename="usage_guide_agents.md",
            development_path=USAGE_GUIDE_REL_PATH,
            override_path=USAGE_GUIDE_OVERRIDE_PATH,
            env_name="USAGE_GUIDE_REL_PATH",
            title="Usage Guide",
        )

    @mcp_instance.resource(
        uri="resource://plan-manager/project_workflow.md",
        name="project_workflow.md",
        title="Plan Manager Project Workflow",
        description="Diagrams and explanations of the core workflows for using Plan Manager.",
        mime_type="text/markdown",
    )
    def project_workflow_resource() -> str:
        return _read_guide(
            filename="project_workflow.md",
            development_path=PROJECT_WORKFLOW_REL_PATH,
            override_path=PROJECT_WORKFLOW_OVERRIDE_PATH,
            env_name="PROJECT_WORKFLOW_REL_PATH",
            title="Project Workflow",
        )

    @mcp_instance.resource(
        uri="resource://plan-manager/build_info.json",
        name="build_info.json",
        title="Plan Manager Build Information",
        description="Product version and package-fixed source revision.",
        mime_type="application/json",
    )
    def build_info_resource() -> str:
        return build_identity_json()

    # Reference the function to avoid unused-function linter warnings.
    _ = usage_guide_resource
    _ = project_workflow_resource
    _ = build_info_resource
