import logging

from typing import Optional, List
from pydantic import ValidationError

from plan_manager.domain.models import Task, Story, Status, Plan
from plan_manager.services import plan_repository as plan_repo
from plan_manager.io.paths import task_file_path
from plan_manager.io.file_mirror import save_item_to_file, read_item_file, delete_item_file
from plan_manager.services.status_utils import rollup_story_status, apply_status_change
from plan_manager.services.activity_repository import append_event
from plan_manager.services.state_repository import (
    get_current_task_id,
    set_current_task_id,
    get_current_story_id,
    set_current_story_id,
)
from plan_manager.services.shared import (
    generate_slug,
    ensure_unique_id_from_set,
    validate_and_save,
    write_task_details,
    write_story_details,
    find_dependents,
    merge_frontmatter_defaults,
    is_unblocked,
)
from plan_manager.logging_context import get_correlation_id


logger = logging.getLogger(__name__)


def _update_dependent_task_statuses(plan: Plan):
    """
    Iterates through all tasks and updates their status to BLOCKED or TODO
    based on the current state of their dependencies.
    """
    logger.debug(f"Running blocker status update for plan '{plan.id}'.")
    for story in plan.stories:
        for task in (story.tasks or []):
            if task.status in [Status.TODO, Status.BLOCKED]:
                currently_unblocked = is_unblocked(task, plan)

                if task.status == Status.TODO and not currently_unblocked:
                    task.status = Status.BLOCKED
                    logger.info(
                        f"Task '{task.id}' is now BLOCKED due to unmet dependencies.")
                elif task.status == Status.BLOCKED and currently_unblocked:
                    task.status = Status.TODO
                    logger.info(
                        f"Task '{task.id}' is now UNBLOCKED and set to TODO.")


