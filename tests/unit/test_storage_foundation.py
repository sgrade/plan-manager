# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime

import pytest

from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.storage.db import StorageBootstrapError, bootstrap
from plan_manager.storage.uow import canonical_utc_timestamp, unit_of_work


def _insert_plan_row(conn: sqlite3.Connection, plan_id: str, order: int = 0) -> None:
    conn.execute(
        "INSERT INTO plans(id, title, description, status, priority, creation_time, completion_time, ord, extra) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            plan_id,
            f"Plan {plan_id}",
            "desc",
            Status.TODO.value,
            1,
            canonical_utc_timestamp(),
            None,
            order,
            json.dumps({"marker": plan_id}),
        ),
    )


def test_uow_applies_connection_pragmas_per_connection(tmp_path):
    db_path = bootstrap(tmp_path)

    with unit_of_work(db_path, busy_timeout_ms=1234) as conn:
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()
        assert foreign_keys is not None
        assert int(foreign_keys[0]) == 1
        assert busy_timeout is not None
        assert int(busy_timeout[0]) == 1234

    with unit_of_work(db_path, busy_timeout_ms=3456) as conn:
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()
        assert busy_timeout is not None
        assert int(busy_timeout[0]) == 3456


def test_uow_rolls_back_on_exception_and_releases_write_lock(tmp_path):
    db_path = bootstrap(tmp_path)

    with pytest.raises(RuntimeError):
        with unit_of_work(db_path, write=True) as conn:
            _insert_plan_row(conn, "rolled-back")
            raise RuntimeError("force rollback")

    second_conn = sqlite3.connect(db_path, timeout=0.05)
    try:
        second_conn.execute("BEGIN IMMEDIATE")
        second_conn.execute(
            "INSERT INTO plans(id, title, status, creation_time, ord) VALUES (?, ?, ?, ?, ?)",
            ("committed", "Committed", Status.TODO.value, canonical_utc_timestamp(), 1),
        )
        second_conn.commit()
    finally:
        second_conn.close()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM plans WHERE id IN (?, ?) ORDER BY id",
            ("committed", "rolled-back"),
        ).fetchall()
    assert [row[0] for row in rows] == ["committed"]


class _RecordingConnection:
    """Delegating proxy that records rollback/close calls (U4 review, major 2).

    The plain behavioral leak test cannot distinguish explicit cleanup from
    CPython's refcounting GC closing an orphaned connection; these spies can.
    """

    def __init__(self, real: sqlite3.Connection) -> None:
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "calls", [])

    def rollback(self):
        self.calls.append("rollback")
        return self._real.rollback()

    def close(self):
        self.calls.append("close")
        return self._real.close()

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)


def test_uow_explicitly_rolls_back_and_closes_on_exception(tmp_path, monkeypatch):
    db_path = bootstrap(tmp_path)
    recorded: list[_RecordingConnection] = []
    real_connect = sqlite3.connect

    def recording_connect(*args, **kwargs):
        wrapper = _RecordingConnection(real_connect(*args, **kwargs))
        recorded.append(wrapper)
        return wrapper

    monkeypatch.setattr("plan_manager.storage.uow.sqlite3.connect", recording_connect)

    with pytest.raises(RuntimeError, match="force rollback"):
        with unit_of_work(db_path, write=True) as conn:
            _insert_plan_row(conn, "spied-rollback")
            raise RuntimeError("force rollback")

    assert len(recorded) == 1
    # Explicit rollback must precede explicit close; GC involvement would
    # leave calls empty or incomplete.
    assert recorded[0].calls == ["rollback", "close"]


def test_uow_read_mode_rejects_write_statements(tmp_path):
    db_path = bootstrap(tmp_path)

    from plan_manager.storage.uow import StorageMisuseError

    with pytest.raises(StorageMisuseError):
        with unit_of_work(db_path) as conn:
            _insert_plan_row(conn, "swallowed-write")

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id FROM plans WHERE id = ?", ("swallowed-write",)
        ).fetchall()
    assert rows == []


def test_bootstrap_is_idempotent_across_restarts(tmp_path):
    db_path = bootstrap(tmp_path)
    db_path_again = bootstrap(tmp_path)
    assert db_path == db_path_again


