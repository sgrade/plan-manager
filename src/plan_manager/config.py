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

# Multi-plan support (plans are stored under todo/<plan_id>/plan.yaml)
TODO_DIR = os.getenv("TODO_DIR", os.path.join(WORKSPACE_ROOT, 'todo'))
PLANS_INDEX_FILE_PATH = os.path.join(TODO_DIR, 'plans', 'index.yaml')

# --- Logging Configuration ---
LOG_DIR = os.getenv("LOG_DIR", os.path.join(WORKSPACE_ROOT, 'logs'))
LOG_FILE_PATH = os.path.join(LOG_DIR, 'mcp_server_app.log')
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
