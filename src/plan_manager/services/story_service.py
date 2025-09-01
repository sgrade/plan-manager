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
    validate_and_save,
    write_story_details,
)
from plan_manager.services.shared import find_dependents
from plan_manager.services.status import apply_status_change
from plan_manager.config import WORKSPACE_ROOT


logger = logging.getLogger(__name__)


def create_story(title: str, priority: Optional[int], depends_on: List[str], notes: Optional[str]) -> dict:
    generated_id = generate_slug(title)
    plan = plan_repo.load()
    if any(s.id == generated_id for s in plan.stories):
        raise ValueError(f"story with ID '{generated_id}' already exists.")

    details_path = story_file_path(generated_id)
    try:
        new_story = Story(
            id=generated_id,
            title=title,
            details=details_path,
            depends_on=depends_on or [],
            notes=notes,
            priority=priority,
        )
    except ValidationError as e:
        logging.exception(
            f"Validation error creating new story '{generated_id}': {e}")
        raise ValueError(
            f"Validation error creating new story '{generated_id}': {e}") from e

    plan.stories.append(new_story)
    validate_and_save(plan)

    try:
        write_story_details(new_story)
    except Exception:
        logging.info(
            f"Best-effort creation of story file failed for '{generated_id}'.")

    return new_story.model_dump(mode='json', include={'id', 'title', 'status', 'details', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)


def get_story(story_id: str) -> dict:
    plan = plan_repo.load()
    story = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        raise KeyError(f"story with ID '{story_id}' not found.")
    return story.model_dump(mode='json', exclude_none=True)


def update_story(
    story_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    priority: Optional[int] = None,
    status: Optional[Status] = None,
) -> dict:
    plan = plan_repo.load()
    idx = next((i for i, s in enumerate(
        plan.stories) if s.id == story_id), None)
    if idx is None:
        raise KeyError(f"story with ID '{story_id}' not found.")
    story_obj = plan.stories[idx]

    if title is not None:
        story_obj.title = title
    if notes is not None:
        story_obj.notes = notes
    if depends_on is not None:
        story_obj.depends_on = depends_on
    if priority is not None:
        story_obj.priority = priority
    if status is not None:
        apply_status_change(story_obj, status)

    plan.stories[idx] = story_obj
    validate_and_save(plan)

    if story_obj.details:
        try:
            save_item_to_file(story_obj.details, story_obj,
                              content=None, overwrite=False)
        except Exception:
            logging.info(
                f"Best-effort update of story file failed for '{story_id}'.")

    return story_obj.model_dump(mode='json', exclude_none=True)


def delete_story(story_id: str) -> dict:
    plan = plan_repo.load()
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
    details = story_to_remove.details
    del plan.stories[idx]
    plan_repo.save(plan)
    # Best-effort removal of story details file and directory tree
    abs_details_path: Optional[str] = None
    if details:
        try:
            delete_item_file(details)
            abs_details_path = os.path.join(WORKSPACE_ROOT, details)
        except Exception:
            logging.info(
                f"Best-effort delete of story file failed for '{story_id}'.")
    # Attempt to remove the entire story directory (e.g., todo/<story_id>/) safely
    try:
        story_dir_candidate: Optional[str] = None
        if abs_details_path and os.path.isabs(abs_details_path):
            story_dir_candidate = os.path.dirname(abs_details_path)
        else:
            # Fall back to the conventional story directory under workspace
            story_dir_candidate = os.path.join(
                WORKSPACE_ROOT, 'todo', story_id)

        norm_story_dir = os.path.normpath(story_dir_candidate)
        norm_ws_root = os.path.normpath(WORKSPACE_ROOT)
        # Guardrails: ensure deletion stays within <WORKSPACE_ROOT>/todo and the directory name matches the story_id
        if norm_story_dir.startswith(os.path.join(norm_ws_root, 'todo') + os.sep) and os.path.basename(norm_story_dir) == story_id:
            if os.path.exists(norm_story_dir):
                shutil.rmtree(norm_story_dir, ignore_errors=True)
                logging.info(f"Deleted story directory: {norm_story_dir}")
    except Exception as e:
        logging.warning(
            f"Best-effort directory delete failed for story '{story_id}': {e}")
    return {"success": True, "message": f"Successfully deleted story '{story_id}'."}


def _generate_id_from_title(title: str) -> str:
    return generate_slug(title)
