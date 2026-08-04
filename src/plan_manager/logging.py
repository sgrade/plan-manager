# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Centralized logging configuration for the Plan Manager application.

This module should be imported once, as early as possible in the application's
lifecycle, typically in the main entrypoint (__main__.py). It sets up the
root logger with handlers and formatting based on the application's
configuration settings.
"""

import logging
import sys
from pathlib import Path

from plan_manager import config

logger = logging.getLogger(__name__)


# Apply the logging configuration using settings from the config module.
level = getattr(logging, config.LOG_LEVEL, logging.INFO)


def build_handlers() -> tuple[list[logging.Handler], OSError | None]:
    """Build logging handlers and gracefully degrade if file logging fails."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    file_log_error: OSError | None = None

    if config.ENABLE_FILE_LOG:
        try:
            Path(config.LOG_DIR).mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(config.LOG_FILE_PATH))
        except OSError as err:
            file_log_error = err

    return handlers, file_log_error


# Default to logging ONLY to stdout, following 12-factor app principles.
# If PLAN_MANAGER_ENABLE_FILE_LOG is set, also log to a file for development.
handlers, file_log_error = build_handlers()

logging.basicConfig(
    level=level,
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
    handlers=handlers,
)

if file_log_error is not None:
    logger.warning(
        "File logging requested but unavailable at %s (%s). Falling back to stdout-only logging.",
        config.LOG_FILE_PATH,
        file_log_error,
    )

# A simple log message to confirm that the configuration has been applied.
# This will be one of the first messages seen when the application starts.
logger.info(
    "Logging configured. Level: %s, File logging enabled: %s",
    config.LOG_LEVEL,
    config.ENABLE_FILE_LOG,
)
