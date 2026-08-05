# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from plan_manager.domain.models import Status, Task
from plan_manager.storage.db import bootstrap
from plan_manager.storage.repositories import (
    StorageConflictError,
    TaskStatusTransitionConflictError,
    append_event,
    create_plan,
    create_story,
    create_task,
    delete_meta_value,
    delete_plan,
    delete_story,
    delete_task,
    get_meta_value,
    get_plan_state,
    list_events,
    list_stories,
    list_tasks,
    set_current_story,
    set_current_task,
    set_meta_value,
    transition_plan_status_guarded,
    transition_story_status_guarded,
    transition_task_status_guarded,
    update_task,
)
from plan_manager.storage.uow import unit_of_work


def _seed_plan_story_task(db_path: Path) -> None:
    with unit_of_work(db_path, write=True) as conn:
        create_plan(
            conn,
            base_id="plan-a",
            title="Plan A",
            description="seed",
            status=Status.TODO,
            priority=1,
            ord_value=0,
        )
        create_story(
            conn,
            plan_id="plan-a",
            base_id="story-a",
            title="Story A",
            description="seed",
            status=Status.TODO,
            priority=1,
            acceptance_criteria=[],
            depends_on=[],
            ord_value=0,
        )
        create_task(
            conn,
            plan_id="plan-a",
            story_id="story-a",
            base_local_id="task-a",
            title="Task A",
            description="seed",
            status=Status.TODO,
            priority=1,
            depends_on=[],
            steps=[Task.Step(title="step")],
            changes=[],
            review_feedback=[],
            ord_value=0,
        )


def test_same_plan_concurrent_create_story_allocates_distinct_ids(
    tmp_path: Path,
) -> None:
    db_path = bootstrap(tmp_path)
    with unit_of_work(db_path, write=True) as conn:
        create_plan(
            conn,
            base_id="race-plan",
            title="Race Plan",
            description=None,
            status=Status.TODO,
            priority=None,
            ord_value=0,
        )

    ready = threading.Barrier(2)
    errors: list[Exception] = []
    created_ids: list[str] = []
    lock = threading.Lock()

    def worker(worker_ord: int) -> None:
        try:
            ready.wait(timeout=1.0)
            with unit_of_work(db_path, write=True, busy_timeout_ms=3000) as conn:
                story_id = create_story(
                    conn,
                    plan_id="race-plan",
                    base_id="same",
                    title=f"Story {worker_ord}",
                    description=None,
                    status=Status.TODO,
                    priority=worker_ord,
                    acceptance_criteria=[],
                    depends_on=[],
                    ord_value=worker_ord,
                )
                with lock:
                    created_ids.append(story_id)
        except (sqlite3.Error, RuntimeError, threading.BrokenBarrierError) as exc:
            with lock:
                errors.append(exc)

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    assert not errors
    assert sorted(created_ids) == ["same", "same-2"]
    with sqlite3.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM stories WHERE plan_id = ?",
            ("race-plan",),
        ).fetchone()
    assert count is not None
    assert int(count[0]) == 2


def test_guarded_task_transition_race_allows_exactly_one_winner(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    _seed_plan_story_task(db_path)

    ready = threading.Barrier(2)
    wins = 0
    conflicts = 0
    lock = threading.Lock()
    errors: list[Exception] = []

    def worker() -> None:
        nonlocal wins, conflicts
        try:
            ready.wait(timeout=1.0)
            with unit_of_work(db_path, write=True, busy_timeout_ms=3000) as conn:
                try:
                    ok = transition_task_status_guarded(
                        conn,
                        plan_id="plan-a",
                        story_id="story-a",
                        local_id="task-a",
                        expected_status=Status.TODO,
                        next_status=Status.IN_PROGRESS,
                    )
                    with lock:
                        wins += int(ok)
                except TaskStatusTransitionConflictError:
                    with lock:
                        conflicts += 1
        except (sqlite3.Error, RuntimeError, threading.BrokenBarrierError) as exc:
            with lock:
                errors.append(exc)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=3.0)
    t2.join(timeout=3.0)

    assert not errors
    assert wins == 1
    assert conflicts == 1
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT status FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            ("plan-a", "story-a", "task-a"),
        ).fetchone()
    assert row is not None
    assert row[0] == Status.IN_PROGRESS.value


