import logging
from typing import TYPE_CHECKING, Optional

from pydantic import ValidationError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from plan_manager.domain.models import Status, Story
from plan_manager.schemas.outputs import OperationResult, StoryListItem, StoryOut
from plan_manager.services.state_repository import (
    get_current_story_id,
    set_current_story_id,
)
from plan_manager.services.story_service import (
    create_story as svc_create_story,
    delete_story as svc_delete_story,
    get_story as svc_get_story,
    list_stories as svc_list_stories,
    update_story as svc_update_story,
)
from plan_manager.tools.util import coerce_optional_int

logger = logging.getLogger(__name__)


def register_story_tools(mcp_instance: "FastMCP") -> None:
    """Register story tools with the MCP instance."""
    mcp_instance.tool()(list_stories)
    mcp_instance.tool()(create_story)
    mcp_instance.tool()(get_story)
    mcp_instance.tool()(update_story)
    mcp_instance.tool()(delete_story)
    mcp_instance.tool()(set_current_story)


def create_story(
    title: str,
    description: Optional[str] = None,
    acceptance_criteria: Optional[list[str]] = None,
    priority: Optional[float] = None,
    depends_on: Optional[list[str]] = None,
) -> StoryOut:
    """Create a new story with the specified details.

    Args:
        title: The title of the story (will be validated and sanitized)
        description: Optional description of the story
        acceptance_criteria: Optional list of acceptance criteria for the story
        priority: Optional priority level (0-5, where 5 is highest)
        depends_on: Optional list of story IDs this story depends on

    Returns:
        StoryOut: The created story with its generated ID and metadata
    """
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_create_story(
        title, description, acceptance_criteria, coerced_priority, depends_on or []
    )
    return StoryOut(**data)


def get_story(story_id: Optional[str] = None) -> StoryOut:
    """Fetch a story by ID or the current story if none provided."""
    story_id = story_id or get_current_story_id()
    if not story_id:
        raise ValueError(
            "No current story set. Call set_current_story or provide story_id."
        )
    data = svc_get_story(story_id)
    return StoryOut(**data)


def update_story(
    story_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    acceptance_criteria: Optional[list[str]] = None,
    depends_on: Optional[list[str]] = None,
    priority: Optional[float] = None,
) -> StoryOut:
    """Update mutable fields of a story."""
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_update_story(
        story_id, title, description, acceptance_criteria, coerced_priority, depends_on
    )
    return StoryOut(**data)


def delete_story(story_id: str) -> OperationResult:
    """Delete a story by ID (fails if other items depend on it)."""
    data = svc_delete_story(story_id)
    return OperationResult(**data)


def list_stories(
    statuses: Optional[list[Status]] = None,
    unblocked: bool = False,
    offset: Optional[int] = 0,
    limit: Optional[int] = None,
) -> list[StoryListItem]:
    """List stories with optional status filter, unblocked flag and pagination."""
    if statuses is None:
        statuses = []
    logger.info("Handling list_stories: statuses=%s, unblocked=%s", statuses, unblocked)
    try:
        stories: list[Story] = svc_list_stories(statuses, unblocked)
        items: list[StoryListItem] = []
        for s in stories:
            items.append(
                StoryListItem(
                    id=s.id,
                    title=s.title,
                    status=s.status,
                    priority=s.priority,
                    creation_time=s.creation_time.isoformat()
                    if s.creation_time
                    else None,
                    completion_time=s.completion_time.isoformat()
                    if s.completion_time
                    else None,
                )
            )
        logger.info(
            "list_stories returning %d stories after sorting and filtering.", len(items)
        )
        start = max(0, offset or 0)
        end = None if limit is None else start + max(0, limit)
        return items[start:end]
    except (FileNotFoundError, ValidationError):
        logger.exception("Failed to load/validate plan data for list_stories")
        raise
    except Exception:
        logger.exception("Unexpected error during list_stories")
        raise


def set_current_story(
    story_id: Optional[str] = None,
) -> OperationResult | list[StoryListItem]:
    """Set the current story. If no ID is provided, lists available stories."""
    if story_id:
        set_current_story_id(story_id)
        return OperationResult(
            success=True, message=f"Current story set to '{story_id}'"
        )
    return list_stories()
