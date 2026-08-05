# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
from typing import Any

from pydantic import ValidationError

from plan_manager.domain.models import Plan, Status, Story, Task
from plan_manager.logging_context import get_correlation_id
from plan_manager.services.changelog_service import generate_changelog_for_task
from plan_manager.services.shared import (
    ensure_plan_exists,
    ensure_story_in_plan,
    ensure_task_in_plan,
    find_dependents,
    generate_slug,
    is_unblocked,
    resolve_task_id,
    service_uow,
    task_to_dict,
)
from plan_manager.services.status_utils import rollup_plan_status, rollup_story_status
from plan_manager.storage import repositories
from plan_manager.storage.uow import canonical_utc_timestamp
from plan_manager.telemetry import incr, timer
from plan_manager.validation import (
    validate_changes,
    validate_description,
    validate_feedback,
    validate_task_steps,
    validate_title,
)

logger = logging.getLogger(__name__)


def _generate_task_id_from_title(title: str) -> str:
    return generate_slug(title)


def _completion_time_for_status(next_status: Status) -> str | None:
    if next_status == Status.DONE:
        return canonical_utc_timestamp()
    return None


def _load_plan_snapshot(conn: Any, plan_id: str) -> Plan:
    plan = repositories.get_plan(conn, plan_id)
    if plan is None:
        raise FileNotFoundError(f"Plan '{plan_id}' not found.")
    stories = repositories.list_stories(conn, plan_id)
    tasks = repositories.list_tasks(conn, plan_id)
    tasks_by_story: dict[str, list[Task]] = {}
    for task in tasks:
        if task.story_id is None:
            continue
        tasks_by_story.setdefault(task.story_id, []).append(task)
    plan.stories = [
        Story(
            id=story.id,
            title=story.title,
            description=story.description,
            status=story.status,
            priority=story.priority,
            acceptance_criteria=story.acceptance_criteria,
            depends_on=story.depends_on,
            creation_time=story.creation_time,
            completion_time=story.completion_time,
            tasks=tasks_by_story.get(story.id, []),
        )
        for story in stories
    ]
    return plan


def _find_task(
    conn: Any,
    plan_id: str,
    story_id: str | None,
    task_id: str,
) -> tuple[Story, Task]:
    resolved_story_id, local_task_id = resolve_task_id(
        task_id, story_id, plan_id=plan_id, conn=conn
    )
    ensure_story_in_plan(
        conn,
        plan_id,
        resolved_story_id,
        parameter_name="story_id",
    )
    ensure_task_in_plan(
        conn,
        plan_id,
        resolved_story_id,
        local_task_id,
        parameter_name="task_id",
    )
    story_obj = repositories.get_story(conn, plan_id, resolved_story_id)
    if story_obj is None:
        raise KeyError(f"Story with ID '{resolved_story_id}' not found.")
    task_obj = repositories.get_task(conn, plan_id, resolved_story_id, local_task_id)
    if task_obj is None:
        raise KeyError(
            f"Task with ID '{resolved_story_id}:{local_task_id}' not found under story '{resolved_story_id}'."
        )
    story = Story(
        id=story_obj.id,
        title=story_obj.title,
        description=story_obj.description,
        status=story_obj.status,
        priority=story_obj.priority,
        acceptance_criteria=story_obj.acceptance_criteria,
        depends_on=story_obj.depends_on,
        creation_time=story_obj.creation_time,
        completion_time=story_obj.completion_time,
        tasks=[],
    )
    return story, task_obj


def _rollup_statuses(conn: Any, plan_id: str, story_id: str) -> None:
    story = repositories.get_story(conn, plan_id, story_id)
    if story is None:
        raise KeyError(f"story with ID '{story_id}' not found.")

    story_tasks = repositories.list_tasks(conn, plan_id, story_id=story_id)
    next_story_status = rollup_story_status([task.status for task in story_tasks])
    if next_story_status != story.status:
        repositories.transition_story_status_guarded(
            conn,
            plan_id=plan_id,
            story_id=story_id,
            expected_status=story.status,
            next_status=next_story_status,
            completion_time=_completion_time_for_status(next_story_status),
        )

    plan = repositories.get_plan(conn, plan_id)
    if plan is None:
        raise FileNotFoundError(f"Plan '{plan_id}' not found.")
    stories = repositories.list_stories(conn, plan_id)
    next_plan_status = rollup_plan_status([entry.status for entry in stories])
    if next_plan_status != plan.status:
        repositories.transition_plan_status_guarded(
            conn,
            plan_id=plan_id,
            expected_status=plan.status,
            next_status=next_plan_status,
            completion_time=_completion_time_for_status(next_plan_status),
        )


