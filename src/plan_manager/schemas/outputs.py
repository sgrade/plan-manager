"""Transport-facing output schemas for MCP tools.

These Pydantic models define the structured shapes returned by the MCP
tool functions. They intentionally sit outside of the domain models to keep
transport concerns (serialization, stability of output contracts) separate
from core domain entities and rules.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from plan_manager.domain.models import Status


class OperationResult(BaseModel):
    """Generic result payload for mutation tools (create, update, delete)."""

    success: bool
    message: str


# --- Context Schemas ---


class CurrentContextOut(BaseModel):
    """Current context output returned by MCP tools."""

    plan_id: Optional[str] = None
    current_story_id: Optional[str] = None
    current_task_id: Optional[str] = None


# --- Report Schemas ---


class ReportOut(BaseModel):
    """Structured report output returned by MCP tools."""

    report: str


# --- Plan Schemas ---


class PlanOut(BaseModel):
    """Structured plan output returned by MCP tools."""

    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None
    description: Optional[str] = None


class PlanListItem(BaseModel):
    """Compact listing shape for plans."""

    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None


class WorkflowStatusOut(BaseModel):
    """Workflow status output showing current state and next actions."""

    current_task: Optional[dict] = None
    workflow_state: dict
    compliance: dict
    next_actions: list[str]
    actions: Optional[list[dict]] = None


class ChangelogPreviewOut(BaseModel):
    """Structured changelog preview output."""

    markdown: str


# --- Story Schemas ---


class StoryOut(BaseModel):
    """Structured story output returned by MCP tools.

    Fields mirror the persisted story attributes that are useful to clients
    and are intentionally stable for external consumers.
    """

    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[list[str]] = None
    depends_on: list[str] = []


class StoryListItem(BaseModel):
    """Compact listing shape for stories.

    Optimized for lists and tables; excludes heavy or rarely used fields.
    """

    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None


# --- Task Schemas ---


class TaskOut(BaseModel):
    """Structured task output returned by MCP tools.

    Includes lifecycle timestamps and dependency list for client UIs and
    automation.
    """

    id: str
    local_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None
    depends_on: list[str] = []
    steps: Optional[list[dict]] = None
    execution_summary: Optional[str] = None
    review_feedback: Optional[list[dict]] = None
    rework_count: Optional[int] = None


class TaskListItem(BaseModel):
    """Compact listing shape for tasks.

    Optimized for lists and tables; excludes heavy or rarely used fields.
    """

    id: str
    local_id: Optional[str] = None
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None


# --- Unified Task Workflow Schemas ---


class WorkflowGate(str, Enum):
    """High-level gate aligned to the Task Execution workflow diagram."""

    READY_TO_START = "READY_TO_START"  # Task in TODO
    EXECUTING = "EXECUTING"  # Task IN_PROGRESS
    AWAITING_REVIEW = "AWAITING_REVIEW"  # Task PENDING_REVIEW
    DONE = "DONE"  # Task DONE
    BLOCKED = "BLOCKED"  # Task BLOCKED


class ActionType(str, Enum):
    """Categorical description of what action this tool performed."""

    NONE = "NONE"
    SET_CURRENT_TASK = "SET_CURRENT_TASK"
    CREATE_STEPS = "CREATE_STEPS"
    APPROVE = "APPROVE"
    SUBMIT_FOR_REVIEW = "SUBMIT_FOR_REVIEW"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class WhoRuns(str, Enum):
    """Who is expected to perform the next action."""

    USER = "USER"
    AGENT = "AGENT"
    AGENT_AFTER_USER_APPROVAL = "AGENT_AFTER_USER_APPROVAL"
    EITHER = "EITHER"


class NextAction(BaseModel):
    """Next step suggestion with clear actor and execution modality."""

    kind: str = Field(default="tool", description="'tool' or 'prompt' or 'instruction'")
    name: str = Field(
        description="Tool or prompt name, e.g., 'approve_task' or '/create_steps'"
    )
    label: str = Field(description="Human-readable label for UI")
    who: WhoRuns
    recommended: bool = False
    blocked_reason: Optional[str] = None
    arguments: Optional[dict] = None


# Intentionally no separate agent policy type: agents derive behavior from next_actions.who


class TaskWorkflowResult(BaseModel):
    """Unified structured result for task workflow operations.

    Provides: outcome, updated task snapshot (if available), current gate, and
    explicit next actions with actor clarity to steer the workflow.
    """

    success: bool
    message: str
    task: Optional[TaskOut] = None
    gate: Optional[WorkflowGate] = None
    action: ActionType = ActionType.NONE
    next_actions: list[NextAction] = Field(default_factory=list)
    changelog_snippet: Optional[str] = None
    # Keep output minimal; agents infer behavior from next_actions.who
