"""Entry point for running the Plan Manager MCP server.

Usage:
    # Dev (auto-reload)
    uv run plan-manager --reload

    # Prod (no reload)
    uv run plan-manager
"""
import logging
import os
import sys
import uvicorn

# Import all config from the central config module
from plan_manager import config

logger = logging.getLogger(__name__)

# --- Centralized Logging Configuration ---
# This part applies the logging configuration using the imported settings
# from the config module. It is placed in the global scope to ensure it's
# configured when uvicorn imports the module.
level = getattr(logging, config.LOG_LEVEL, logging.INFO)

# --- Handler Configuration ---
# Default to logging ONLY to stdout, following 12-factor app principles.
# If PLAN_MANAGER_ENABLE_FILE_LOG is set, also log to a file for development.
handlers = [logging.StreamHandler(sys.stdout)]
if config.ENABLE_FILE_LOG:
    # Ensure the log directory exists before configuring the file handler
    os.makedirs(os.path.dirname(config.LOG_FILE_PATH), exist_ok=True)
    handlers.append(logging.FileHandler(config.LOG_FILE_PATH))

logging.basicConfig(
    level=level,
    format='%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s',
    handlers=handlers
)


def main():
    logger.info("Initializing Plan Manager")

    log_destination = config.LOG_FILE_PATH if config.ENABLE_FILE_LOG else "stdout only"
    logger.info(
        "Starting MCP Plan Manager Server on %s:%s (reload=%s). App logs to: %s",
        config.HOST, config.PORT, config.RELOAD, log_destination
    )

    uvicorn.run(
        "plan_manager.mcp_server:starlette_app",
        factory=True,
        log_config=None,  # IMPORTANT: This tells uvicorn to use our configuration above.
        host=config.HOST,
        port=config.PORT,
        reload=config.RELOAD,
        reload_dirs=[d for d in config.RELOAD_DIRS if d],
        reload_includes=[p for p in config.RELOAD_INCLUDES if p],
        reload_excludes=[p for p in config.RELOAD_EXCLUDES if p],
        timeout_graceful_shutdown=config.TIMEOUT_GRACEFUL_SHUTDOWN,
        timeout_keep_alive=config.TIMEOUT_KEEP_ALIVE,
    )


if __name__ == "__main__":
    main()
