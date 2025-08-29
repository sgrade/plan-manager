import os
import logging
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone
import yaml

from plan_manager.config import WORKSPACE_ROOT


logger = logging.getLogger(__name__)


def split_front_matter(raw_text: str) -> Tuple[Dict[str, Any], str]:
    if raw_text.startswith('---'):
        parts = raw_text.split('\n')
        if len(parts) > 1:
            try:
                end_index = None
                for i in range(1, len(parts)):
                    if parts[i].strip() == '---':
                        end_index = i
                        break
                if end_index is not None:
                    yaml_block = '\n'.join(parts[1:end_index])
                    body = '\n'.join(parts[end_index + 1:])
                    front = yaml.safe_load(yaml_block) or {}
                    if not isinstance(front, dict):
                        front = {}
                    return front, body.lstrip('\n')
            except Exception:
                pass
    return {}, raw_text


def render_with_front_matter(front: Dict[str, Any], body: str) -> str:
    fm = yaml.safe_dump(front, sort_keys=False).rstrip() + '\n'
    return f"---\n{fm}---\n\n{body or ''}"


def atomic_write(abs_path: str, content: str) -> None:
    directory = os.path.dirname(abs_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = abs_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp_path, abs_path)


def read_item_file(details_path: str) -> Tuple[Dict[str, Any], str]:
    abs_path = os.path.join(WORKSPACE_ROOT, details_path)
    if not os.path.exists(abs_path):
        return {}, ''
    with open(abs_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    return split_front_matter(raw)


def _to_iso_z(val: Any) -> Any:  # type: ignore[name-defined]
    if isinstance(val, datetime):
        dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return val


def save_item_to_file(details_path: str, front_source: Any, content: Optional[str] = None, overwrite: bool = False) -> None:  # type: ignore[name-defined]
    abs_path = os.path.join(WORKSPACE_ROOT, details_path)
    try:
        existing_front, existing_body = ({}, '')
        if os.path.exists(abs_path):
            existing_front, existing_body = read_item_file(details_path)

        if hasattr(front_source, 'model_dump'):
            # Use JSON mode to serialize Enums (e.g., Status) as strings
            front = front_source.model_dump(mode='json', exclude_none=True)
            # If this is a Story-like object, ensure tasks are written as a list of IDs
            try:
                if isinstance(front.get('tasks', None), list) and front_source.__class__.__name__ in ('Story',):
                    front['tasks'] = [t.get('id') if isinstance(t, dict) else getattr(t, 'id', None) for t in front['tasks']]
                    front['tasks'] = [tid for tid in front['tasks'] if tid]
            except Exception:
                pass
        elif isinstance(front_source, dict):
            front = {k: v for k, v in front_source.items() if v is not None}
        else:
            front = {k: v for k, v in vars(front_source).items() if v is not None}

        # Normalize datetimes
        for key in ('creation_time', 'completion_time'):
            if key in front and front[key] is not None:
                front[key] = _to_iso_z(front[key])

        merged: Dict[str, Any] = dict(existing_front) if (os.path.exists(abs_path) and not overwrite) else {}
        merged.update(front)
        merged.setdefault('schema_version', 1)

        rendered = render_with_front_matter(merged, existing_body if content is None else content)
        atomic_write(abs_path, rendered)
        logger.info(f"Wrote details file: {abs_path}")
    except Exception as e:
        logger.warning(f"Best-effort write failed for '{abs_path}': {e}")


def delete_item_file(details_path: str) -> None:
    try:
        abs_path = os.path.join(WORKSPACE_ROOT, details_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
            logger.info(f"Deleted details file: {abs_path}")
    except Exception as e:
        logger.warning(f"Best-effort delete failed for '{details_path}': {e}")
