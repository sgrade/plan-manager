# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging

from plan_manager.domain.models import Plan, Status, Task
from plan_manager.services.shared import (
    ensure_plan_exists,
    get_current_story_id,
    get_current_task_id,
    is_unblocked,
    service_uow,
)
from plan_manager.storage import repositories

logger = logging.getLogger(__name__)


def _get_blockers_for_task(task: Task, plan: Plan) -> list[str]:
    """Returns a list of human-readable strings describing the task's blockers."""
    if not task.depends_on:
        return []

    blockers = []
    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: t for s in plan.stories for t in (s.tasks or [])}

    for dep_id in task.depends_on:
        # Normalize to fully-qualified ID for lookup
        fq_dep_id = f"{task.story_id}:{dep_id}" if ":" not in dep_id else dep_id

        if fq_dep_id in task_index:
            dep_task = task_index[fq_dep_id]
            if dep_task.status != Status.DONE:
                blockers.append(
                    f"Task '{dep_task.title}' is not DONE (status: {dep_task.status.value})"
                )
        elif dep_id in story_index:
            dep_story = story_index[dep_id]
            if dep_story.status != Status.DONE:
                blockers.append(
                    f"Story '{dep_story.title}' is not DONE (status: {dep_story.status.value})"
                )
        else:
            blockers.append(f"Dependency '{dep_id}' not found.")

    return blockers


def get_report(plan_id: str, scope: str = "story") -> str:
    """
    Generates a status report for a plan or current story in that plan.
    """
    plan = _get_plan(plan_id)
    if not plan:
        return f"Plan '{plan_id}' was not found."

    if scope == "plan":
        return _generate_plan_report(plan)

    # Default to story scope
    return _generate_story_report(plan)


def _get_plan(plan_id: str) -> Plan | None:
    try:
        with service_uow(
            write=False, operation="report_get_plan", plan_id=plan_id
        ) as conn:
            ensure_plan_exists(conn, plan_id)
            plan = repositories.get_plan(conn, plan_id)
            if plan is None:
                return None
            stories = repositories.list_stories(conn, plan_id)
            tasks = repositories.list_tasks(conn, plan_id)
        tasks_by_story: dict[str, list[Task]] = {}
        for task in tasks:
            if task.story_id is None:
                continue
            tasks_by_story.setdefault(task.story_id, []).append(task)
        plan.stories = []
        for story in stories:
            story.tasks = tasks_by_story.get(story.id, [])
            plan.stories.append(story)
        return plan
    except FileNotFoundError:
        logger.warning("Active plan with ID '%s' not found on disk.", plan_id)
        return None


def _generate_plan_report(plan: Plan) -> str:
    """Generates a high-level summary of all stories in the plan."""
    if not plan.stories:
        return f"Plan '{plan.title}' is active but contains no stories."

    report = [
        f"Plan Summary: {plan.title} ({plan.status.value})",
        "---------------------------------------------------",
    ]

    for story in sorted(plan.stories, key=lambda s: s.creation_time):
        if story.tasks:
            done_tasks = sum(1 for t in story.tasks if t.status == Status.DONE)
            total_tasks = len(story.tasks)
            progress = f"({done_tasks}/{total_tasks} tasks done)"
        else:
            progress = "(no tasks)"

        report.append(f"[{story.status.value:<13}] {story.title} {progress}")

    return "\n".join(report)


def _generate_story_report(plan: Plan) -> str:
    """Generates a detailed report for the currently active story."""
    story_id = get_current_story_id(plan.id)
    if not story_id:
        return (
            f"Plan '{plan.title}' is active, but no story is selected. "
            "Use `set_current_story` with plan_id if you have a specific story in mind, "
            "or `list_stories` with plan_id to see all stories."
        )

    story = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        # This case should ideally not be reachable if state is consistent
        return f"Error: Active story with ID '{story_id}' not found in plan '{plan.title}'."

    report = [
        f"Current Story: {story.title} ({story.status.value})",
        "---------------------------------------------------",
    ]

    # State detection
    active_task_id = get_current_task_id(plan.id)
    active_task = None
    if active_task_id:
        active_task = next(
            (t for t in (story.tasks or []) if t.id == active_task_id), None
        )

    # Scenario 1: No tasks in the story
    if not story.tasks:
        report.append("This story has no tasks.")
        report.append("\nNext Action: Create tasks for this story.")
        return "\n".join(report)

    # Display task list
    report.append(
        f"Tasks ({sum(1 for t in story.tasks if t.status == Status.DONE)}/{len(story.tasks)} done):"
    )
    for task in sorted(story.tasks, key=lambda t: t.creation_time):
        is_active_marker = ">>" if task.id == active_task_id else "  "
        report.append(
            f"{is_active_marker} [{task.status.value:<13}] {task.local_id} - {task.title}"
        )

    # Scenario 2: A task is active and BLOCKED
    if active_task and not is_unblocked(active_task, plan):
        blockers = _get_blockers_for_task(active_task, plan)
        report.append(
            "\n------------------------------------------------------------------------"
        )
        report.append(f"ATTENTION: Current task '{active_task.title}' is BLOCKED.")
        report.append("It cannot be started because of the following dependencies:")
        report.extend(f"- {blocker}" for blocker in blockers)
        report.append("\nNext Action: Complete the dependencies to unblock this task.")
        return "\n".join(report)

    # Scenario 3: Active task is awaiting pre-execution review
    if active_task and active_task.status == Status.TODO and active_task.steps:
        report.append(
            f"\nNext Action: The plan for '{active_task.title}' is ready for review. Run `start_task` with plan_id and task_id to start work."
        )
        return "\n".join(report)

    # Scenario 4: Active task is awaiting code review
    if active_task and active_task.status == Status.PENDING_REVIEW:
        report.append(
            f"\nNext Action: '{active_task.title}' is ready for code review. Run `approve_pr` with plan_id and task_id to mark it as DONE."
        )
        changes = getattr(active_task, "changes", [])
        if changes:
            report.append("\nChangelog Entries:")
            report.extend(f"  - {entry}" for entry in changes)
        return "\n".join(report)

    # Scenario 5: No active task, or active task is DONE/IN_PROGRESS. Suggest
    # next unblocked task.
    next_task_to_do = next(
        (
            t
            for t in sorted(story.tasks, key=lambda t: t.creation_time)
            if t.status == Status.TODO and is_unblocked(t, plan)
        ),
        None,
    )

    if next_task_to_do:
        if next_task_to_do.steps:
            report.append(
                f"\nNext Action: The plan for '{next_task_to_do.title}' is ready for review. Set it as active (`set_current_task` with plan_id and task_id), then run `start_task`."
            )
        else:
            report.append(
                f"\nNext Action: Run `create_task_steps` for task '{next_task_to_do.id}' (with plan_id), then run `start_task`."
            )
    # Check if all tasks are done
    elif all(t.status == Status.DONE for t in story.tasks):
        report.append("\nAll tasks for this story are complete!")
    else:
        report.append(
            "\nAll remaining tasks are either in progress, in review, or blocked."
        )

    return "\n".join(report)
