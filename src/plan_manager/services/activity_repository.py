import os
from datetime import datetime, timezone
from typing import Any, Optional

import yaml

from plan_manager.config import TODO_DIR


def _activity_file_path(plan_id: str) -> str:
    """Get the file path for storing activity events for a plan.

    Args:
        plan_id: The plan identifier

    Returns:
        str: The file path for the activity file
    """
    return os.path.join(TODO_DIR, plan_id, "activity.yaml")


def _read_events(plan_id: str) -> list[dict[str, Any]]:
    """Read activity events from the plan's activity file.

    Args:
        plan_id: The plan identifier

    Returns:
        List[Dict[str, Any]]: List of activity events
    """
    path = _activity_file_path(plan_id)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if isinstance(data, list):
        return data
    return []


def _write_events(plan_id: str, events: list[dict[str, Any]]) -> None:
    """Write activity events to the plan's activity file.

    Args:
        plan_id: The plan identifier
        events: List of activity events to write
    """
    path = _activity_file_path(plan_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(events, f, default_flow_style=False, sort_keys=False)


def append_event(
    plan_id: str,
    event_type: str,
    scope: dict[str, Any],
    data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Append a new activity event to the plan's activity log.

    Args:
        plan_id: The plan identifier
        event_type: The type of event (e.g., 'task_created', 'status_changed')
        scope: Context information about what the event relates to
        data: Optional additional event data

    Returns:
        Dict[str, Any]: The created event record
    """
    events = _read_events(plan_id)
    eid = str(len(events) + 1)
    event = {
        "id": eid,
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "scope": scope,
    }
    if data:
        event["data"] = data
    events.append(event)
    _write_events(plan_id, events)
    return event


def list_events(plan_id: str) -> list[dict[str, Any]]:
    """List all activity events for a plan.

    Args:
        plan_id: The plan identifier

    Returns:
        List[Dict[str, Any]]: List of all activity events for the plan
    """
    return _read_events(plan_id)