def test_guarded_transition_conflict_is_typed(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    _seed_plan_story_task(db_path)

    with unit_of_work(db_path, write=True) as conn:
        with pytest.raises(TaskStatusTransitionConflictError) as exc:
            transition_task_status_guarded(
                conn,
                plan_id="plan-a",
                story_id="story-a",
                local_id="task-a",
                expected_status=Status.DONE,
                next_status=Status.IN_PROGRESS,
            )
    assert exc.value.plan_id == "plan-a"
    assert exc.value.story_id == "story-a"
    assert exc.value.local_id == "task-a"


def test_meta_value_round_trip(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    key = "agent_scope_test_key"
    with unit_of_work(db_path, write=True) as conn:
        assert get_meta_value(conn, key) is None
        set_meta_value(conn, key, "plan-a")
    with unit_of_work(db_path) as conn:
        assert get_meta_value(conn, key) == "plan-a"
    with unit_of_work(db_path, write=True) as conn:
        delete_meta_value(conn, key)
    with unit_of_work(db_path) as conn:
        assert get_meta_value(conn, key) is None


def test_story_and_plan_guarded_transition_conflicts(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    _seed_plan_story_task(db_path)

    with unit_of_work(db_path, write=True) as conn:
        with pytest.raises(StorageConflictError):
            transition_story_status_guarded(
                conn,
                plan_id="plan-a",
                story_id="story-a",
                expected_status=Status.DONE,
                next_status=Status.IN_PROGRESS,
            )
        with pytest.raises(StorageConflictError):
            transition_plan_status_guarded(
                conn,
                plan_id="plan-a",
                expected_status=Status.DONE,
                next_status=Status.IN_PROGRESS,
            )


def test_story_and_plan_guarded_transition_sets_and_clears_completion_time(
    tmp_path: Path,
) -> None:
    db_path = bootstrap(tmp_path)
    _seed_plan_story_task(db_path)

    with unit_of_work(db_path, write=True) as conn:
        transition_story_status_guarded(
            conn,
            plan_id="plan-a",
            story_id="story-a",
            expected_status=Status.TODO,
            next_status=Status.DONE,
            completion_time="2026-08-05T06:00:00.000Z",
        )
        transition_plan_status_guarded(
            conn,
            plan_id="plan-a",
            expected_status=Status.TODO,
            next_status=Status.DONE,
            completion_time="2026-08-05T06:00:01.000Z",
        )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT (SELECT completion_time FROM stories WHERE plan_id = ? AND id = ?), "
            "(SELECT completion_time FROM plans WHERE id = ?)",
            ("plan-a", "story-a", "plan-a"),
        ).fetchone()
    assert row == ("2026-08-05T06:00:00.000Z", "2026-08-05T06:00:01.000Z")

    with unit_of_work(db_path, write=True) as conn:
        transition_story_status_guarded(
            conn,
            plan_id="plan-a",
            story_id="story-a",
            expected_status=Status.DONE,
            next_status=Status.IN_PROGRESS,
            completion_time=None,
        )
        transition_plan_status_guarded(
            conn,
            plan_id="plan-a",
            expected_status=Status.DONE,
            next_status=Status.IN_PROGRESS,
            completion_time=None,
        )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT (SELECT completion_time FROM stories WHERE plan_id = ? AND id = ?), "
            "(SELECT completion_time FROM plans WHERE id = ?)",
            ("plan-a", "story-a", "plan-a"),
        ).fetchone()
    assert row == (None, None)


def test_update_task_is_per_item_write(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    with unit_of_work(db_path, write=True) as conn:
        create_plan(
            conn,
            base_id="plan-p",
            title="Plan P",
            description=None,
            status=Status.TODO,
            priority=1,
            ord_value=0,
        )
        create_story(
            conn,
            plan_id="plan-p",
            base_id="story-p",
            title="Story P",
            description=None,
            status=Status.TODO,
            priority=1,
            acceptance_criteria=[],
            depends_on=[],
            ord_value=0,
        )
        create_task(
            conn,
            plan_id="plan-p",
            story_id="story-p",
            base_local_id="one",
            title="One",
            description=None,
            status=Status.TODO,
            priority=1,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            ord_value=0,
        )
        create_task(
            conn,
            plan_id="plan-p",
            story_id="story-p",
            base_local_id="two",
            title="Two",
            description="stable",
            status=Status.TODO,
            priority=2,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            ord_value=1,
        )

    with sqlite3.connect(db_path) as conn:
        before = conn.execute(
            "SELECT title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra "
            "FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            ("plan-p", "story-p", "two"),
        ).fetchone()
    assert before is not None

    with unit_of_work(db_path, write=True) as conn:
        updated = update_task(
            conn,
            plan_id="plan-p",
            story_id="story-p",
            local_id="one",
            title="One Updated",
            rollup_story_status=Status.IN_PROGRESS,
            rollup_plan_status=Status.IN_PROGRESS,
        )
    assert updated

    with sqlite3.connect(db_path) as conn:
        after = conn.execute(
            "SELECT title, description, status, priority, depends_on, steps, changes, review_feedback, rework_count, body, creation_time, completion_time, ord, extra "
            "FROM tasks WHERE plan_id = ? AND story_id = ? AND local_id = ?",
            ("plan-p", "story-p", "two"),
        ).fetchone()
    assert after == before


def test_fk_state_pointers_and_cascades(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    _seed_plan_story_task(db_path)

    with unit_of_work(db_path, write=True) as conn:
        set_current_story(conn, plan_id="plan-a", current_story_id="story-a")
        set_current_task(
            conn,
            plan_id="plan-a",
            current_task_story_id="story-a",
            current_task_local_id="task-a",
        )
        append_event(
            conn,
            plan_id="plan-a",
            event_type="task_created",
            scope={"task_id": "story-a:task-a"},
        )

    with unit_of_work(db_path, write=True) as conn:
        deleted = delete_task(conn, "plan-a", "story-a", "task-a")
    assert deleted
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT current_story_id, current_task_story_id, current_task_local_id "
            "FROM plan_state WHERE plan_id = ?",
            ("plan-a",),
        ).fetchone()
    assert row == ("story-a", None, None)

    with unit_of_work(db_path, write=True) as conn:
        story_deleted = delete_story(conn, "plan-a", "story-a")
    assert story_deleted
    with unit_of_work(db_path) as conn:
        state = get_plan_state(conn, "plan-a")
    assert state.current_story_id is None
    assert state.current_task_id is None

    with unit_of_work(db_path, write=True) as conn:
        delete_plan(conn, "plan-a")
    with sqlite3.connect(db_path) as conn:
        counts = conn.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM plans), "
            "(SELECT COUNT(*) FROM stories), "
            "(SELECT COUNT(*) FROM tasks), "
            "(SELECT COUNT(*) FROM plan_state), "
            "(SELECT COUNT(*) FROM events)"
        ).fetchone()
    assert counts == (0, 0, 0, 0, 0)


