# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import json
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from plan_manager.domain.models import Status
from plan_manager.logging import logger
from plan_manager.schemas.outputs import (
    ActionType,
    NextAction,
    OperationResult,
    TaskFinalizationOut,
    TaskListItem,
    TaskOut,
    TaskWorkflowResult,
    WhoRuns,
    WorkflowGate,
)
from plan_manager.services import changelog_service
from plan_manager.services.shared import (
    get_current_story_id,
    resolve_task_id,
    set_current_task_id,
)
from plan_manager.services.task_service import (
    approve_pr as svc_approve_pr,
)
from plan_manager.services.task_service import (
    create_steps as svc_create_steps,
)
from plan_manager.services.task_service import (
    create_task as svc_create_task,
)
from plan_manager.services.task_service import (
    delete_task as svc_delete_task,
)
from plan_manager.services.task_service import (
    get_task as svc_get_task,
)
from plan_manager.services.task_service import (
    list_tasks as svc_list_tasks,
)
from plan_manager.services.task_service import (
    request_changes as svc_request_pr_changes,
)
from plan_manager.services.task_service import (
    start_task as svc_start_task,
)
from plan_manager.services.task_service import (
    submit_pr as svc_submit_pr,
)
from plan_manager.services.task_service import (
    update_task as svc_update_task,
)
from plan_manager.telemetry import incr, timer
from plan_manager.tools.util import coerce_optional_int


def _create_task_out(data: dict[str, Any]) -> TaskOut:
    """Create a TaskOut object from a dictionary, populating the local_id."""
    if "id" in data and ":" in data["id"]:
        data["local_id"] = data["id"].split(":", 1)[1]
    return TaskOut(**data)


def _raise_workflow_error(
    *,
    plan_id: str,
    message: str,
    recovery: list[str],
) -> NoReturn:
    """Raise a contract-friendly workflow error with structured guidance."""
    payload = TaskWorkflowResult(
        success=False,
        message=message,
        plan_id=plan_id,
        action=ActionType.NONE,
        next_actions=[],
    ).model_dump(mode="json")
    payload["recovery"] = recovery
    raise ValueError(f"{message}\nstructured_recovery={json.dumps(payload)}")


def register_task_tools(mcp_instance: "FastMCP") -> None:
    """Register task tools with the MCP instance."""
    mcp_instance.tool()(list_tasks)
    mcp_instance.tool()(create_task)
    mcp_instance.tool()(get_task)
    mcp_instance.tool()(update_task)
    mcp_instance.tool()(delete_task)
    mcp_instance.tool()(set_current_task)
    mcp_instance.tool()(create_task_steps)
    mcp_instance.tool()(submit_pr)
    mcp_instance.tool()(start_task)  # Gate 1
    mcp_instance.tool()(approve_pr)  # Gate 2
    mcp_instance.tool()(request_pr_changes)
    mcp_instance.tool()(merge_pr)  # Convenience: Gate 2 + artifacts


# ---------- Task CRUD operations ----------


def create_task(
    plan_id: str,
    story_id: str,
    title: str,
    priority: float | None = None,
    depends_on: list[str] | None = None,
    description: str | None = None,
) -> TaskOut:
    """Create a new task under the specified story.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        story_id: The ID of the story to create the task under
        title: The title of the task (will be validated and sanitized)
        priority: Optional priority level (0-5, where 0 is highest priority)
        depends_on: Optional list of task IDs this task depends on
        description: Optional description of the task

    Returns:
        TaskOut: The created task with its generated ID and metadata
    """
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_create_task(
        plan_id,
        story_id,
        title,
        coerced_priority,
        depends_on or [],
        description,
    )
    return _create_task_out(data)


def get_task(
    plan_id: str,
    task_id: str | None = None,
    story_id: str | None = None,
) -> TaskOut:
    """Get a task by its ID.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Optional task ID (local or fully qualified).
        story_id: Optional story ID when task_id is local, for example `task_orchestration`.

    Returns:
        TaskOut: The requested task with its metadata and current state

    Raises:
        ValueError: If task_id is not provided
    """
    effective_task_id = task_id
    if not effective_task_id:
        raise ValueError(
            "Missing required parameter 'task_id'. "
            "Obtain task_id from `list_tasks(plan_id=...)` or from a `create_task` result, "
            "then retry with a fully-qualified value like 'story_id:task_id'."
        )

    resolved_story_id, local_task_id = resolve_task_id(
        effective_task_id, story_id=story_id, plan_id=plan_id
    )
    data = svc_get_task(plan_id, resolved_story_id, local_task_id)
    return _create_task_out(data)


