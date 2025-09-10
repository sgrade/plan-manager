import logging
from typing import List

from plan_manager.services import plan_repository as plan_repo
from plan_manager.services.state_repository import get_current_plan_id, get_current_story_id, get_current_task_id
from plan_manager.domain.models import Status, Task, Plan

logger = logging.getLogger(__name__)


def _format_task_line(task: Task) -> str:
    """Formats a single task line for display."""
    return f"[{task.status.value:<14}] {task.id.split(':')[-1]} - {task.title}"


def _get_blockers_for_task(task: Task, plan: Plan) -> List[str]:
    """Returns a list of human-readable strings describing the task's blockers."""
    if not task.depends_on:
        return []

    blockers = []
    story_index = {s.id: s for s in plan.stories}
    task_index = {t.id: t for s in plan.stories for t in (s.tasks or [])}

    for dep_id in task.depends_on:
        # Normalize to fully-qualified ID for lookup
        fq_dep_id = f"{task.story_id}:{dep_id}" if ':' not in dep_id else dep_id

        if fq_dep_id in task_index:
            dep_task = task_index[fq_dep_id]
            if dep_task.status != Status.DONE:
                blockers.append(
                    f"Task '{dep_task.title}' is not DONE (status: {dep_task.status.value})")
        elif dep_id in story_index:
            dep_story = story_index[dep_id]
            if dep_story.status != Status.DONE:
                blockers.append(
                    f"Story '{dep_story.title}' is not DONE (status: {dep_story.status.value})")
        else:
            blockers.append(f"Dependency '{dep_id}' not found.")

    return blockers


def get_report() -> str:
    """
    Generates a dynamic, contextual report based on the current state.
    """
    plan_id = get_current_plan_id()
    if not plan_id:
        return "No active plan. Please select or create a plan first."
    plan = plan_repo.load(plan_id)

    # State detection
    active_story_id = get_current_story_id(plan_id)
    active_task_id = get_current_task_id(plan_id)

    active_story = next(
        (s for s in plan.stories if s.id == active_story_id), None)
    active_task = next((t for t in (active_story.tasks or [])
                       if t.id == active_task_id), None) if active_story else None

    # Scenario 1: Pending Code Review
    if active_task and active_task.status == Status.PENDING_REVIEW:
        report = [
            f"Current Task: {active_task.title} (Ready for Code Review)",
            "----------------------------------------------------------",
            "The agent has completed the work with the following summary:",
            f"- {active_task.execution_summary or 'No summary provided.'}",
            "\nNext Action: Review the code changes, then `approve_task` to merge or `change <instructions>`."
        ]
        return "\n".join(report)

    # Scenario 2: Pending Pre-Execution Review
    if active_task and active_task.status == Status.TODO and active_task.steps:
        report = [
            f"Current Task: {active_task.title} (Pending Pre-Execution Approval)",
            "---------------------------------------------------------------------",
            "The agent proposes the following plan:",
            f"- {active_task.steps or 'No plan provided.'}",
            "\nNext Action: `approve_task` to authorize this plan, or `change <instructions>`."
        ]
        return "\n".join(report)

    # Scenario 3: Task is Blocked
    if active_task and active_task.status == Status.BLOCKED:
        blockers = _get_blockers_for_task(active_task, plan)
        report = [
            f"Current Task: {active_task.title} (BLOCKED)",
            "----------------------------------------------------------",
            "This task cannot be started because of the following blockers:"
        ]
        for blocker in blockers:
            report.append(f"- {blocker}")
        report.append(
            "\nNext Action: Complete the dependencies to unblock this task.")
        return "\n".join(report)

    # Scenario 4: General Overview
    if active_story:
        tasks_done = sum(
            1 for t in active_story.tasks if t.status == Status.DONE)
        total_tasks = len(active_story.tasks)
        report = [
            f"Current Story: {active_story.title} ({active_story.status.value})",
            "---------------------------------------------------",
            f"Tasks ({tasks_done}/{total_tasks} done):"
        ]
        for task in sorted(active_story.tasks, key=lambda t: t.creation_time or ''):
            report.append(_format_task_line(task))

        next_task_to_do = next((t for t in active_story.tasks if t.status ==
                               Status.TODO and not t.steps), None)
        if next_task_to_do:
            local_id = next_task_to_do.id.split(':')[-1]
            report.append(
                f"\nNext Action: `prepare` to create steps for Task '{local_id}', or `approve_task {local_id}` to fast-track.")
        else:
            report.append(
                "\nAll tasks for this story are complete or in review.")
        return "\n".join(report)

    # Fallback: Plan-level overview
    stories_done = sum(1 for s in plan.stories if s.status == Status.DONE)
    total_stories = len(plan.stories)
    report = [
        f"Current Plan: {plan.title} ({plan.status.value})",
        "---------------------------------------------------",
        f"Stories ({stories_done}/{total_stories} done):"
    ]
    for story in plan.stories:
        report.append(f"[{story.status.value:<14}] {story.id} - {story.title}")
    report.append("\nNext Action: Select a story to begin work.")
    return "\n".join(report)
