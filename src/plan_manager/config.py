import os

# --- Helper for parsing boolean env vars ---


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable.

    Accepts common boolean string representations: '1', 'true', 'yes', 'on'
    (case-insensitive).

    Args:
        name: Environment variable name
        default: Default value if variable is not set

    Returns:
        bool: The parsed boolean value
    """
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float = 1.0) -> float:
    """Parse a float environment variable.

    Args:
        name: Environment variable name
        default: Default value if variable is not set or parsing fails

    Returns:
        float: The parsed float value, or default if parsing fails
    """
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return float(val)
    except Exception:
        return default


# --- Core Paths ---
# Determine the workspace root, which serves as the default base for other paths.
WORKSPACE_ROOT = os.getcwd()

# Multi-plan support (plans are stored under todo/<plan_id>/plan.yaml)
TODO_DIR = os.getenv("TODO_DIR", os.path.join(WORKSPACE_ROOT, "todo"))
PLANS_INDEX_FILE_PATH = os.path.join(TODO_DIR, "plans", "index.yaml")

# --- Logging Configuration ---
LOG_DIR = os.getenv("LOG_DIR", os.path.join(WORKSPACE_ROOT, "logs"))
LOG_FILE_PATH = os.path.join(LOG_DIR, "mcp_server_app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENABLE_FILE_LOG = _env_bool("PLAN_MANAGER_ENABLE_FILE_LOG")

# --- Workflow Guardrails ---
# Require approval before moving a Story/Task off TODO (to IN_PROGRESS/DONE)
REQUIRE_APPROVAL_BEFORE_PROGRESS = _env_bool("REQUIRE_APPROVAL_BEFORE_PROGRESS", True)

# Require an execution_intent before moving a Task to IN_PROGRESS
REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS = _env_bool(
    "REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS", True
)

# Require an execution_summary before moving a Task to DONE
REQUIRE_EXECUTION_SUMMARY_BEFORE_DONE = _env_bool(
    "REQUIRE_EXECUTION_SUMMARY_BEFORE_DONE", True
)

# --- UI / Browser ---
ENABLE_BROWSER = _env_bool("PLAN_MANAGER_ENABLE_BROWSER", True)

# --- Uvicorn Configuration ---
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "3000"))
RELOAD = _env_bool("PLAN_MANAGER_RELOAD")
RELOAD_DIRS = os.getenv("RELOAD_DIRS", "src").split(",")
RELOAD_INCLUDES = os.getenv("RELOAD_INCLUDE", "*.py").split(",")
RELOAD_EXCLUDES = os.getenv("RELOAD_EXCLUDE", "logs/*").split(",")
TIMEOUT_GRACEFUL_SHUTDOWN = int(os.getenv("TIMEOUT_GRACEFUL_SHUTDOWN", "3"))
TIMEOUT_KEEP_ALIVE = int(os.getenv("TIMEOUT_KEEP_ALIVE", "5"))

# --- Docs / Agent Guides ---
# Workspace-relative paths to agent-facing docs so deployments can override.
USAGE_GUIDE_REL_PATH = os.getenv(
    "USAGE_GUIDE_REL_PATH", os.path.join("docs", "usage_guide_agents.md")
)
PROJECT_WORKFLOW_REL_PATH = os.getenv(
    "PROJECT_WORKFLOW_REL_PATH", os.path.join("docs", "project_workflow.md")
)

# --- Telemetry ---
# Lightweight, opt-in counters/timers for key flows
TELEMETRY_ENABLED = _env_bool("PLAN_MANAGER_TELEMETRY_ENABLED")
TELEMETRY_SAMPLE_RATE = _env_float("PLAN_MANAGER_TELEMETRY_SAMPLE_RATE", 1.0)