def update_task(
    plan_id: str,
    task_id: str,
    story_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    priority: float | None = None,
    depends_on: list[str] | None = None,
    status: str | None = None,
    steps: list[dict[str, Any]] | None = None,
) -> TaskOut:
    """Update mutable fields of a task.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Task identifier, for example `task_orchestration:fix_yaml_races_add_write_lock`.
        story_id: Optional story ID when task_id is local, for example `task_orchestration`.
    """
    resolved_story_id, local_task_id = resolve_task_id(
        task_id, story_id=story_id, plan_id=plan_id
    )
    # If steps are provided here, forward them via status/utils path by
    # calling create_steps first
    if steps is not None:
        svc_create_steps(
            plan_id=plan_id,
            story_id=resolved_story_id,
            task_id=local_task_id,
            steps=steps,
        )
    coerced_priority = coerce_optional_int(priority, "priority")
    # Coerce status string to Status enum if provided
    coerced_status = None
    if status is not None:
        if isinstance(status, Status):
            coerced_status = status
        elif isinstance(status, str):
            try:
                coerced_status = Status(status.upper())
            except ValueError as e:
                raise ValueError(
                    f"Invalid value for parameter 'status': {status!r}. Allowed: {
                        ', '.join([s.value for s in Status])
                    }"
                ) from e
        else:
            raise ValueError(
                f"Invalid type for parameter 'status': expected string or null, got {
                    type(status).__name__
                }."
            )

    data = svc_update_task(
        plan_id,
        resolved_story_id,
        local_task_id,
        title,
        description,
        depends_on,
        coerced_priority,
        coerced_status,
    )
    return _create_task_out(data)


def delete_task(
    plan_id: str,
    task_id: str,
    story_id: str | None = None,
) -> OperationResult:
    """Delete a task by ID (fails if other items depend on it).

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Task identifier, for example `task_orchestration:fix_yaml_races_add_write_lock`.
        story_id: Optional story ID when task_id is local.
    """
    resolved_story_id, local_task_id = resolve_task_id(
        task_id, story_id=story_id, plan_id=plan_id
    )
    data = svc_delete_task(plan_id, resolved_story_id, local_task_id)
    return OperationResult(**data)


def list_tasks(
    plan_id: str,
    statuses: list[Status] | None = None,
    story_id: str | None = None,
    offset: int | None = 0,
    limit: int | None = None,
) -> list[TaskListItem]:
    """List tasks with optional filtering by status and story, with pagination support.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        statuses: Optional list of task statuses to filter by. Empty list means no status filter.
        story_id: Optional story ID to filter tasks by, for example `task_orchestration`.
        offset: Number of tasks to skip (for pagination). Defaults to 0.
        limit: Maximum number of tasks to return. None means no limit.

    Returns:
        List[TaskListItem]: List of task summaries matching the filter criteria
    """
    if statuses is None:
        statuses = []
    tasks = svc_list_tasks(plan_id, statuses, story_id)
    items = [
        TaskListItem(
            plan_id=plan_id,
            id=t.id,
            title=t.title,
            status=t.status,
            priority=t.priority,
            creation_time=t.creation_time.isoformat() if t.creation_time else None,
            local_id=t.id.split(":", 1)[1] if ":" in t.id else t.id,
        )
        for t in tasks
    ]
    start = max(0, offset or 0)
    end = None if limit is None else start + max(0, limit)
    return items[start:end]


# ---------- Task workflow operations ----------


def _status_to_gate(
    status: Status, _steps: list[dict[str, Any]] | None
) -> WorkflowGate:
    if status == Status.DONE:
        return WorkflowGate.DONE
    if status == Status.PENDING_REVIEW:
        return WorkflowGate.AWAITING_REVIEW
    if status == Status.IN_PROGRESS:
        return WorkflowGate.EXECUTING
    if status == Status.BLOCKED:
        return WorkflowGate.BLOCKED
    return WorkflowGate.READY_TO_START


