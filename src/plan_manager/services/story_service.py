import logging
import os
import shutil
from typing import Optional, List

from pydantic import ValidationError

from plan_manager.domain.models import Story, Status
from plan_manager.services import plan_repository as plan_repo
from plan_manager.io.paths import story_file_path
from plan_manager.io.file_mirror import save_item_to_file, delete_item_file
from plan_manager.services.shared import (
    generate_slug,
    ensure_unique_id_from_set,
    validate_and_save,
    write_story_details,
)
from plan_manager.services.shared import find_dependents
from plan_manager.config import WORKSPACE_ROOT
from plan_manager.services.state_repository import (
    get_current_story_id,
    set_current_story_id,
    set_current_task_id,
)


logger = logging.getLogger(__name__)


def create_story(
    title: str,
    description: Optional[str],
    acceptance_criteria: Optional[List[str]],
    priority: Optional[int],
    depends_on: List[str]
) -> dict:
    generated_id = generate_slug(title)
    plan = plan_repo.load_current()
    existing_ids = [s.id for s in plan.stories]
    generated_id = ensure_unique_id_from_set(generated_id, existing_ids)

    details_path = story_file_path(generated_id)
    try:
        new_story = Story(
            id=generated_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            file_path=details_path,
            depends_on=depends_on or [],
            priority=priority,
        )
    except ValidationError as e:
        logger.exception(
            f"Validation error creating new story '{generated_id}': {e}")
        raise ValueError(
            f"Validation error creating new story '{generated_id}': {e}") from e

    plan.stories.append(new_story)
    validate_and_save(plan)

    try:
        write_story_details(new_story)
    except Exception:
        logger.info(
            f"Best-effort creation of story file failed for '{generated_id}'.")

    return new_story.model_dump(mode='json', include={'id', 'title', 'description', 'acceptance_criteria', 'priority', 'depends_on', 'status', 'file_path', 'creation_time'}, exclude_none=True)


def get_story(story_id: str) -> dict:
    plan = plan_repo.load_current()
    story = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    return story.model_dump(mode='json', exclude_none=True)


# Note: The status of a Story is a calculated property based on the statuses of its Tasks.
# It is not set directly and is therefore not a parameter in this function.
# The status rollup is handled by the task_service.
def update_story(
    story_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    acceptance_criteria: Optional[List[str]] = None,
    priority: Optional[int] = None,
    depends_on: Optional[List[str]] = None,
) -> dict:
    plan = plan_repo.load_current()
    idx = next((i for i, s in enumerate(
        plan.stories) if s.id == story_id), None)
    if idx is None:
        raise KeyError(f"story with ID '{story_id}' not found.")
    story_obj = plan.stories[idx]

    if title is not None:
        story_obj.title = title
    if description is not None:
        story_obj.description = description
    if acceptance_criteria is not None:
        story_obj.acceptance_criteria = acceptance_criteria
    if depends_on is not None:
        story_obj.depends_on = depends_on
    if priority is not None:
        story_obj.priority = priority

    plan.stories[idx] = story_obj
    validate_and_save(plan)

    if story_obj.file_path:
        try:
            save_item_to_file(story_obj.file_path, story_obj,
                              content=None, overwrite=False)
        except Exception:
            logger.info(
                f"Best-effort update of story file failed for '{story_id}'.")

    return story_obj.model_dump(mode='json', exclude_none=True)


