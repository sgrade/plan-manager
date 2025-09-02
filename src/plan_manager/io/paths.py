import os
import re


def slugify(title: str) -> str:
    if not title:
        raise ValueError("Title cannot be empty when generating a slug.")
    s = title.lower()
    s = re.sub(r'[^a-z0-9\s]+', ' ', s)
    s = re.sub(r'\s+', '_', s.strip())
    return s


def story_file_path(story_id: str, plan_id: str | None = None) -> str:
    from plan_manager.services.plan_repository import get_current_plan_id
    pid = plan_id or get_current_plan_id()
    return os.path.join('todo', pid, story_id, 'story.md')


def task_file_path(story_id: str, task_local_id: str, plan_id: str | None = None) -> str:
    from plan_manager.services.plan_repository import get_current_plan_id
    pid = plan_id or get_current_plan_id()
    return os.path.join('todo', pid, story_id, 'tasks', f"{task_local_id}.md")
