from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from plan_manager.config import PROJECT_WORKFLOW_REL_PATH, USAGE_GUIDE_REL_PATH
from plan_manager.io.files import read_markdown


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
        try:
            return read_markdown(USAGE_GUIDE_REL_PATH)
        except Exception:
            # Fallback minimal content
            return "# Plan Manager — Usage Guide\n\nSee project docs for details."

    @mcp_instance.resource(
        uri="resource://plan-manager/project_workflow.md",
        name="project_workflow.md",
        title="Plan Manager Project Workflow",
        description="Diagrams and explanations of the core workflows for using Plan Manager.",
        mime_type="text/markdown",
    )
    def project_workflow_resource() -> str:
        try:
            return read_markdown(PROJECT_WORKFLOW_REL_PATH)
        except Exception:
            return "# Plan Manager — Project Workflow\n\nSee project docs for details."

    # Reference the function to avoid unused-function linter warnings.
    _ = usage_guide_resource
    _ = project_workflow_resource
