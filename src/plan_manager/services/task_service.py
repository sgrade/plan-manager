import logging
from typing import Any, Optional

from pydantic import ValidationError

from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.io.file_mirror import (
    delete_item_file,
    read_item_file,
    save_item_to_file,
)
from plan_manager.io.paths import task_file_path
from plan_manager.logging_context import get_correlation_id
from plan_manager.services import plan_repository, task_service
from plan_manager.services.activity_repository import append_event
from plan_manager.services.changelog_service import generate_changelog_for_task
from plan_manager.services.shared import (
    ensure_unique_id_from_set,
    find_dependents,
    generate_slug,
    is_unblocked,
    merge_frontmatter_defaults,
    resolve_task_id,
    validate_and_save,
    write_story_details,
    write_task_details,
)
from plan_manager.services.state_repository import (
    get_current_story_id,
    get_current_task_id,
    set_current_story_id,
    set_current_task_id,
)
from plan_manager.services.status_utils import (
    apply_status_change,
    rollup_plan_status,
    rollup_story_status,
)
from plan_manager.telemetry import incr, timer
from plan_manager.validation import (
    validate_description,
    validate_execution_summary,
    validate_feedback,
    validate_task_steps,
    validate_title,
)

logger = logging.getLogger(__name__)


# ---------- CRUD operations ----------


def _generate_task_id_from_title(title: str) -> str:
    return generate_slug(title)


def create_task(
    story_id: str,
    title: str,
    priority: Optional[int],
    depends_on: list[str],
    description: Optional[str],
) -> dict[str, Any]:
    """Create a new task in the specified story.

    Args:
        story_id: The ID of the story to add the task to
        title: The title of the task (will be validated and sanitized)
        priority: Optional priority level (0-5, where 5 is highest)
        depends_on: List of task IDs this task depends on
        description: Optional description of the task

    Returns:
        dict: Task data including the generated task ID

    Raises:
        ValueError: If input validation fails or story doesn't exist
        KeyError: If the specified story doesn't exist
    """
    # Validate inputs
    title = validate_title(title)
    description = validate_description(description)

    logger.info(
        {
            "event": "create_task",
            "story_id": story_id,
            "title": title,
            "priority": priority,
            "depends_on": depends_on,
            "corr_id": get_correlation_id(),
        }
    )
    plan = plan_repository.load_current()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")

    task_local_id = _generate_task_id_from_title(title)
    fq_task_id = f"{story_id}:{task_local_id}"
    existing_locals = [
        t.id.split(":", 1)[1] if ":" in t.id else t.id for t in (story.tasks or [])
    ]
    task_local_id = ensure_unique_id_from_set(task_local_id, existing_locals)
    fq_task_id = f"{story_id}:{task_local_id}"

    try:
        task = Task(
            id=fq_task_id,
            title=title,
            depends_on=depends_on,
            description=description,
            priority=priority,
            story_id=story_id,
            local_id=task_local_id,
        )
    except ValidationError as e:
        logger.exception(f"Validation error creating new task '{fq_task_id}': {e}")
        raise ValueError(
            f"Validation error creating new task '{fq_task_id}': {e}"
        ) from e

    story.tasks = (story.tasks or []) + [task]
    validate_and_save(plan)

    try:
        write_task_details(task)
    except Exception:
        logger.info(f"Best-effort creation of task file failed for '{fq_task_id}'.")

    try:
        write_story_details(story)
    except Exception:
        logger.info(
            f"Best-effort update of story file tasks list failed for '{story_id}'."
        )

    return task.model_dump(
        mode="json",
        include={
            "id",
            "title",
            "status",
            "priority",
            "creation_time",
            "description",
            "depends_on",
        },
        exclude_none=True,
    )


