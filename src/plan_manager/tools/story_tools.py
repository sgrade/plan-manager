import logging
from typing import List, Optional

from pydantic import ValidationError

from plan_manager.domain.models import Story, Status
from plan_manager.services.story_service import (
    create_story as svc_create_story,
    get_story as svc_get_story,
    update_story as svc_update_story,
    delete_story as svc_delete_story,
    list_stories as svc_list_stories,
)
from plan_manager.schemas.outputs import StoryOut, OperationResult, StoryListItem
from plan_manager.services.state_repository import set_current_story_id, get_current_story_id


logger = logging.getLogger(__name__)


def register_story_tools(mcp_instance) -> None:
    """Register story tools with the MCP instance."""
    mcp_instance.tool()(list_stories)
    mcp_instance.tool()(create_story)
    mcp_instance.tool()(get_story)
    mcp_instance.tool()(update_story)
    mcp_instance.tool()(delete_story)
    mcp_instance.tool()(set_current_story)


def create_story(title: str, description: Optional[str] = None, acceptance_criteria: Optional[list[str]] = None, priority: Optional[int] = None, depends_on: Optional[list[str]] = None) -> StoryOut:
    """Create a story.

    Args:
        title: The title of the story.
        description: The description of the story.
        acceptance_criteria: The acceptance criteria of the story.
        priority: The priority of the story.
        depends_on: The dependencies of the story.
    """
    data = svc_create_story(title, description, acceptance_criteria, priority,
                            depends_on or [])
    return StoryOut(**data)


def get_story(story_id: Optional[str] = None) -> StoryOut:
    """Fetch a story by ID or the current story if none provided."""
    story_id = story_id or get_current_story_id()
    if not story_id:
        raise ValueError(
            "No current story set. Call set_current_story or provide story_id.")
    data = svc_get_story(story_id)
    return StoryOut(**data)


def update_story(story_id: str, title: Optional[str] = None, description: Optional[str] = None, acceptance_criteria: Optional[list[str]] = None, depends_on: Optional[list[str]] = None, priority: Optional[int] = None) -> StoryOut:
    """Update mutable fields of a story."""
    data = svc_update_story(story_id, title, description,
                            acceptance_criteria, priority, depends_on)
    return StoryOut(**data)


def delete_story(story_id: str) -> OperationResult:
    """Delete a story by ID (fails if other items depend on it)."""
    data = svc_delete_story(story_id)
    return OperationResult(**data)


def list_stories(statuses: Optional[List[Status]] = None, unblocked: bool = False, offset: Optional[int] = 0, limit: Optional[int] = None) -> List[StoryListItem]:
    """List stories with optional status filter, unblocked flag and pagination."""
    logger.info(
        f"Handling list_stories: statuses={statuses}, unblocked={unblocked}")
    try:
        stories: List[Story] = svc_list_stories(statuses, unblocked)
        items: List[StoryListItem] = []
        for s in stories:
            items.append(
                StoryListItem(
                    id=s.id,
                    title=s.title,
                    status=s.status,
                    priority=s.priority,
                    creation_time=s.creation_time.isoformat() if s.creation_time else None,
                    completion_time=s.completion_time.isoformat() if getattr(
                        s, 'completion_time', None) else None,
                )
            )
        logger.info(
            f"list_stories returning {len(items)} stories after sorting and filtering.")
        start = max(0, offset or 0)
        end = None if limit is None else start + max(0, limit)
        return items[start:end]
    except (FileNotFoundError, ValidationError) as e:
        logger.exception("Failed to load/validate plan data for list_stories")
        raise e
    except Exception as e:
        logger.exception("Unexpected error during list_stories")
        raise e


def set_current_story(story_id: Optional[str] = None) -> OperationResult | List[StoryListItem]:
    """Set the current story. If no ID is provided, lists available stories."""
    if story_id:
        set_current_story_id(story_id)
        return OperationResult(success=True, message=f"Current story set to '{story_id}'")
    return list_stories()
