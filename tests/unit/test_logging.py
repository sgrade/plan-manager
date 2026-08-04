# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Unit tests for logging configuration."""

import logging
from pathlib import Path

from plan_manager import logging as app_logging


def testbuild_handlers_falls_back_to_stdout_when_log_dir_unwritable(monkeypatch):
    """File logging errors should degrade to stdout-only handlers."""
    monkeypatch.setattr(app_logging.config, "ENABLE_FILE_LOG", True)
    monkeypatch.setattr(app_logging.config, "LOG_DIR", "/unwritable/logs")
    monkeypatch.setattr(
        app_logging.config,
        "LOG_FILE_PATH",
        "/unwritable/logs/mcp_server_app.log",
    )

    def _raise_permission_error(*args, **kwargs):
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", _raise_permission_error)

    handlers, file_log_error = app_logging.build_handlers()

    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert not any(isinstance(handler, logging.FileHandler) for handler in handlers)
    assert isinstance(file_log_error, PermissionError)
