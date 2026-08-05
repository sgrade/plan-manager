# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Database bootstrap and WAL verification helpers."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from plan_manager.storage.schema import (
    IMPORT_STATE_DONE,
    IMPORT_STATE_KEY,
    apply_migrations,
)

DB_FILENAME = "plan_manager.sqlite3"


class StorageBootstrapError(RuntimeError):
    """Raised when storage bootstrap or WAL verification fails."""


class StartupAction(StrEnum):
    INITIALIZE_EMPTY = "initialize_empty"
    IMPORT_LEGACY = "import_legacy"
    SERVE_DB = "serve_db"


@dataclass(frozen=True)
class StartupDecision:
    action: StartupAction
    db_path: Path
    has_published_db: bool
    has_legacy_yaml: bool


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


def decide_startup_action(todo_dir: str | Path, db_dir: str | Path) -> StartupDecision:
    """Decide startup flow based on published DB marker and legacy YAML presence."""
    _sweep_orphaned_import_temp_dbs(Path(db_dir))
    db_path = Path(db_dir) / DB_FILENAME
    has_done_db = _has_published_db(db_path)
    has_legacy_yaml = (Path(todo_dir) / "plans" / "index.yaml").exists()

    if has_done_db:
        return StartupDecision(
            action=StartupAction.SERVE_DB,
            db_path=db_path,
            has_published_db=True,
            has_legacy_yaml=has_legacy_yaml,
        )
    if has_legacy_yaml:
        return StartupDecision(
            action=StartupAction.IMPORT_LEGACY,
            db_path=db_path,
            has_published_db=False,
            has_legacy_yaml=True,
        )
    return StartupDecision(
        action=StartupAction.INITIALIZE_EMPTY,
        db_path=db_path,
        has_published_db=False,
        has_legacy_yaml=False,
    )


def startup_storage(todo_dir: str | Path, db_dir: str | Path) -> StartupDecision:
    """Execute startup decision and return the selected action."""
    decision = decide_startup_action(todo_dir, db_dir)
    if decision.action == StartupAction.SERVE_DB:
        return decision
    if decision.action == StartupAction.INITIALIZE_EMPTY:
        db_path = bootstrap(db_dir)
        _mark_import_done(db_path)
        return decision
    from plan_manager.storage.importer import import_legacy_tree

    import_legacy_tree(todo_dir=todo_dir, db_dir=db_dir, dry_run=False)
    return decision


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


def _has_published_db(db_path: Path) -> bool:
    if not db_path.exists():
        return False
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = ?",
                (IMPORT_STATE_KEY,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    if row is None:
        return False
    return str(row[0]) == IMPORT_STATE_DONE


def _mark_import_done(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            conn.execute(
                "INSERT INTO meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (IMPORT_STATE_KEY, IMPORT_STATE_DONE),
            )
    finally:
        conn.close()


def _cleanup_sqlite_artifacts(db_path: Path) -> None:
    candidates = [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]
    for candidate in candidates:
        if candidate.exists():
            candidate.unlink()


def _sweep_orphaned_import_temp_dbs(db_dir: Path) -> None:
    for temp_file in db_dir.glob(f"{DB_FILENAME}.import.*.tmp"):
        _safe_unlink(temp_file)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return