def _find_task(plan, story_id, task_id):
    """Helper to find a task and its story, returning (story, task) or raising KeyError."""
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"Story with ID '{story_id}' not found.")

    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next(
        (t for t in (story.tasks or []) if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(
            f"Task with ID '{fq_task_id}' not found under story '{story_id}'.")
    return story, task_obj, fq_task_id


def _generate_task_id_from_title(title: str) -> str:
    return generate_slug(title)


def create_task(story_id: str, title: str, priority: Optional[int], depends_on: List[str], description: Optional[str]) -> dict:
    logger.info({
        'event': 'create_task',
        'story_id': story_id,
        'title': title,
        'priority': priority,
        'depends_on': depends_on,
        'corr_id': get_correlation_id(),
    })
    plan = plan_repo.load_current()
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")

    task_local_id = _generate_task_id_from_title(title)
    fq_task_id = f"{story_id}:{task_local_id}"
    existing_locals = [t.id.split(
        ':', 1)[1] if ':' in t.id else t.id for t in (story.tasks or [])]
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
        )
    except ValidationError as e:
        logger.exception(
            f"Validation error creating new task '{fq_task_id}': {e}")
        raise ValueError(
            f"Validation error creating new task '{fq_task_id}': {e}") from e

    story.tasks = (story.tasks or []) + [task]
    validate_and_save(plan)

    try:
        write_task_details(task)
    except Exception:
        logger.info(
            f"Best-effort creation of task file failed for '{fq_task_id}'.")

    try:
        write_story_details(story)
    except Exception:
        logger.info(
            f"Best-effort update of story file tasks list failed for '{story_id}'.")

    return task.model_dump(mode='json', include={'id', 'title', 'status', 'priority', 'creation_time', 'description', 'depends_on'}, exclude_none=True)


def get_task(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load_current()
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(
            f"task with ID '{fq_task_id}' not found under story '{story_id}'.")
    task_obj = next((t for t in story.tasks if t.id == fq_task_id), None)
    if task_obj:
        base = task_obj.model_dump(include={
                                   'id', 'title', 'status', 'priority', 'creation_time', 'description', 'execution_summary', 'depends_on'}, exclude_none=True)
        # Normalize datetime fields to ISO strings for transport schema expectations
        ct = base.get('creation_time')
        try:
            # Pydantic BaseModel dumps datetime by default; ensure str
            if hasattr(ct, 'isoformat'):
                base['creation_time'] = ct.isoformat()
        except Exception:
            base['creation_time'] = None
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = task_file_path(story_id, local_task_id)
        return merge_frontmatter_defaults(task_details_path, base)
    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    front, _body = read_item_file(task_details_path)
    if front:
        out = {'id': front.get('id', fq_task_id), 'title': front.get(
            'title', local_task_id.replace('_', ' ')), 'status': front.get('status', 'TODO')}
        for k in ('priority', 'creation_time', 'description', 'depends_on'):
            if front.get(k) is not None:
                out[k] = front.get(k)
        return out
    return {"id": fq_task_id, "title": local_task_id.replace('_', ' '), "status": "TODO"}


def create_steps(story_id: str, task_id: str, steps: List[dict]) -> dict:
    """Sets the implementation steps for a task, making it ready for pre-execution review.

    Expects a list of step dicts with 'title' and optional 'description'.
    """
    plan = plan_repo.load_current()
    story, task_obj, _fq_task_id = _find_task(plan, story_id, task_id)

    if task_obj.status not in [Status.TODO, Status.IN_PROGRESS]:
        raise ValueError(
            f"Can only propose a plan for a task in TODO or IN_PROGRESS status. Current status is {task_obj.status}.")

    # Validate and coerce into Step models
    new_steps: List[Task.Step] = []
    for s in (steps or []):
        if not isinstance(s, dict) or 'title' not in s:
            raise ValueError(
                "Each step must be an object with at least a 'title'.")
        new_steps.append(
            Task.Step(title=s['title'], description=s.get('description')))
    task_obj.steps = new_steps

    # Re-assign the tasks list to ensure the parent model detects the change.
    story.tasks = [t for t in (story.tasks or [])]

    validate_and_save(plan)
    return task_obj.model_dump(mode='json', exclude_none=True)


def submit_for_code_review(story_id: str, task_id: str, summary_text: str) -> dict:
    """Sets the execution summary and moves the task to PENDING_REVIEW."""
    plan = plan_repo.load_current()
    story, task_obj, _fq_task_id = _find_task(plan, story_id, task_id)

    if task_obj.status != Status.IN_PROGRESS:
        raise ValueError(
            f"Can only submit for review a task that is IN_PROGRESS. Current status is {task_obj.status}.")

    task_obj.execution_summary = summary_text

    prev_status = task_obj.status
    apply_status_change(task_obj, Status.PENDING_REVIEW)
    append_event(plan.id, 'task_status_changed', {'task_id': task_obj.id}, {
        'from': prev_status.value, 'to': task_obj.status.value
    })

    # Trigger story status rollup
    prev_story_status = story.status
    next_story_status = rollup_story_status(
        [t.status for t in (story.tasks or [])])
    if prev_story_status != next_story_status:
        apply_status_change(story, next_story_status)

    validate_and_save(plan)
    return task_obj.model_dump(mode='json', exclude_none=True)


def update_task(
    story_id: str,
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    priority: Optional[int] = None,
    status: Optional[Status] = None,
) -> dict:
    plan = plan_repo.load_current()
    story, task_obj, fq_task_id = _find_task(plan, story_id, task_id)

    # Prevent starting a blocked task
    if status == Status.IN_PROGRESS and task_obj.status == Status.TODO:
        if not is_unblocked(task_obj, plan):
            raise ValueError(
                f"Task '{task_obj.title}' cannot be started because it is blocked by one or more dependencies.")

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
                    "An implementation plan must be approved before starting work.")
            apply_status_change(task_obj, status)
        elif status == Status.DONE and prev_status == Status.PENDING_REVIEW:
            if not task_obj.execution_summary:
                raise ValueError(
                    "An execution summary must be provided before marking as DONE.")
            apply_status_change(task_obj, status)
            # After a task is done, re-evaluate blockers across the plan
            _update_dependent_task_statuses(plan)
        elif status == prev_status:
            pass  # No change
        else:
            raise ValueError(
                f"Invalid status transition from {prev_status} to {status}.")

        if prev_status != task_obj.status:
            append_event(plan.id, 'task_status_changed', {'task_id': task_obj.id}, {
                         'from': prev_status.value, 'to': task_obj.status.value})

    validate_and_save(plan)

    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    try:
        save_item_to_file(task_details_path, task_obj,
                          content=None, overwrite=False)
    except Exception:
        logger.info(
            f"Best-effort update of task file failed for '{fq_task_id}'.")

    prev_story_status = story.status
    next_story_status = rollup_story_status(
        [t.status for t in (story.tasks or [])])
    if prev_story_status != next_story_status:
        apply_status_change(story, next_story_status)
        # Save again if story status changed
        plan_repo.save(plan, plan_id=plan.id)
        if story.file_path:
            try:
                save_item_to_file(story.file_path, story,
                                  content=None, overwrite=False)
            except Exception:
                logger.info(
                    f"Best-effort rollup update of story file failed for '{story_id}'.")

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

    return task_obj.model_dump(mode='json', exclude_none=True)


def delete_task(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load_current()
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(
            f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    dependents = find_dependents(plan, fq_task_id)
    if dependents:
        raise ValueError(
            f"Cannot delete task '{fq_task_id}' because it is a dependency of: {', '.join(dependents)}"
        )

    story.tasks = [t for t in (story.tasks or []) if t.id != fq_task_id]
    plan_repo.save(plan)
    try:
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = task_file_path(story_id, local_task_id)
        delete_item_file(task_details_path)
    except Exception:
        logger.info(
            f"Best-effort delete of task file failed for '{fq_task_id}'.")
    try:
        if story.file_path:
            save_item_to_file(story.file_path, story,
                              content=None, overwrite=False)
    except Exception:
        logger.info(
            f"Best-effort update of story file tasks list failed for '{story_id}'.")
    # Selection invariants: if deleted task was current, auto-advance/reset
    try:
        current_tid = get_current_task_id(plan.id)
        if current_tid == fq_task_id:
            # Prefer next TODO/IN_PROGRESS task
            for t in (story.tasks or []):
                if t.status in (Status.TODO, Status.IN_PROGRESS):
                    set_current_task_id(t.id, plan.id)
                    break
            else:
                set_current_task_id(None, plan.id)
    except Exception:
        pass

    return {"success": True, "message": f"Successfully deleted task '{fq_task_id}'."}


def list_tasks(statuses: Optional[List[Status]], story_id: Optional[str] = None) -> List[Task]:
    plan = plan_repo.load_current()
    tasks: List[Task] = []
    for s in plan.stories:
        if story_id and s.id != story_id:
            continue
        for t in (s.tasks or []):
            if isinstance(t, Task):
                tasks.append(t)

    allowed_statuses = set(statuses) if statuses else None

    filtered: List[Task] = []
    for t in tasks:
        if allowed_statuses is not None and t.status not in allowed_statuses:
            continue
        filtered.append(t)

    def _prio_key(task: Task):
        return task.priority if task.priority is not None else 6

    def _ctime_key(task: Task):
        return (task.creation_time is None, task.creation_time or '9999')

    filtered.sort(key=lambda t: (_prio_key(t), _ctime_key(t), t.id))
    return filtered
