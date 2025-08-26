"""Entry point for running the Plan Manager MCP server.

Usage:
    # Dev (auto-reload)
    uv run plan-manager --reload

    # Prod (no reload)
    uv run plan-manager
"""
import argparse
import logging
import os
import sys
import uvicorn

from plan_manager.config import LOG_FILE_PATH

logger = logging.getLogger(__name__)

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true")

# --- Centralized Logging Configuration ---
# This single basicConfig call sets up logging for the entire application.
# It's placed in the global scope to ensure it's configured when uvicorn
# imports the module.
level_name = os.getenv("LOG_LEVEL", "INFO").upper()
level = getattr(logging, level_name, logging.INFO)

# --- Handler Configuration ---
# Default to logging ONLY to stdout, following 12-factor app principles.
# If PLAN_MANAGER_ENABLE_FILE_LOG is set, also log to a file for development.
handlers = [logging.StreamHandler(sys.stdout)]
if _env_bool("PLAN_MANAGER_ENABLE_FILE_LOG"):
    # Ensure the log directory exists before configuring the file handler
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    handlers.append(logging.FileHandler(LOG_FILE_PATH))

logging.basicConfig(
    level=level,
    format='%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s',
    handlers=handlers
)


def main():
    logger.info("Initializing Plan Manager")

    # Configure and parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the Plan Manager MCP server.")
    # parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--timeout-graceful-shutdown", type=int, default=int(os.getenv("TIMEOUT_GRACEFUL_SHUTDOWN", "2")))
    parser.add_argument("--timeout-keep-alive", type=int, default=int(os.getenv("TIMEOUT_KEEP_ALIVE", "2")))
    parser.add_argument("--reload", action=argparse.BooleanOptionalAction, default=_env_bool("PLAN_MANAGER_RELOAD", False))
    parser.add_argument("--reload-dir", action="append", default=os.getenv("RELOAD_DIRS", "src").split(","))
    parser.add_argument("--reload-include", action="append", default=os.getenv("RELOAD_INCLUDE", "*.py").split(","))
    parser.add_argument("--reload-exclude", action="append", default=os.getenv("RELOAD_EXCLUDE", "logs/*").split(","))
    args = parser.parse_args()

    logger.info(
        "Starting MCP Plan Manager Server on %s:%s (reload=%s). App logs: %s",
        args.host, args.port, bool(args.reload), LOG_FILE_PATH
    )

    uvicorn.run(
        "plan_manager.mcp_server:starlette_app",
        factory=True,
        log_config=None,  # IMPORTANT: This tells uvicorn to use our configuration above.
        host=args.host,
        port=args.port,
        reload=bool(args.reload),
        reload_dirs=[d for d in args.reload_dir if d],
        reload_includes=[p for p in args.reload_include if p],
        reload_excludes=[p for p in args.reload_exclude if p],
        timeout_graceful_shutdown=args.timeout_graceful_shutdown,
        timeout_keep_alive=args.timeout_keep_alive,
    )


if __name__ == "__main__":
    main()
