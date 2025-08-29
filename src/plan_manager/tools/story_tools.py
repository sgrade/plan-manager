from typing import Optional
from plan_manager.services.story_service import (
    create_story as svc_create_story,
    get_story as svc_get_story,
    update_story as svc_update_story,
    delete_story as svc_delete_story,
)


def register_story_tools(mcp_instance) -> None:
    mcp_instance.tool()(create_story)
    mcp_instance.tool()(get_story)
    mcp_instance.tool()(update_story)
    mcp_instance.tool()(delete_story)


def create_story(title: str, priority: str, depends_on: str, notes: str) -> dict:
    return svc_create_story(title, priority, depends_on, notes)


def get_story(story_id: str) -> dict:
    return svc_get_story(story_id)


def update_story(
    story_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    depends_on: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    return svc_update_story(story_id, title, notes, depends_on, priority, status)


def delete_story(story_id: str) -> dict:
    return svc_delete_story(story_id)
