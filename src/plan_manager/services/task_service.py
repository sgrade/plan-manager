import logging
from typing import Optional, List

from pydantic import ValidationError

from plan_manager.domain.models import Task, Story, Status
from plan_manager.services import plan_repository as plan_repo
from plan_manager.io.paths import task_file_path
from plan_manager.io.file_mirror import save_item_to_file, read_item_file, delete_item_file
from plan_manager.services.status import rollup_story_status, apply_status_change
from plan_manager.services.shared import (
    generate_slug,
    validate_and_save,
    write_task_details,
    write_story_details,
    find_dependents,
    merge_frontmatter_defaults
)


logger = logging.getLogger(__name__)


def _generate_task_id_from_title(title: str) -> str:
    return generate_slug(title)


def create_task(story_id: str, title: str, priority: Optional[int], depends_on: List[str], notes: Optional[str]) -> dict:
    logging.info(
        f"Handling create_task: story_id='{story_id}', title='{title}', priority='{priority}', depends_on={depends_on}"
    )
    plan = plan_repo.load()
    story: Optional[Story] = next(
        (s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")

    task_local_id = _generate_task_id_from_title(title)
    fq_task_id = f"{story_id}:{task_local_id}"
    if story.tasks and any(t.id == fq_task_id for t in story.tasks):
        raise ValueError(
            f"task with ID '{fq_task_id}' already exists in story '{story_id}'.")

    try:
        task = Task(
            id=fq_task_id,
            title=title,
            depends_on=depends_on,
            notes=notes,
            priority=priority,
            story_id=story_id,
        )
    except ValidationError as e:
        logging.exception(
            f"Validation error creating new task '{fq_task_id}': {e}")
        raise ValueError(
            f"Validation error creating new task '{fq_task_id}': {e}") from e

    story.tasks = (story.tasks or []) + [task]
    validate_and_save(plan)

    try:
        write_task_details(task)
    except Exception:
        logging.info(
            f"Best-effort creation of task file failed for '{fq_task_id}'.")

    try:
        write_story_details(story)
    except Exception:
        logging.info(
            f"Best-effort update of story file tasks list failed for '{story_id}'.")

    return task.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)


def get_task(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load()
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
                                   'id', 'title', 'status', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = task_file_path(story_id, local_task_id)
        return merge_frontmatter_defaults(task_details_path, base)
    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    front, _body = read_item_file(task_details_path)
    if front:
        out = {'id': front.get('id', fq_task_id), 'title': front.get(
            'title', local_task_id.replace('_', ' ')), 'status': front.get('status', 'TODO')}
        for k in ('priority', 'creation_time', 'notes', 'depends_on'):
            if front.get(k) is not None:
                out[k] = front.get(k)
        return out
    return {"id": fq_task_id, "title": local_task_id.replace('_', ' '), "status": "TODO"}


def update_task(
    story_id: str,
    task_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    priority: Optional[int] = None,
    status: Optional[Status] = None,
) -> dict:
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

    if title is not None:
        task_obj.title = title
    if notes is not None:
        task_obj.notes = notes
    if depends_on is not None:
        task_obj.depends_on = depends_on
    if priority is not None:
        task_obj.priority = priority
    if status is not None:
        apply_status_change(task_obj, status)

    validate_and_save(plan)

    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    try:
        save_item_to_file(task_details_path, task_obj,
                          content=None, overwrite=False)
    except Exception:
        logging.info(
            f"Best-effort update of task file failed for '{fq_task_id}'.")

    next_story_status = rollup_story_status(
        [t.status for t in (story.tasks or [])])
    apply_status_change(story, next_story_status)
    plan_repo.save(plan)
    if story.details:
        try:
            save_item_to_file(story.details, story,
                              content=None, overwrite=False)
        except Exception:
            logging.info(
                f"Best-effort rollup update of story file failed for '{story_id}'.")

    return task_obj.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'completion_time', 'notes', 'depends_on'}, exclude_none=True)


def delete_task(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load()
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
        logging.info(
            f"Best-effort delete of task file failed for '{fq_task_id}'.")
    try:
        if story.details:
            save_item_to_file(story.details, story,
                              content=None, overwrite=False)
    except Exception:
        logging.info(
            f"Best-effort update of story file tasks list failed for '{story_id}'.")
    return {"success": True, "message": f"Successfully deleted task '{fq_task_id}'."}


def list_tasks(statuses: Optional[List[str]], story_id: Optional[str] = None) -> list[dict]:
    plan = plan_repo.load()
    tasks_index: List[tuple[Story, Task]] = []
    for s in plan.stories:
        if story_id and s.id != story_id:
            continue
        for t in (s.tasks or []):
            if isinstance(t, Task):
                tasks_index.append((s, t))

    normalized_statuses = None
    if statuses:
        tokens = [t.strip().upper() for t in statuses if t and t.strip()]
        if tokens:
            normalized_statuses = set(tokens)

    results: List[dict] = []
    for s, t in tasks_index:
        sid, lid = s.id, t.id.split(':', 1)[1] if ':' in t.id else t.id
        base = t.model_dump(
            include={'id', 'title', 'status', 'priority', 'creation_time'}, exclude_none=True)
        path = task_file_path(sid, lid)
        item = merge_frontmatter_defaults(path, base)
        status_val = item.get('status')
        status_str = status_val.value if isinstance(
            status_val, Status) else (status_val or 'TODO')
        if normalized_statuses is None or status_str in normalized_statuses:
            results.append(item)

    def _prio_key(v):
        p = v.get('priority')
        return p if p is not None else 6

    def _ctime_key(v):
        return (v.get('creation_time') is None, v.get('creation_time') or '9999')

    results.sort(key=lambda v: (_prio_key(v), _ctime_key(v), v['id']))
    return results


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
