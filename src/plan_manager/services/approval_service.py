import logging
from typing import Dict, Any, List

from plan_manager.services import plan_repository as plan_repo
from plan_manager.services import task_service
from plan_manager.services.state_repository import get_current_plan_id, get_current_story_id, get_current_task_id, set_current_task_id
from plan_manager.domain.models import Status, Task

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


def approve_active_task() -> Dict[str, Any]:
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
    if task.status == Status.TODO and task.steps:
        logger.info(f"Approving implementation plan for task: {task.id}")
        return task_service.update_task(
            story_id=story.id,
            task_id=task.id,
            status=Status.IN_PROGRESS
        )

    # Case 2: Approving a code review
    elif task.status == Status.PENDING_REVIEW:
        logger.info(f"Approving code review for task: {task.id}")
        return task_service.update_task(
            story_id=story.id,
            task_id=task.id,
            status=Status.DONE
        )

    # Case 3: Task is not in a reviewable state
    else:
        raise ValueError(
            f"The active task '{task.title}' is not in a reviewable state (current status: {task.status}).")


def approve_fast_track(item_id: str) -> Dict[str, Any]:
    """
    Performs a "fast-track" approval, skipping the pre-execution review.
    """
    plan_id = get_current_plan_id()
    if not plan_id:
        raise ValueError("No active plan to fast-track a task in.")
    plan = plan_repo.load(plan_id)

    # Find the task and its story by local ID
    found_story = None
    found_task = None
    for s in plan.stories:
        for t in (s.tasks or []):
            local_id = t.id.split(':')[-1]
            if local_id == item_id:
                found_story = s
                found_task = t
                break
        if found_task:
            break

    if found_task and found_story:
        if found_task.status == Status.TODO:
            logger.info(f"Fast-tracking task: {found_task.id}")
            # We set a dummy plan to satisfy the check in update_task, and set the task as active.
            task_service.propose_steps(
                found_story.id, found_task.id, "Fast-tracked by user.")
            set_current_task_id(found_task.id, plan_id)
            return task_service.update_task(
                story_id=found_story.id,
                task_id=found_task.id,
                status=Status.IN_PROGRESS
            )
        else:
            raise ValueError(
                f"Cannot fast-track task '{item_id}'; its status is not TODO.")
    else:
        raise KeyError(
            f"Task with local ID '{item_id}' not found in the current plan.")
