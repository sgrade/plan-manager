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

# Default to logging ONLY to stdout, following 12-factor app principles.
# If PLAN_MANAGER_ENABLE_FILE_LOG is set, also log to a file for development.
handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
if config.ENABLE_FILE_LOG:
    # Ensure the log directory exists before configuring the file handler
    Path(config.LOG_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)
    handlers.append(logging.FileHandler(config.LOG_FILE_PATH))

logging.basicConfig(
    level=level,
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
    handlers=handlers,
)

# A simple log message to confirm that the configuration has been applied.
# This will be one of the first messages seen when the application starts.
logger.info(
    "Logging configured. Level: %s, File logging enabled: %s",
    config.LOG_LEVEL,
    config.ENABLE_FILE_LOG,
)
