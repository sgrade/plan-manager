# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Transport-facing output schemas for MCP tools.

These Pydantic models define the structured shapes returned by the MCP
tool functions. They intentionally sit outside of the domain models to keep
transport concerns (serialization, stability of output contracts) separate
from core domain entities and rules.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from plan_manager.domain.models import Status


class OperationResult(BaseModel):
    """Generic result payload for mutation tools (create, update, delete)."""

    success: bool
    message: str


# --- Context Schemas ---


class CurrentContextOut(BaseModel):
    """Current context output returned by MCP tools."""

    plan_id: str
    current_story_id: str | None = None
    current_task_id: str | None = None


# --- Report Schemas ---


class ReportOut(BaseModel):
    """Structured report output returned by MCP tools."""

    plan_id: str
    report: str


# --- Plan Schemas ---


class PlanOut(BaseModel):
    """Structured plan output returned by MCP tools."""

    id: str
    title: str
    status: Status
    priority: int | None = None
    creation_time: str | None = None
    completion_time: str | None = None
    description: str | None = None


class PlanListItem(BaseModel):
    """Compact listing shape for plans."""

    id: str
    title: str
    status: Status
    priority: int | None = None
    creation_time: str | None = None


class WorkflowStatusOut(BaseModel):
    """Workflow status output showing current state and next actions."""

    current_task: dict[str, Any] | None = None
    workflow_state: dict[str, Any]
    compliance: dict[str, Any]
    next_actions: list[str]
    actions: list[dict[str, Any]] | None = None


class ChangelogPreviewOut(BaseModel):
    """Structured changelog preview output."""

    markdown: str


# --- Story Schemas ---


class StoryOut(BaseModel):
    """Structured story output returned by MCP tools.

    Fields mirror the persisted story attributes that are useful to clients
    and are intentionally stable for external consumers.
    """

    plan_id: str
    id: str
    title: str
    status: Status
    priority: int | None = None
    creation_time: str | None = None
    description: str | None = None
    acceptance_criteria: list[str] | None = None
    depends_on: list[str] = []


class StoryListItem(BaseModel):
    """Compact listing shape for stories.

    Optimized for lists and tables; excludes heavy or rarely used fields.
    """

    plan_id: str
    id: str
    title: str
    status: Status
    priority: int | None = None
    creation_time: str | None = None
    completion_time: str | None = None


# --- Task Schemas ---


class TaskOut(BaseModel):
    """Structured task output returned by MCP tools.

    Includes lifecycle timestamps and dependency list for client UIs and
    automation.
    """

    plan_id: str
    id: str
    local_id: str | None = None
    title: str
    description: str | None = None
    status: Status
    priority: int | None = None
    creation_time: str | None = None
    completion_time: str | None = None
    depends_on: list[str] = []
    steps: list[dict[str, Any]] | None = None
    changes: list[str] = []
    review_feedback: list[dict[str, Any]] | None = None
    rework_count: int | None = None


class TaskListItem(BaseModel):
    """Compact listing shape for tasks.

    Optimized for lists and tables; excludes heavy or rarely used fields.
    """

    plan_id: str
    id: str
    local_id: str | None = None
    title: str
    status: Status
    priority: int | None = None
    creation_time: str | None = None


# --- Unified Task Workflow Schemas ---


class WorkflowGate(StrEnum):
    """High-level gate aligned to the Task Execution workflow diagram."""

    READY_TO_START = "READY_TO_START"  # Task in TODO
    EXECUTING = "EXECUTING"  # Task IN_PROGRESS
    AWAITING_REVIEW = "AWAITING_REVIEW"  # Task PENDING_REVIEW
    DONE = "DONE"  # Task DONE
    BLOCKED = "BLOCKED"  # Task BLOCKED


class ActionType(StrEnum):
    """Categorical description of what action this tool performed."""

    NONE = "NONE"
    SET_CURRENT_TASK = "SET_CURRENT_TASK"
    CREATE_STEPS = "CREATE_STEPS"
    START_TASK = "START_TASK"
    APPROVE_PR = "APPROVE_PR"
    MERGE_PR = "MERGE_PR"
    SUBMIT_PR = "SUBMIT_PR"
    REQUEST_PR_CHANGES = "REQUEST_PR_CHANGES"


class WhoRuns(StrEnum):
    """Who is expected to perform the next action."""

    USER = "USER"
    AGENT = "AGENT"
    AGENT_AFTER_USER_APPROVAL = "AGENT_AFTER_USER_APPROVAL"
    EITHER = "EITHER"


class NextAction(BaseModel):
    """Next step suggestion with clear actor and execution modality."""

    kind: str = Field(default="tool", description="'tool' or 'prompt' or 'instruction'")
    name: str = Field(
        description="Tool or prompt name, e.g., 'approve_pr' or '/create_steps'"
    )
    label: str = Field(description="Human-readable label for UI")
    who: WhoRuns
    recommended: bool = False
    blocked_reason: str | None = None
    arguments: dict[str, Any] | None = None
    pending_arguments: list[str] | None = None


# Intentionally no separate agent policy type: agents derive behavior from
# next_actions.who


class TaskWorkflowResult(BaseModel):
    """Unified structured result for task workflow operations.

    Provides: outcome, updated task snapshot (if available), current gate, and
    explicit next actions with actor clarity to steer the workflow.
    """

    success: bool
    message: str
    plan_id: str | None = None
    task: TaskOut | None = None
    gate: WorkflowGate | None = None
    action: ActionType = ActionType.NONE
    next_actions: list[NextAction] = Field(default_factory=list)
    changelog_snippet: str | None = None
    # Keep output minimal; agents infer behavior from next_actions.who


class ChangelogEntryOut(BaseModel):
    """Output schema for generated changelog entries."""

    plan_id: str
    markdown: str
    task_id: str
    category: str


class CommitMessageOut(BaseModel):
    """Output schema for generated commit messages."""

    plan_id: str
    message: str
    task_id: str
    commit_type: str


class TaskFinalizationOut(BaseModel):
    """Output schema for finalize_task convenience tool."""

    action: ActionType = ActionType.MERGE_PR
    plan_id: str
    task_id: str
    task_title: str
    status: str
    changelog_entry: str
    commit_message: str