def _compute_next_actions_for_task(
    plan_id: str,
    task: TaskOut,
    gate: WorkflowGate,
) -> list[NextAction]:
    actions: list[NextAction] = []

    if gate == WorkflowGate.BLOCKED:
        actions.append(
            NextAction(
                kind="instruction",
                name="resolve_dependencies",
                label="Resolve blockers (dependencies) before starting",
                who=WhoRuns.USER,
                recommended=True,
                blocked_reason="Task is BLOCKED by unmet dependencies.",
            )
        )
        return actions

    if gate == WorkflowGate.READY_TO_START:
        if not (task.steps or []):
            actions.append(
                NextAction(
                    kind="instruction",
                    name="ask_user_next_step",
                    label="Ask: Would you like assisted steps or fast-track?",
                    who=WhoRuns.AGENT,
                    recommended=True,
                )
            )
            # Only user instructions at this point; the agent must wait for the user's
            # choice
            actions.append(
                NextAction(
                    kind="prompt",
                    name="/create_steps",
                    label="Assisted: User runs /create_steps prompt",
                    who=WhoRuns.USER,
                    recommended=False,
                    arguments={"plan_id": plan_id, "task_id": task.id},
                )
            )
            actions.append(
                NextAction(
                    kind="instruction",
                    name="user_approval_fast_track",
                    label="Fast-track: User says 'approve steps' with concrete steps",
                    who=WhoRuns.USER,
                    recommended=False,
                )
            )
        else:
            actions.append(
                NextAction(
                    kind="instruction",
                    name="user_approves_steps",
                    label="User says 'approve steps' in chat",
                    who=WhoRuns.USER,
                    recommended=True,
                    arguments={
                        "then": [
                            {
                                "tool": "start_task",
                                "arguments": {"plan_id": plan_id, "task_id": task.id},
                            }
                        ]
                    },
                )
            )
            actions.append(
                NextAction(
                    kind="tool",
                    name="start_task",
                    label="Agent runs start_task after user approval",
                    who=WhoRuns.AGENT_AFTER_USER_APPROVAL,
                    recommended=False,
                    blocked_reason="Waiting for user approval at Gate 1.",
                    arguments={"plan_id": plan_id, "task_id": task.id},
                )
            )
        return actions

    if gate == WorkflowGate.EXECUTING:
        # Follow the diagram: user instructs to execute, agent executes, then
        # submits for review
        actions.append(
            NextAction(
                kind="instruction",
                name="user_execute_instruction",
                label="User says 'execute' in chat",
                who=WhoRuns.USER,
                recommended=True,
            )
        )
        actions.append(
            NextAction(
                kind="instruction",
                name="agent_execute_work",
                label="Agent executes the task",
                who=WhoRuns.AGENT,
                recommended=False,
            )
        )
        actions.append(
            NextAction(
                kind="tool",
                name="submit_pr",
                label=(
                    "Agent runs submit_pr when the work is complete, supplying "
                    "'changes' as a list of change summaries"
                ),
                who=WhoRuns.AGENT,
                recommended=False,
                arguments={"plan_id": plan_id, "task_id": task.id},
                pending_arguments=["changes"],
            )
        )
        return actions

    if gate == WorkflowGate.AWAITING_REVIEW:
        # Gate 2 sequence per workflow:
        # 1) Agent displays changes and asks the user to approve or
        # request changes
        actions.append(
            NextAction(
                kind="instruction",
                name="display_review_and_prompt",
                label="Show changelog entries and ask: Say 'approve review' or provide feedback to request changes.",
                who=WhoRuns.AGENT,
                recommended=True,
            )
        )
        # 2a) PRIMARY: User approves review in chat, then agent runs finalize_task
        actions.append(
            NextAction(
                kind="instruction",
                name="user_approves_review",
                label="User says 'approve review' in chat",
                who=WhoRuns.USER,
                recommended=False,
                arguments={
                    "then": [
                        {
                            "tool": "approve_pr",
                            "arguments": {"plan_id": plan_id, "task_id": task.id},
                        },
                        {
                            "tool": "merge_pr",
                            "arguments": {
                                "plan_id": plan_id,
                                "task_id": task.id,
                            },
                            "pending_arguments": ["changelog_category", "commit_type"],
                        },
                    ]
                },
            )
        )
        actions.append(
            NextAction(
                kind="tool",
                name="merge_pr",
                label="Agent runs merge_pr after user approval (choose changelog_category and commit_type to reflect the actual change)",
                who=WhoRuns.AGENT_AFTER_USER_APPROVAL,
                recommended=False,
                blocked_reason="Waiting for user approval at Gate 2.",
                arguments={
                    "plan_id": plan_id,
                    "task_id": task.id,
                },
                pending_arguments=["changelog_category", "commit_type"],
            )
        )
        # 2b) FALLBACK: Manual approval + artifact generation
        actions.append(
            NextAction(
                kind="tool",
                name="approve_pr",
                label="Agent runs approve_pr (Gate 2: Code Review Approval) - then generate artifacts separately",
                who=WhoRuns.AGENT_AFTER_USER_APPROVAL,
                recommended=False,
                blocked_reason="Waiting for user approval at Gate 2.",
                arguments={"plan_id": plan_id, "task_id": task.id},
            )
        )
        # 2c) REWORK: User provides feedback, then agent runs request_pr_changes
        actions.append(
            NextAction(
                kind="instruction",
                name="user_provides_feedback",
                label="User provides feedback in chat",
                who=WhoRuns.USER,
                recommended=False,
                arguments={
                    "then": [
                        {
                            "tool": "request_pr_changes",
                            "arguments": {"plan_id": plan_id, "task_id": task.id},
                            "pending_arguments": ["feedback"],
                        }
                    ]
                },
            )
        )
        return actions

    if gate == WorkflowGate.DONE:
        # After a task is DONE:
        # 1) If there are remaining (non-DONE) tasks in the current story, suggest listing tasks for that story.
        # 2) Otherwise, suggest verifying story acceptance criteria.
        try:
            story_id = task.id.split(":", 1)[0]
        except (AttributeError, ValueError, IndexError):
            story_id = None

        has_remaining_in_story = False
        if story_id:
            try:
                remaining = [
                    t
                    for t in svc_list_tasks(plan_id, None, story_id)
                    if t.status != Status.DONE
                ]
                has_remaining_in_story = len(remaining) > 0
            except (ValueError, KeyError, OSError):
                # Handle service call failures gracefully
                has_remaining_in_story = False

        if has_remaining_in_story:
            actions.append(
                NextAction(
                    kind="tool",
                    name="list_tasks",
                    label="List remaining tasks in the current story",
                    who=WhoRuns.AGENT,
                    recommended=True,
                    arguments={
                        "plan_id": plan_id,
                        "story_id": story_id,
                    }
                    if story_id
                    else {"plan_id": plan_id},
                )
            )
        else:
            actions.append(
                NextAction(
                    kind="instruction",
                    name="verify_story_acceptance",
                    label="Review story acceptance criteria",
                    who=WhoRuns.USER,
                    recommended=True,
                    arguments={
                        "then": [
                            {
                                "tool": "report",
                                "arguments": {"plan_id": plan_id, "scope": "story"},
                            }
                        ]
                    },
                )
            )

    return actions


