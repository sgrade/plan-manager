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
    """Create a new task under the specified story.

    Args:
        story_id: The ID of the story to create the task under
        title: The title of the task (will be validated and sanitized)
        priority: Optional priority level (0-5, where 5 is highest)
        depends_on: Optional list of task IDs this task depends on
        description: Optional description of the task

    Returns:
        TaskOut: The created task with its generated ID and metadata
    """
    coerced_priority = coerce_optional_int(priority, 'priority')
    data = svc_create_task(story_id, title,
                           coerced_priority, depends_on or [], description)
    return _create_task_out(data)


def get_task(task_id: Optional[str] = None) -> TaskOut:
    """Get a task by its ID, defaulting to the current task if no ID provided.

    Args:
        task_id: Optional task ID (local or fully qualified). If not provided,
                returns the current task of the current story.

    Returns:
        TaskOut: The requested task with its metadata and current state

    Raises:
        ValueError: If no task ID provided and no current task is set
    """
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
            except ValueError as e:
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


def list_tasks(statuses: List[Status] = [], story_id: Optional[str] = None, offset: Optional[int] = 0, limit: Optional[int] = None) -> List[TaskListItem]:
    """List tasks with optional filtering by status and story, with pagination support.

    Args:
        statuses: Optional list of task statuses to filter by. Empty list means no status filter.
        story_id: Optional story ID to filter tasks by. Defaults to current story if not provided.
        offset: Number of tasks to skip (for pagination). Defaults to 0.
        limit: Maximum number of tasks to return. None means no limit.

    Returns:
        List[TaskListItem]: List of task summaries matching the filter criteria
    """
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
                name="ask_user_next_step",
                label="Ask: Would you like assisted steps or fast-track?",
                who=WhoRuns.AGENT,
                recommended=True,
                arguments={
                    "then": [
                        {"prompt": "/create_steps",
                            "arguments": {"task_id": task.id}},
                        {"instruction": "user_approval_fast_track"}
                    ]
                }
            ))
            # Only user instructions at this point; the agent must wait for the user's choice
            actions.append(NextAction(
                kind="prompt",
                name="/create_steps",
                label="Assisted: User runs /create_steps prompt",
                who=WhoRuns.USER,
                recommended=False,
                arguments={"task_id": task.id}
            ))
            actions.append(NextAction(
                kind="instruction",
                name="user_approval_fast_track",
                label="Fast-track: User says 'approve steps' in chat",
                who=WhoRuns.USER,
                recommended=False,
                arguments={
                    "then": [
                        {"tool": "create_task_steps", "arguments": {
                            "task_id": task.id, "steps": []}},
                        {"tool": "approve_task"}
                    ]
                }
            ))
        else:
            actions.append(NextAction(
                kind="tool",
                name="approve_task",
                label="Gate 1: Agent runs approve_task to start execution",
                who=WhoRuns.AGENT,
                recommended=True
            ))
        return actions

    if gate == WorkflowGate.EXECUTING:
        # Follow the diagram: user instructs to execute, agent executes, then submits for review
        actions.append(NextAction(
            kind="instruction",
            name="user_execute_instruction",
            label="User says 'execute' in chat",
            who=WhoRuns.USER,
            recommended=True
        ))
        actions.append(NextAction(
            kind="instruction",
            name="agent_execute_work",
            label="Agent executes the task",
            who=WhoRuns.AGENT,
            recommended=False
        ))
        actions.append(NextAction(
            kind="tool",
            name="submit_for_review",
            label="Agent runs submit_for_review (non-empty execution_summary)",
            who=WhoRuns.AGENT,
            recommended=False,
            arguments={"task_id": task.id, "execution_summary": ""}
        ))
        return actions

    if gate == WorkflowGate.AWAITING_REVIEW:
        # Gate 2 sequence per workflow:
        # 1) Agent displays execution_summary and asks the user to approve or request changes
        actions.append(NextAction(
            kind="instruction",
            name="display_review_and_prompt",
            label="Show execution summary and ask: Say 'approve review' or provide feedback to request changes.",
            who=WhoRuns.AGENT,
            recommended=True
        ))
        # 2a) User approves review in chat, then agent runs approve_task
        actions.append(NextAction(
            kind="instruction",
            name="user_approves_review",
            label="User says 'approve review' in chat",
            who=WhoRuns.USER,
            recommended=False,
            arguments={
                "then": [
                    {"tool": "approve_task"}
                ]
            }
        ))
        actions.append(NextAction(
            kind="tool",
            name="approve_task",
            label="Agent runs approve_task to mark task DONE",
            who=WhoRuns.AGENT,
            recommended=False
        ))
        # 2b) Or the user provides feedback, then agent runs request_changes
        actions.append(NextAction(
            kind="instruction",
            name="user_provides_feedback",
            label="User provides feedback in chat",
            who=WhoRuns.USER,
            recommended=False,
            arguments={
                "then": [
                    {"tool": "request_changes"}
                ]
            }
        ))
        actions.append(NextAction(
            kind="tool",
            name="request_changes",
            label="Agent runs request_changes to return task to IN_PROGRESS",
            who=WhoRuns.AGENT,
            recommended=False,
            arguments={"feedback": "", "task_id": task.id}
        ))
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
                remaining = [t for t in svc_list_tasks(
                    None, story_id) if t.status != Status.DONE]
                has_remaining_in_story = len(remaining) > 0
            except (ValueError, KeyError, OSError):
                # Handle service call failures gracefully
                has_remaining_in_story = False

        if has_remaining_in_story:
            actions.append(NextAction(
                kind="tool",
                name="list_tasks",
                label="List remaining tasks in the current story",
                who=WhoRuns.AGENT,
                recommended=True,
                arguments={"story_id": story_id} if story_id else None
            ))
        else:
            actions.append(NextAction(
                kind="instruction",
                name="verify_story_acceptance",
                label="Review story acceptance criteria",
                who=WhoRuns.USER,
                recommended=True,
                arguments={
                    "then": [
                        {"tool": "report", "arguments": {"scope": "story"}}
                    ]
                }
            ))
        return actions

    return actions


