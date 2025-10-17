import logging
from typing import Any, Optional

from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.io.file_mirror import read_item_file, save_item_to_file
from plan_manager.io.paths import slugify, task_file_path
from plan_manager.services import plan_repository as plan_repo
from plan_manager.services.state_repository import get_current_story_id

logger = logging.getLogger(__name__)


def generate_slug(title: str) -> str:
    """Generate a URL-safe slug from a title.

    Args:
        title: The title to convert into a slug

    Returns:
        str: The slugified title
    """
    return slugify(title)


def ensure_unique_id_from_set(base_id: str, existing_ids: list[str] | set[str]) -> str:
    """Ensure a unique ID by appending -2, -3, ... if base_id is taken.

    The caller provides the set/list of existing IDs in the relevant scope
    (plans index, plan.stories, or story-local task IDs).
    """
    taken = set(existing_ids)
    if base_id not in taken:
        return base_id
    counter = 2
    while True:
        candidate = f"{base_id}-{counter}"
        if candidate not in taken:
            return candidate
        counter += 1


def resolve_task_id(task_id: str, story_id: Optional[str] = None) -> tuple[str, str]:
    """Resolve a task ID into a (story_id, local_task_id) tuple.

    - If task_id is fully-qualified ('story:task'), it is parsed.
    - If task_id is local, story_id must be provided or available in the current context.
    - Rejects ambiguous inputs and ensures a valid, usable pair is returned.
    """
    if ":" in task_id:
        try:
            parsed_story_id, local_task_id = task_id.split(":", 1)
            if story_id and story_id != parsed_story_id:
                raise ValueError(
                    f"Mismatched story_id: provided '{story_id}' but task has '{parsed_story_id}'."
                )
            return parsed_story_id, local_task_id
        except ValueError as e:
            raise ValueError(
                f"Invalid fully-qualified task ID '{task_id}'. Expected 'story_id:task_id'."
            ) from e
    else:
        # Local ID: require story context
        s_id = story_id or get_current_story_id()
        if not s_id:
            raise ValueError(
                "Cannot use a local task ID without a current story. Call `set_current_story` or provide a fully-qualified ID ('story:task')."
            )
        return s_id, task_id


def parse_status(value: Optional[str | Status]) -> Optional[Status]:
    """Parse a status input string."""
    if value is None:
        return None
    if isinstance(value, Status):
        return value
    token = value.strip().upper()
    if not token:
        return None
    try:
        return Status(token)
    except Exception as e:
        raise ValueError(
            f"Invalid status '{value}'. Allowed: {', '.join([s.value for s in Status])}"
        ) from e


def parse_priority_input(priority: str) -> Optional[int]:
    """Parse a priority input string."""
    if priority == "6":
        return None
    if priority == "":
        raise ValueError("Priority string cannot be empty. Use '6' for no priority.")
    try:
        return int(priority)
    except ValueError as e:
        raise ValueError(
            f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' for no priority."
        ) from e


def parse_csv_list(csv: str) -> list[str]:
    """Parse a CSV list of strings."""
    if not csv:
        return []
    return [t.strip() for t in csv.split(",") if t.strip()]


def validate_and_save(plan: Plan) -> None:
    """Validate and save the plan."""
    try:
        # Import here to avoid potential import cycles
        from plan_manager.domain.validation import validate_plan_dependencies

        validate_plan_dependencies(plan.stories)
        plan_repo.save(plan, plan.id)
    except Exception:
        logger.exception("Plan validation failed; changes were not saved.")
        raise


def write_story_details(story: Story) -> None:
    """Write story details to file."""
    if getattr(story, "file_path", None):
        try:
            # Persist tasks as identifiers only to keep story frontmatter small and stable
            front = story.model_dump(mode="json", exclude_none=True)
            front["tasks"] = [
                (
                    t.local_id
                    if getattr(t, "local_id", None)
                    else (
                        t.id.split(":", 1)[1]
                        if isinstance(getattr(t, "id", None), str) and ":" in t.id
                        else getattr(t, "id", None)
                    )
                )
                for t in (story.tasks or [])
            ]
            front["tasks"] = [
                tid for tid in front["tasks"] if isinstance(tid, str) and tid
            ]
            if story.file_path:
                save_item_to_file(story.file_path, front, content=None, overwrite=False)
        except (KeyError, ValueError, AttributeError, OSError):
            # Best-effort: log but don't fail on write errors
            logger.info(
                f"Best-effort write of story file_path failed for '{story.id}'."
            )


def write_task_details(task: Task) -> None:
    """Write task details to file."""
    try:
        story_id = getattr(task, "story_id", None)
        local_task_id = None
        task_id = getattr(task, "id", "")
        if ":" in task_id:
            parts = task_id.split(":", 1)
            story_id = story_id or parts[0]
            local_task_id = parts[1]
        else:
            local_task_id = slugify(task_id)
        if not story_id or not local_task_id:
            raise ValueError(
                "Cannot determine story_id or local_task_id for task file_path path."
            )
        path = task_file_path(story_id, local_task_id)
        save_item_to_file(path, task, content=None, overwrite=False)
    except (ValueError, AttributeError, OSError):
        # Best-effort: log but don't fail on write errors
        logger.info(
            f"Best-effort write of task file_path failed for '{getattr(task, 'id', 'unknown')}'."
        )


def merge_frontmatter_defaults(path: str, base: dict[str, Any]) -> dict[str, Any]:
    """Merge default values with frontmatter values."""
    try:
        front, _ = read_item_file(path)
        result = dict(base)
        if front:
            for k, v in front.items():
                result.setdefault(k, v)
        return result
    except (OSError, KeyError):
        # Fallback to base if frontmatter cannot be read
        return base


def find_dependents(plan: Plan, target_id: str) -> list[str]:
    """Return IDs that depend on the target story or task.

    - If target is a story ID (no ':'), returns stories and tasks that list it in depends_on.
    - If target is a task ID (story_id:local_id), returns tasks that list it; also considers
      local references (just local_id) within the same story.
    """
    dependents: list[str] = []
    is_task = ":" in target_id
    target_story_id: Optional[str] = None
    target_local: Optional[str] = None
    if is_task:
        target_story_id, target_local = target_id.split(":", 1)

    # Story dependents: other stories that depend on the story
    if not is_task:
        for s in plan.stories:
            for dep in s.depends_on or []:
                if dep == target_id:
                    dependents.append(s.id)

    # Task dependents: tasks depending on the target
    for s in plan.stories:
        for t in s.tasks or []:
            for dep in t.depends_on or []:
                if dep == target_id:
                    dependents.append(t.id)
                    continue
                if is_task and s.id == target_story_id and dep == target_local:
                    dependents.append(t.id)
                if not is_task and dep == target_id:
                    # tasks depending on a story ID
                    dependents.append(t.id)
    return sorted(set(dependents))


def is_unblocked(item: Story | Task, plan: Plan) -> bool:
    """Check if a story or task is unblocked by checking the status of its dependencies."""
    if not item.depends_on:
        return True

    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: t for s in plan.stories for t in (s.tasks or [])}

    for dep_id in item.depends_on:
        # Normalize to fully-qualified ID for lookup if it's a task
        fq_dep_id = (
            f"{getattr(item, 'story_id', '')}:{dep_id}"
            if isinstance(item, Task) and ":" not in dep_id
            else dep_id
        )

        if fq_dep_id in task_index:
            if task_index[fq_dep_id].status != Status.DONE:
                return False
        elif dep_id in story_index:
            if story_index[dep_id].status != Status.DONE:
                return False
        else:
            # Dependency not found, assume it's a blocker
            return False

    return True
