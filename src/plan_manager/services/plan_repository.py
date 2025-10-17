import logging
import os
import shutil
from typing import Any

import yaml

from plan_manager.config import PLANS_INDEX_FILE_PATH, TODO_DIR
from plan_manager.domain.models import Plan, Story, Task
from plan_manager.io.file_mirror import read_item_file, save_item_to_file
from plan_manager.io.paths import story_file_path, task_file_path

logger = logging.getLogger(__name__)


def _plan_file_path(plan_id: str) -> str:
    """Get the path to the plan file for a given plan ID."""
    return os.path.join(TODO_DIR, plan_id, "plan.yaml")


def _ensure_plans_index_exists() -> None:
    """Ensure the plans index file exists."""
    index_dir = os.path.dirname(PLANS_INDEX_FILE_PATH)
    os.makedirs(index_dir, exist_ok=True)
    if not os.path.exists(PLANS_INDEX_FILE_PATH):
        with open(PLANS_INDEX_FILE_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "current": "default",
                    "plans": [{"id": "default", "title": "default", "status": "TODO"}],
                },
                f,
                default_flow_style=False,
                sort_keys=False,
            )


def save(plan: Plan, plan_id: str = "default") -> None:
    """Persist a validated Plan model to todo/<plan_id>/plan.yaml and ensure it's in the index."""
    # 1. Save the main plan file (manifest)
    plan_path = _plan_file_path(plan_id)
    os.makedirs(os.path.dirname(plan_path), exist_ok=True)
    plan_manifest = plan.model_dump(mode="json", exclude={"stories"}, exclude_none=True)
    plan_manifest["stories"] = [s.id for s in plan.stories]
    with open(plan_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(plan_manifest, f, default_flow_style=False, sort_keys=False)

    # 2. Save each story to its own file
    for story in plan.stories:
        _save_story(story)

    # 3. Update the global plans index
    _update_plan_in_index(plan)


def _save_story(story: Story) -> None:
    """Saves a story and its tasks to their respective files."""
    story_path = story_file_path(story.id)
    story.file_path = story_path
    # Persist story frontmatter with task IDs (not embedded task objects)
    try:
        front = story.model_dump(mode="json", exclude_none=True)
        # Replace tasks with list of task identifiers (use local IDs for readability)
        front["tasks"] = [
            t.local_id
            if hasattr(t, "local_id") and t.local_id
            else (
                t.id.split(":", 1)[1]
                if isinstance(getattr(t, "id", None), str) and ":" in t.id
                else getattr(t, "id", None)
            )
            for t in (story.tasks or [])
        ]
        # Remove any None entries from tasks list
        front["tasks"] = [tid for tid in front["tasks"] if isinstance(tid, str) and tid]
        save_item_to_file(story_path, front, overwrite=True)
    except (KeyError, ValueError, AttributeError):
        # Fallback to prior behavior if shaping fails
        save_item_to_file(story_path, story, overwrite=True)

    # Save each task to its own file
    for task in story.tasks:
        if task.local_id:
            task_path = task_file_path(story.id, task.local_id)
            task.file_path = task_path
            save_item_to_file(task_path, task, overwrite=True)


def _update_plan_in_index(plan: Plan) -> None:
    """Ensure the plan is in the index and its status is up-to-date."""
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, encoding="utf-8") as f:
        idx = yaml.safe_load(f) or {}

    plans_list = idx.get("plans", [])
    plan_found = False
    for p in plans_list:
        if p.get("id") == plan.id:
            p["status"] = plan.status.value
            p["title"] = plan.title
            plan_found = True
            break

    if not plan_found:
        plans_list.append(
            {"id": plan.id, "title": plan.title, "status": plan.status.value}
        )

    idx["plans"] = plans_list
    with open(PLANS_INDEX_FILE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(idx, f, default_flow_style=False, sort_keys=False)


def delete(plan_id: str) -> None:
    """Delete a plan by ID from the index and remove its directory."""
    _ensure_plans_index_exists()

    # Remove from index
    with open(PLANS_INDEX_FILE_PATH, encoding="utf-8") as f:
        idx = yaml.safe_load(f) or {}

    plans_list = idx.get("plans", [])
    if plan_id not in [p.get("id") for p in plans_list]:
        raise FileNotFoundError(f"Plan '{plan_id}' not found in index.")

    idx["plans"] = [p for p in plans_list if p.get("id") != plan_id]

    # If the deleted plan was the current one, reset it
    if idx.get("current") == plan_id:
        if idx["plans"]:
            idx["current"] = idx["plans"][0].get("id")
        else:
            # No plans left, so create a default one
            idx["current"] = "default"
            idx["plans"] = [{"id": "default", "title": "default", "status": "TODO"}]

    with open(PLANS_INDEX_FILE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(idx, f, default_flow_style=False, sort_keys=False)

    # Remove directory
    plan_dir = os.path.join(TODO_DIR, plan_id)
    if os.path.isdir(plan_dir):
        try:
            shutil.rmtree(plan_dir)
            logger.info(f"Deleted plan directory: {plan_dir}")
        except OSError as e:
            logger.exception(f"Error deleting directory {plan_dir}: {e}")
            raise


def list_plans() -> list[dict[str, Any]]:
    """List plans from the strict index file. No directory scanning fallback."""
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, encoding="utf-8") as idxf:
        idx = yaml.safe_load(idxf) or {}
    plans_list = idx.get("plans")
    if plans_list is None:
        raise ValueError(
            f"Plans index at {PLANS_INDEX_FILE_PATH} is missing 'plans' key"
        )
    return list(plans_list)


def load(plan_id: str) -> Plan:
    """Load a specific plan by ID, rehydrating it from normalized files."""
    # 1. Load the plan manifest
    plan_path = _plan_file_path(plan_id)
    if not os.path.exists(plan_path):
        raise FileNotFoundError(f"Plan file not found for ID '{plan_id}'")

    with open(plan_path, encoding="utf-8") as f:
        plan_manifest = yaml.safe_load(f) or {}

    # 2. Load stories and their tasks
    stories = []
    for story_id in plan_manifest.get("stories", []):
        story = _load_story(story_id)
        if story:
            stories.append(story)

    plan_manifest["stories"] = stories
    return Plan.model_validate(plan_manifest)


def _load_story(story_id: str) -> Story | None:
    """Loads a single story and its tasks from their files."""
    try:
        story_path = story_file_path(story_id)
        frontmatter, _ = read_item_file(story_path)
        if not frontmatter:
            return None

        tasks = []
        for task_id in frontmatter.get("tasks", []):
            task = _load_task(story_id, task_id)
            if task:
                tasks.append(task)

        frontmatter["tasks"] = tasks
        return Story.model_validate(frontmatter)
    except (OSError, KeyError, ValidationError) as e:
        logger.warning(f"Failed to load story '{story_id}': {e}")
        return None


def _load_task(story_id: str, task_id: str) -> Task | None:
    """Loads a single task from its file."""
    try:
        # task_id can be fully qualified, so extract local_id for path
        local_id = task_id.split(":")[-1]
        task_path = task_file_path(story_id, local_id)
        frontmatter, _ = read_item_file(task_path)
        if not frontmatter:
            return None
        return Task.model_validate(frontmatter)
    except (OSError, KeyError, ValidationError) as e:
        logger.warning(f"Failed to load task '{task_id}' in story '{story_id}': {e}")
        return None


def load_current() -> Plan:
    """Load the current plan."""
    return load(get_current_plan_id())


def get_current_plan_id() -> str:
    """Get the current plan ID."""
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, encoding="utf-8") as f:
        idx = yaml.safe_load(f) or {}
    cur = idx.get("current")
    if not isinstance(cur, str):
        raise ValueError(f"'current' plan is not set in index {PLANS_INDEX_FILE_PATH}")
    plans_list = idx.get("plans") or []
    if cur not in [p.get("id") for p in plans_list]:
        raise ValueError(
            f"Current plan '{cur}' not present in index {PLANS_INDEX_FILE_PATH}"
        )
    return cur


def set_current_plan_id(plan_id: str) -> None:
    """Set the current plan ID."""
    _ensure_plans_index_exists()
    with open(PLANS_INDEX_FILE_PATH, encoding="utf-8") as f:
        idx = yaml.safe_load(f) or {}
    plans_list = idx.get("plans") or []
    if plan_id not in [p.get("id") for p in plans_list]:
        raise ValueError(
            f"Plan '{plan_id}' not present in index {PLANS_INDEX_FILE_PATH}"
        )
    idx["current"] = plan_id
    with open(PLANS_INDEX_FILE_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(idx, f, default_flow_style=False, sort_keys=False)
