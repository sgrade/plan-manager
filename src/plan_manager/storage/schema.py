# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""SQLite schema and forward-only migrations for storage v2."""

import sqlite3

LATEST_USER_VERSION = 1
IMPORT_STATE_KEY = "import_state"
IMPORT_STATE_PENDING = "pending"
IMPORT_STATE_DONE = "done"

STATUS_CHECK = (
    "CHECK(status IN ("
    "'TODO','IN_PROGRESS','PENDING_REVIEW','DONE','BLOCKED','DEFERRED'"
    "))"
)

MIGRATION_1_DDL = [
    ("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT"),
    (
        "CREATE TABLE plans ("
        "id TEXT PRIMARY KEY CHECK(length(id)>0), "
        "title TEXT NOT NULL, "
        "description TEXT, "
        f"status TEXT NOT NULL {STATUS_CHECK}, "
        "priority INTEGER CHECK(priority BETWEEN 0 AND 5), "
        "creation_time TEXT NOT NULL, "
        "completion_time TEXT, "
        "ord INTEGER NOT NULL, "
        "extra TEXT"
        ") STRICT"
    ),
    (
        "CREATE TABLE stories ("
        "plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE, "
        "id TEXT NOT NULL CHECK(length(id)>0), "
        "title TEXT NOT NULL, "
        f"status TEXT NOT NULL {STATUS_CHECK}, "
        "priority INTEGER, "
        "description TEXT, "
        "acceptance_criteria TEXT CHECK(acceptance_criteria IS NULL OR json_valid(acceptance_criteria)), "
        "depends_on TEXT CHECK(depends_on IS NULL OR json_valid(depends_on)), "
        "body TEXT, "
        "creation_time TEXT NOT NULL, "
        "completion_time TEXT, "
        "ord INTEGER NOT NULL, "
        "extra TEXT, "
        "PRIMARY KEY (plan_id, id), "
        "UNIQUE(plan_id, ord)"
        ") STRICT"
    ),
    (
        "CREATE TABLE tasks ("
        "plan_id TEXT NOT NULL, "
        "story_id TEXT NOT NULL, "
        "local_id TEXT NOT NULL CHECK(length(local_id)>0), "
        "title TEXT NOT NULL, "
        f"status TEXT NOT NULL {STATUS_CHECK}, "
        "priority INTEGER, "
        "description TEXT, "
        "depends_on TEXT CHECK(depends_on IS NULL OR json_valid(depends_on)), "
        "steps TEXT CHECK(steps IS NULL OR json_valid(steps)), "
        "changes TEXT CHECK(changes IS NULL OR json_valid(changes)), "
        "review_feedback TEXT CHECK(review_feedback IS NULL OR json_valid(review_feedback)), "
        "rework_count INTEGER NOT NULL DEFAULT 0, "
        "body TEXT, "
        "creation_time TEXT NOT NULL, "
        "completion_time TEXT, "
        "ord INTEGER NOT NULL, "
        "extra TEXT, "
        "PRIMARY KEY (plan_id, story_id, local_id), "
        "UNIQUE(plan_id, story_id, ord), "
        "FOREIGN KEY (plan_id, story_id) REFERENCES stories(plan_id, id) ON DELETE CASCADE"
        ") STRICT"
    ),
    (
        "CREATE TABLE plan_state ("
        "plan_id TEXT PRIMARY KEY REFERENCES plans(id) ON DELETE CASCADE, "
        "current_story_id TEXT, "
        "current_task_story_id TEXT, "
        "current_task_local_id TEXT, "
        "FOREIGN KEY (plan_id, current_story_id) REFERENCES stories(plan_id, id) ON DELETE SET NULL, "
        "FOREIGN KEY (plan_id, current_task_story_id, current_task_local_id) "
        "REFERENCES tasks(plan_id, story_id, local_id) ON DELETE SET NULL"
        ") STRICT"
    ),
    (
        "CREATE TABLE events ("
        "seq INTEGER PRIMARY KEY AUTOINCREMENT, "
        "plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE, "
        "legacy_id TEXT, "
        "ts TEXT NOT NULL, "
        "type TEXT NOT NULL, "
        "scope TEXT NOT NULL CHECK(json_valid(scope)), "
        "data TEXT CHECK(data IS NULL OR json_valid(data))"
        ") STRICT"
    ),
    "CREATE INDEX events_plan ON events(plan_id, seq)",
]


def apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply forward-only schema migrations based on PRAGMA user_version."""
    row = conn.execute("PRAGMA user_version").fetchone()
    current_version = int(row[0]) if row is not None else 0

    if current_version > LATEST_USER_VERSION:
        raise RuntimeError(
            f"Unsupported schema version {current_version}; "
            f"maximum supported is {LATEST_USER_VERSION}."
        )

    if current_version == 0:
        _apply_migration_1(conn)
        current_version = 1

    if current_version != LATEST_USER_VERSION:
        raise RuntimeError(
            f"Failed to reach schema version {LATEST_USER_VERSION}; got {current_version}."
        )


def _apply_migration_1(conn: sqlite3.Connection) -> None:
    with conn:
        for statement in MIGRATION_1_DDL:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (IMPORT_STATE_KEY, IMPORT_STATE_PENDING),
        )
