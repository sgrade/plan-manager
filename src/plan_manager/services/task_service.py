import logging
from typing import Optional, List

from pydantic import ValidationError

from plan_manager.domain.models import Task, Story, Status
from plan_manager.services import plan_repository as plan_repo
from plan_manager.io.paths import task_file_path
from plan_manager.io.file_mirror import save_item_to_file, read_item_file, delete_item_file
from plan_manager.services.status import rollup_story_status, apply_status_change
from plan_manager.config import (
    REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS,
    REQUIRE_EXECUTION_SUMMARY_BEFORE_DONE,
)
from plan_manager.services.shared import guard_approval_before_progress
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
    merge_frontmatter_defaults
)


logger = logging.getLogger(__name__)


def _generate_task_id_from_title(title: str) -> str:
    return generate_slug(title)


def create_task(story_id: str, title: str, priority: Optional[int], depends_on: List[str], description: Optional[str]) -> dict:
    logger.info(
        f"Handling create_task: story_id='{story_id}', title='{title}', priority='{priority}', depends_on={depends_on}"
    )
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
                                   'id', 'title', 'status', 'priority', 'creation_time', 'description', 'depends_on'}, exclude_none=True)
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


def update_task(
    story_id: str,
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    priority: Optional[int] = None,
    status: Optional[Status] = None,
    execution_summary: Optional[str] = None,
) -> dict:
    plan = plan_repo.load_current()
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next(
        (t for t in story.tasks if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(
            f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    if title is not None:
        task_obj.title = title
    if description is not None:
        task_obj.description = description
    if depends_on is not None:
        task_obj.depends_on = depends_on
    if priority is not None:
        task_obj.priority = priority
    if status is not None:
        # Optional guardrails: require intent before IN_PROGRESS; summary before DONE
        if status == Status.IN_PROGRESS and REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS:
            if not getattr(task_obj, 'execution_intent', None):
                raise ValueError(
                    "Execution intent is required before starting work (IN_PROGRESS).")
        if status == Status.DONE and REQUIRE_EXECUTION_SUMMARY_BEFORE_DONE:
            summary_value = execution_summary if execution_summary is not None else getattr(
                task_obj, 'execution_summary', None)
            if not summary_value:
                raise ValueError(
                    "Execution summary is required before marking DONE.")

        guard_approval_before_progress(
            task_obj.status, status, getattr(task_obj, 'approval', None),
        )
        prev = task_obj.status
        apply_status_change(task_obj, status)
        if prev != task_obj.status:
            append_event(plan.id, 'task_status_changed', {'task_id': task_obj.id}, {
                         'from': prev.value if hasattr(prev, 'value') else prev, 'to': task_obj.status.value if hasattr(task_obj.status, 'value') else task_obj.status})
    if execution_summary is not None:
        task_obj.execution_summary = execution_summary

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
    apply_status_change(story, next_story_status)
    plan_repo.save(plan, plan_id=plan.id)
    if story.file_path:
        try:
            save_item_to_file(story.file_path, story,
                              content=None, overwrite=False)
        except Exception:
            logger.info(
                f"Best-effort rollup update of story file failed for '{story_id}'.")

    # Selection invariants: if current task was completed, auto-advance/reset
    try:
        current_tid = get_current_task_id(plan.id)
        if current_tid == task_obj.id and task_obj.status == Status.DONE:
            # Prefer IN_PROGRESS tasks first
            next_id: Optional[str] = None
            for t in (story.tasks or []):
                if t.id != task_obj.id and t.status == Status.IN_PROGRESS:
                    next_id = t.id
                    break
            # If none in progress, choose first TODO that is unblocked
            if next_id is None:
                try:
                    for t in (story.tasks or []):
                        if t.id == task_obj.id or t.status != Status.TODO:
                            continue
                        local = t.id.split(':', 1)[1] if ':' in t.id else t.id
                        # type: ignore[name-defined]
                        info = explain_task_blockers(story.id, local)
                        if info and info.get('unblocked', False):
                            next_id = t.id
                            break
                except Exception:
                    # Fallback: keep behavior even if blocker analysis fails
                    pass
            if next_id is not None:
                set_Current = set_current_task_id  # alias to preserve indentation pattern
                set_Current(next_id, plan.id)
            else:
                # No next task; clear selection
                set_current_task_id(None, plan.id)
        # If story rolled up to DONE and it's current, clear story and task selections
        if prev_story_status != story.status and story.status == Status.DONE:
            current_sid = get_current_story_id(plan.id)
            if current_sid == story.id:
                set_current_task_id(None, plan.id)
                set_current_story_id(None, plan.id)
    except Exception:
        # Best-effort; do not block primary update on selection maintenance
        pass

    return task_obj.model_dump(mode='json', include={'id', 'title', 'status', 'priority', 'creation_time', 'completion_time', 'description', 'depends_on'}, exclude_none=True)


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


def explain_task_blockers(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load()
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next(
        (t for t in story.tasks if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(
            f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    blockers: List[dict] = []
    deps = task_obj.depends_on or []
    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: (s.id, t)
                  for s in plan.stories for t in (s.tasks or [])}

    for dep in deps:
        if ':' in dep:
            tinfo = task_index.get(dep)
            if not tinfo:
                blockers.append(
                    {'type': 'task', 'id': dep, 'status': 'UNKNOWN', 'reason': 'Dependency not found'})
                continue
            _sid, dep_task = tinfo
            dep_status = dep_task.status.value if isinstance(
                dep_task.status, Status) else dep_task.status
            if dep_status != 'DONE':
                blockers.append({'type': 'task', 'id': dep_task.id,
                                'status': dep_status, 'reason': 'Task not DONE'})
        else:
            if dep in story_index:
                dep_story = story_index[dep]
                dep_status = dep_story.status.value if hasattr(dep_story, 'status') and hasattr(
                    dep_story.status, 'value') else dep_story.status
                if dep_status != 'DONE':
                    blockers.append({'type': 'story', 'id': dep_story.id,
                                    'status': dep_status, 'reason': 'Story not DONE'})
            else:
                fq_local = f"{story_id}:{dep}"
                tinfo = task_index.get(fq_local)
                if not tinfo:
                    blockers.append(
                        {'type': 'task', 'id': fq_local, 'status': 'UNKNOWN', 'reason': 'Dependency not found'})
                    continue
                _sid, dep_task = tinfo
                dep_status = dep_task.status.value if isinstance(
                    dep_task.status, Status) else dep_task.status
                if dep_status != 'DONE':
                    blockers.append({'type': 'task', 'id': dep_task.id,
                                    'status': dep_status, 'reason': 'Task not DONE'})

    try:
        local_task_id = fq_task_id.split(':', 1)[1]
        front, _ = read_item_file(task_file_path(story_id, local_task_id))
        title = front.get('title', task_obj.title)
    except Exception:
        title = task_obj.title

    return {
        'id': fq_task_id,
        'title': title,
        'status': task_obj.status.value if isinstance(task_obj.status, Status) else task_obj.status,
        'blockers': blockers,
        'unblocked': len(blockers) == 0,
    }