# NOTE: threads below intentionally use distinct plan ids; SQLite's write lock
# is database-global, so this exercises the same contention path. Same-plan
# *semantic* races are covered at the repository layer in U5b (U4 review, minor).
def test_uow_contention_retries_begin_immediate(tmp_path, monkeypatch):
    db_path = bootstrap(tmp_path)
    retry_sleep_calls: list[float] = []
    retry_observed = threading.Event()
    allow_retry_to_continue = threading.Event()
    holder_started = threading.Event()
    release_holder = threading.Event()

    def fake_sleep(seconds: float) -> None:
        retry_sleep_calls.append(seconds)
        retry_observed.set()
        allow_retry_to_continue.wait(timeout=5.0)

    monkeypatch.setattr("plan_manager.storage.uow.time.sleep", fake_sleep)
    monkeypatch.setattr("plan_manager.storage.uow.random.uniform", lambda _a, _b: 0.0)

    def lock_holder() -> None:
        with unit_of_work(db_path, write=True, busy_timeout_ms=10) as conn:
            _insert_plan_row(conn, "holder")
            holder_started.set()
            release_holder.wait(timeout=2.0)

    contender_error: list[RuntimeError] = []

    def contender() -> None:
        try:
            with unit_of_work(db_path, write=True, busy_timeout_ms=10) as conn:
                _insert_plan_row(conn, "contender", order=1)
        except (
            RuntimeError
        ) as exc:  # pragma: no cover - defensive capture for thread failures
            contender_error.append(exc)

    holder_thread = threading.Thread(target=lock_holder)
    contender_thread = threading.Thread(target=contender)
    holder_thread.start()
    assert holder_started.wait(timeout=1.0)

    contender_thread.start()
    assert retry_observed.wait(timeout=1.0)
    # Retire the holder completely before releasing the retry: sleep is faked to
    # return instantly, so a holder still committing would burn every remaining
    # attempt against the 10ms busy timeout and raise StorageBusyError.
    release_holder.set()
    holder_thread.join(timeout=5.0)
    assert not holder_thread.is_alive(), "Lock holder did not release."
    allow_retry_to_continue.set()

    contender_thread.join(timeout=5.0)

    assert not contender_error
    assert retry_sleep_calls, "Expected at least one busy retry sleep."
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM plans WHERE id IN ('holder', 'contender')"
        ).fetchone()
    assert count is not None
    assert int(count[0]) == 2


def test_bootstrap_fails_loudly_when_wal_verification_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "plan_manager.storage.db._set_journal_mode_wal", lambda _conn: "delete"
    )

    with pytest.raises(StorageBootstrapError):
        bootstrap(tmp_path)