def create_task_steps(
    plan_id: str,
    task_id: str,
    steps: list[dict[str, Any]],
    story_id: str | None = None,
) -> TaskWorkflowResult:
    """Create implementation steps for a task, enabling pre-execution review.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: The ID of the task to add steps to (local or fully qualified)
        steps: List of step objects, each with 'title' and optional 'description'
        story_id: Optional story ID when task_id is local.

    Returns:
        TaskWorkflowResult: Result containing the updated task and next actions
    """
    try:
        resolved_story_id, local_task_id = resolve_task_id(
            task_id, story_id=story_id, plan_id=plan_id
        )
        data = svc_create_steps(
            plan_id=plan_id,
            story_id=resolved_story_id,
            task_id=local_task_id,
            steps=steps,
        )
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        _raise_workflow_error(
            plan_id=plan_id,
            message=str(exc),
            recovery=[
                "Confirm task_id and plan_id belong together (prefer fully qualified task_id).",
                "If task_id is local, provide story_id explicitly.",
                "Provide a non-empty steps list with required step fields.",
            ],
        )
    task = _create_task_out(data)
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(plan_id, task, gate)
    message_lines = [
        f"Gate 1: Pre-Execution — steps attached for task '{task.title}'.",
        "Ask the user to approve the steps before running start_task.",
    ]
    return TaskWorkflowResult(
        success=True,
        message="\n".join(message_lines),
        task=task,
        plan_id=plan_id,
        gate=gate,
        action=ActionType.CREATE_STEPS,
        next_actions=next_actions,
    )


