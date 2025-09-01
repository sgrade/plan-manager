from plan_manager.services.story_service import (
    create_story as svc_create_story,
    get_story as svc_get_story,
    update_story as svc_update_story,
    delete_story as svc_delete_story,
)
from plan_manager.schemas.inputs import (
    CreateStoryIn, GetStoryIn, UpdateStoryIn, DeleteStoryIn,
)
from plan_manager.schemas.outputs import StoryOut, OperationResult


def register_story_tools(mcp_instance) -> None:
    mcp_instance.tool()(create_story)
    mcp_instance.tool()(get_story)
    mcp_instance.tool()(update_story)
    mcp_instance.tool()(delete_story)


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
