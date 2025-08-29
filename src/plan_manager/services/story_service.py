import logging
import os
import shutil
from typing import Optional, List
from datetime import datetime, timezone

from pydantic import ValidationError

from plan_manager.domain.models import Story, Status
from plan_manager.services import plan_repository as plan_repo
from plan_manager.io.paths import story_file_path, slugify
from plan_manager.io.file_mirror import save_item_to_file, delete_item_file
from plan_manager.config import WORKSPACE_ROOT


logger = logging.getLogger(__name__)


def create_story(title: str, priority: str, depends_on: str, notes: str) -> dict:
    logging.info(
        f"Handling create_story: title='{title}', priority='{priority}', depends_on='{depends_on}', notes present={bool(notes)}"
    )
    generated_id = slugify(title)

    if priority == "6":
        numeric_priority: Optional[int] = None
    elif not priority:
        raise ValueError("Priority string cannot be empty. Use '6' for no priority.")
    else:
        try:
            numeric_priority = int(priority)
        except ValueError as e:
            raise ValueError(
                f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' for no priority."
            ) from e

    actual_depends: Optional[List[str]] = None if depends_on == "" else [d.strip() for d in depends_on.split(',') if d.strip()]
    actual_notes: Optional[str] = None if notes == "" else notes

    plan = plan_repo.load()
    if any(s.id == generated_id for s in plan.stories):
        raise ValueError(f"story with ID '{generated_id}' already exists.")

    if actual_depends:
        existing_ids = {s.id for s in plan.stories}
        for dep in actual_depends:
            if dep not in existing_ids:
                raise ValueError(f"Dependency story with ID '{dep}' not found.")
            if dep == generated_id:
                raise ValueError(f"story '{generated_id}' cannot depend on itself.")

    details_path = story_file_path(generated_id)

    try:
        new_story = Story(
            id=generated_id,
            title=title,
            status=Status.TODO,
            details=details_path,
            depends_on=actual_depends or [],
            notes=actual_notes,
            creation_time=datetime.now(timezone.utc),
            priority=numeric_priority,
        )
    except ValidationError as e:
        logging.exception(f"Validation error creating new story '{generated_id}': {e}")
        raise ValueError(f"Validation error creating new story '{generated_id}': {e}") from e

    plan.stories.append(new_story)
    plan_repo.save(plan)

    try:
        save_item_to_file(details_path, new_story, content=None, overwrite=False)
    except Exception:
        logging.info(f"Best-effort creation of story file failed for '{generated_id}'.")

    return new_story.model_dump(include={'id', 'title', 'status', 'details', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)


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
    depends_on: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    plan = plan_repo.load()
    idx = next((i for i, s in enumerate(plan.stories) if s.id == story_id), None)
    if idx is None:
        raise KeyError(f"story with ID '{story_id}' not found.")
    story_obj = plan.stories[idx]

    if title is not None:
        story_obj.title = title
    if notes is not None:
        story_obj.notes = None if notes == '' else notes
    if depends_on is not None:
        dep_list: List[str] = [d.strip() for d in depends_on.split(',') if d.strip()]
        existing_ids = {s.id for s in plan.stories}
        for dep in dep_list:
            if dep not in existing_ids:
                raise ValueError(f"Dependency story with ID '{dep}' not found.")
            if dep == story_id:
                raise ValueError(f"story '{story_id}' cannot depend on itself.")
        story_obj.depends_on = dep_list
    if priority is not None:
        if priority.strip() == "":
            pass
        elif priority == "6":
            story_obj.priority = None
        else:
            try:
                story_obj.priority = int(priority)
            except ValueError as e:
                raise ValueError(
                    f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' to remove priority."
                ) from e
    if status is not None:
        if status.strip() != "":
            new_status_upper = status.upper()
            try:
                new_status = Status(new_status_upper)
            except Exception as e:
                raise ValueError(
                    f"Invalid status '{status}'. Allowed: {', '.join([s.value for s in Status])}"
                ) from e
            old = story_obj.status.value if hasattr(story_obj.status, 'value') else story_obj.status
            story_obj.status = new_status
            if new_status == Status.DONE and old != 'DONE':
                story_obj.completion_time = datetime.now(timezone.utc)
            elif new_status != Status.DONE and old == 'DONE':
                story_obj.completion_time = None

    plan.stories[idx] = story_obj
    plan_repo.save(plan)

    if story_obj.details:
        try:
            save_item_to_file(story_obj.details, story_obj, content=None, overwrite=False)
        except Exception:
            logging.info(f"Best-effort update of story file failed for '{story_id}'.")

    return story_obj.model_dump(mode='json', exclude_none=True)


def delete_story(story_id: str) -> dict:
    plan = plan_repo.load()
    idx = next((i for i, s in enumerate(plan.stories) if s.id == story_id), None)
    if idx is None:
        raise KeyError(f"story with ID '{story_id}' not found.")
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
            logging.info(f"Best-effort delete of story file failed for '{story_id}'.")
    # Attempt to remove the entire story directory (e.g., todo/<story_id>/) safely
    try:
        story_dir_candidate: Optional[str] = None
        if abs_details_path and os.path.isabs(abs_details_path):
            story_dir_candidate = os.path.dirname(abs_details_path)
        else:
            # Fall back to the conventional story directory under workspace
            story_dir_candidate = os.path.join(WORKSPACE_ROOT, 'todo', story_id)

        norm_story_dir = os.path.normpath(story_dir_candidate)
        norm_ws_root = os.path.normpath(WORKSPACE_ROOT)
        # Guardrails: ensure deletion stays within <WORKSPACE_ROOT>/todo and the directory name matches the story_id
        if norm_story_dir.startswith(os.path.join(norm_ws_root, 'todo') + os.sep) and os.path.basename(norm_story_dir) == story_id:
            if os.path.exists(norm_story_dir):
                shutil.rmtree(norm_story_dir, ignore_errors=True)
                logging.info(f"Deleted story directory: {norm_story_dir}")
    except Exception as e:
        logging.warning(f"Best-effort directory delete failed for story '{story_id}': {e}")
    return {"success": True, "message": f"Successfully deleted story '{story_id}'."}


def _generate_id_from_title(title: str) -> str:
    return slugify(title)
