# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
from typing import TYPE_CHECKING, Optional

from pydantic import ValidationError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from plan_manager.domain.models import Status, Story
from plan_manager.schemas.outputs import OperationResult, StoryListItem, StoryOut
from plan_manager.services.shared import (
    get_current_story_id,
    set_current_story_id,
)
from plan_manager.services.story_service import (
    create_story as svc_create_story,
)
from plan_manager.services.story_service import (
    delete_story as svc_delete_story,
)
from plan_manager.services.story_service import (
    get_story as svc_get_story,
)
from plan_manager.services.story_service import (
    list_stories as svc_list_stories,
)
from plan_manager.services.story_service import (
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
    plan_id: str,
    title: str,
    description: Optional[str] = None,
    acceptance_criteria: Optional[list[str]] = None,
    priority: Optional[float] = None,
    depends_on: Optional[list[str]] = None,
) -> StoryOut:
    """Create a new story with the specified details.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        title: The title of the story (will be validated and sanitized)
        description: Optional description of the story
        acceptance_criteria: Optional list of acceptance criteria for the story
        priority: Optional priority level (0-5, where 0 is highest priority)
        depends_on: Optional list of story IDs this story depends on

    Returns:
        StoryOut: The created story with its generated ID and metadata
    """
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_create_story(
        plan_id,
        title,
        description,
        acceptance_criteria,
        coerced_priority,
        depends_on or [],
    )
    return StoryOut(**data)


def get_story(plan_id: str, story_id: Optional[str] = None) -> StoryOut:
    """Fetch a story by ID or the current story for a plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        story_id: Story identifier, for example `task_orchestration`.
    """
    story_id = story_id or get_current_story_id(plan_id)
    if not story_id:
        raise ValueError(
            "Missing required parameter 'story_id': no current story for this plan. Call `set_current_story` with plan_id, or provide story_id."
        )
    data = svc_get_story(plan_id, story_id)
    return StoryOut(**data)


def update_story(
    plan_id: str,
    story_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    acceptance_criteria: Optional[list[str]] = None,
    depends_on: Optional[list[str]] = None,
    priority: Optional[float] = None,
) -> StoryOut:
    """Update mutable fields of a story.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        story_id: Story identifier, for example `task_orchestration`.
    """
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_update_story(
        plan_id,
        story_id,
        title,
        description,
        acceptance_criteria,
        coerced_priority,
        depends_on,
    )
    return StoryOut(**data)


def delete_story(plan_id: str, story_id: str) -> OperationResult:
    """Delete a story by ID (fails if other items depend on it).

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        story_id: Story identifier, for example `task_orchestration`.
    """
    data = svc_delete_story(plan_id, story_id)
    return OperationResult(**data)


def list_stories(
    plan_id: str,
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
        stories: list[Story] = svc_list_stories(plan_id, statuses, unblocked)
        items = [
            StoryListItem(
                plan_id=plan_id,
                id=s.id,
                title=s.title,
                status=s.status,
                priority=s.priority,
                creation_time=s.creation_time.isoformat() if s.creation_time else None,
                completion_time=(
                    s.completion_time.isoformat() if s.completion_time else None
                ),
            )
            for s in stories
        ]
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
    plan_id: str,
    story_id: Optional[str] = None,
) -> OperationResult | list[StoryListItem]:
    """Set the current story for a specific plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        story_id: Story identifier, for example `task_orchestration`.
    """
    if story_id:
        set_current_story_id(story_id, plan_id)
        return OperationResult(
            success=True, message=f"Current story set to '{story_id}'"
        )
    return list_stories(plan_id=plan_id)
