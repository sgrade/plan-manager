import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import yaml

from plan_manager.config import WORKSPACE_ROOT

logger = logging.getLogger(__name__)


def split_front_matter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Split markdown text containing YAML front matter into metadata and body.

    Args:
        raw_text: The raw markdown text that may contain YAML front matter

    Returns:
        Tuple[Dict[str, Any], str]: A tuple of (front_matter_dict, body_text)
                                   where front_matter_dict contains parsed YAML metadata
                                   and body_text is the remaining markdown content
    """
    if raw_text.startswith("---"):
        parts = raw_text.split("\n")
        if len(parts) > 1:
            try:
                end_index = None
                for i in range(1, len(parts)):
                    if parts[i].strip() == "---":
                        end_index = i
                        break
                if end_index is not None:
                    yaml_block = "\n".join(parts[1:end_index])
                    body = "\n".join(parts[end_index + 1 :])
                    front = yaml.safe_load(yaml_block) or {}
                    if not isinstance(front, dict):
                        front = {}
                    return front, body.lstrip("\n")
            except Exception:
                pass
    return {}, raw_text


def render_with_front_matter(front: dict[str, Any], body: str) -> str:
    """Render a dictionary and body text into markdown with YAML front matter.

    Args:
        front: The metadata dictionary to serialize as YAML front matter
        body: The main content body

    Returns:
        str: The complete markdown text with front matter
    """
    fm = yaml.safe_dump(front, sort_keys=False).rstrip() + "\n"
    return f"---\n{fm}---\n\n{body or ''}"


def atomic_write(abs_path: str, content: str) -> None:
    """Write content to a file atomically to prevent corruption on failure.

    Args:
        abs_path: The absolute path to write to
        content: The content to write
    """
    directory = os.path.dirname(abs_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp_path = abs_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp_path, abs_path)


def read_item_file(details_path: str) -> tuple[dict[str, Any], str]:
    """Read a markdown file with YAML front matter and split into metadata and content.

    Args:
        details_path: Workspace-relative path to the markdown file

    Returns:
        Tuple[Dict[str, Any], str]: A tuple of (metadata_dict, content_body)
    """
    abs_path = os.path.join(WORKSPACE_ROOT, details_path)
    if not os.path.exists(abs_path):
        return {}, ""
    with open(abs_path, encoding="utf-8") as f:
        raw = f.read()
    return split_front_matter(raw)


def _to_iso_z(val: Any) -> Any:
    """Convert datetime objects to ISO format strings with Z suffix for YAML serialization."""
    if isinstance(val, datetime):
        dt = val if val.tzinfo else val.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return val


def save_item_to_file(
    details_path: str,
    front_source: Any,
    content: Optional[str] = None,
    overwrite: bool = False,
) -> None:
    """Save data to a markdown file with YAML front matter.

    Args:
        details_path: Workspace-relative path where the file should be saved
        front_source: The data object to serialize as YAML front matter
        content: Optional body content to append after front matter
        overwrite: If True, overwrite existing file; if False, merge with existing front matter

    Raises:
        FileExistsError: If overwrite=False and file already exists with different data
    """
    abs_path = os.path.join(WORKSPACE_ROOT, details_path)
    try:
        existing_front: dict[str, Any]
        existing_body: str
        existing_front, existing_body = ({}, "")
        if os.path.exists(abs_path):
            existing_front, existing_body = read_item_file(details_path)

        if hasattr(front_source, "model_dump"):
            # Use JSON mode to serialize Enums (e.g., Status) as strings
            front = front_source.model_dump(mode="json", exclude_none=True)
        elif isinstance(front_source, dict):
            front = {k: v for k, v in front_source.items() if v is not None}
        else:
            front = {k: v for k, v in vars(front_source).items() if v is not None}

        # Normalize datetimes
        for key in ("creation_time", "completion_time"):
            if key in front and front[key] is not None:
                front[key] = _to_iso_z(front[key])

        merged: dict[str, Any] = (
            dict(existing_front) if (os.path.exists(abs_path) and not overwrite) else {}
        )
        merged.update(front)
        merged.setdefault("schema_version", 1)

        rendered = render_with_front_matter(
            merged, existing_body if content is None else content
        )
        atomic_write(abs_path, rendered)
        logger.info(f"Wrote file_path file: {abs_path}")
    except Exception as e:
        logger.warning(f"Best-effort write failed for '{abs_path}': {e}")


def delete_item_file(details_path: str) -> None:
    """Delete a markdown file containing item data.

    Args:
        details_path: Workspace-relative path to the file to delete
    """
    try:
        abs_path = os.path.join(WORKSPACE_ROOT, details_path)
        if os.path.exists(abs_path):
            os.remove(abs_path)
            logger.info(f"Deleted file_path file: {abs_path}")
    except Exception as e:
        logger.warning(f"Best-effort delete failed for '{details_path}': {e}")