def set_current_task(plan_id: str, task_id: str | None = None) -> TaskWorkflowResult:
    """Set the current task for a specific plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Task identifier, for example `task_orchestration:fix_yaml_races_add_write_lock`.
    """
    # Ensure a story is selected
    story_id = get_current_story_id(plan_id)
    if not story_id:
        _raise_workflow_error(
            plan_id=plan_id,
            message=(
                "Missing required scope for parameter 'story_id': no current story is set "
                "for the supplied plan_id."
            ),
            recovery=[
                "Obtain story_id from list_stories(plan_id=...) or a create_story result.",
                "Retry with set_current_story(plan_id=..., story_id=...).",
            ],
        )

    # Require a task identifier
    if not task_id:
        _raise_workflow_error(
            plan_id=plan_id,
            message="Missing required parameter 'task_id'.",
            recovery=[
                "Obtain task_id from list_tasks(plan_id=..., story_id=...) or a create_task result.",
                "Retry with set_current_task(plan_id=..., task_id='story_id:task_id').",
            ],
        )

    s_id, local_task_id = resolve_task_id(task_id, story_id, plan_id=plan_id)
    fq_task_id = f"{s_id}:{local_task_id}"

    set_current_task_id(fq_task_id, plan_id)
    data = svc_get_task(plan_id, s_id, local_task_id)
    task = _create_task_out(data)
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(plan_id, task, gate)
    message_lines = [
        f"Current task set: '{task.title}' ({task.local_id}).",
    ]
    return TaskWorkflowResult(
        success=True,
        message="\n".join(message_lines),
        task=task,
        plan_id=plan_id,
        gate=gate,
        action=ActionType.SET_CURRENT_TASK,
        next_actions=next_actions,
    )


def start_task(
    plan_id: str,
    task_id: str,
    story_id: str | None = None,
) -> TaskWorkflowResult:
    """
    Start work on a TODO task (Gate 1: Pre-Execution Approval).

    Approves the implementation plan and transitions the task from TODO to IN_PROGRESS status.
    This tool should be called after create_task_steps() has been used to define the
    implementation plan.

    Validates:
    - Task is in TODO status
    - Task has steps defined
    - Task is not blocked by dependencies

    Transition: TODO → IN_PROGRESS
    Gate: Gate 1 (Pre-Execution Approval)

    Returns:
        TaskWorkflowResult: Result with task details and next actions for execution

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Task identifier, for example `task_orchestration:fix_yaml_races_add_write_lock`.
        story_id: Optional story ID when task_id is local, for example `task_orchestration`.
    """
    logger.debug("start_task tool called.")
    try:
        resolved_story_id, local_task_id = resolve_task_id(
            task_id, story_id=story_id, plan_id=plan_id
        )
        result = svc_start_task(
            plan_id=plan_id,
            task_id=f"{resolved_story_id}:{local_task_id}",
            story_id=resolved_story_id,
        )
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        _raise_workflow_error(
            plan_id=plan_id,
            message=str(exc),
            recovery=[
                "Confirm task_id and plan_id belong together (prefer fully qualified task_id).",
                "If task_id is local, provide story_id explicitly.",
                "Run create_task_steps(plan_id, task_id, steps) before start_task.",
            ],
        )
    task = _create_task_out(
        {
            k: v
            for k, v in result.items()
            if k not in ("success", "message", "changelog_snippet")
        }
    )
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(plan_id, task, gate)
    return TaskWorkflowResult(
        success=result.get("success", False),
        message=result.get("message", ""),
        task=task,
        plan_id=plan_id,
        gate=gate,
        action=ActionType.START_TASK,
        next_actions=next_actions,
        changelog_snippet=result.get("changelog_snippet"),
    )


