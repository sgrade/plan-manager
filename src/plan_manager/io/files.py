from pathlib import Path
from typing import Optional

from plan_manager.config import WORKSPACE_ROOT


def resolve_workspace_path(relative_path: str, base: Optional[str] = None) -> str:
    """Resolve a workspace-relative path to an absolute path.

    Args:
        relative_path: The relative path to resolve
        base: Optional base directory. If not provided, uses WORKSPACE_ROOT.

    Returns:
        str: The absolute path
    """
    base_dir = base or WORKSPACE_ROOT
    return str((Path(base_dir) / relative_path).resolve())


def read_text(path: str, encoding: str = "utf-8") -> str:
    """Read a text file and return its contents.

    Args:
        path: The file path to read
        encoding: The text encoding to use (default: utf-8)

    Returns:
        str: The file contents
    """
    return Path(path).read_text(encoding=encoding)


def write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """Write text content to a file, creating parent directories as needed.

    Args:
        path: The file path to write to
        content: The text content to write
        encoding: The text encoding to use (default: utf-8)
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=encoding)


def read_markdown(relative_path: str) -> str:
    """Read and strip a markdown file located under the workspace.

    Args:
        relative_path: Workspace-relative path to the markdown file
                      (e.g., "docs/quickstart_agents.md")

    Returns:
        str: The stripped markdown content
    """
    abs_path = resolve_workspace_path(relative_path)
    return read_text(abs_path).strip()
