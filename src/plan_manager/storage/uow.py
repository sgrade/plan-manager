# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Unit-of-work helpers for SQLite interactions."""

import random
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_BUSY_TIMEOUT_MS = 5000
DEFAULT_BUSY_RETRY_ATTEMPTS = 3


class StorageBusyError(RuntimeError):
    """Raised when storage remains busy after bounded retries."""

    def __init__(
        self,
        message: str = "SQLite is busy. Please retry later.",
        *,
        operation: str | None = None,
        plan_id: str | None = None,
        attempts: int | None = None,
    ) -> None:
        super().__init__(message)
        self.operation = operation
        self.plan_id = plan_id
        self.attempts = attempts


class StorageMisuseError(RuntimeError):
    """Raised when a unit of work is used contrary to its declared mode."""


@contextmanager
def unit_of_work(
    db_path: str | Path,
    *,
    write: bool = False,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    busy_retry_attempts: int = DEFAULT_BUSY_RETRY_ATTEMPTS,
) -> Iterator[sqlite3.Connection]:
    """Run a single unit of work with deterministic transaction lifecycle."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        _apply_connection_pragmas(conn, busy_timeout_ms=busy_timeout_ms)
        if write:
            _begin_immediate_with_retry(conn, attempts=busy_retry_attempts)

        try:
            yield conn
        except Exception as exc:
            if conn.in_transaction:
                conn.rollback()
            if _is_busy_error(exc):
                raise StorageBusyError(
                    operation="unit_of_work", attempts=busy_retry_attempts
                ) from exc
            raise
        else:
            if write and conn.in_transaction:
                try:
                    conn.commit()
                except Exception as exc:
                    if conn.in_transaction:
                        conn.rollback()
                    if _is_busy_error(exc):
                        raise StorageBusyError(operation="commit", attempts=1) from exc
                    raise
            elif not write and conn.in_transaction:
                # A mutating statement ran in a read-only unit of work. Without
                # this guard the implicit transaction would be silently
                # discarded on close (U4 review, major finding 1).
                conn.rollback()
                raise StorageMisuseError(
                    "Write statement executed in a read-only unit_of_work; "
                    "open it with write=True."
                )
    finally:
        conn.close()


def canonical_utc_timestamp(value: datetime | None = None) -> str:
    """Return canonical RFC3339 UTC timestamp with millisecond precision."""
    if value is not None and not isinstance(value, datetime):
        raise TypeError(f"expected datetime, got {type(value).__name__}")
    moment = value or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _apply_connection_pragmas(
    conn: sqlite3.Connection, *, busy_timeout_ms: int
) -> None:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")


def _begin_immediate_with_retry(conn: sqlite3.Connection, *, attempts: int) -> None:
    if attempts < 1:
        raise ValueError("busy_retry_attempts must be >= 1")

    _begin_immediate_attempt(conn, attempt=1, attempts=attempts)


def _begin_immediate_attempt(
    conn: sqlite3.Connection, *, attempt: int, attempts: int
) -> None:
    try:
        conn.execute("BEGIN IMMEDIATE")
        return
    except Exception as exc:
        if not _is_busy_error(exc):
            raise
        if attempt >= attempts:
            raise StorageBusyError(
                operation="BEGIN IMMEDIATE", attempts=attempt
            ) from exc
        # Exponential backoff with bounded jitter keeps retries deterministic enough for tests.
        lower = 0.005 * (2 ** (attempt - 1))
        upper = 0.020 * (2 ** (attempt - 1))
        time.sleep(random.uniform(lower, upper))  # nosec B311 - retry jitter
        _begin_immediate_attempt(conn, attempt=attempt + 1, attempts=attempts)


def _is_busy_error(exc: Exception) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    code = getattr(exc, "sqlite_errorcode", None)
    if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        return True
    message = str(exc).lower()
    return "database is locked" in message or "database is busy" in message
