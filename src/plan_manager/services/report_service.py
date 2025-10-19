import logging

from plan_manager.domain.models import Plan, Status, Task
from plan_manager.services import plan_repository as plan_repo
from plan_manager.services.shared import is_unblocked
from plan_manager.services.state_repository import (
    get_current_plan_id,
    get_current_story_id,
    get_current_task_id,
)

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
                    f"Task '{dep_task.title}' is not DONE (status: {
                        dep_task.status.value
                    })"
                )
        elif dep_id in story_index:
            dep_story = story_index[dep_id]
            if dep_story.status != Status.DONE:
                blockers.append(
                    f"Story '{dep_story.title}' is not DONE (status: {
                        dep_story.status.value
                    })"
                )
        else:
            blockers.append(f"Dependency '{dep_id}' not found.")

    return blockers


def get_report(scope: str = "story") -> str:
    """
    Generates a status report for the current plan or story.
    """
    plan = _get_current_plan()
    if not plan:
        return "No active plan. Use `list_plans` and `set_current_plan` to start."

    if scope == "plan":
        return _generate_plan_report(plan)

    # Default to story scope
    return _generate_story_report(plan)


def _get_current_plan() -> Plan | None:
    plan_id = get_current_plan_id()
    if not plan_id:
        return None
    try:
        return plan_repo.load(plan_id)
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
        return f"Plan '{
            plan.title
        }' is active, but no story is selected. Use `set_current_story` if you have a specific story in mind, or `list_stories` to see all stories."

    story = next((s for s in plan.stories if s.id == story_id), None)
    if not story:
        # This case should ideally not be reachable if state is consistent
        return f"Error: Active story with ID '{story_id}' not found in plan '{
            plan.title
        }'."

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
            f"\nNext Action: The plan for '{
                active_task.title
            }' is ready for review. Run `approve_task` to start work."
        )
        return "\n".join(report)

    # Scenario 4: Active task is awaiting code review
    if active_task and active_task.status == Status.PENDING_REVIEW:
        report.append(
            f"\nNext Action: '{
                active_task.title
            }' is ready for code review. Run `approve_task` to mark it as DONE."
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
                f"\nNext Action: The plan for '{
                    next_task_to_do.title
                }' is ready for review. Set it as active (`set_current_task {
                    next_task_to_do.local_id
                }`) and run `approve_task`."
            )
        else:
            report.append(
                f"\nNext Action: `create_task_steps` for Task '{
                    next_task_to_do.local_id
                }', or `approve_task {story.id}:{
                    next_task_to_do.local_id
                }` to fast-track."
            )
    # Check if all tasks are done
    elif all(t.status == Status.DONE for t in story.tasks):
        report.append("\nAll tasks for this story are complete!")
    else:
        report.append(
            "\nAll remaining tasks are either in progress, in review, or blocked."
        )

    return "\n".join(report)
