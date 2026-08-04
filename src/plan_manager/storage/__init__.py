# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Storage foundation for SQLite-backed plan manager."""

from plan_manager.storage.db import DB_FILENAME, StorageBootstrapError, bootstrap
from plan_manager.storage.schema import LATEST_USER_VERSION, apply_migrations
from plan_manager.storage.uow import (
    DEFAULT_BUSY_RETRY_ATTEMPTS,
    DEFAULT_BUSY_TIMEOUT_MS,
    StorageBusyError,
    canonical_utc_timestamp,
    unit_of_work,
)

__all__ = [
    "DB_FILENAME",
    "DEFAULT_BUSY_RETRY_ATTEMPTS",
    "DEFAULT_BUSY_TIMEOUT_MS",
    "LATEST_USER_VERSION",
    "StorageBootstrapError",
    "StorageBusyError",
    "apply_migrations",
    "bootstrap",
    "canonical_utc_timestamp",
    "unit_of_work",
]
