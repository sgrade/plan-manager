"""Entry point for running the Plan Manager MCP server.

Usage:
    # Dev (auto-reload)
    uv run plan-manager --reload

    # Prod (no reload)
    uv run plan-manager
"""

# --- Configuration Bootstrap ---
# This is the first and only place where these modules should be imported to
# ensure that configuration and logging are set up exactly once, as soon as
# the application starts. The order is critical.
from plan_manager import config

import logging
import uvicorn

logger = logging.getLogger(__name__)


def main():

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
