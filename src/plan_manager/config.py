import os

# --- Helper for parsing boolean env vars ---


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# --- Core Paths ---
# Determine the workspace root, which serves as the default base for other paths.
WORKSPACE_ROOT = os.getcwd()

# --- Configurable Paths (from environment with sensible defaults) ---
TODO_DIR = os.getenv("TODO_DIR", os.path.join(WORKSPACE_ROOT, 'todo'))
PLAN_FILE_PATH = os.path.join(TODO_DIR, 'plan.yaml')

ARCHIVE_DIR_PATH = os.path.join(TODO_DIR, 'archive')
ARCHIVE_PLAN_FILE_PATH = os.path.join(ARCHIVE_DIR_PATH, 'plan_archive.yaml')
ARCHIVED_DETAILS_DIR_PATH = os.path.join(ARCHIVE_DIR_PATH, 'file_path')

LOG_DIR = os.getenv("LOG_DIR", os.path.join(WORKSPACE_ROOT, 'logs'))
LOG_FILE_PATH = os.path.join(LOG_DIR, 'mcp_server_app.log')

# --- Logging Configuration ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENABLE_FILE_LOG = _env_bool("PLAN_MANAGER_ENABLE_FILE_LOG")

# --- Uvicorn Configuration ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "3000"))
RELOAD = _env_bool("PLAN_MANAGER_RELOAD")
RELOAD_DIRS = os.getenv("RELOAD_DIRS", "src").split(",")
RELOAD_INCLUDES = os.getenv("RELOAD_INCLUDE", "*.py").split(",")
RELOAD_EXCLUDES = os.getenv("RELOAD_EXCLUDE", "logs/*").split(",")
TIMEOUT_GRACEFUL_SHUTDOWN = int(os.getenv("TIMEOUT_GRACEFUL_SHUTDOWN", "3"))
TIMEOUT_KEEP_ALIVE = int(os.getenv("TIMEOUT_KEEP_ALIVE", "5"))