def _refresh_blocked_tasks(conn: Any, plan_id: str) -> None:
    plan = _load_plan_snapshot(conn, plan_id)
    for story in plan.stories:
        for task in story.tasks or []:
            if task.status not in (Status.TODO, Status.BLOCKED):
                continue
            next_status = Status.TODO if is_unblocked(task, plan) else Status.BLOCKED
            if next_status == task.status:
                continue
            repositories.transition_task_status_guarded(
                conn,
                plan_id=plan_id,
                story_id=task.story_id or story.id,
                local_id=task.local_id or task.id.split(":", 1)[1],
                expected_status=task.status,
                next_status=next_status,
            )


def create_task(
    plan_id: str,
    story_id: str,
    title: str,
    priority: int | None,
    depends_on: list[str],
    description: str | None,
) -> dict[str, Any]:
    title = validate_title(title)
    description = validate_description(description)

    logger.info(
        {
            "event": "create_task",
            "story_id": story_id,
            "title": title,
            "priority": priority,
            "depends_on": depends_on,
            "corr_id": get_correlation_id(),
        }
    )
    task_local_id = _generate_task_id_from_title(title)
    try:
        task = Task(
            id=f"{story_id}:{task_local_id}",
            title=title,
            depends_on=depends_on,
            description=description,
            priority=priority,
            story_id=story_id,
            local_id=task_local_id,
        )
    except ValidationError as e:
        logger.exception(
            "Validation error creating new task '%s:%s'", story_id, task_local_id
        )
        raise ValueError(
            f"Validation error creating new task '{story_id}:{task_local_id}': {e}"
        ) from e

    with service_uow(write=True, operation="create_task", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        ensure_story_in_plan(conn, plan_id, story_id, parameter_name="story_id")
        local_id = repositories.create_task(
            conn,
            plan_id=plan_id,
            story_id=story_id,
            base_local_id=task_local_id,
            title=task.title,
            description=task.description,
            status=task.status,
            priority=task.priority,
            depends_on=task.depends_on,
            steps=task.steps,
            changes=task.changes,
            review_feedback=task.review_feedback,
            rework_count=task.rework_count,
            ord_value=len(repositories.list_tasks(conn, plan_id, story_id=story_id)),
        )
        created = repositories.get_task(conn, plan_id, story_id, local_id)
    if created is None:
        raise RuntimeError(f"Task '{story_id}:{local_id}' was not persisted.")
    payload = task_to_dict(created)
    payload["plan_id"] = plan_id
    return {
        key: value
        for key, value in payload.items()
        if key
        in {
            "plan_id",
            "id",
            "title",
            "status",
            "priority",
            "creation_time",
            "description",
            "depends_on",
        }
    }


def get_task(plan_id: str, story_id: str, task_id: str) -> dict[str, Any]:
    resolved_story_id, local_task_id = resolve_task_id(
        task_id, story_id, plan_id=plan_id
    )
    with service_uow(write=False, operation="get_task", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        ensure_story_in_plan(
            conn,
            plan_id,
            resolved_story_id,
            parameter_name="story_id",
        )
        ensure_task_in_plan(
            conn,
            plan_id,
            resolved_story_id,
            local_task_id,
            parameter_name="task_id",
        )
        task_obj = repositories.get_task(
            conn, plan_id, resolved_story_id, local_task_id
        )
    if task_obj is None:
        raise KeyError(
            f"task with ID '{resolved_story_id}:{local_task_id}' not found under story '{resolved_story_id}'."
        )
    payload = task_to_dict(task_obj)
    payload["plan_id"] = plan_id
    return payload


def update_task(
    plan_id: str,
    story_id: str,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    depends_on: list[str] | None = None,
    priority: int | None = None,
    status: Status | None = None,
) -> dict[str, Any]:
    with service_uow(write=True, operation="update_task", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        story, task_obj = _find_task(conn, plan_id, story_id, task_id)
        plan_snapshot = _load_plan_snapshot(conn, plan_id)

        if (
            status == Status.IN_PROGRESS
            and task_obj.status == Status.TODO
            and not is_unblocked(task_obj, plan_snapshot)
        ):
            raise ValueError(
                f"Task '{task_obj.title}' cannot be started because it is blocked by one or more dependencies."
            )

        if title is not None:
            task_obj.title = title
        if description is not None:
            task_obj.description = description
        if depends_on is not None:
            task_obj.depends_on = depends_on
        if priority is not None:
            task_obj.priority = priority

        repositories.update_task(
            conn,
            plan_id=plan_id,
            story_id=task_obj.story_id or story.id,
            local_id=task_obj.local_id or task_obj.id.split(":", 1)[1],
            title=task_obj.title,
            description=task_obj.description,
            depends_on=task_obj.depends_on,
            priority=task_obj.priority,
        )

        if status is not None and status != task_obj.status:
            prev_status = task_obj.status
            if status == Status.IN_PROGRESS and prev_status == Status.TODO:
                if not task_obj.steps:
                    raise ValueError(
                        "An implementation plan must be approved before starting work."
                    )
            elif status == Status.IN_PROGRESS and prev_status == Status.PENDING_REVIEW:
                pass
            elif status == Status.PENDING_REVIEW and prev_status == Status.IN_PROGRESS:
                if not task_obj.changes:
                    raise ValueError(
                        "Changes must be provided before submitting for review."
                    )
            elif status == Status.DONE and prev_status == Status.PENDING_REVIEW:
                if not task_obj.changes:
                    raise ValueError("Changes must be provided before marking as DONE.")
            else:
                raise ValueError(
                    f"Invalid status transition from {prev_status} to {status}."
                )

            repositories.transition_task_status_guarded(
                conn,
                plan_id=plan_id,
                story_id=task_obj.story_id or story.id,
                local_id=task_obj.local_id or task_obj.id.split(":", 1)[1],
                expected_status=prev_status,
                next_status=status,
                completion_time=_completion_time_for_status(status),
            )
            repositories.append_event(
                conn,
                plan_id=plan_id,
                event_type="task_status_changed",
                scope={"task_id": task_obj.id},
                data={"from": prev_status.value, "to": status.value},
            )
            if status == Status.DONE:
                _refresh_blocked_tasks(conn, plan_id)

        _rollup_statuses(conn, plan_id, story.id)

        current_task = repositories.get_plan_state(conn, plan_id).current_task_id
        updated_task = repositories.get_task(
            conn,
            plan_id,
            task_obj.story_id or story.id,
            task_obj.local_id or task_obj.id.split(":", 1)[1],
        )
        if updated_task is None:
            raise RuntimeError(f"Task '{task_obj.id}' disappeared during update.")
        if updated_task.status == Status.DONE and current_task == updated_task.id:
            repositories.set_current_task(
                conn,
                plan_id=plan_id,
                current_task_story_id=None,
                current_task_local_id=None,
            )
        updated_story = repositories.get_story(conn, plan_id, story.id)
        if (
            updated_story is not None
            and updated_story.status == Status.DONE
            and repositories.get_plan_state(conn, plan_id).current_story_id == story.id
        ):
            repositories.set_current_story(conn, plan_id=plan_id, current_story_id=None)

    payload = task_to_dict(updated_task)
    payload["plan_id"] = plan_id
    return payload


def delete_task(plan_id: str, story_id: str, task_id: str) -> dict[str, Any]:
    with service_uow(write=True, operation="delete_task", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        _story, task_obj = _find_task(conn, plan_id, story_id, task_id)
        plan = _load_plan_snapshot(conn, plan_id)
        dependents = find_dependents(plan, task_obj.id)
        if dependents:
            raise ValueError(
                f"Cannot delete task '{task_obj.id}' because it is a dependency of: {', '.join(dependents)}"
            )
        repositories.delete_task(
            conn,
            plan_id,
            task_obj.story_id or story_id,
            task_obj.local_id or task_obj.id.split(":", 1)[1],
        )
        _rollup_statuses(conn, plan_id, task_obj.story_id or story_id)
    return {"success": True, "message": f"Successfully deleted task '{task_obj.id}'."}


def list_tasks(
    plan_id: str,
    statuses: list[Status] | None,
    story_id: str | None = None,
) -> list[Task]:
    with service_uow(write=False, operation="list_tasks", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        return repositories.list_tasks(
            conn,
            plan_id,
            statuses=statuses,
            story_id=story_id,
        )


def create_steps(
    plan_id: str, story_id: str, task_id: str, steps: list[dict[str, Any]]
) -> dict[str, Any]:
    validated_steps = validate_task_steps(steps)
    new_steps = [
        Task.Step(title=step["title"], description=step["description"])
        for step in validated_steps
    ]

    with service_uow(write=True, operation="create_steps", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        _story, task_obj = _find_task(conn, plan_id, story_id, task_id)
        if task_obj.status not in [Status.TODO, Status.IN_PROGRESS]:
            raise ValueError(
                "Can only propose a plan for a task in TODO or IN_PROGRESS status. "
                f"Current status is {task_obj.status}."
            )
        repositories.update_task(
            conn,
            plan_id=plan_id,
            story_id=task_obj.story_id or story_id,
            local_id=task_obj.local_id or task_obj.id.split(":", 1)[1],
            steps=new_steps,
        )
        updated = repositories.get_task(
            conn,
            plan_id,
            task_obj.story_id or story_id,
            task_obj.local_id or task_obj.id.split(":", 1)[1],
        )
    if updated is None:
        raise RuntimeError(f"Task '{task_obj.id}' disappeared while setting steps.")
    payload = task_to_dict(updated)
    payload["plan_id"] = plan_id
    return payload


def start_task(
    plan_id: str, task_id: str, story_id: str | None = None
) -> dict[str, Any]:
    with service_uow(write=True, operation="start_task", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        story, task = _find_task(conn, plan_id, story_id, task_id)
        if task.status != Status.TODO:
            raise ValueError(
                f"Task '{task.title}' is not in TODO status (current: {task.status}). "
                "Only TODO tasks can be started."
            )
        if not task.steps:
            raise ValueError(
                "No steps found. Create steps first via create_task_steps, then run start_task."
            )
        plan = _load_plan_snapshot(conn, plan_id)
        if not is_unblocked(task, plan):
            raise ValueError(
                f"Task '{task.title}' is BLOCKED by unmet dependencies. Resolve blockers before starting."
            )
        repositories.transition_task_status_guarded(
            conn,
            plan_id=plan_id,
            story_id=task.story_id or story.id,
            local_id=task.local_id or task.id.split(":", 1)[1],
            expected_status=Status.TODO,
            next_status=Status.IN_PROGRESS,
            completion_time=_completion_time_for_status(Status.IN_PROGRESS),
        )
        repositories.append_event(
            conn,
            plan_id=plan_id,
            event_type="task_status_changed",
            scope={"task_id": task.id},
            data={"from": Status.TODO.value, "to": Status.IN_PROGRESS.value},
        )
        _rollup_statuses(conn, plan_id, story.id)
        updated = repositories.get_task(
            conn,
            plan_id,
            task.story_id or story.id,
            task.local_id or task.id.split(":", 1)[1],
        )
    if updated is None:
        raise RuntimeError(f"Task '{task_id}' disappeared while starting.")
    with timer("start_task.duration_ms", kind="plan", task_id=task.id):
        pass
    incr("start_task.count", kind="plan")
    return {
        "success": True,
        "message": f"Task '{task.title}' started and moved to IN_PROGRESS.",
        "changelog_snippet": None,
        "plan_id": plan_id,
        **task_to_dict(updated),
    }


def approve_pr(
    plan_id: str, task_id: str, story_id: str | None = None
) -> dict[str, Any]:
    with service_uow(write=True, operation="approve_pr", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        story, task = _find_task(conn, plan_id, story_id, task_id)
        if task.status != Status.PENDING_REVIEW:
            raise ValueError(
                f"Task '{task.title}' is not in PENDING_REVIEW status (current: {task.status}). "
                "Only PENDING_REVIEW tasks can be approved."
            )
        if not task.changes:
            raise ValueError("Changes must be provided before marking as DONE.")
        repositories.transition_task_status_guarded(
            conn,
            plan_id=plan_id,
            story_id=task.story_id or story.id,
            local_id=task.local_id or task.id.split(":", 1)[1],
            expected_status=Status.PENDING_REVIEW,
            next_status=Status.DONE,
            completion_time=_completion_time_for_status(Status.DONE),
        )
        repositories.append_event(
            conn,
            plan_id=plan_id,
            event_type="task_status_changed",
            scope={"task_id": task.id},
            data={"from": Status.PENDING_REVIEW.value, "to": Status.DONE.value},
        )
        _refresh_blocked_tasks(conn, plan_id)
        _rollup_statuses(conn, plan_id, story.id)
        updated = repositories.get_task(
            conn,
            plan_id,
            task.story_id or story.id,
            task.local_id or task.id.split(":", 1)[1],
        )
    if updated is None:
        raise RuntimeError(f"Task '{task_id}' disappeared while approving.")
    with timer("approve_task.duration_ms", kind="review", task_id=task.id):
        pass
    incr("approve_task.count", kind="review")
    changelog_snippet = generate_changelog_for_task(updated, category="Changed")
    return {
        "success": True,
        "message": f"Task '{task.title}' approved and moved to DONE.",
        "changelog_snippet": changelog_snippet,
        "plan_id": plan_id,
        **task_to_dict(updated),
    }


def submit_pr(
    plan_id: str,
    story_id: str,
    task_id: str,
    changes: list[str],
) -> dict[str, Any]:
    changes = validate_changes(changes)
    with service_uow(write=True, operation="submit_pr", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        story, task = _find_task(conn, plan_id, story_id, task_id)
        if task.status != Status.IN_PROGRESS:
            raise ValueError(
                "Can only submit for review a task that is IN_PROGRESS. "
                f"Current status is {task.status}."
            )
        repositories.update_task(
            conn,
            plan_id=plan_id,
            story_id=task.story_id or story.id,
            local_id=task.local_id or task.id.split(":", 1)[1],
            changes=changes,
        )
        repositories.transition_task_status_guarded(
            conn,
            plan_id=plan_id,
            story_id=task.story_id or story.id,
            local_id=task.local_id or task.id.split(":", 1)[1],
            expected_status=Status.IN_PROGRESS,
            next_status=Status.PENDING_REVIEW,
            completion_time=_completion_time_for_status(Status.PENDING_REVIEW),
        )
        repositories.append_event(
            conn,
            plan_id=plan_id,
            event_type="task_status_changed",
            scope={"task_id": task.id},
            data={"from": Status.IN_PROGRESS.value, "to": Status.PENDING_REVIEW.value},
        )
        _rollup_statuses(conn, plan_id, story.id)
        updated = repositories.get_task(
            conn,
            plan_id,
            task.story_id or story.id,
            task.local_id or task.id.split(":", 1)[1],
        )
    if updated is None:
        raise RuntimeError(f"Task '{task_id}' disappeared while submitting for review.")
    payload = task_to_dict(updated)
    payload["plan_id"] = plan_id
    return payload


def request_changes(
    plan_id: str,
    story_id: str,
    task_id: str,
    feedback: str,
) -> dict[str, Any]:
    feedback = validate_feedback(feedback)
    with service_uow(write=True, operation="request_changes", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        story, task = _find_task(conn, plan_id, story_id, task_id)
        if task.status != Status.PENDING_REVIEW:
            raise ValueError(
                f"Task '{task.title}' is not awaiting review. Current status: {task.status}."
            )
        next_feedback = (task.review_feedback or []) + [
            Task.ReviewFeedback(message=feedback.strip())
        ]
        repositories.update_task(
            conn,
            plan_id=plan_id,
            story_id=task.story_id or story.id,
            local_id=task.local_id or task.id.split(":", 1)[1],
            review_feedback=next_feedback,
            rework_count=(task.rework_count or 0) + 1,
        )
        repositories.append_event(
            conn,
            plan_id=plan_id,
            event_type="review_changes_requested",
            scope={"task_id": task.id},
            data={"feedback": feedback.strip()},
        )
        repositories.transition_task_status_guarded(
            conn,
            plan_id=plan_id,
            story_id=task.story_id or story.id,
            local_id=task.local_id or task.id.split(":", 1)[1],
            expected_status=Status.PENDING_REVIEW,
            next_status=Status.IN_PROGRESS,
            completion_time=None,
        )
        repositories.append_event(
            conn,
            plan_id=plan_id,
            event_type="task_status_changed",
            scope={"task_id": task.id},
            data={"from": Status.PENDING_REVIEW.value, "to": Status.IN_PROGRESS.value},
        )
        _rollup_statuses(conn, plan_id, story.id)

    return {
        "success": True,
        "message": f"Changes requested for task '{task.title}'. Moved to IN_PROGRESS.",
        "plan_id": plan_id,
    }


def find_reviewable_tasks(plan_id: str) -> list[Task]:
    with service_uow(
        write=False, operation="find_reviewable_tasks", plan_id=plan_id
    ) as conn:
        ensure_plan_exists(conn, plan_id)
        tasks = repositories.list_tasks(conn, plan_id)
    return [
        task
        for task in tasks
        if (task.status == Status.TODO and task.steps)
        or task.status == Status.PENDING_REVIEW
    ]
