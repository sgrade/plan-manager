import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import yaml

from plan_manager.config import TODO_DIR


def _activity_file_path(plan_id: str) -> str:
    return os.path.join(TODO_DIR, plan_id, 'activity.yaml')


def _read_events(plan_id: str) -> List[Dict[str, Any]]:
    path = _activity_file_path(plan_id)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or []
    if isinstance(data, list):
        return data
    return []


def _write_events(plan_id: str, events: List[Dict[str, Any]]) -> None:
    path = _activity_file_path(plan_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(events, f, default_flow_style=False, sort_keys=False)


def append_event(
    plan_id: str,
    event_type: str,
    scope: Dict[str, Any],
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    events = _read_events(plan_id)
    eid = str(len(events) + 1)
    event = {
        'id': eid,
        'ts': datetime.now(timezone.utc).isoformat(),
        'type': event_type,
        'scope': scope,
    }
    if data:
        event['data'] = data
    events.append(event)
    _write_events(plan_id, events)
    return event


def list_events(plan_id: str) -> List[Dict[str, Any]]:
    return _read_events(plan_id)
