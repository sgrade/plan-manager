from datetime import datetime, timezone
from typing import Optional

from plan_manager.domain.models import Task


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def generate_changelog_for_task(task: Task, version: Optional[str] = None, date: Optional[str] = None) -> str:
    """Generates a changelog snippet for a single completed task."""

    header = []
    if version:
        header.append(f"## {version} - {date or _today_str()}\n")
    else:
        header.append(f"## {date or _today_str()}\n")

    body = ["### Changed\n"]

    summary = task.execution_summary or 'No summary provided.'
    entry = f"- **{task.title}**: {summary}"
    body.append(entry)

    return "\n".join(header + body).strip() + "\n"
