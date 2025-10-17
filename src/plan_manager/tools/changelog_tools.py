from typing import TYPE_CHECKING

from plan_manager.schemas.outputs import ChangelogPreviewOut
from plan_manager.services.changelog_service import generate_changelog_for_task
from plan_manager.services.plan_repository import load_current

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_changelog_tools(mcp_instance: "FastMCP") -> None:
    """Register changelog tools with the MCP instance."""
    mcp_instance.tool()(generate_changelog)


def generate_changelog(
    version: str | None = None, date: str | None = None
) -> ChangelogPreviewOut:
    """Generate a changelog for all completed tasks in the current plan.

    Args:
        version: Optional version string to include in changelog headers
        date: Optional date string to include in changelog headers

    Returns:
        ChangelogPreviewOut: The generated changelog in markdown format
    """
    plan = load_current()
    completed_tasks = [
        task for story in plan.stories for task in story.tasks if task.status == "DONE"
    ]

    snippets = []
    for task in completed_tasks:
        # We pass the version and date for the header of each snippet
        snippet = generate_changelog_for_task(task, version, date)
        snippets.append(snippet)

    md = "\n\n".join(snippets)
    return ChangelogPreviewOut(markdown=md)
