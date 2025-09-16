from plan_manager.io.files import read_markdown
from plan_manager.config import USAGE_GUIDE_REL_PATH


def register_usage_resources(mcp_instance) -> None:
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

    # Reference the function to avoid unused-function linter warnings.
    _ = usage_guide_resource
