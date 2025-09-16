import logging
from typing import Dict, Any, List

from plan_manager.services import plan_repository as plan_repo
from plan_manager.services import task_service
from plan_manager.services.state_repository import get_current_plan_id, get_current_story_id, get_current_task_id
from plan_manager.domain.models import Status, Task
from plan_manager.services.changelog_service import generate_changelog_for_task

logger = logging.getLogger(__name__)


def find_reviewable_tasks() -> List[Task]:
    """Finds all tasks across all stories that are in a reviewable state."""
    plan_id = get_current_plan_id()
    if not plan_id:
        return []
    plan = plan_repo.load(plan_id)

    reviewable = []
    for story in plan.stories:
        for task in (story.tasks or []):
            is_pending_pre_review = task.status == Status.TODO and task.steps
            is_pending_code_review = task.status == Status.PENDING_REVIEW
            if is_pending_pre_review or is_pending_code_review:
                reviewable.append(task)
    return reviewable


def approve_current_task() -> Dict[str, Any]:
    """
    Approves the currently active task, moving it to its next state.
    This is the core engine for moving a task through its lifecycle.
    """
    plan_id = get_current_plan_id()
    if not plan_id:
        raise ValueError("No active plan. Please select a plan first.")
    plan = plan_repo.load(plan_id)

    task_id = get_current_task_id(plan_id)
    if not task_id:
        raise ValueError("No active task. There is nothing to approve.")

    story_id = get_current_story_id(plan_id)
    if not story_id:
        # This should ideally not happen if a task is active
        story_id = task_id.split(':')[0]

    story = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise RuntimeError(
            f"Data inconsistency: Story '{story_id}' not found for active task.")

    task = next((t for t in (story.tasks or []) if t.id == task_id), None)
    if not task:
        raise RuntimeError(
            f"Data inconsistency: Active task '{task_id}' not found in story '{story_id}'.")

    # Case 1: Approving a pre-execution review
    if task.status == Status.TODO:
        if not task.steps:
            # Seed minimal steps to satisfy the pre-execution gate, then set task as active.
            logger.info(
                f"Seeding minimal steps to satisfy the pre-execution gate for task: {task.id}")
            task_service.create_steps(story.id, task.id, steps=[
                {"title": "Fast-tracked by user."}])
        if task.steps:
            logger.info(f"Approving implementation plan for task: {task.id}")
            updated_task_data = task_service.update_task(
                story_id=story.id,
                task_id=task.id,
                status=Status.IN_PROGRESS
            )
            return {"success": True, "message": f"Task '{task.title}' approved and moved to IN_PROGRESS.", "changelog_snippet": None, **updated_task_data}
        else:
            raise ValueError(
                "No steps found. Run /create_steps to define steps, or run approve again to fast-track.")

    # Case 2: Approving a code review
    elif task.status == Status.PENDING_REVIEW:
        logger.info(f"Approving code review for task: {task.id}")
        updated_task_data = task_service.update_task(
            story_id=story.id,
            task_id=task.id,
            status=Status.DONE
        )

        # Generate changelog snippet
        updated_task = Task(**updated_task_data)
        changelog_snippet = generate_changelog_for_task(updated_task)

        return {"success": True, "message": f"Task '{task.title}' approved and moved to DONE.", "changelog_snippet": changelog_snippet, **updated_task_data}

    # Case 3: Task is not in a reviewable state
    else:
        raise ValueError(
            f"The active task '{task.title}' is not in a reviewable state (current status: {task.status}).")
