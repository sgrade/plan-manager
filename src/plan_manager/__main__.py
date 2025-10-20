"""Entry point for running the Plan Manager MCP server."""

import logging
from importlib import import_module

import uvicorn

# --- Configuration Bootstrap ---
# This is the first and only place where these modules should be imported to
# ensure that configuration and logging are set up exactly once, as soon as
# the application starts. The order is critical.
from plan_manager import config

# To prevent the warning: Import "plan_manager.logging" is not accessed
import_module("plan_manager.logging")


logger = logging.getLogger(__name__)


def main() -> None:
    log_destination = config.LOG_FILE_PATH if config.ENABLE_FILE_LOG else "stdout only"
    logger.info(
        "Starting MCP Plan Manager Server on %s:%s (reload=%s). App logs to: %s",
        config.HOST,
        config.PORT,
        config.RELOAD,
        log_destination,
    )

    if config.RELOAD:
        logger.info(
            "Reloading enabled. Reload dirs: %s, includes: %s, excludes: %s",
            config.RELOAD_DIRS,
            config.RELOAD_INCLUDES,
            config.RELOAD_EXCLUDES,
        )
    else:
        logger.info("Reloading disabled. App will not restart on code changes.")

    uvicorn.run(
        "plan_manager.server.app:starlette_app",
        factory=True,
        # IMPORTANT: This tells uvicorn to use our configuration above.
        log_config=None,
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
