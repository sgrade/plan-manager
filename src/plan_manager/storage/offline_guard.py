# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Advisory lock guard for offline export/import operations."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

SERVER_LOCK_FILENAME = "plan_manager.server.lock"


class LiveServerDetectedError(RuntimeError):
    """Raised when an offline-only command detects a running server."""


@contextlib.contextmanager
def hold_server_lock(db_dir: str | Path) -> Iterator[None]:
    """Hold an advisory lock for the duration of a live server process."""
    lock_file = Path(db_dir) / SERVER_LOCK_FILENAME
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LiveServerDetectedError(
                "Another Plan Manager server is already using this database."
            ) from exc
        handle.seek(0)
        handle.truncate(0)
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "db_dir": str(Path(db_dir).resolve()),
                },
                sort_keys=True,
            )
            + "\n"
        )
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def require_offline(db_dir: str | Path) -> None:
    """Refuse if a live server currently holds the storage lock."""
    lock_file = Path(db_dir) / SERVER_LOCK_FILENAME
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise LiveServerDetectedError(
                "Refusing operation: Plan Manager server appears to be running. "
                "Stop the server and retry."
            ) from exc
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
