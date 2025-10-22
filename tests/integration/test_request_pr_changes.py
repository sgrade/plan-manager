"""Integration test for request_pr_changes workflow."""

import uuid

import pytest

from plan_manager.domain.models import Status


@pytest.mark.integration
def test_request_pr_changes_workflow():
    """Test the complete review workflow including requesting changes."""
    # Test isolation handled by autouse fixture in conftest.py

    from plan_manager.services import plan_repository as repo
    from plan_manager.services import plan_service, story_service, task_service
    from plan_manager.services import state_repository as state

    suffix = str(uuid.uuid4())[:8]
    plan_title = f"test-review-{suffix}"
    plan = plan_service.create_plan(plan_title, description=None, priority=None)
    plan_id = plan["id"]
    repo.set_current_plan_id(plan_id)

    story = story_service.create_story(
        title=f"Review Story {suffix}",
        description=None,
        acceptance_criteria=None,
        priority=None,
        depends_on=[],
    )
    story_id = story["id"]
    state.set_current_story_id(story_id)

    # Create a task
    task = task_service.create_task(
        story_id=story_id,
        title=f"Review Task {suffix}",
        priority=None,
        depends_on=[],
        description=None,
    )
    task_id = task["id"]
    task_local = task_id.split(":", 1)[1]
    state.set_current_task_id(task_id)

    # Add steps and start task (TODO → IN_PROGRESS)
    steps = [{"title": "Implement feature", "description": "Do the work"}]
    task_service.create_steps(story_id=story_id, task_id=task_local, steps=steps)
    result = task_service.start_current_task()
    assert result["success"] is True

    task_data = task_service.get_task(story_id, task_local)
    assert task_data["status"] == Status.IN_PROGRESS

    # Submit for review (IN_PROGRESS → PENDING_REVIEW)
    result = task_service.submit_pr(
        story_id=story_id,
        task_id=task_local,
        changes=["Implemented feature X", "Added basic tests"],
    )
    task_data = task_service.get_task(story_id, task_local)
    assert task_data["status"] == Status.PENDING_REVIEW
    assert task_data["rework_count"] == 0

    # Request changes (PENDING_REVIEW → IN_PROGRESS) - THE FIX
    result = task_service.request_changes(
        story_id=story_id, task_id=task_local, feedback="Please add more test coverage"
    )
    assert result["success"] is True
    assert "Moved to IN_PROGRESS" in result["message"]

    task_data = task_service.get_task(story_id, task_local)
    assert task_data["status"] == Status.IN_PROGRESS
    assert task_data["rework_count"] == 1
    assert len(task_data["review_feedback"]) == 1
    assert "more test coverage" in task_data["review_feedback"][0]["message"]

    # Submit again with improvements (IN_PROGRESS → PENDING_REVIEW)
    result = task_service.submit_pr(
        story_id=story_id,
        task_id=task_local,
        changes=[
            "Implemented feature X",
            "Added basic tests",
            "Added comprehensive test coverage",
        ],
    )
    task_data = task_service.get_task(story_id, task_local)
    assert task_data["status"] == Status.PENDING_REVIEW

    # Approve (PENDING_REVIEW → DONE)
    result = task_service.approve_pr()
    assert result["success"] is True

    task_data = task_service.get_task(story_id, task_local)
    assert task_data["status"] == Status.DONE
    assert task_data["rework_count"] == 1  # Should persist


@pytest.mark.integration
def test_request_pr_changes_multiple_iterations():
    """Test multiple rounds of review feedback."""
    from plan_manager.services import plan_repository as repo
    from plan_manager.services import plan_service, story_service, task_service
    from plan_manager.services import state_repository as state

    suffix = str(uuid.uuid4())[:8]
    plan = plan_service.create_plan(f"multi-review-{suffix}", None, None)
    repo.set_current_plan_id(plan["id"])

    story = story_service.create_story(f"Story {suffix}", None, None, None, [])
    state.set_current_story_id(story["id"])

    task = task_service.create_task(story["id"], f"Task {suffix}", None, [], None)
    task_local = task["id"].split(":", 1)[1]
    state.set_current_task_id(task["id"])

    # Start task
    task_service.create_steps(story["id"], task_local, [{"title": "Work"}])
    task_service.start_current_task()

    # Round 1: Submit → Request changes
    task_service.submit_pr(story["id"], task_local, ["Change 1"])
    task_service.request_changes(story["id"], task_local, "Needs improvement 1")

    task_data = task_service.get_task(story["id"], task_local)
    assert task_data["rework_count"] == 1

    # Round 2: Submit → Request changes again
    task_service.submit_pr(story["id"], task_local, ["Change 1", "Change 2"])
    task_service.request_changes(story["id"], task_local, "Needs improvement 2")

    task_data = task_service.get_task(story["id"], task_local)
    assert task_data["rework_count"] == 2
    assert len(task_data["review_feedback"]) == 2

    # Round 3: Submit → Approve
    task_service.submit_pr(
        story["id"], task_local, ["Change 1", "Change 2", "Change 3"]
    )
    task_service.approve_pr()

    task_data = task_service.get_task(story["id"], task_local)
    assert task_data["status"] == Status.DONE
    assert task_data["rework_count"] == 2
