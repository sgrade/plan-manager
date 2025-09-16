import os
from typing import Optional
from plan_manager.config import WORKSPACE_ROOT


def resolve_workspace_path(relative_path: str, base: Optional[str] = None) -> str:
    """Resolve a workspace-relative path to an absolute path.

    If base is provided, it is used as the starting directory; otherwise the
    current working directory is used. This keeps resolution consistent across
    environments.
    """
    base_dir = base or WORKSPACE_ROOT
    return os.path.abspath(os.path.join(base_dir, relative_path))


def read_text(path: str, encoding: str = "utf-8") -> str:
    """Read a UTF-8 text file and return its contents."""
    with open(path, "r", encoding=encoding) as f:
        return f.read()


def write_text(path: str, content: str, encoding: str = "utf-8") -> None:
    """Write text content to a file, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        f.write(content)


def read_markdown(relative_path: str) -> str:
    """Convenience: read and strip a markdown file located under the workspace.

    Accepts a workspace-relative path like "docs/quickstart_agents.md".
    """
    abs_path = resolve_workspace_path(relative_path)
    return read_text(abs_path).strip()
