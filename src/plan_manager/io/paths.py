import os
import re


def slugify(title: str) -> str:
    """Convert a title into a URL-safe slug.

    Args:
        title: The title to convert

    Returns:
        str: The slugified version with lowercase letters, numbers, and underscores

    Raises:
        ValueError: If title is empty
    """
    if not title:
        raise ValueError("Title cannot be empty when generating a slug.")
    s = title.lower()
    s = re.sub(r'[^a-z0-9\s]+', ' ', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s


def story_file_path(story_id: str, plan_id: str | None = None) -> str:
    """Generate the file path for a story's markdown file.

    Args:
        story_id: The ID of the story
        plan_id: Optional plan ID. If not provided, uses current plan.

    Returns:
        str: The relative file path to the story markdown file
    """
    from plan_manager.services.plan_repository import get_current_plan_id
    from plan_manager.config import TODO_DIR
    pid = plan_id or get_current_plan_id()
    return os.path.join(TODO_DIR, pid, story_id, 'story.md')


def task_file_path(story_id: str, task_local_id: str, plan_id: str | None = None) -> str:
    """Generate the file path for a task's markdown file.

    Args:
        story_id: The ID of the parent story
        task_local_id: The local ID of the task within the story
        plan_id: Optional plan ID. If not provided, uses current plan.

    Returns:
        str: The relative file path to the task markdown file
    """
    from plan_manager.services.plan_repository import get_current_plan_id
    from plan_manager.config import TODO_DIR
    pid = plan_id or get_current_plan_id()
    return os.path.join(TODO_DIR, pid, story_id, 'tasks', f"{task_local_id}.md")