def delete_story(story_id: str) -> dict:
    plan = plan_repo.load_current()
    idx = next((i for i, s in enumerate(
        plan.stories) if s.id == story_id), None)
    if idx is None:
        raise KeyError(f"story with ID '{story_id}' not found.")
    # Block if there are dependents
    deps = find_dependents(plan, story_id)
    if deps:
        raise ValueError(
            f"Cannot delete story '{story_id}' because it is a dependency of: {', '.join(deps)}"
        )
    story_to_remove = plan.stories[idx]
    file_path = story_to_remove.file_path
    del plan.stories[idx]
    plan_repo.save(plan, plan_id=plan.id)
    # Best-effort removal of story file_path file and directory tree
    abs_details_path: Optional[str] = None
    if file_path:
        try:
            delete_item_file(file_path)
            abs_details_path = os.path.join(WORKSPACE_ROOT, file_path)
        except Exception:
            logger.info(
                f"Best-effort delete of story file failed for '{story_id}'.")
    # Attempt to remove the entire story directory (e.g., todo/<story_id>/) safely
    try:
        story_dir_candidate: Optional[str] = None
        if abs_details_path and os.path.isabs(abs_details_path):
            story_dir_candidate = os.path.dirname(abs_details_path)
        else:
            # Fall back to the conventional story directory under workspace
            story_dir_candidate = os.path.join(
                WORKSPACE_ROOT, 'todo', plan.id, story_id)

        norm_story_dir = os.path.normpath(story_dir_candidate)
        norm_ws_root = os.path.normpath(WORKSPACE_ROOT)
        # Guardrails: ensure deletion stays within <WORKSPACE_ROOT>/todo and the directory name matches the story_id
        if norm_story_dir.startswith(os.path.join(norm_ws_root, 'todo') + os.sep) and os.path.basename(norm_story_dir) == story_id:
            if os.path.exists(norm_story_dir):
                shutil.rmtree(norm_story_dir, ignore_errors=True)
                logger.info(f"Deleted story directory: {norm_story_dir}")
    except Exception as e:
        logger.warning(
            f"Best-effort directory delete failed for story '{story_id}': {e}")
    # Selection invariants: if deleted story was current, clear selections
    try:
        current_sid = get_current_story_id(plan.id)
        if current_sid == story_id:
            set_current_task_id(None, plan.id)
            set_current_story_id(None, plan.id)
    except Exception:
        pass
    return {"success": True, "message": f"Successfully deleted story '{story_id}'."}


def list_stories(statuses: Optional[List[Status]], unblocked: bool = False) -> List[Story]:
    """Return domain stories after topological sort and filtering.

    - Topo sorts by dependencies (Kahn's algorithm).
    - Within each ready set, sorts by priority asc (None last), creation_time asc (None last), id asc.
    - Filters by allowed statuses if provided.
    - If unblocked=True, includes only TODO stories whose dependencies are all DONE.
    """
    plan = plan_repo.load_current()
    stories: List[Story] = plan.stories or []
    if not stories:
        return []

    # Build graph
    adj: dict[str, list[str]] = {}
    in_deg: dict[str, int] = {}
    by_id: dict[str, Story] = {s.id: s for s in stories}
    for s in stories:
        in_deg.setdefault(s.id, 0)
        for dep in (s.depends_on or []):
            adj.setdefault(dep, []).append(s.id)
            in_deg[s.id] = in_deg.get(s.id, 0) + 1

    # Initialize queue with zero in-degree
    ready: List[Story] = [by_id[sid]
                          for sid in by_id if in_deg.get(sid, 0) == 0]
    sorted_list: List[Story] = []

    def sort_key(s: Story):
        prio = s.priority if s.priority is not None else 6
        ctime_key = (s.creation_time is None, s.creation_time or '9999')
        return (prio, ctime_key, s.id)

    while ready:
        ready.sort(key=sort_key)
        current = ready.pop(0)
        sorted_list.append(current)
        for nxt in adj.get(current.id, []):
            in_deg[nxt] -= 1
            if in_deg[nxt] == 0:
                ready.append(by_id[nxt])

    if len(sorted_list) != len(stories):
        missing = set(by_id) - set(s.id for s in sorted_list)
        logger.error(
            f"Cycle detected or inconsistency in story dependencies. total={len(stories)} sorted={len(sorted_list)} missing={missing}")

    allowed = set(statuses) if statuses else None
    out: List[Story] = []
    for s in sorted_list:
        if allowed is not None and s.status not in allowed:
            continue
        if unblocked:
            if s.status != Status.TODO:
                continue
            deps_ok = True
            for dep_id in (s.depends_on or []):
                dep_s = by_id.get(dep_id)
                if not dep_s or dep_s.status != Status.DONE:
                    deps_ok = False
                    break
            if not deps_ok:
                continue
        out.append(s)

    return out