def get_task(story_id: str, task_id: str) -> dict[str, Any]:
    plan = plan_repository.load_current()
    s_id, local_task_id = resolve_task_id(task_id, story_id)

    story: Optional[Story] = next((s for s in plan.stories if s.id == s_id), None)
    if not story:
        raise KeyError(f"story with ID '{s_id}' not found.")

    fq_task_id = f"{s_id}:{local_task_id}"
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{s_id}'.")
    task_obj = next((t for t in story.tasks if t.id == fq_task_id), None)
    if task_obj:
        base = task_obj.model_dump(
            include={
                "id",
                "title",
                "status",
                "priority",
                "creation_time",
                "description",
                "execution_summary",
                "depends_on",
            },
            exclude_none=True,
        )
        # Normalize datetime fields to ISO strings for transport schema expectations
        ct = base.get("creation_time")
        try:
            # Pydantic BaseModel dumps datetime by default; ensure str
            if hasattr(ct, "isoformat"):
                base["creation_time"] = ct.isoformat()
        except Exception:
            base["creation_time"] = None
        task_details_path = task_file_path(s_id, local_task_id)
        return merge_frontmatter_defaults(task_details_path, base)
    task_details_path = task_file_path(s_id, local_task_id)
    front, _body = read_item_file(task_details_path)
    if front:
        out = {
            "id": front.get("id", fq_task_id),
            "title": front.get("title", local_task_id.replace("_", " ")),
            "status": front.get("status", "TODO"),
        }
        for k in ("priority", "creation_time", "description", "depends_on"):
            if front.get(k) is not None:
                out[k] = front.get(k)
        return out
    return {
        "id": fq_task_id,
        "title": local_task_id.replace("_", " "),
        "status": "TODO",
    }


def _find_task(
    plan: Plan, story_id: Optional[str], task_id: str
) -> tuple[Story, Task, str]:
    """Helper to find a task and its story, returning (story, task, fq_id) or raising KeyError."""
    s_id, local_task_id = resolve_task_id(task_id, story_id)

    story: Optional[Story] = next((s for s in plan.stories if s.id == s_id), None)
    if not story:
        raise KeyError(f"Story with ID '{s_id}' not found.")

    fq_task_id = f"{s_id}:{local_task_id}"
    task_obj: Optional[Task] = next(
        (t for t in (story.tasks or []) if t.id == fq_task_id), None
    )
    if not task_obj:
        raise KeyError(f"Task with ID '{fq_task_id}' not found under story '{s_id}'.")
    return story, task_obj, fq_task_id


def _update_dependent_task_statuses(plan: Plan) -> None:
    """
    Iterates through all tasks and updates their status to BLOCKED or TODO
    based on the current state of their dependencies.
    """
    logger.debug(f"Running blocker status update for plan '{plan.id}'.")
    for story in plan.stories:
        for task in story.tasks or []:
            if task.status in [Status.TODO, Status.BLOCKED]:
                currently_unblocked = is_unblocked(task, plan)

                if task.status == Status.TODO and not currently_unblocked:
                    task.status = Status.BLOCKED
                    logger.info(
                        f"Task '{task.id}' is now BLOCKED due to unmet dependencies."
                    )
                elif task.status == Status.BLOCKED and currently_unblocked:
                    task.status = Status.TODO
                    logger.info(f"Task '{task.id}' is now UNBLOCKED and set to TODO.")


