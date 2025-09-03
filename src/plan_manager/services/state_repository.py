import os
import yaml
from typing import Optional

from plan_manager.services.plan_repository import get_current_plan_id
from plan_manager.config import TODO_DIR


def _state_file_path(plan_id: str) -> str:
    """Get the path to the state file for a given plan ID."""
    return os.path.join(TODO_DIR, plan_id, 'state.yaml')


def _read_state(plan_id: str) -> dict:
    """Read the state file for a given plan ID."""
    path = _state_file_path(plan_id)
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _write_state(plan_id: str, data: dict) -> None:
    """Write the state file for a given plan ID."""
    path = _state_file_path(plan_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


def get_current_story_id(plan_id: Optional[str] = None) -> Optional[str]:
    """Get the current story ID for a given plan ID."""
    pid = plan_id or get_current_plan_id()
    state = _read_state(pid)
    return state.get('current_story_id')


def set_current_story_id(story_id: Optional[str], plan_id: Optional[str] = None) -> None:
    """Set the current story ID for a given plan ID."""
    pid = plan_id or get_current_plan_id()
    state = _read_state(pid)
    if story_id is None:
        state.pop('current_story_id', None)
    else:
        state['current_story_id'] = story_id
    _write_state(pid, state)


def get_current_task_id(plan_id: Optional[str] = None) -> Optional[str]:
    """Get the current task ID for a given plan ID."""
    pid = plan_id or get_current_plan_id()
    state = _read_state(pid)
    return state.get('current_task_id')


def set_current_task_id(task_id: Optional[str], plan_id: Optional[str] = None) -> None:
    """Set the current task ID for a given plan ID."""
    pid = plan_id or get_current_plan_id()
    state = _read_state(pid)
    if task_id is None:
        state.pop('current_task_id', None)
    else:
        state['current_task_id'] = task_id
    _write_state(pid, state)
