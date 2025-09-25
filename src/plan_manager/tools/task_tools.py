from typing import List, Optional

from plan_manager.services.task_service import (
    create_task as svc_create_task,
    get_task as svc_get_task,
    update_task as svc_update_task,
    delete_task as svc_delete_task,
    list_tasks as svc_list_tasks,
    submit_for_code_review as svc_submit_for_code_review,
    create_steps as svc_create_steps,
)
from plan_manager.schemas.outputs import (
    TaskOut,
    TaskListItem,
    OperationResult,
    TaskWorkflowResult,
    NextAction,
    WhoRuns,
    WorkflowGate,
    ActionType,
)
from plan_manager.telemetry import incr, timer
from plan_manager.tools.util import coerce_optional_int
from plan_manager.services.shared import resolve_task_id
from plan_manager.services.state_repository import get_current_story_id, set_current_task_id, get_current_task_id
from plan_manager.domain.models import Status
from plan_manager.services.task_service import task_service
from plan_manager.logging import logger


def _create_task_out(data: dict) -> TaskOut:
    """Create a TaskOut object from a dictionary, populating the local_id."""
    if "id" in data and ":" in data["id"]:
        data["local_id"] = data["id"].split(":", 1)[1]
    return TaskOut(**data)


def register_task_tools(mcp_instance) -> None:
    """Register task tools with the MCP instance."""
    mcp_instance.tool()(list_tasks)
    mcp_instance.tool()(create_task)
    mcp_instance.tool()(get_task)
    mcp_instance.tool()(update_task)
    mcp_instance.tool()(delete_task)
    mcp_instance.tool()(set_current_task)
    mcp_instance.tool()(create_task_steps)
    mcp_instance.tool()(submit_for_review)
    mcp_instance.tool()(approve_task)
    mcp_instance.tool()(request_changes)


# ---------- Task CRUD operations ----------


def create_task(story_id: str, title: str, priority: Optional[float] = None, depends_on: Optional[list[str]] = None, description: Optional[str] = None) -> TaskOut:
    """Create a task under a story."""
    coerced_priority = coerce_optional_int(priority, 'priority')
    data = svc_create_task(story_id, title,
                           coerced_priority, depends_on or [], description)
    return _create_task_out(data)


def get_task(task_id: Optional[str] = None) -> TaskOut:
    """Fetch a task by ID (local or FQ). Defaults to current task of current story."""
    effective_task_id = task_id or get_current_task_id()
    if not effective_task_id:
        raise ValueError(
            "No current task set. Call set_current_task or provide task_id.")

    story_id, local_task_id = resolve_task_id(effective_task_id)
    data = svc_get_task(story_id, local_task_id)
    return _create_task_out(data)


def update_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[float] = None,
    depends_on: Optional[list[str]] = None,
    status: Optional[str] = None,
    steps: Optional[list[dict]] = None
) -> TaskOut:
    """Update mutable fields of a task."""
    story_id, local_task_id = resolve_task_id(task_id)
    # If steps are provided here, forward them via status/utils path by calling create_steps first
    if steps is not None:
        svc_create_steps(story_id=story_id, task_id=local_task_id, steps=steps)
    coerced_priority = coerce_optional_int(priority, 'priority')
    # Coerce status string to Status enum if provided
    coerced_status = None
    if status is not None:
        if isinstance(status, Status):
            coerced_status = status
        elif isinstance(status, str):
            try:
                coerced_status = Status(status.upper())
            except Exception as e:
                raise ValueError(
                    f"Invalid value for parameter 'status': {status!r}. Allowed: {', '.join([s.value for s in Status])}"
                ) from e
        else:
            raise ValueError(
                f"Invalid type for parameter 'status': expected string or null, got {type(status).__name__}."
            )

    data = svc_update_task(story_id, local_task_id, title,
                           description, depends_on, coerced_priority, coerced_status)
    return _create_task_out(data)


def delete_task(task_id: str) -> OperationResult:
    """Delete a task by ID (fails if other items depend on it)."""
    try:
        story_id, local_task_id = resolve_task_id(task_id)
        data = svc_delete_task(story_id, local_task_id)
        return OperationResult(**data)
    except (ValueError, KeyError) as e:
        return OperationResult(success=False, message=str(e))