def update_task(
    story_id: str,
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    depends_on: Optional[list[str]] = None,
    priority: Optional[int] = None,
    status: Optional[Status] = None,
) -> dict[str, Any]:
    plan = plan_repository.load_current()
    story, task_obj, _fq_task_id = _find_task(plan, story_id, task_id)

    # Prevent starting a blocked task
    if status == Status.IN_PROGRESS and task_obj.status == Status.TODO:
        if not is_unblocked(task_obj, plan):
            raise ValueError(
                f"Task '{task_obj.title}' cannot be started because it is blocked by one or more dependencies."
            )

    if title is not None:
        task_obj.title = title
    if description is not None:
        task_obj.description = description
    if depends_on is not None:
        task_obj.depends_on = depends_on
    if priority is not None:
        task_obj.priority = priority

    if status is not None:
        prev_status = task_obj.status

        # Enforce strict state transitions authorized by the 'approve' command
        if status == Status.IN_PROGRESS and prev_status == Status.TODO:
            if not task_obj.steps:
                raise ValueError(
                    "An implementation plan must be approved before starting work."
                )
            apply_status_change(task_obj, status)
        elif status == Status.PENDING_REVIEW and prev_status == Status.IN_PROGRESS:
            # Submitting for review requires an execution summary to have been set
            if not task_obj.execution_summary:
                raise ValueError(
                    "An execution summary must be provided before submitting for review."
                )
            apply_status_change(task_obj, status)
        elif status == Status.DONE and prev_status == Status.PENDING_REVIEW:
            if not task_obj.execution_summary:
                raise ValueError(
                    "An execution summary must be provided before marking as DONE."
                )
            apply_status_change(task_obj, status)
            # After a task is done, re-evaluate blockers across the plan
            _update_dependent_task_statuses(plan)
        elif status == prev_status:
            pass  # No change
        else:
            raise ValueError(
                f"Invalid status transition from {prev_status} to {status}."
            )

        if prev_status != task_obj.status:
            append_event(
                plan.id,
                "task_status_changed",
                {"task_id": task_obj.id},
                {"from": prev_status.value, "to": task_obj.status.value},
            )

    # 1. Roll up story status
    prev_story_status = story.status
    next_story_status = rollup_story_status([t.status for t in (story.tasks or [])])
    if prev_story_status != next_story_status:
        apply_status_change(story, next_story_status)
        if story.file_path:
            try:
                save_item_to_file(story.file_path, story, content=None, overwrite=False)
            except Exception:
                logger.info(
                    f"Best-effort rollup update of story file failed for '{story_id}'."
                )

    # 3. Roll up plan status
    prev_plan_status = plan.status
    next_plan_status = rollup_plan_status([s.status for s in plan.stories])
    if prev_plan_status != next_plan_status:
        apply_status_change(plan, next_plan_status)

    # 4. Save the final state
    plan_repository.save(plan, plan_id=plan.id)

    # Selection invariants (simplified)
    try:
        if task_obj.status == Status.DONE:
            current_tid = get_current_task_id(plan.id)
            if current_tid == task_obj.id:
                # Clear selection on completion
                set_current_task_id(None, plan.id)
        if story.status == Status.DONE:
            current_sid = get_current_story_id(plan.id)
            if current_sid == story.id:
                set_current_story_id(None, plan.id)
    except Exception:
        logger.warning("Failed to update current selection state.")

    return task_obj.model_dump(mode="json", exclude_none=True)


def delete_task(story_id: str, task_id: str) -> dict[str, Any]:
    plan = plan_repository.load_current()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ":" not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(
            f"task with ID '{fq_task_id}' not found under story '{story_id}'."
        )

    dependents = find_dependents(plan, fq_task_id)
    if dependents:
        raise ValueError(
            f"Cannot delete task '{fq_task_id}' because it is a dependency of: {', '.join(dependents)}"
        )

    story.tasks = [t for t in (story.tasks or []) if t.id != fq_task_id]
    plan_repository.save(plan)
    try:
        local_task_id = fq_task_id.split(":", 1)[1]
        task_details_path = task_file_path(story_id, local_task_id)
        delete_item_file(task_details_path)
    except Exception:
        logger.info(f"Best-effort delete of task file failed for '{fq_task_id}'.")
    try:
        if story.file_path:
            save_item_to_file(story.file_path, story, content=None, overwrite=False)
    except Exception:
        logger.info(
            f"Best-effort update of story file tasks list failed for '{story_id}'."
        )
    # Selection invariants: if deleted task was current, auto-advance/reset
    try:
        current_tid = get_current_task_id(plan.id)
        if current_tid == fq_task_id:
            # Prefer next TODO/IN_PROGRESS task
            for t in story.tasks or []:
                if t.status in (Status.TODO, Status.IN_PROGRESS):
                    set_current_task_id(t.id, plan.id)
                    break
            else:
                set_current_task_id(None, plan.id)
    except Exception:
        pass

    return {"success": True, "message": f"Successfully deleted task '{fq_task_id}'."}


def list_tasks(
    statuses: Optional[list[Status]], story_id: Optional[str] = None
) -> list[Task]:
    plan = plan_repository.load_current()
    tasks: list[Task] = []
    for s in plan.stories:
        if story_id and s.id != story_id:
            continue
        for t in s.tasks or []:
            if isinstance(t, Task):
                tasks.append(t)

    allowed_statuses = set(statuses) if statuses else None

    filtered: list[Task] = []
    for t in tasks:
        if allowed_statuses is not None and t.status not in allowed_statuses:
            continue
        filtered.append(t)

    def _prio_key(task: Task) -> int:
        return task.priority if task.priority is not None else 6

    def _ctime_key(task: Task) -> tuple[bool, str]:
        return (task.creation_time is None, task.creation_time or "9999")

    filtered.sort(key=lambda t: (_prio_key(t), _ctime_key(t), t.id))
    return filtered