def test_event_append_is_transactional_and_rolls_back(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    with unit_of_work(db_path, write=True) as conn:
        create_plan(
            conn,
            base_id="events-plan",
            title="Events Plan",
            description=None,
            status=Status.TODO,
            priority=None,
            ord_value=0,
        )

    with pytest.raises(RuntimeError, match="rollback"):
        with unit_of_work(db_path, write=True) as conn:
            append_event(
                conn,
                plan_id="events-plan",
                event_type="x",
                scope={"story_id": "s"},
            )
            raise RuntimeError("rollback")

    with unit_of_work(db_path) as conn:
        events = list_events(conn, "events-plan")
    assert events == []


def test_list_ordering_matches_service_expectations(tmp_path: Path) -> None:
    db_path = bootstrap(tmp_path)
    with unit_of_work(db_path, write=True) as conn:
        create_plan(
            conn,
            base_id="order-plan",
            title="Order Plan",
            description=None,
            status=Status.TODO,
            priority=None,
            ord_value=0,
        )
        create_story(
            conn,
            plan_id="order-plan",
            base_id="a",
            title="A",
            description=None,
            status=Status.DONE,
            priority=2,
            acceptance_criteria=[],
            depends_on=[],
            creation_time="2026-08-04T10:00:01.000Z",
            ord_value=0,
        )
        create_story(
            conn,
            plan_id="order-plan",
            base_id="b",
            title="B",
            description=None,
            status=Status.TODO,
            priority=1,
            acceptance_criteria=[],
            depends_on=["a"],
            creation_time="2026-08-04T10:00:03.000Z",
            ord_value=1,
        )
        create_story(
            conn,
            plan_id="order-plan",
            base_id="c",
            title="C",
            description=None,
            status=Status.TODO,
            priority=1,
            acceptance_criteria=[],
            depends_on=[],
            creation_time="2026-08-04T10:00:00.000Z",
            ord_value=2,
        )
        create_task(
            conn,
            plan_id="order-plan",
            story_id="a",
            base_local_id="z",
            title="Z",
            description=None,
            status=Status.TODO,
            priority=None,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            creation_time="2026-08-04T10:00:01.000Z",
            ord_value=0,
        )
        create_task(
            conn,
            plan_id="order-plan",
            story_id="a",
            base_local_id="x",
            title="X",
            description=None,
            status=Status.TODO,
            priority=1,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            creation_time="2026-08-04T10:00:00.000Z",
            ord_value=1,
        )
        create_task(
            conn,
            plan_id="order-plan",
            story_id="a",
            base_local_id="y",
            title="Y",
            description=None,
            status=Status.TODO,
            priority=1,
            depends_on=[],
            steps=[],
            changes=[],
            review_feedback=[],
            creation_time="2026-08-04T10:00:02.000Z",
            ord_value=2,
        )

    with unit_of_work(db_path) as conn:
        stories = list_stories(conn, "order-plan")
        unblocked_todo = list_stories(
            conn,
            "order-plan",
            statuses=[Status.TODO],
            unblocked=True,
        )
        tasks = list_tasks(conn, "order-plan")

    assert [story.id for story in stories] == ["c", "a", "b"]
    assert [story.id for story in unblocked_todo] == ["c", "b"]
    assert [task.id for task in tasks] == ["a:x", "a:y", "a:z"]


def test_repository_module_avoids_connect_and_uow_calls() -> None:
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "plan_manager"
        / "storage"
        / "repositories.py"
    )
    source = module_path.read_text(encoding="utf-8")
    assert "sqlite3.connect(" not in source
    assert "unit_of_work(" not in source
    assert "from plan_manager.services" not in source
    assert "from plan_manager.tools" not in source
    assert "from plan_manager.server" not in source
