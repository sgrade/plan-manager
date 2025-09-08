import logging
from typing import List, Dict, Any

from plan_manager.services import plan_repository as plan_repo
from plan_manager.services import story_service
from plan_manager.services.state_repository import get_current_plan_id, get_current_story_id
from plan_manager.domain.models import Story, Task

logger = logging.getLogger(__name__)


class NoContextError(Exception):
    """Raised when an action requires a context (like a plan) but none is set."""
    pass


def review_backlog() -> List[Dict[str, Any]]:
    """
    Reviews the current work item based on the active context.
    - If a story is selected, lists its tasks.
    - If a plan is selected, lists its stories.
    """
    plan_id = get_current_plan_id()
    if not plan_id:
        raise NoContextError(
            "No active plan. Please select or create a plan first.")

    plan = plan_repo.load(plan_id)
    story_id = get_current_story_id(plan_id)

    if story_id:
        story = next((s for s in plan.stories if s.id == story_id), None)
        if story:
            return [t.model_dump(mode='json', exclude_none=True) for t in (story.tasks or [])]
        else:
            # Story context is stale, fall back to plan context
            return [s.model_dump(mode='json', exclude_none=True) for s in plan.stories]
    else:
        return [s.model_dump(mode='json', exclude_none=True) for s in plan.stories]


def create_story_in_current_plan(title: str, description: str) -> Dict[str, Any]:
    """
    Creates a new story within the currently active plan.
    """
    plan_id = get_current_plan_id()
    if not plan_id:
        raise NoContextError(
            "Cannot create a story because no plan is currently selected.")

    # create_story uses the "current" plan, which is what we want
    new_story = story_service.create_story(
        title=title,
        description=description,
        priority=None,
        depends_on=[]
    )
    return new_story