def list_tasks(statuses: Optional[List[Status]] = None, story_id: Optional[str] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> List[TaskListItem]:
    """List tasks, optionally filtering by statuses and story with pagination."""
    story_id = story_id or get_current_story_id()
    tasks = svc_list_tasks(statuses, story_id)
    items: List[TaskListItem] = []
    for t in tasks:
        items.append(
            TaskListItem(
                id=t.id,
                title=t.title,
                status=t.status,
                priority=t.priority,
                creation_time=t.creation_time.isoformat() if t.creation_time else None,
                local_id=t.id.split(":", 1)[1] if ":" in t.id else t.id,
            )
        )
    start = max(0, offset or 0)
    end = None if limit is None else start + max(0, limit)
    return items[start:end]


# ---------- Task workflow operations ----------


def _status_to_gate(status: Status, steps: Optional[List[dict]]) -> WorkflowGate:
    if status == Status.DONE:
        return WorkflowGate.DONE
    if status == Status.PENDING_REVIEW:
        return WorkflowGate.AWAITING_REVIEW
    if status == Status.IN_PROGRESS:
        return WorkflowGate.EXECUTING
    if status == Status.BLOCKED:
        return WorkflowGate.BLOCKED
    return WorkflowGate.READY_TO_START


def _compute_next_actions_for_task(task: TaskOut, gate: WorkflowGate) -> List[NextAction]:
    actions: List[NextAction] = []

    if gate == WorkflowGate.BLOCKED:
        actions.append(NextAction(
            kind="instruction",
            name="resolve_dependencies",
            label="Resolve blockers (dependencies) before starting",
            who=WhoRuns.USER,
            recommended=True,
            blocked_reason="Task is BLOCKED by unmet dependencies."
        ))
        return actions

    if gate == WorkflowGate.READY_TO_START:
        if not (task.steps or []):
            actions.append(NextAction(
                kind="instruction",
                name="user_approval_fast_track",
                label="Fast-track: User says 'approve' in chat",
                who=WhoRuns.USER,
                recommended=True
            ))
            actions.append(NextAction(
                kind="tool",
                name="create_task_steps",
                label="Gate 1 Fast-track: Create steps now (no proposal UI)",
                who=WhoRuns.USER,
                recommended=True,
                arguments={"task_id": task.id, "steps": []}
            ))
            actions.append(NextAction(
                kind="tool",
                name="approve_task",
                label="Then: Approve to start execution",
                who=WhoRuns.USER,
                recommended=False
            ))
        else:
            actions.append(NextAction(
                kind="tool",
                name="approve_task",
                label="Gate 1: Approve plan to start execution",
                who=WhoRuns.USER,
                recommended=True
            ))
        return actions

    if gate == WorkflowGate.EXECUTING:
        actions.append(NextAction(
            kind="tool",
            name="submit_for_review",
            label="Submit task for code review",
            who=WhoRuns.AGENT,
            recommended=True,
            arguments={"task_id": task.id, "execution_summary": ""}
        ))
        return actions

    if gate == WorkflowGate.AWAITING_REVIEW:
        actions.append(NextAction(
            kind="tool",
            name="approve_task",
            label="Approve review to mark task DONE",
            who=WhoRuns.USER,
            recommended=True
        ))
        actions.append(NextAction(
            kind="tool",
            name="request_changes",
            label="Request changes and return task to IN_PROGRESS",
            who=WhoRuns.USER,
            recommended=False,
            arguments={"feedback": "", "task_id": task.id}
        ))
        return actions

    return actions


def create_task_steps(task_id: str, steps: List[dict]) -> TaskWorkflowResult:
    """Proposes implementation steps for a task, moving it to a reviewable state.

    Expects a list of step objects with 'title' and optional 'description'.
    """
    story_id, local_task_id = resolve_task_id(task_id)
    data = svc_create_steps(
        story_id=story_id, task_id=local_task_id, steps=steps)
    task = _create_task_out(data)
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(task, gate)
    message_lines = [
        f"Gate 1: Pre-Execution — steps attached for task '{task.title}'.",
        "Run approve_task to start work.",
    ]
    result = TaskWorkflowResult(
        success=True,
        message="\n".join(message_lines),
        task=task,
        gate=gate,
        action=ActionType.CREATE_STEPS,
        next_actions=next_actions,
    )
    return result


def set_current_task(task_id: Optional[str] = None) -> TaskWorkflowResult:
    """Set the current task for the current story."""
    # Ensure a story is selected
    story_id = get_current_story_id()
    if not story_id:
        return TaskWorkflowResult(success=False, message="No current story set. Run `set_current_story` first.", action=ActionType.SET_CURRENT_TASK)

    # Require a task identifier
    if not task_id:
        return TaskWorkflowResult(success=False, message="No task specified. Run `list_tasks` to view tasks, then `set_current_task <id>`.", action=ActionType.SET_CURRENT_TASK)

    s_id, local_task_id = resolve_task_id(task_id, story_id)
    fq_task_id = f"{s_id}:{local_task_id}"

    set_current_task_id(fq_task_id)
    data = svc_get_task(s_id, fq_task_id)
    task = _create_task_out(data)
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(task, gate)
    message_lines = [
        f"Current task set: '{task.title}' ({task.local_id}).",
    ]
    result = TaskWorkflowResult(
        success=True,
        message="\n".join(message_lines),
        task=task,
        gate=gate,
        action=ActionType.SET_CURRENT_TASK,
        next_actions=next_actions,
    )
    return result


def approve_task() -> TaskWorkflowResult:
    """
    Contextually approves the current task. This command is the primary way
    to move a task forward through its lifecycle.

    Important: agents should only call this tool after the user runs `approve_task` or provides similar instruction.
    """
    logger.debug("approve_task tool called.")
    try:
        result = task_service.approve_current_task()
        # result includes updated task fields
        task = _create_task_out({k: v for k, v in result.items()
                                 if k not in ("success", "message", "changelog_snippet")})
        gate = _status_to_gate(task.status, task.steps)
        next_actions = _compute_next_actions_for_task(task, gate)
        result = TaskWorkflowResult(
            success=result.get('success', False),
            message=result.get('message', ''),
            task=task,
            gate=gate,
            action=ActionType.APPROVE,
            next_actions=next_actions,
            changelog_snippet=result.get('changelog_snippet'),
        )
        return result

    except ValueError as e:
        # Keep selection orchestration client-side; return clear error only.
        return TaskWorkflowResult(success=False, message=str(e), action=ActionType.APPROVE)

    except KeyError as e:
        tmp = TaskWorkflowResult(
            success=False, message=f"Error: Could not find the specified item. {e}", action=ActionType.APPROVE)
        return tmp
    except RuntimeError as e:
        # Handle data inconsistencies or other specific errors
        tmp = TaskWorkflowResult(
            success=False, message=f"Error: {e}", action=ActionType.APPROVE)
        return tmp

    except Exception as e:
        # Log the full exception for debugging
        logger.exception("An unexpected error occurred during approval.")
        tmp = TaskWorkflowResult(
            success=False, message=f"An unexpected error occurred: {e}", action=ActionType.APPROVE)
        return tmp


def request_changes(task_id: str, feedback: str) -> TaskWorkflowResult:
    """Request changes for the current task (PENDING_REVIEW -> IN_PROGRESS)."""
    logger.debug("request_changes tool called.")
    try:
        s_id, local_task_id = resolve_task_id(task_id)
        result = task_service.request_changes(
            story_id=s_id, task_id=local_task_id, feedback=feedback)
        # Fetch the now-current task to include snapshot and next actions
        story_id = get_current_story_id()
        cur_task_id = get_current_task_id()
        task: Optional[TaskOut] = None
        gate: Optional[WorkflowGate] = None
        next_actions: List[NextAction] = []
        if story_id and cur_task_id:
            try:
                data = svc_get_task(story_id, cur_task_id)
                task = _create_task_out(data)
                gate = _status_to_gate(task.status, task.steps)
                next_actions = _compute_next_actions_for_task(task, gate)
            except Exception:
                pass
        tmp = TaskWorkflowResult(
            success=result.get('success', False),
            message=result.get('message', ''),
            task=task,
            gate=gate,
            action=ActionType.REQUEST_CHANGES,
            next_actions=next_actions,
        )
        return tmp
    except Exception as e:
        logger.exception(
            "An unexpected error occurred during request_changes.")
        tmp = TaskWorkflowResult(success=False, message=str(
            e), action=ActionType.REQUEST_CHANGES)
        return tmp


def submit_for_review(task_id: str, execution_summary: str) -> TaskWorkflowResult:
    """Submits a task for code review, moving it to PENDING_REVIEW status."""
    story_id, local_task_id = resolve_task_id(task_id)
    with timer("submit_for_review.duration_ms", task_id=local_task_id):
        data = svc_submit_for_code_review(
            story_id=story_id,
            task_id=local_task_id,
            summary_text=execution_summary
        )
    incr("submit_for_review.count")
    task = _create_task_out(data)
    execution_summary = task.execution_summary
    message_lines = [
        f"Task '{task.title}' is now PENDING_REVIEW.",
        "Review Summary:",
        execution_summary or "",
    ]
    gate = _status_to_gate(task.status, task.steps)
    next_actions = _compute_next_actions_for_task(task, gate)
    result = TaskWorkflowResult(
        success=True,
        message="\n".join(message_lines),
        task=task,
        gate=gate,
        action=ActionType.SUBMIT_FOR_REVIEW,
        next_actions=next_actions,
    )
    return result
