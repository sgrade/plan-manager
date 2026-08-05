# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import threading

import pytest

from plan_manager.domain.models import Status


def test_submit_pr_rolls_back_when_event_append_fails(monkeypatch):
    from plan_manager.services import plan_service, story_service, task_service
    from plan_manager.services.shared import set_current_plan_id, set_current_task_id
    from plan_manager.storage import repositories

    plan = plan_service.create_plan("Atomicity Plan", None, None)
    set_current_plan_id(plan["id"])
    story = story_service.create_story("Atomicity Story", None, None, None, [])
    task = task_service.create_task(story["id"], "Atomicity Task", None, [], None)
    task_local_id = task["id"].split(":", 1)[1]

    task_service.create_steps(story["id"], task_local_id, [{"title": "step"}])
    set_current_task_id(task["id"], plan["id"])
    task_service.start_current_task()

    original_append = repositories.append_event

    def failing_append(*args, **kwargs):
        raise RuntimeError("injected event failure")

    monkeypatch.setattr(
        "plan_manager.services.task_service.repositories.append_event", failing_append
    )
    try:
        with pytest.raises(RuntimeError, match="injected event failure"):
            task_service.submit_pr(story["id"], task_local_id, ["changed"])
    finally:
        monkeypatch.setattr(
            "plan_manager.services.task_service.repositories.append_event",
            original_append,
        )

    task_after = task_service.get_task(story["id"], task_local_id)
    assert task_after["status"] == Status.IN_PROGRESS
    assert task_after.get("changes") == []


def test_concurrent_create_story_generates_distinct_ids():
    from plan_manager.services import plan_service, story_service
    from plan_manager.services.shared import set_current_plan_id

    plan = plan_service.create_plan("Story Race Plan", None, None)
    set_current_plan_id(plan["id"])

    ready = threading.Barrier(2)
    created_ids: list[str] = []
    failures: list[Exception] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            ready.wait(timeout=2.0)
            story = story_service.create_story("Same title", None, None, None, [])
            with lock:
                created_ids.append(story["id"])
        except Exception as exc:  # noqa: BLE001
            with lock:
                failures.append(exc)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=4.0)
    t2.join(timeout=4.0)

    assert not failures
    assert len(created_ids) == 2
    assert len(set(created_ids)) == 2


def test_concurrent_start_task_allows_exactly_one_success():
    from plan_manager.services import plan_service, story_service, task_service
    from plan_manager.services.shared import (
        set_current_plan_id,
        set_current_story_id,
        set_current_task_id,
    )

    plan = plan_service.create_plan("Start Race Plan", None, None)
    set_current_plan_id(plan["id"])
    story = story_service.create_story("Start Race Story", None, None, None, [])
    task = task_service.create_task(story["id"], "Start Race Task", None, [], None)
    task_local_id = task["id"].split(":", 1)[1]
    task_service.create_steps(story["id"], task_local_id, [{"title": "step"}])
    set_current_story_id(story["id"], plan["id"])
    set_current_task_id(task["id"], plan["id"])

    ready = threading.Barrier(2)
    outcomes: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            ready.wait(timeout=2.0)
            task_service.start_current_task()
            success = True
        except Exception:  # noqa: BLE001
            success = False
        with lock:
            outcomes.append(success)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=4.0)
    t2.join(timeout=4.0)

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 1
    task_after = task_service.get_task(story["id"], task_local_id)
    assert task_after["status"] == Status.IN_PROGRESS


def test_done_transitions_set_completion_time_and_roundtrip():
    from plan_manager.services import plan_service, story_service, task_service
    from plan_manager.services.shared import (
        set_current_plan_id,
        set_current_story_id,
        set_current_task_id,
    )

    plan = plan_service.create_plan("Completion Plan", None, None)
    set_current_plan_id(plan["id"])
    story = story_service.create_story("Completion Story", None, None, None, [])
    task = task_service.create_task(story["id"], "Completion Task", None, [], None)
    task_local_id = task["id"].split(":", 1)[1]

    set_current_story_id(story["id"], plan["id"])
    set_current_task_id(task["id"], plan["id"])
    task_service.create_steps(story["id"], task_local_id, [{"title": "step"}])
    task_service.start_current_task()
    task_service.submit_pr(story["id"], task_local_id, ["implemented"])
    task_service.approve_pr()

    done_task = task_service.get_task(story["id"], task_local_id)
    done_story = story_service.get_story(story["id"])
    done_plan = plan_service.get_plan(plan["id"])

    assert done_task["status"] == Status.DONE
    assert done_story["status"] == Status.DONE
    assert done_plan["status"] == Status.DONE
    assert done_task["completion_time"] is not None
    assert done_story["completion_time"] is not None
    assert done_plan["completion_time"] is not None


def test_set_current_task_local_id_uses_single_uow(monkeypatch):
    from plan_manager.services import plan_service, shared, story_service, task_service
    from plan_manager.services.shared import set_current_plan_id, set_current_story_id

    plan = plan_service.create_plan("Set Current Task Plan", None, None)
    set_current_plan_id(plan["id"])
    story = story_service.create_story("Set Current Task Story", None, None, None, [])
    task = task_service.create_task(story["id"], "Set Current Task", None, [], None)
    task_local_id = task["id"].split(":", 1)[1]
    set_current_story_id(story["id"], plan["id"])

    original_service_uow = shared.service_uow
    uow_calls = 0

    def counting_service_uow(*args, **kwargs):
        nonlocal uow_calls
        uow_calls += 1
        return original_service_uow(*args, **kwargs)

    monkeypatch.setattr(
        "plan_manager.services.shared.service_uow", counting_service_uow
    )
    shared.set_current_task_id(task_local_id, plan["id"])
    assert uow_calls == 1
