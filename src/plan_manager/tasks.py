import logging
from typing import Optional, List
from datetime import datetime, timezone

from pydantic import ValidationError

from plan_manager.story_model import Task, Story, ALLOWED_STATUSES
from plan_manager.plan import load_plan_data, save_plan_data
from plan_manager.story_utils import get_task_details_path, save_item_to_file, read_item_file, delete_item_file, update_story_file


logger = logging.getLogger(__name__)


def register_task_tools(mcp_instance) -> None:
    """Register task tools with the given FastMCP instance."""
    mcp_instance.tool()(create_task)
    mcp_instance.tool()(get_task)
    mcp_instance.tool()(update_task)
    mcp_instance.tool()(delete_task)
    mcp_instance.tool()(list_tasks)
    mcp_instance.tool()(explain_task_blockers)


def _generate_task_id_from_title(title: str) -> str:
    import re
    if not title:
        raise ValueError("Title cannot be empty when generating a task ID.")
    id_str = title.lower()
    id_str = re.sub(r'[^a-z0-9\s]+', ' ', id_str)
    id_str = re.sub(r'\s+', '_', id_str.strip())
    return id_str


def create_task(
    story_id: str,
    title: str,
    priority: str,
    depends_on: str,
    notes: str,
) -> dict:
    """Creates a new task under a story in plan.yaml.

    - priority: string '0'-'5' or '6' to unset
    - depends_on: CSV of task IDs (scoped to the same story) or fully-qualified 'other_story:task'
    - notes: string (empty means unset)
    """
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

    plan = load_plan_data()
    # Find story
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")

    # Build dependency list (store as fully qualified ids)
    dep_list: List[str] = []
    if depends_on:
        for token in [d.strip() for d in depends_on.split(',') if d.strip()]:
            dep_list.append(token)
    # Validate dependencies against plan
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
            # Local task id within the same story
            if f"{story_id}:{dep}" in existing_task_ids:
                continue
            raise ValueError(f"Dependency '{dep}' not found as story or local task in '{story_id}'.")

    # Generate unique task id within story
    task_local_id = _generate_task_id_from_title(title)
    fq_task_id = f"{story_id}:{task_local_id}"
    if story.tasks and any(t.id == fq_task_id for t in story.tasks):
        raise ValueError(f"task with ID '{fq_task_id}' already exists in story '{story_id}'.")

    # Create task
    try:
        task = Task(
            id=fq_task_id,
            title=title,
            status='TODO',
            depends_on=dep_list,
            notes=None if notes == '' else notes,
            creation_time=datetime.now(timezone.utc),
            priority=numeric_priority,
            story_id=story_id,
        )
    except ValidationError as e:
        logging.exception(f"Validation error creating new task '{fq_task_id}': {e}")
        raise ValueError(f"Validation error creating new task '{fq_task_id}': {e}") from e

    # Persist in plan
    story.tasks = (story.tasks or []) + [task]
    save_plan_data(plan)

    # Best-effort: create task details file with front matter
    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = get_task_details_path(story_id, local_task_id)
    try:
        save_item_to_file(task_details_path, {
            'schema_version': 1,
            'kind': 'task',
            'id': fq_task_id,
            'title': title,
            'status': 'TODO',
            'priority': numeric_priority,
            'depends_on': dep_list,
            'notes': None if notes == '' else notes,
            'creation_time': task.creation_time,
        }, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort creation of task file failed for '{fq_task_id}'.")

    # Best-effort: update story file tasks list in front matter
    try:
        update_story_file(story.details, story) if story.details else None
    except Exception:
        logging.info(f"Best-effort update of story file tasks list failed for '{story_id}'.")

    return task.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)


