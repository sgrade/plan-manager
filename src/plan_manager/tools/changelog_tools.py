from typing import TYPE_CHECKING

from plan_manager.domain.models import Task
from plan_manager.schemas.outputs import (
    ChangelogEntryOut,
    CommitMessageOut,
)
from plan_manager.services import changelog_service
from plan_manager.services.task_service import get_task
from plan_manager.tools.task_tools import resolve_task_id

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_changelog_tools(mcp_instance: "FastMCP") -> None:
    """Register changelog tools with the MCP instance."""
    mcp_instance.tool()(generate_changelog_entry)
    mcp_instance.tool()(generate_commit_message)


def generate_changelog_entry(
    task_id: str,
    category: str,
    version: str | None = None,
    date: str | None = None,
) -> ChangelogEntryOut:
    """Generate keepachangelog.com format entry from a completed task's changelog entries.

    Args:
        task_id: The ID of the task (local or fully qualified)
        category: Changelog category - one of: Added, Changed, Deprecated, Removed, Fixed, Security
        version: Optional version string (e.g., "0.9.0")
        date: Optional date string (e.g., "2025-01-19")

    Returns:
        ChangelogEntryOut: Formatted changelog entry ready to paste into CHANGELOG.md
    """
    story_id, local_task_id = resolve_task_id(task_id)
    task_data = get_task(story_id, local_task_id)
    task = Task(**task_data)

    markdown = changelog_service.generate_changelog_for_task(
        task, category=category, version=version, date=date
    )

    return ChangelogEntryOut(markdown=markdown, task_id=task.id, category=category)


def generate_commit_message(
    task_id: str,
    commit_type: str,
) -> CommitMessageOut:
    """Generate conventional commit message from a completed task's changelog entries.

    Args:
        task_id: The ID of the task (local or fully qualified)
        commit_type: Commit type - one of: feat, fix, docs, style, refactor, perf, test, build, ci, chore

    Returns:
        CommitMessageOut: Formatted commit message following conventional commits spec
    """
    story_id, local_task_id = resolve_task_id(task_id)
    task_data = get_task(story_id, local_task_id)
    task = Task(**task_data)

    message = changelog_service.generate_commit_message_for_task(
        task, commit_type=commit_type
    )

    return CommitMessageOut(message=message, task_id=task.id, commit_type=commit_type)
