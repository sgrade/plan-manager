# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from plan_manager.config import PLANS_INDEX_FILE_PATH, TODO_DIR
from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.io.file_mirror import read_item_file, save_item_to_file
from plan_manager.services import activity_repository, plan_repository, state_repository


def _make_plan(plan_id: str, story_id: str) -> Plan:
    task = Task(
        id=f"{story_id}:task",
        title="Task",
        status=Status.TODO,
        story_id=story_id,
        local_id="task",
    )
    story = Story(id=story_id, title="Story", status=Status.TODO, tasks=[task])
    return Plan(
        id=plan_id, title=f"Plan {plan_id}", status=Status.TODO, stories=[story]
    )


def test_concurrent_yaml_writes_are_atomic_and_not_lost():
    thread_count = 16
    iterations = 10
    shared_merge_file = str(
        Path(TODO_DIR) / "default" / "concurrency_story" / "story.md"
    )

    # Ensure both IDs exist before concurrent current-plan flips.
    plan_repository.save(_make_plan("default", "bootstrap_default"), plan_id="default")
    plan_repository.save(_make_plan("anchor", "bootstrap_anchor"), plan_id="anchor")

    expected_merge_keys: set[str] = set()
    expected_plan_ids = {"default", "anchor"}
    expected_lock = threading.Lock()

    def worker(worker_id: int) -> None:
        for iteration in range(iterations):
            plan_id = f"plan_{worker_id}_{iteration}"
            story_id = f"story_{worker_id}_{iteration}"
            merge_key = f"merge_{worker_id}_{iteration}"

            plan_repository.save(_make_plan(plan_id, story_id), plan_id=plan_id)
            state_repository.set_current_story_id(
                f"current_story_{worker_id}_{iteration}", plan_id="default"
            )
            state_repository.set_current_task_id(
                f"current_task_{worker_id}_{iteration}", plan_id="default"
            )
            plan_repository.set_current_plan_id(
                "default" if (worker_id + iteration) % 2 == 0 else "anchor"
            )
            save_item_to_file(
                shared_merge_file, {merge_key: f"value_{merge_key}"}, overwrite=False
            )

            with expected_lock:
                expected_merge_keys.add(merge_key)
                expected_plan_ids.add(plan_id)

    with ThreadPoolExecutor(max_workers=thread_count) as pool:
        futures = [pool.submit(worker, worker_id) for worker_id in range(thread_count)]
        for future in futures:
            future.result()

    # Index updates should retain every plan inserted by concurrent workers.
    with Path(PLANS_INDEX_FILE_PATH).open(encoding="utf-8") as idx_file:
        index_data = yaml.safe_load(idx_file) or {}
    indexed_plan_ids = {entry["id"] for entry in index_data.get("plans", [])}
    assert expected_plan_ids.issubset(indexed_plan_ids)

    # Merged frontmatter should preserve every unique key written concurrently.
    merged_frontmatter, _ = read_item_file(shared_merge_file)
    assert expected_merge_keys.issubset(set(merged_frontmatter.keys()))

    # All yaml files under TODO_DIR should remain parseable.
    for yaml_file in Path(TODO_DIR).rglob("*.yaml"):
        with yaml_file.open(encoding="utf-8") as handle:
            yaml.safe_load(handle)


def test_concurrent_same_plan_save_and_activity_integrity():
    thread_count = 16
    iterations = 12
    shared_plan_id = "same_plan"
    expected_events = thread_count * iterations

    # Keep story writes scoped to the shared plan under test.
    plan_repository.save(
        _make_plan(shared_plan_id, "bootstrap_story"), plan_id=shared_plan_id
    )
    plan_repository.set_current_plan_id(shared_plan_id)

    def worker(worker_id: int) -> None:
        for iteration in range(iterations):
            story_id = f"same_story_{worker_id}_{iteration}"
            plan_repository.save(
                _make_plan(shared_plan_id, story_id),
                plan_id=shared_plan_id,
            )
            activity_repository.append_event(
                shared_plan_id,
                "story_saved",
                {"story_id": story_id},
                {"worker_id": worker_id, "iteration": iteration},
            )

    with ThreadPoolExecutor(max_workers=thread_count) as pool:
        futures = [pool.submit(worker, worker_id) for worker_id in range(thread_count)]
        for future in futures:
            future.result()

    events = activity_repository.list_events(shared_plan_id)
    assert len(events) == expected_events
    assert [event["id"] for event in events] == [
        str(i) for i in range(1, expected_events + 1)
    ]

    loaded_plan = plan_repository.load(shared_plan_id)
    assert len(loaded_plan.stories) == 1
    assert loaded_plan.stories[0].id.startswith("same_story_")

    # All yaml files under TODO_DIR should remain parseable.
    for yaml_file in Path(TODO_DIR).rglob("*.yaml"):
        with yaml_file.open(encoding="utf-8") as handle:
            yaml.safe_load(handle)
