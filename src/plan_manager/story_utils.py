import os
import logging
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timezone
import yaml
from plan_manager.story_model import Story, Task
from plan_manager.config import WORKSPACE_ROOT

logger = logging.getLogger(__name__)


def _split_front_matter(raw_text: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML front matter from a Markdown file. Returns (front_matter, body).
    If no front matter is present, returns ({}, full_text).
    """
    if raw_text.startswith('---'):
        # Find the closing '---' after the first line
        parts = raw_text.split('\n')
        if len(parts) > 1:
            try:
                # Search for the next line that is exactly '---'
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
                # Fall through to default behavior
                pass
    return {}, raw_text


def _render_with_front_matter(front: Dict[str, Any], body: str) -> str:
    fm = yaml.safe_dump(front, sort_keys=False).rstrip() + '\n'
    return f"---\n{fm}---\n\n{body or ''}"


def _atomic_write(abs_path: str, content: str) -> None:
    directory = os.path.dirname(abs_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = abs_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(tmp_path, abs_path)


def read_item_file(details_path: str) -> Tuple[Dict[str, Any], str]:
    """Read a Markdown file with optional front matter. Returns (front_matter, body).
    Always treats `details_path` as relative to WORKSPACE_ROOT.
    """
    abs_path = os.path.join(WORKSPACE_ROOT, details_path)
    if not os.path.exists(abs_path):
        return {}, ''
    with open(abs_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    return _split_front_matter(raw)


def save_item_to_file(details_path: str, item: Any, content: Optional[str] = None, overwrite: bool = False) -> None:
    """Create or update a Markdown file with YAML front matter for the provided item.
    - If file exists and overwrite=False: merge front matter from item, preserve body unless `content` is provided.
    - If file does not exist or overwrite=True: write front matter and provided body (or empty if none).
    """
    abs_path = os.path.join(WORKSPACE_ROOT, details_path)
    try:
        existing_front, existing_body = ({}, '')
        if os.path.exists(abs_path):
            existing_front, existing_body = read_item_file(details_path)

        # Build front matter from item (prefer model_dump when available)
        item_dict: Dict[str, Any] = {}
        if hasattr(item, 'model_dump'):
            item_dict = item.model_dump(exclude_none=True)
        elif isinstance(item, dict):
            item_dict = {k: v for k, v in item.items() if v is not None}
        elif hasattr(item, '__dict__'):
            item_dict = {k: v for k, v in vars(item).items() if v is not None}

        # For stories, only mirror task IDs in front matter (not embedded Task objects)
        if isinstance(item, Story) and 'tasks' in item_dict:
            try:
                item_dict['tasks'] = [t.id for t in (item.tasks or []) if hasattr(t, 'id')]
            except Exception:
                # If tasks is already a list of strings/dicts, leave as-is
                pass

        # Add schema and kind hints where obvious
        front: Dict[str, Any] = dict(existing_front) if (os.path.exists(abs_path) and not overwrite) else {}
        front.update(item_dict)
        front.setdefault('schema_version', 1)
        # Best-effort infer kind if not present
        if 'kind' not in front:
            if isinstance(item, Story):
                front['kind'] = 'story'
            elif isinstance(item, Task) or (isinstance(item, dict) and isinstance(item.get('id'), str) and ':' in item.get('id')):
                front['kind'] = 'task'

        # Normalize datetimes to ISO 8601 Z strings
        def _to_iso_z(val: Any) -> Any:
            if isinstance(val, datetime):
                dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            return val

        for key in ('creation_time', 'completion_time'):
            if key in front and front[key] is not None:
                front[key] = _to_iso_z(front[key])

        body = existing_body if (content is None) else content
        rendered = _render_with_front_matter(front, body or '')
        _atomic_write(abs_path, rendered)
        logger.info(f"Wrote details file: {abs_path}")
    except Exception as e:
        logger.warning(f"Best-effort write failed for '{abs_path}': {e}")


def update_item_file(details_path: str, item: Any, content: Optional[str] = None) -> None:
    """Merge front matter with latest item values, preserving body by default."""
    return save_item_to_file(details_path, item, content=content, overwrite=False)


def save_story_to_file(details_path_to_store: str, created_story_model: Story) -> None:
    """Create/merge a story Markdown file with YAML front matter, preserving any body content."""
    save_item_to_file(details_path_to_store, created_story_model, content=None, overwrite=False)


def update_story_file(details_path_to_store: str, story_model: Story) -> None:
    """Update only the front matter for a story file, preserving its body."""
    update_item_file(details_path_to_store, story_model, content=None)


def get_task_details_path(story_id: str, task_local_id: str) -> str:
    """Compute the relative details path for a task file."""
    return os.path.join('todo', story_id, 'tasks', f"{task_local_id}.md")


def delete_item_file(details_path: str) -> None:
    """Best-effort delete for an item details file."""
    try:
        abs_path = os.path.join(WORKSPACE_ROOT, details_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
            logger.info(f"Deleted details file: {abs_path}")
    except Exception as e:
        logger.warning(f"Best-effort delete failed for '{details_path}': {e}")
