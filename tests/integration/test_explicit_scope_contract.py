# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import inspect
import threading

import pytest

from plan_manager.domain.models import Status
from plan_manager.services.shared import service_uow
from plan_manager.storage import repositories
from plan_manager.tools import (
    changelog_tools,
    context_tools,
    plan_tools,
    report_tools,
    story_tools,
    task_tools,
)


def _counts() -> tuple[int, int, int]:
    with service_uow(write=False, operation="test_count_snapshot") as conn:
        return (
            len(repositories.list_plans(conn)),
            len(conn.execute("SELECT 1 FROM stories").fetchall()),
            len(conn.execute("SELECT 1 FROM tasks").fetchall()),
        )


@pytest.mark.integration
def test_plan_scoped_tools_require_plan_id_in_signature():
    plan_scoped_functions = [
        story_tools.create_story,
        story_tools.get_story,
        story_tools.update_story,
        story_tools.delete_story,
        story_tools.list_stories,
        story_tools.set_current_story,
        task_tools.create_task,
        task_tools.get_task,
        task_tools.update_task,
        task_tools.delete_task,
        task_tools.list_tasks,
        task_tools.set_current_task,
        task_tools.create_task_steps,
        task_tools.start_task,
        task_tools.submit_pr,
        task_tools.approve_pr,
        task_tools.request_pr_changes,
        task_tools.merge_pr,
        report_tools.report,
        context_tools.get_current,
        changelog_tools.generate_changelog_entry,
        changelog_tools.generate_commit_message,
        plan_tools.get_plan,
        plan_tools.update_plan,
        plan_tools.delete_plan,
    ]
    for fn in plan_scoped_functions:
        sig = inspect.signature(fn)
        assert "plan_id" in sig.parameters, f"{fn.__name__} must define plan_id"
        assert sig.parameters["plan_id"].default is inspect.Signature.empty, (
            f"{fn.__name__} plan_id must be required"
        )


@pytest.mark.integration
def test_missing_plan_id_rejected_before_write():
    before = _counts()
    with pytest.raises(TypeError):
        story_tools.create_story(title="x")
    with pytest.raises(TypeError):
        task_tools.create_task(story_id="s", title="t")
    with pytest.raises(TypeError):
        task_tools.start_task(task_id="s:t")
    with pytest.raises(TypeError):
        report_tools.report()
    after = _counts()
    assert after == before


@pytest.mark.integration
def test_scope_mismatch_rejected_before_write():
    from plan_manager.tools.plan_tools import create_plan

    plan_a = create_plan("Scope Plan A")
    plan_b = create_plan("Scope Plan B")
    story = story_tools.create_story(plan_a.id, "Story A")
    task = task_tools.create_task(plan_a.id, story.id, "Task A")

    before = _counts()
    with pytest.raises(ValueError, match="Scope mismatch"):
        story_tools.update_story(plan_b.id, story.id, title="Should fail")
    with pytest.raises(ValueError, match="Scope mismatch"):
        task_tools.create_task_steps(
            plan_id=plan_b.id,
            task_id=task.id,
            steps=[{"title": "Should fail"}],
        )
    assert _counts() == before


@pytest.mark.integration
def test_concurrent_agents_on_different_plans_do_not_interfere():
    from plan_manager.tools.plan_tools import create_plan

    plan_a = create_plan("Concurrent Plan A")
    plan_b = create_plan("Concurrent Plan B")
    story_a = story_tools.create_story(plan_a.id, "Story A")
    story_b = story_tools.create_story(plan_b.id, "Story B")
    task_a = task_tools.create_task(plan_a.id, story_a.id, "Task A")
    task_b = task_tools.create_task(plan_b.id, story_b.id, "Task B")

    errors: list[Exception] = []

    def worker(plan_id: str, story_id: str, task_id: str) -> None:
        try:
            task_tools.create_task_steps(
                plan_id=plan_id,
                task_id=task_id,
                steps=[{"title": "step"}],
                story_id=story_id,
            )
            task_tools.start_task(plan_id=plan_id, task_id=task_id, story_id=story_id)
            task_tools.submit_pr(
                plan_id=plan_id,
                task_id=task_id,
                story_id=story_id,
                changes=["implemented"],
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=worker, args=(plan_a.id, story_a.id, task_a.id))
    t2 = threading.Thread(target=worker, args=(plan_b.id, story_b.id, task_b.id))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors
    status_a = task_tools.get_task(plan_a.id, task_a.id).status
    status_b = task_tools.get_task(plan_b.id, task_b.id).status
    assert status_a is Status.PENDING_REVIEW
    assert status_b is Status.PENDING_REVIEW


@pytest.mark.integration
def test_workflow_happy_path_with_explicit_task_id():
    from plan_manager.tools.plan_tools import create_plan

    plan = create_plan("Workflow Plan")
    story = story_tools.create_story(plan.id, "Workflow Story")
    task = task_tools.create_task(plan.id, story.id, "Workflow Task")

    task_tools.create_task_steps(
        plan_id=plan.id,
        task_id=task.id,
        steps=[{"title": "Implement"}],
    )
    started = task_tools.start_task(plan_id=plan.id, task_id=task.id)
    assert started.success is True

    submitted = task_tools.submit_pr(
        plan_id=plan.id,
        task_id=task.id,
        changes=["Implemented workflow task"],
    )
    assert submitted.success is True

    approved = task_tools.approve_pr(plan_id=plan.id, task_id=task.id)
    assert approved.success is True
    assert approved.task.status is Status.DONE
