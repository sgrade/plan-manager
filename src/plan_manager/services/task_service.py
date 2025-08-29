import logging
from typing import Optional, List
from datetime import datetime, timezone

from pydantic import ValidationError

from plan_manager.domain.models import Task, Story, Status
from plan_manager.services import plan_repository as plan_repo
from plan_manager.io.paths import task_file_path, slugify
from plan_manager.io.file_mirror import save_item_to_file, read_item_file, delete_item_file
from plan_manager.services.status import rollup_story_status, apply_status_change


logger = logging.getLogger(__name__)


def _generate_task_id_from_title(title: str) -> str:
    return slugify(title)


def create_task(story_id: str, title: str, priority: str, depends_on: str, notes: str) -> dict:
    logging.info(
        f"Handling create_task: story_id='{story_id}', title='{title}', priority='{priority}', depends_on='{depends_on}'"
    )

    numeric_priority: Optional[int] = None
    if priority == "6":
        numeric_priority = None
    elif priority == "":
        raise ValueError("Priority string cannot be empty. Use '6' for no priority.")
    else:
        try:
            numeric_priority = int(priority)
        except ValueError as e:
            raise ValueError(
                f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' for no priority."
            ) from e

    plan = plan_repo.load()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")

    dep_list: List[str] = []
    if depends_on:
        for token in [d.strip() for d in depends_on.split(',') if d.strip()]:
            dep_list.append(token)

    existing_story_ids = {s.id for s in plan.stories}
    existing_task_ids = {t.id for s in plan.stories for t in (s.tasks or []) if hasattr(t, 'id')}
    for dep in dep_list:
        if ':' in dep:
            if dep in existing_task_ids:
                continue
            raise ValueError(f"Dependency task '{dep}' not found.")
        else:
            if dep in existing_story_ids:
                continue
            if f"{story_id}:{dep}" in existing_task_ids:
                continue
            raise ValueError(f"Dependency '{dep}' not found as story or local task in '{story_id}'.")

    task_local_id = _generate_task_id_from_title(title)
    fq_task_id = f"{story_id}:{task_local_id}"
    if story.tasks and any(t.id == fq_task_id for t in story.tasks):
        raise ValueError(f"task with ID '{fq_task_id}' already exists in story '{story_id}'.")

    try:
        task = Task(
            id=fq_task_id,
            title=title,
            status=Status.TODO,
            depends_on=dep_list,
            notes=None if notes == '' else notes,
            creation_time=datetime.now(timezone.utc),
            priority=numeric_priority,
            story_id=story_id,
        )
    except ValidationError as e:
        logging.exception(f"Validation error creating new task '{fq_task_id}': {e}")
        raise ValueError(f"Validation error creating new task '{fq_task_id}': {e}") from e

    story.tasks = (story.tasks or []) + [task]
    plan_repo.save(plan)

    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    try:
        save_item_to_file(task_details_path, {
            'schema_version': 1,
            'kind': 'task',
            'id': fq_task_id,
            'title': title,
            'status': Status.TODO.value,
            'priority': numeric_priority,
            'depends_on': dep_list,
            'notes': None if notes == '' else notes,
            'creation_time': task.creation_time,
        }, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort creation of task file failed for '{fq_task_id}'.")

    try:
        if story.details:
            save_item_to_file(story.details, story, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort update of story file tasks list failed for '{story_id}'.")

    return task.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)


def get_task(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")
    task_obj = next((t for t in story.tasks if t.id == fq_task_id), None)
    if task_obj:
        result = task_obj.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = task_file_path(story_id, local_task_id)
        front, _body = read_item_file(task_details_path)
        if front:
            result.setdefault('title', front.get('title'))
            result.setdefault('status', front.get('status'))
            if front.get('priority') is not None:
                result.setdefault('priority', front.get('priority'))
        return result
    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    front, _body = read_item_file(task_details_path)
    if front:
        out = {'id': front.get('id', fq_task_id), 'title': front.get('title', local_task_id.replace('_', ' ')), 'status': front.get('status', 'TODO')}
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
    depends_on: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    plan = plan_repo.load()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next((t for t in story.tasks if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    if title is not None:
        task_obj.title = title
    if notes is not None:
        task_obj.notes = None if notes == '' else notes
    if depends_on is not None:
        dep_list: List[str] = [d.strip() for d in depends_on.split(',') if d.strip()]
        existing_story_ids = {s.id for s in plan.stories}
        existing_task_ids = {t.id for s in plan.stories for t in (s.tasks or []) if hasattr(t, 'id')}
        for dep in dep_list:
            if ':' in dep:
                if dep not in existing_task_ids:
                    raise ValueError(f"Dependency task '{dep}' not found.")
            else:
                if dep not in existing_story_ids and f"{story_id}:{dep}" not in existing_task_ids:
                    raise ValueError(f"Dependency '{dep}' not found as story or local task in '{story_id}'.")
        task_obj.depends_on = dep_list
    if priority is not None:
        if priority.strip() == "":
            pass
        elif priority == "6":
            task_obj.priority = None
        else:
            try:
                task_obj.priority = int(priority)
            except ValueError as e:
                raise ValueError(
                    f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' to remove priority."
                ) from e
    if status is not None:
        new_status_upper = status.strip().upper()
        if new_status_upper:
            try:
                new_status = Status(new_status_upper)
            except Exception as e:
                raise ValueError(
                    f"Invalid status '{status}'. Allowed: {', '.join([s.value for s in Status])}"
                ) from e
            apply_status_change(task_obj, new_status)

    plan_repo.save(plan)

    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = task_file_path(story_id, local_task_id)
    try:
        save_item_to_file(task_details_path, task_obj, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort update of task file failed for '{fq_task_id}'.")

    next_story_status = rollup_story_status([t.status for t in (story.tasks or [])])
    apply_status_change(story, next_story_status)
    plan_repo.save(plan)
    if story.details:
        try:
            save_item_to_file(story.details, story, content=None, overwrite=False)
        except Exception:
            logging.info(f"Best-effort rollup update of story file failed for '{story_id}'.")

    return task_obj.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'completion_time', 'notes', 'depends_on'}, exclude_none=True)


def delete_task(story_id: str, task_id: str) -> dict:
    plan = plan_repo.load()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    dependents: List[str] = []
    for s in plan.stories:
        for t in (s.tasks or []):
            for dep in (t.depends_on or []):
                if dep == fq_task_id or (s.id == story_id and dep == task_id):
                    dependents.append(t.id)
    if dependents:
        raise ValueError(
            f"Cannot delete task '{fq_task_id}' because it is a dependency of: {', '.join(sorted(dependents))}"
        )

    story.tasks = [t for t in (story.tasks or []) if t.id != fq_task_id]
    plan_repo.save(plan)
    try:
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = task_file_path(story_id, local_task_id)
        delete_item_file(task_details_path)
    except Exception:
        logging.info(f"Best-effort delete of task file failed for '{fq_task_id}'.")
    try:
        if story.details:
            save_item_to_file(story.details, story, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort update of story file tasks list failed for '{story_id}'.")
    return {"success": True, "message": f"Successfully deleted task '{fq_task_id}'."}


def list_tasks(statuses: str, story_id: Optional[str] = None) -> list[dict]:
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
        tokens = [t.strip().upper() for t in statuses.split(',') if t.strip()]
        if tokens:
            normalized_statuses = set(tokens)

    results: List[dict] = []
    for s, t in tasks_index:
        sid, lid = s.id, t.id.split(':', 1)[1] if ':' in t.id else t.id
        item = t.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time'}, exclude_none=True)
        path = task_file_path(sid, lid)
        front, _body = read_item_file(path)
        if front:
            item.setdefault('title', front.get('title'))
            if front.get('priority') is not None:
                item.setdefault('priority', front.get('priority'))
        status_val = item.get('status')
        status_str = status_val.value if isinstance(status_val, Status) else (status_val or 'TODO')
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
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next((t for t in story.tasks if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    blockers: List[dict] = []
    deps = task_obj.depends_on or []
    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: (s.id, t) for s in plan.stories for t in (s.tasks or [])}

    for dep in deps:
        if ':' in dep:
            tinfo = task_index.get(dep)
            if not tinfo:
                blockers.append({'type': 'task', 'id': dep, 'status': 'UNKNOWN', 'reason': 'Dependency not found'})
                continue
            _sid, dep_task = tinfo
            dep_status = dep_task.status.value if isinstance(dep_task.status, Status) else dep_task.status
            if dep_status != 'DONE':
                blockers.append({'type': 'task', 'id': dep_task.id, 'status': dep_status, 'reason': 'Task not DONE'})
        else:
            if dep in story_index:
                dep_story = story_index[dep]
                dep_status = dep_story.status.value if hasattr(dep_story, 'status') and hasattr(dep_story.status, 'value') else dep_story.status
                if dep_status != 'DONE':
                    blockers.append({'type': 'story', 'id': dep_story.id, 'status': dep_status, 'reason': 'Story not DONE'})
            else:
                fq_local = f"{story_id}:{dep}"
                tinfo = task_index.get(fq_local)
                if not tinfo:
                    blockers.append({'type': 'task', 'id': fq_local, 'status': 'UNKNOWN', 'reason': 'Dependency not found'})
                    continue
                _sid, dep_task = tinfo
                dep_status = dep_task.status.value if isinstance(dep_task.status, Status) else dep_task.status
                if dep_status != 'DONE':
                    blockers.append({'type': 'task', 'id': dep_task.id, 'status': dep_status, 'reason': 'Task not DONE'})

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
