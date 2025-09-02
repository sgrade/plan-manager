import logging
from typing import List

from pydantic import ValidationError

from plan_manager.domain.models import Story
from plan_manager.services.story_service import (
    create_story as svc_create_story,
    get_story as svc_get_story,
    update_story as svc_update_story,
    delete_story as svc_delete_story,
    list_stories as svc_list_stories,
)
from plan_manager.schemas.inputs import (
    CreateStoryIn, GetStoryIn, UpdateStoryIn, DeleteStoryIn, ListStoriesIn,
)
from plan_manager.schemas.outputs import StoryOut, OperationResult, StoryListItem


logger = logging.getLogger(__name__)


def register_story_tools(mcp_instance) -> None:
    mcp_instance.tool()(create_story)
    mcp_instance.tool()(get_story)
    mcp_instance.tool()(update_story)
    mcp_instance.tool()(delete_story)
    mcp_instance.tool()(list_stories)


def create_story(payload: CreateStoryIn) -> StoryOut:
    """Create a story.

    Parameters:
    - title: Story title
    - priority: 0..5 or None
    - depends_on: List of story IDs this story depends on
    - notes: Optional freeform notes

    Returns: StoryOut
    """
    data = svc_create_story(payload.title, payload.priority,
                            payload.depends_on, payload.notes)
    return StoryOut(**data)


def get_story(payload: GetStoryIn) -> StoryOut:
    """Fetch a story by ID."""
    data = svc_get_story(payload.story_id)
    return StoryOut(**data)


def update_story(payload: UpdateStoryIn) -> StoryOut:
    """Update mutable fields of a story.

    Parameters:
    - story_id: Story ID
    - title, notes: Optional updates
    - depends_on: Optional new list of story IDs
    - priority: Optional new priority (0..5 or None)
    - status: Optional new status

    Returns: StoryOut
    """
    data = svc_update_story(payload.story_id, payload.title, payload.notes,
                            payload.depends_on, payload.priority, payload.status)
    return StoryOut(**data)


def delete_story(payload: DeleteStoryIn) -> OperationResult:
    """Delete a story by ID (fails if other items depend on it)."""
    data = svc_delete_story(payload.story_id)
    return OperationResult(**data)


def list_stories(payload: ListStoriesIn) -> List[StoryListItem]:
    """List stories with topological sort and structured filters."""
    logger.info(
        f"Handling list_stories: statuses={payload.statuses}, unblocked={payload.unblocked}")
    try:
        stories: List[Story] = svc_list_stories(
            payload.statuses, payload.unblocked)
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
        return items
    except (FileNotFoundError, ValidationError) as e:
        logger.exception("Failed to load/validate plan data for list_stories")
        raise e
    except Exception as e:
        logger.exception("Unexpected error during list_stories")
        raise e