def create_task_steps(task_id: str, steps: List[dict]) -> TaskWorkflowResult:
    """Create implementation steps for a task, enabling pre-execution review.

    Args:
        task_id: The ID of the task to add steps to (local or fully qualified)
        steps: List of step objects, each with 'title' and optional 'description'

    Returns:
        TaskWorkflowResult: Result containing the updated task and next actions
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

    except (ValueError, KeyError, OSError, RuntimeError) as e:
        # Handle expected business logic errors
        logger.warning(f"Approval failed due to business logic error: {e}")
        tmp = TaskWorkflowResult(
            success=False, message=str(e), action=ActionType.APPROVE)
        return tmp
    except Exception as e:
        # Log unexpected errors for debugging
        logger.exception(f"An unexpected error occurred during approval: {e}")
        tmp = TaskWorkflowResult(
            success=False, message="An unexpected error occurred during approval", action=ActionType.APPROVE)
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
            except (ValueError, KeyError, OSError):
                # Handle service call failures gracefully
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
    except (ValueError, KeyError, OSError, RuntimeError) as e:
        # Handle expected business logic errors
        logger.warning(
            f"Request changes failed due to business logic error: {e}")
        tmp = TaskWorkflowResult(success=False, message=str(
            e), action=ActionType.REQUEST_CHANGES)
        return tmp
    except Exception as e:
        # Log unexpected errors for debugging
        logger.exception(
            f"An unexpected error occurred during request_changes: {e}")
        tmp = TaskWorkflowResult(
            success=False, message=f"An unexpected error occurred during request changes: {e}", action=ActionType.REQUEST_CHANGES)
        return tmp


def submit_for_review(task_id: str, execution_summary: str) -> TaskWorkflowResult:
    """Submit a completed task for code review and move it to PENDING_REVIEW status.

    Args:
        task_id: The ID of the task to submit for review (local or fully qualified)
        execution_summary: Summary of the work completed and implementation details

    Returns:
        TaskWorkflowResult: Result containing the updated task and next actions for review
    """
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
