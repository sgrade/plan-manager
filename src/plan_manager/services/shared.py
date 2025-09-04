import logging
from typing import Optional, List, Dict, Any

from plan_manager.io.paths import slugify, task_file_path
from plan_manager.io.file_mirror import save_item_to_file, read_item_file
from plan_manager.services import plan_repository as plan_repo
from plan_manager.domain.models import Status, Story, Task, Plan, Approval


logger = logging.getLogger(__name__)


def generate_slug(title: str) -> str:
    """Generate a slug from a title."""
    return slugify(title)


def ensure_unique_id_from_set(base_id: str, existing_ids: List[str] | set[str]) -> str:
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


def guard_approval_before_progress(
    current_status: Status,
    target_status: Optional[Status],
    approval: Optional[Approval],
    enabled: Optional[bool] = None,
) -> None:
    """Enforce approval before progressing from TODO to IN_PROGRESS/DONE.

    - If `enabled` is None, reads the default from config.
    - No-op when `target_status` is None.
    - Raises ValueError when guard fails.
    """
    if enabled is None:
        try:
            from plan_manager.config import REQUIRE_APPROVAL_BEFORE_PROGRESS as _DEFAULT_FLAG
        except Exception:
            _DEFAULT_FLAG = True
        enabled = _DEFAULT_FLAG
    if not enabled or target_status is None:
        return
    if current_status == Status.TODO and target_status in (Status.IN_PROGRESS, Status.DONE):
        if not (approval and approval.approved_at):
            raise ValueError("Approval required before progressing from TODO.")


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
        raise ValueError(
            "Priority string cannot be empty. Use '6' for no priority.")
    try:
        return int(priority)
    except ValueError as e:
        raise ValueError(
            f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' for no priority."
        ) from e


def parse_csv_list(csv: str) -> List[str]:
    """Parse a CSV list of strings."""
    if not csv:
        return []
    tokens = [t.strip() for t in csv.split(',') if t.strip()]
    return tokens


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
    if getattr(story, 'file_path', None):
        try:
            save_item_to_file(story.file_path, story,
                              content=None, overwrite=False)
        except Exception:
            logger.info(
                f"Best-effort write of story file_path failed for '{story.id}'.")


def write_task_details(task: Task) -> None:
    """Write task details to file."""
    try:
        story_id = getattr(task, 'story_id', None)
        local_task_id = None
        task_id = getattr(task, 'id', '')
        if ':' in task_id:
            parts = task_id.split(':', 1)
            story_id = story_id or parts[0]
            local_task_id = parts[1]
        else:
            local_task_id = slugify(task_id)
        if not story_id or not local_task_id:
            raise ValueError(
                "Cannot determine story_id or local_task_id for task file_path path.")
        path = task_file_path(story_id, local_task_id)
        save_item_to_file(path, task, content=None, overwrite=False)
    except Exception:
        logger.info(
            f"Best-effort write of task file_path failed for '{getattr(task, 'id', 'unknown')}'.")


def merge_frontmatter_defaults(path: str, base: Dict[str, Any]) -> Dict[str, Any]:
    """Merge default values with frontmatter values."""
    try:
        front, _ = read_item_file(path)
        result = dict(base)
        if front:
            for k, v in front.items():
                result.setdefault(k, v)
        return result
    except Exception:
        return base


def find_dependents(plan: Plan, target_id: str) -> List[str]:
    """Return IDs that depend on the target story or task.

    - If target is a story ID (no ':'), returns stories and tasks that list it in depends_on.
    - If target is a task ID (story_id:local_id), returns tasks that list it; also considers
      local references (just local_id) within the same story.
    """
    dependents: List[str] = []
    is_task = ':' in target_id
    target_story_id: Optional[str] = None
    target_local: Optional[str] = None
    if is_task:
        target_story_id, target_local = target_id.split(':', 1)

    # Story dependents: other stories that depend on the story
    if not is_task:
        for s in plan.stories:
            for dep in (s.depends_on or []):
                if dep == target_id:
                    dependents.append(s.id)

    # Task dependents: tasks depending on the target
    for s in plan.stories:
        for t in (s.tasks or []):
            for dep in (t.depends_on or []):
                if dep == target_id:
                    dependents.append(t.id)
                    continue
                if is_task and s.id == target_story_id and dep == target_local:
                    dependents.append(t.id)
                if not is_task and dep == target_id:
                    # tasks depending on a story ID
                    dependents.append(t.id)
    return sorted(set(dependents))