def create_steps(
    story_id: str, task_id: str, steps: list[dict[str, Any]]
) -> dict[str, Any]:
    """Set the implementation steps for a task, making it ready for pre-execution review.

    Args:
        story_id: The ID of the story containing the task
        task_id: The local ID of the task within the story
        steps: List of step dictionaries, each with 'title' and optional 'description'

    Returns:
        dict: Updated task data

    Raises:
        ValueError: If steps validation fails or task is in wrong status
        KeyError: If story or task doesn't exist
    """
    plan = plan_repository.load_current()
    story, task_obj, _fq_task_id = _find_task(plan, story_id, task_id)

    if task_obj.status not in [Status.TODO, Status.IN_PROGRESS]:
        raise ValueError(
            f"Can only propose a plan for a task in TODO or IN_PROGRESS status. Current status is {task_obj.status}."
        )

    # Validate steps using centralized validation
    validated_steps = validate_task_steps(steps)

    # Convert validated steps to domain models
    new_steps: list[Task.Step] = []
    for step in validated_steps:
        new_steps.append(
            Task.Step(title=step["title"], description=step["description"])
        )
    task_obj.steps = new_steps

    # Re-assign the tasks list to ensure the parent model detects the change.
    story.tasks = list(story.tasks or [])

    validate_and_save(plan)
    return task_obj.model_dump(mode="json", exclude_none=True)


# ---------- Task workflow operations ----------


def approve_current_task() -> dict[str, Any]:
    """Approve the currently active task, moving it to its next state in the workflow.

    This is the core engine for moving a task through its lifecycle. The transition
    depends on the current task state:
    - TODO with steps → IN_PROGRESS
    - TODO without steps → requires steps first (fast-track)
    - IN_PROGRESS → PENDING_REVIEW (after execution)

    Returns:
        Dict[str, Any]: Result containing success status and any error messages

    Raises:
        ValueError: If no active plan/task or invalid state transitions
    """
    plan_id = plan_repository.get_current_plan_id()
    if not plan_id:
        raise ValueError("No active plan. Please select a plan first.")
    plan = plan_repository.load(plan_id)

    task_id = get_current_task_id(plan_id)
    if not task_id:
        raise ValueError("No active task. There is nothing to approve.")

    story_id = get_current_story_id(plan_id)
    if not story_id:
        # This should ideally not happen if a task is active
        story_id = task_id.split(":")[0]

    story = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise RuntimeError(
            f"Data inconsistency: Story '{story_id}' not found for active task."
        )

    task = next((t for t in (story.tasks or []) if t.id == task_id), None)
    if not task:
        raise RuntimeError(
            f"Data inconsistency: Active task '{task_id}' not found in story '{story_id}'."
        )

    # Case 1: Approving a pre-execution review (Gate 1)
    if task.status == Status.TODO:
        # Require steps to exist. Fast-track does not seed steps server-side.
        if not task.steps:
            raise ValueError(
                "No steps found. Fast-track: create steps now via create_task_steps, then run approve_task."
            )
        # Enforce dependency gate right before transition
        if not is_unblocked(task, plan):
            raise ValueError(
                f"Task '{task.title}' is BLOCKED by unmet dependencies. Resolve blockers before starting."
            )
        logger.info(
            {
                "event": "approve_plan",
                "task_id": task.id,
                "corr_id": get_correlation_id(),
            }
        )
        with timer("approve_task.duration_ms", kind="plan", task_id=task.id):
            updated_task_data = task_service.update_task(
                story_id=story.id, task_id=task.id, status=Status.IN_PROGRESS
            )
        incr("approve_task.count", kind="plan")
        return {
            "success": True,
            "message": f"Task '{task.title}' approved and moved to IN_PROGRESS.",
            "changelog_snippet": None,
            **updated_task_data,
        }

    # Case 2: Approving a code review
    if task.status == Status.PENDING_REVIEW:
        logger.info(
            {
                "event": "approve_review",
                "task_id": task.id,
                "corr_id": get_correlation_id(),
            }
        )
        with timer("approve_task.duration_ms", kind="review", task_id=task.id):
            updated_task_data = task_service.update_task(
                story_id=story.id, task_id=task.id, status=Status.DONE
            )
        incr("approve_task.count", kind="review")

        # Generate changelog snippet
        updated_task = Task(**updated_task_data)
        changelog_snippet = generate_changelog_for_task(updated_task)

        return {
            "success": True,
            "message": f"Task '{task.title}' approved and moved to DONE.",
            "changelog_snippet": changelog_snippet,
            **updated_task_data,
        }

    # Case 3: Task is not in a reviewable state
    raise ValueError(
        f"The active task '{task.title}' is not in a reviewable state (current status: {task.status})."
    )