def get_task(story_id: str, task_id: str) -> dict:
    logging.info(f"Handling get_task: story_id='{story_id}', task_id='{task_id}'")
    plan = load_plan_data()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")
    # Prefer embedded plan data if available
    task_obj = next((t for t in story.tasks if t.id == fq_task_id), None)
    if task_obj:
        result = task_obj.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)
        # Enrich from front matter if present
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = get_task_details_path(story_id, local_task_id)
        front, _body = read_item_file(task_details_path)
        if front:
            result.setdefault('title', front.get('title'))
            result.setdefault('status', front.get('status'))
            if front.get('priority') is not None:
                result.setdefault('priority', front.get('priority'))
        return result
    # Fallback: read front matter only
    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = get_task_details_path(story_id, local_task_id)
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
    """Update an embedded Task in plan.yaml and mirror to file front matter.
    - Mutates fields directly on the Task object
    - Handles completion_time transitions on status changes
    - Best-effort sync to task and story files
    """
    logging.info(
        f"Handling update_task: story_id='{story_id}', task_id='{task_id}', updates(title={title is not None}, notes={notes is not None}, depends_on={depends_on is not None}, priority={priority is not None}, status={status is not None})"
    )
    plan = load_plan_data()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    # Find the embedded task
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next((t for t in story.tasks if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    # Apply title (ID is not changed here to avoid breaking references)
    if title is not None:
        task_obj.title = title

    # Apply notes
    if notes is not None:
        task_obj.notes = None if notes == '' else notes

    # Apply depends_on (CSV)
    if depends_on is not None:
        dep_list: List[str] = [d.strip() for d in depends_on.split(',') if d.strip()]
        # Validate
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

    # Apply priority
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

    # Apply status and completion_time transitions
    if status is not None:
        new_status_upper = status.strip().upper()
        if new_status_upper:
            if new_status_upper not in ALLOWED_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Allowed: {', '.join(sorted(list(ALLOWED_STATUSES)))}"
                )
            old_status = task_obj.status
            task_obj.status = new_status_upper
            if new_status_upper == 'DONE' and old_status != 'DONE':
                task_obj.completion_time = datetime.now(timezone.utc)
            elif new_status_upper != 'DONE' and old_status == 'DONE':
                task_obj.completion_time = None

    # Persist plan
    save_plan_data(plan)

    # Mirror to task front matter
    local_task_id = fq_task_id.split(':', 1)[1]
    task_details_path = get_task_details_path(story_id, local_task_id)
    try:
        save_item_to_file(task_details_path, task_obj, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort update of task file failed for '{fq_task_id}'.")
    
    # Roll up story status (simple heuristic)
    try:
        task_statuses = [t.status for t in (story.tasks or [])]
        if task_statuses:
            if all(s == 'DONE' for s in task_statuses):
                if story.status != 'DONE':
                    story.status = 'DONE'
                    story.completion_time = datetime.now(timezone.utc)
            elif any(s == 'IN_PROGRESS' for s in task_statuses):
                if story.status == 'DONE':
                    story.completion_time = None
                if story.status != 'IN_PROGRESS':
                    story.status = 'IN_PROGRESS'
            else:
                # If all TODO/BLOCKED/DEFERRED and none IN_PROGRESS/DONE
                if story.status == 'DONE':
                    story.completion_time = None
                if story.status not in ('TODO', 'BLOCKED', 'DEFERRED'):
                    story.status = 'TODO'
        save_plan_data(plan)
        if story.details:
            try:
                update_story_file(story.details, story)
            except Exception:
                logging.info(f"Best-effort rollup update of story file failed for '{story_id}'.")
    except Exception:
        logging.info(f"Best-effort story rollup failed for '{story_id}'.")

    return task_obj.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time', 'completion_time', 'notes', 'depends_on'}, exclude_none=True)


def delete_task(story_id: str, task_id: str) -> dict:
    logging.info(f"Handling delete_task: story_id='{story_id}', task_id='{task_id}'")
    plan = load_plan_data()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    if not story.tasks or not any(t.id == fq_task_id for t in story.tasks):
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    # Guard: prevent deletion if other tasks depend on this task
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
    save_plan_data(plan)
    # Best-effort delete the task file
    try:
        local_task_id = fq_task_id.split(':', 1)[1]
        task_details_path = get_task_details_path(story_id, local_task_id)
        delete_item_file(task_details_path)
    except Exception:
        logging.info(f"Best-effort delete of task file failed for '{fq_task_id}'.")
    # Best-effort: update story file tasks list in front matter
    try:
        update_story_file(story.details, story) if story.details else None
    except Exception:
        logging.info(f"Best-effort update of story file tasks list failed for '{story_id}'.")
    return {"success": True, "message": f"Successfully deleted task '{fq_task_id}'."}


def list_tasks(statuses: str, story_id: Optional[str] = None) -> list[dict]:
    """List tasks across plan, optionally filtering by statuses and story.
    Prefer embedded plan data, enrich with front matter when present.
    """
    logging.info(f"Handling list_tasks: statuses='{statuses}', story_id='{story_id}'")
    plan = load_plan_data()
    # Collect task objects
    tasks_index: List[tuple[Story, Task]] = []
    for s in plan.stories:
        if story_id and s.id != story_id:
            continue
        for t in (s.tasks or []):
            if isinstance(t, Task):
                tasks_index.append((s, t))

    # Parse filter
    normalized_statuses = None
    if statuses:
        tokens = [t.strip().upper() for t in statuses.split(',') if t.strip()]
        if tokens:
            normalized_statuses = set(tokens)

    results: List[dict] = []
    for s, t in tasks_index:
        sid, lid = s.id, t.id.split(':', 1)[1] if ':' in t.id else t.id
        item = t.model_dump(include={'id', 'title', 'status', 'priority', 'creation_time'}, exclude_none=True)
        # Enrich with front matter
        path = get_task_details_path(sid, lid)
        front, _body = read_item_file(path)
        if front:
            item.setdefault('title', front.get('title'))
            if front.get('priority') is not None:
                item.setdefault('priority', front.get('priority'))
        if normalized_statuses is None or item.get('status', 'TODO') in normalized_statuses:
            results.append(item)

    # Sort: priority asc (None last), creation_time asc (None last), id asc
    def _prio_key(v):
        p = v.get('priority')
        return p if p is not None else 6
    def _ctime_key(v):
        return (v.get('creation_time') is None, v.get('creation_time') or '9999')

    results.sort(key=lambda v: (_prio_key(v), _ctime_key(v), v['id']))
    return results


def explain_task_blockers(story_id: str, task_id: str) -> dict:
    """Explain why a task is blocked by enumerating non-DONE dependencies.

    Returns:
      {
        id, title, status,
        blockers: [ { type: 'task'|'story', id, status, reason } ],
        unblocked: bool
      }
    """
    logging.info(f"Handling explain_task_blockers: story_id='{story_id}', task_id='{task_id}'")
    plan = load_plan_data()
    story: Optional[Story] = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    fq_task_id = f"{story_id}:{task_id}" if ':' not in task_id else task_id
    task_obj: Optional[Task] = next((t for t in story.tasks if t.id == fq_task_id), None)
    if not task_obj:
        raise KeyError(f"task with ID '{fq_task_id}' not found under story '{story_id}'.")

    blockers: List[dict] = []
    deps = task_obj.depends_on or []
    # Build indices for quick lookup
    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: (s.id, t) for s in plan.stories for t in (s.tasks or [])}

    for dep in deps:
        if ':' in dep:
            # Task dependency
            tinfo = task_index.get(dep)
            if not tinfo:
                blockers.append({'type': 'task', 'id': dep, 'status': 'UNKNOWN', 'reason': 'Dependency not found'})
                continue
            _sid, dep_task = tinfo
            if dep_task.status != 'DONE':
                blockers.append({'type': 'task', 'id': dep_task.id, 'status': dep_task.status, 'reason': 'Task not DONE'})
        else:
            # Could be a story or a local task id within this story
            if dep in story_index:
                dep_story = story_index[dep]
                if dep_story.status != 'DONE':
                    blockers.append({'type': 'story', 'id': dep_story.id, 'status': dep_story.status, 'reason': 'Story not DONE'})
            else:
                fq_local = f"{story_id}:{dep}"
                tinfo = task_index.get(fq_local)
                if not tinfo:
                    blockers.append({'type': 'task', 'id': fq_local, 'status': 'UNKNOWN', 'reason': 'Dependency not found'})
                    continue
                _sid, dep_task = tinfo
                if dep_task.status != 'DONE':
                    blockers.append({'type': 'task', 'id': dep_task.id, 'status': dep_task.status, 'reason': 'Task not DONE'})

    # Enrich with titles from front matter where possible (best-effort)
    try:
        local_task_id = fq_task_id.split(':', 1)[1]
        front, _ = read_item_file(get_task_details_path(story_id, local_task_id))
        title = front.get('title', task_obj.title)
    except Exception:
        title = task_obj.title

    return {
        'id': fq_task_id,
        'title': title,
        'status': task_obj.status,
        'blockers': blockers,
        'unblocked': len(blockers) == 0,
    }

