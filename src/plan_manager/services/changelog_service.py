from datetime import datetime, timezone
from typing import Optional

from plan_manager.domain.models import Task


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def generate_changelog_for_task(
    task: Task,
    category: str,
    version: Optional[str] = None,
    date: Optional[str] = None,
) -> str:
    """Generate a changelog entry for a completed task in keepachangelog.com format.

    Args:
        task: The completed task
        category: Changelog category (e.g., "Added", "Changed", "Fixed", "Removed")
        version: Optional version string to include in header
        date: Optional date string to include in header

    Returns:
        Formatted changelog entry ready to paste into CHANGELOG.md
    """
    # Validate category
    valid_categories = [
        "Added",
        "Changed",
        "Deprecated",
        "Removed",
        "Fixed",
        "Security",
    ]
    if category not in valid_categories:
        raise ValueError(
            f"Invalid category '{category}'. Must be one of: {', '.join(valid_categories)}"
        )

    # Build header
    header = []
    if version:
        header.append(f"## [{version}] - {date or _today_str()}\n")

    # Build entry
    header.append(f"### {category}\n")

    # Format entries as bullets
    entries = task.changes if task.changes else ["No entries provided"]
    bullets = [f"- {entry}" for entry in entries]

    return "\n".join(header + bullets).strip() + "\n"


def generate_commit_message_for_task(
    task: Task,
    commit_type: str,
) -> str:
    """Generate a conventional commit message for a completed task.

    Args:
        task: The completed task
        commit_type: Commit type (e.g., "feat", "fix", "docs", "refactor")

    Returns:
        Formatted commit message following conventional commits spec
    """
    # Validate commit type
    valid_types = [
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
    ]
    if commit_type not in valid_types:
        raise ValueError(
            f"Invalid commit type '{commit_type}'. Must be one of: {', '.join(valid_types)}"
        )

    # Subject line: type(scope): title
    local_id = task.local_id or task.id.split(":")[-1]
    subject = f"{commit_type}({local_id}): {task.title}"

    # Body: changelog entries as bullets
    body_lines = []
    if task.changes:
        body_lines = [f"- {entry}" for entry in task.changes]

    # Footer: story reference
    footer = []
    if task.story_id:
        footer.append(f"Refs: {task.story_id}")

    # Assemble message
    parts = [subject, ""]
    if body_lines:
        parts.extend(body_lines)
        parts.append("")
    if footer:
        parts.extend(footer)

    return "\n".join(parts).strip() + "\n"