def submit_for_code_review(
    story_id: str, task_id: str, summary_text: str
) -> dict[str, Any]:
    """Submit a task for code review by setting execution summary and moving to PENDING_REVIEW.

    Args:
        story_id: The ID of the story containing the task
        task_id: The local ID of the task within the story
        summary_text: Summary of work completed (will be validated)

    Returns:
        dict: Updated task data

    Raises:
        ValueError: If task is not in IN_PROGRESS or summary validation fails
        KeyError: If story or task doesn't exist
    """
    # Validate execution summary
    summary_text = validate_execution_summary(summary_text)

    plan = plan_repository.load_current()
    _, task_obj, _ = _find_task(plan, story_id, task_id)

    if task_obj.status != Status.IN_PROGRESS:
        raise ValueError(
            f"Can only submit for review a task that is IN_PROGRESS. Current status is {task_obj.status}."
        )

    task_obj.execution_summary = summary_text
    # Persist the execution_summary so the subsequent update_task (which reloads the plan)
    # can see it when validating the transition to PENDING_REVIEW.
    plan_repository.save(plan, plan_id=plan.id)

    # Delegate to update_task to handle status transition and rollups
    return update_task(story_id=story_id, task_id=task_id, status=Status.PENDING_REVIEW)


def request_changes(story_id: str, task_id: str, feedback: str) -> dict[str, Any]:
    """Request changes for a task, moving it from PENDING_REVIEW back to IN_PROGRESS.

    Args:
        story_id: The ID of the story containing the task
        task_id: The local ID of the task within the story
        feedback: Feedback explaining what changes are needed (will be validated)

    Returns:
        Dict[str, Any]: Result containing success status and task data

    Raises:
        ValueError: If task is not in PENDING_REVIEW or feedback validation fails
        KeyError: If story or task doesn't exist
    """
    # Validate feedback input
    feedback = validate_feedback(feedback)

    plan = plan_repository.load_current()
    _, task, _ = _find_task(plan, story_id, task_id)

    if task.status != Status.PENDING_REVIEW:
        raise ValueError(
            f"Task '{task.title}' is not awaiting review. Current status: {task.status}."
        )

    # Log feedback and update rework count
    _log_review_feedback(plan.id, task, feedback)

    # Delegate to update_task for status change
    update_task(story_id=story_id, task_id=task_id, status=Status.IN_PROGRESS)

    return {
        "success": True,
        "message": f"Changes requested for task '{task.title}'. Moved to IN_PROGRESS.",
    }


def _log_review_feedback(plan_id: str, task: Task, feedback: str) -> None:
    """Helper to log review feedback and update task state."""
    try:
        append_event(
            plan_id,
            "review_changes_requested",
            {"task_id": task.id},
            {"feedback": feedback.strip()},
        )
    except Exception:
        logger.warning(
            f"Failed to log review_changes_requested event for task {task.id}"
        )

    try:
        task.review_feedback = (task.review_feedback or []) + [
            Task.ReviewFeedback(message=feedback.strip())
        ]
        task.rework_count = (getattr(task, "rework_count", 0) or 0) + 1
    except Exception:
        logger.warning(f"Failed to persist review feedback for task {task.id}")


def find_reviewable_tasks() -> list[Task]:
    """Finds all tasks across all stories that are in a reviewable state."""
    plan_id = plan_repository.get_current_plan_id()
    if not plan_id:
        return []
    plan = plan_repository.load(plan_id)

    reviewable = []
    for story in plan.stories:
        for task in story.tasks or []:
            is_pending_pre_review = task.status == Status.TODO and task.steps
            is_pending_code_review = task.status == Status.PENDING_REVIEW
            if is_pending_pre_review or is_pending_code_review:
                reviewable.append(task)
    return reviewable