def approve_pr(
    plan_id: str,
    task_id: str,
    story_id: str | None = None,
) -> TaskWorkflowResult:
    """
    Approve a PENDING_REVIEW task (Gate 2: Code Review Approval).

    Completes the code review process and marks the task as DONE. This tool should be
    called after the user has reviewed the submitted work and provides approval.

    Validates:
    - Task is in PENDING_REVIEW status
    - Task has changes

    Transition: PENDING_REVIEW → DONE
    Gate: Gate 2 (Code Review Approval)

    Important: agents should only call this tool after the user approves the review.

    Returns:
        TaskWorkflowResult: Result with task details, changelog snippet, and next actions

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Task identifier, for example `task_orchestration:fix_yaml_races_add_write_lock`.
        story_id: Optional story ID when task_id is local, for example `task_orchestration`.
    """
    logger.debug("approve_pr tool called.")
    try:
        resolved_story_id, local_task_id = resolve_task_id(
            task_id, story_id=story_id, plan_id=plan_id
        )
        result = svc_approve_pr(
            plan_id=plan_id,
            task_id=f"{resolved_story_id}:{local_task_id}",
            story_id=resolved_story_id,
        )
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        _raise_workflow_error(
            plan_id=plan_id,
            message=str(exc),
            recovery=[
                "Confirm task_id points to a PENDING_REVIEW task in the supplied plan_id.",
                "Run submit_pr(plan_id, task_id, changes) before approving.",
            ],
        )
    task = _create_task_out(
        {
            k: v
            for k, v in result.items()
            if k not in ("success", "message", "changelog_snippet")
        }
    )
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(plan_id, task, gate)
    return TaskWorkflowResult(
        success=result.get("success", False),
        message=result.get("message", ""),
        task=task,
        plan_id=plan_id,
        gate=gate,
        action=ActionType.APPROVE_PR,
        next_actions=next_actions,
        changelog_snippet=result.get("changelog_snippet"),
    )


def request_pr_changes(
    plan_id: str,
    task_id: str,
    feedback: str,
    story_id: str | None = None,
) -> TaskWorkflowResult:
    """Request changes for a task (PENDING_REVIEW -> IN_PROGRESS).

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: Task identifier, for example `task_orchestration:fix_yaml_races_add_write_lock`.
        feedback: Review feedback message.
        story_id: Optional story ID when task_id is local, for example `task_orchestration`.
    """
    logger.debug("request_changes tool called.")
    try:
        s_id, local_task_id = resolve_task_id(
            task_id, story_id=story_id, plan_id=plan_id
        )
        result = svc_request_pr_changes(
            plan_id=plan_id,
            story_id=s_id,
            task_id=local_task_id,
            feedback=feedback,
        )
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        logger.warning("Request changes failed due to business logic error: %s", exc)
        _raise_workflow_error(
            plan_id=plan_id,
            message=str(exc),
            recovery=[
                "Provide non-empty review feedback in the feedback parameter.",
                "Confirm task_id points to a PENDING_REVIEW task in the supplied plan_id.",
            ],
        )
    cur_task_id = f"{s_id}:{local_task_id}"
    task: TaskOut | None = None
    gate: WorkflowGate | None = None
    next_actions: list[NextAction] = []
    if cur_task_id:
        try:
            data = svc_get_task(plan_id, s_id, cur_task_id)
            task = _create_task_out(data)
            gate = _status_to_gate(task.status, task.steps)
            next_actions = _compute_next_actions_for_task(plan_id, task, gate)
        except (ValueError, KeyError, OSError):
            # Preserve primary success result even if a follow-up read fails.
            pass
    return TaskWorkflowResult(
        success=result.get("success", False),
        message=result.get("message", ""),
        task=task,
        plan_id=plan_id,
        gate=gate,
        action=ActionType.REQUEST_PR_CHANGES,
        next_actions=next_actions,
    )


