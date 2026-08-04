# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Database bootstrap and WAL verification helpers."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from plan_manager.storage.schema import apply_migrations

DB_FILENAME = "plan_manager.sqlite3"


class StorageBootstrapError(RuntimeError):
    """Raised when storage bootstrap or WAL verification fails."""


def bootstrap(db_dir: str | Path) -> Path:
    """Bootstrap SQLite storage and return the real database path."""
    target_dir = Path(db_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    _verify_wal_with_disposable_db(target_dir)

    db_path = target_dir / DB_FILENAME
    conn = sqlite3.connect(db_path)
    try:
        journal_mode = _set_journal_mode_wal(conn)
        if journal_mode != "wal":
            raise StorageBootstrapError(
                "WAL bootstrap failed: PRAGMA journal_mode did not return 'wal'."
            )
        apply_migrations(conn)
    finally:
        conn.close()

    return db_path


def _verify_wal_with_disposable_db(db_dir: Path) -> None:
    probe_base = db_dir / f"wal_probe_{uuid.uuid4().hex}.sqlite3"
    conn1: sqlite3.Connection | None = None
    conn2: sqlite3.Connection | None = None
    try:
        conn1 = sqlite3.connect(probe_base)
        mode = _set_journal_mode_wal(conn1)
        if mode != "wal":
            raise StorageBootstrapError(
                "Disposable WAL self-check failed: PRAGMA journal_mode did not return 'wal'."
            )

        conn1.execute(
            "CREATE TABLE IF NOT EXISTS wal_probe (id INTEGER PRIMARY KEY, value TEXT)"
        )
        conn1.commit()

        conn2 = sqlite3.connect(probe_base)
        second_mode = _set_journal_mode_wal(conn2)
        if second_mode != "wal":
            raise StorageBootstrapError(
                "Disposable WAL self-check failed on second connection."
            )
        conn2.execute("BEGIN IMMEDIATE")
        conn2.execute("INSERT INTO wal_probe(value) VALUES (?)", ("ok",))
        conn2.commit()
    except sqlite3.DatabaseError as exc:
        raise StorageBootstrapError(
            f"Disposable WAL self-check failed with SQLite error: {exc}"
        ) from exc
    finally:
        if conn2 is not None:
            conn2.close()
        if conn1 is not None:
            conn1.close()
        _cleanup_sqlite_artifacts(probe_base)


def _set_journal_mode_wal(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
    if row is None:
        return ""
    return str(row[0]).lower()


def _cleanup_sqlite_artifacts(db_path: Path) -> None:
    candidates = [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]
    for candidate in candidates:
        if candidate.exists():
            candidate.unlink()