def test_schema_round_trip_full_plan_story_task_payload(tmp_path):
    db_path = bootstrap(tmp_path)
    base_time = datetime(2026, 8, 4, 12, 34, 56, 789000, tzinfo=UTC)

    prep_task = Task(
        id="story-main:prep",
        story_id="story-main",
        local_id="prep",
        title="Prep",
        description="Prepare environment",
        status=Status.TODO,
        priority=2,
        depends_on=[],
        steps=[Task.Step(title="Read docs", description="Review architecture docs")],
        changes=["initialized workspace"],
        review_feedback=[],
        rework_count=0,
        creation_time=base_time,
        completion_time=None,
    )
    main_task = Task(
        id="story-main:build",
        story_id="story-main",
        local_id="build",
        title="Build",
        description="Implement feature",
        status=Status.PENDING_REVIEW,
        priority=1,
        depends_on=["story-main:prep"],
        steps=[
            Task.Step(title="Write schema", description="Create strict DDL"),
            Task.Step(title="Add tests"),
        ],
        changes=["added schema", "added tests"],
        review_feedback=[
            Task.ReviewFeedback(
                message="Looks good",
                by="reviewer-1",
                at=base_time,
            )
        ],
        rework_count=2,
        creation_time=base_time,
        completion_time=base_time,
    )
    dependency_story = Story(
        id="story-prior",
        title="Prior Story",
        description="Dependency story",
        status=Status.DONE,
        priority=3,
        acceptance_criteria=["prior done"],
        depends_on=[],
        tasks=[],
        creation_time=base_time,
        completion_time=base_time,
    )
    main_story = Story(
        id="story-main",
        title="Main Story",
        description="Main implementation story",
        status=Status.IN_PROGRESS,
        priority=1,
        acceptance_criteria=["criterion one", "criterion two"],
        depends_on=["story-prior"],
        tasks=[prep_task, main_task],
        creation_time=base_time,
        completion_time=None,
    )
    plan = Plan(
        id="plan-alpha",
        title="Plan Alpha",
        description="A complete plan payload",
        status=Status.IN_PROGRESS,
        priority=1,
        stories=[dependency_story, main_story],
        creation_time=base_time,
        completion_time=None,
    )

    with unit_of_work(db_path, write=True) as conn:
        conn.execute(
            "INSERT INTO plans(id, title, description, status, priority, creation_time, completion_time, ord, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                plan.id,
                plan.title,
                plan.description,
                plan.status.value,
                plan.priority,
                canonical_utc_timestamp(plan.creation_time),
                None,
                0,
                json.dumps({"notes": "keep me"}),
            ),
        )
        conn.execute(
            "INSERT INTO stories(plan_id, id, title, status, priority, description, acceptance_criteria, depends_on, body, creation_time, completion_time, ord, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                plan.id,
                dependency_story.id,
                dependency_story.title,
                dependency_story.status.value,
                dependency_story.priority,
                dependency_story.description,
                json.dumps(dependency_story.acceptance_criteria),
                json.dumps(dependency_story.depends_on),
                "dependency story body",
                canonical_utc_timestamp(dependency_story.creation_time),
                canonical_utc_timestamp(dependency_story.completion_time),
                0,
                json.dumps({"legacy_key": "dependency"}),
            ),
        )
        conn.execute(
            "INSERT INTO stories(plan_id, id, title, status, priority, description, acceptance_criteria, depends_on, body, creation_time, completion_time, ord, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                plan.id,
                main_story.id,
                main_story.title,
                main_story.status.value,
                main_story.priority,
                main_story.description,
                json.dumps(main_story.acceptance_criteria),
                json.dumps(main_story.depends_on),
                "main story body",
                canonical_utc_timestamp(main_story.creation_time),
                None,
                1,
                json.dumps({"legacy_key": "main"}),
            ),
        )
        for ord_value, task in enumerate(main_story.tasks):
            conn.execute(
                "INSERT INTO tasks(plan_id, story_id, local_id, title, status, priority, description, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    plan.id,
                    main_story.id,
                    task.local_id,
                    task.title,
                    task.status.value,
                    task.priority,
                    task.description,
                    json.dumps(task.depends_on),
                    json.dumps([step.model_dump() for step in task.steps or []]),
                    json.dumps(task.changes),
                    json.dumps(
                        [
                            {
                                "message": feedback.message,
                                "at": canonical_utc_timestamp(feedback.at),
                                "by": feedback.by,
                            }
                            for feedback in task.review_feedback
                        ]
                    ),
                    task.rework_count,
                    f"{task.title} body",
                    canonical_utc_timestamp(task.creation_time),
                    (
                        canonical_utc_timestamp(task.completion_time)
                        if task.completion_time
                        else None
                    ),
                    ord_value,
                    json.dumps({"legacy_key": task.local_id}),
                ),
            )

    with unit_of_work(db_path) as conn:
        plan_row = conn.execute(
            "SELECT id, title, description, status, priority, creation_time, completion_time, extra "
            "FROM plans WHERE id = ?",
            (plan.id,),
        ).fetchone()
        story_rows = conn.execute(
            "SELECT id, title, description, status, priority, acceptance_criteria, depends_on, creation_time, completion_time, ord, extra "
            "FROM stories WHERE plan_id = ? ORDER BY ord",
            (plan.id,),
        ).fetchall()
        task_rows = conn.execute(
            "SELECT story_id, local_id, title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, creation_time, completion_time, ord, extra "
            "FROM tasks WHERE plan_id = ? ORDER BY story_id, ord",
            (plan.id,),
        ).fetchall()

    assert plan_row is not None
    story_by_id: dict[str, Story] = {}
    for row in story_rows:
        story_by_id[str(row["id"])] = Story(
            id=str(row["id"]),
            title=str(row["title"]),
            description=row["description"],
            status=Status(str(row["status"])),
            priority=row["priority"],
            acceptance_criteria=json.loads(str(row["acceptance_criteria"])),
            depends_on=json.loads(str(row["depends_on"])),
            creation_time=str(row["creation_time"]),
            completion_time=row["completion_time"],
            tasks=[],
        )

    for row in task_rows:
        task = Task(
            id=f"{row['story_id']}:{row['local_id']}",
            story_id=str(row["story_id"]),
            local_id=str(row["local_id"]),
            title=str(row["title"]),
            description=row["description"],
            status=Status(str(row["status"])),
            priority=row["priority"],
            depends_on=json.loads(str(row["depends_on"])),
            steps=[
                Task.Step.model_validate(step) for step in json.loads(str(row["steps"]))
            ],
            changes=json.loads(str(row["changes"])),
            review_feedback=[
                Task.ReviewFeedback.model_validate(feedback)
                for feedback in json.loads(str(row["review_feedback"]))
            ],
            rework_count=int(row["rework_count"]),
            creation_time=str(row["creation_time"]),
            completion_time=row["completion_time"],
        )
        story_by_id[str(row["story_id"])].tasks.append(task)

    round_trip_plan = Plan(
        id=str(plan_row["id"]),
        title=str(plan_row["title"]),
        description=plan_row["description"],
        status=Status(str(plan_row["status"])),
        priority=plan_row["priority"],
        creation_time=str(plan_row["creation_time"]),
        completion_time=plan_row["completion_time"],
        stories=list(story_by_id.values()),
    )

    loaded_main_story = next(
        story for story in round_trip_plan.stories if story.id == "story-main"
    )
    loaded_main_task = next(
        task for task in loaded_main_story.tasks if task.local_id == "build"
    )

    assert round_trip_plan.id == plan.id
    assert round_trip_plan.status == plan.status
    assert loaded_main_story.depends_on == main_story.depends_on
    assert loaded_main_story.acceptance_criteria == main_story.acceptance_criteria
    assert loaded_main_task.depends_on == main_task.depends_on
    assert [step.model_dump() for step in (loaded_main_task.steps or [])] == [
        step.model_dump() for step in (main_task.steps or [])
    ]
    assert loaded_main_task.changes == main_task.changes
    assert loaded_main_task.review_feedback[0].message == "Looks good"
    assert loaded_main_task.review_feedback[0].by == "reviewer-1"
    assert loaded_main_task.rework_count == main_task.rework_count

    with sqlite3.connect(db_path) as conn:
        extra_values = conn.execute(
            "SELECT extra FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            (plan.id, main_story.id, main_task.local_id),
        ).fetchone()
    assert extra_values is not None
    assert json.loads(str(extra_values[0])) == {"legacy_key": "build"}