def submit_pr(
    plan_id: str,
    task_id: str,
    changes: list[str],
    story_id: str | None = None,
) -> TaskWorkflowResult:
    """Submit a completed task for code review and move it to PENDING_REVIEW status.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: The ID of the task to submit for review (local or fully qualified)
        changes: List of changelog entries describing what was accomplished
        story_id: Optional story ID when task_id is local, for example `task_orchestration`.

    Returns:
        TaskWorkflowResult: Result containing the updated task and next actions for review
    """
    try:
        resolved_story_id, local_task_id = resolve_task_id(
            task_id, story_id=story_id, plan_id=plan_id
        )
        with timer("submit_for_review.duration_ms", task_id=local_task_id):
            data = svc_submit_pr(
                plan_id=plan_id,
                story_id=resolved_story_id,
                task_id=local_task_id,
                changes=changes,
            )
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        _raise_workflow_error(
            plan_id=plan_id,
            message=str(exc),
            recovery=[
                "Confirm task_id points to an IN_PROGRESS task in the supplied plan_id.",
                "Provide a non-empty changes list describing the implemented work.",
            ],
        )
    incr("submit_for_review.count")
    task = _create_task_out(data)

    entries_formatted = "\n".join([f"- {entry}" for entry in task.changes])
    message_lines = [
        f"Task '{task.title}' is now PENDING_REVIEW.",
        "Changelog Entries:",
        entries_formatted,
    ]
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(plan_id, task, gate)
    return TaskWorkflowResult(
        success=True,
        message="\n".join(message_lines),
        task=task,
        plan_id=plan_id,
        gate=gate,
        action=ActionType.SUBMIT_PR,
        next_actions=next_actions,
    )


def merge_pr(
    plan_id: str,
    task_id: str,
    changelog_category: str,
    commit_type: str,
    version: str | None = None,
) -> TaskFinalizationOut:
    """Convenience tool: approve task + generate changelog + commit message in one call.

    This tool combines the approve_pr, generate_changelog_entry, and generate_commit_message
    operations into a single workflow step for convenience when the user approves the review.

    ONLY use this if:
    - Task is in PENDING_REVIEW status
    - User has explicitly approved the review
    - No further changes are needed

    If changes are needed, use request_pr_changes to return the task to IN_PROGRESS.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        task_id: The ID of the task (local or fully qualified)
        changelog_category: Category for changelog (Added, Changed, Fixed, Removed, Deprecated, Security)
        commit_type: Type for commit message (feat, fix, docs, style, refactor, perf, test, build, ci, chore)
        version: Optional version for changelog header

    Returns:
        TaskFinalizationOut: Contains approved task details, changelog entry, and commit message
    """
    try:
        # 1. Approve task review (will fail if not in PENDING_REVIEW)
        resolved_story_id, local_task_id = resolve_task_id(task_id, plan_id=plan_id)
        svc_approve_pr(
            plan_id=plan_id,
            task_id=f"{resolved_story_id}:{local_task_id}",
            story_id=resolved_story_id,
        )

        # 2. Get the updated task
        task_data = svc_get_task(plan_id, resolved_story_id, local_task_id)
        task_out = _create_task_out(task_data)
    except (ValueError, KeyError, RuntimeError, OSError) as exc:
        _raise_workflow_error(
            plan_id=plan_id,
            message=str(exc),
            recovery=[
                "Call this tool only after user review approval at Gate 2.",
                "Confirm task_id points to a PENDING_REVIEW task in the supplied plan_id.",
                "Provide changelog_category and commit_type explicitly.",
            ],
        )

    # Convert TaskOut to Task for changelog generation
    from plan_manager.domain.models import Task as TaskModel

    task = TaskModel(**task_data)

    # 3. Generate changelog entry
    changelog_markdown = changelog_service.generate_changelog_for_task(
        task, category=changelog_category, version=version
    )

    # 4. Generate commit message
    commit_message = changelog_service.generate_commit_message_for_task(
        task, commit_type=commit_type
    )

    return TaskFinalizationOut(
        plan_id=plan_id,
        task_id=task_out.id,
        task_title=task_out.title,
        status=task_out.status,
        changelog_entry=changelog_markdown,
        commit_message=commit_message,
    )
