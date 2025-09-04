from typing import Optional, List
import logging
import importlib
from enum import Enum
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo


logger = logging.getLogger(__name__)


class Status(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"


class WorkItem(BaseModel):
    id: str
    title: str
    status: Status = Field(default=Status.TODO)
    depends_on: Optional[List[str]] = Field(default_factory=list)
    description: Optional[str] = None
    creation_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))
    completion_time: Optional[datetime] = None
    priority: Optional[int] = None

    @field_validator("status")
    @classmethod
    def status_must_be_allowed(cls, value: Status | str) -> Status:
        if isinstance(value, Status):
            return value
        upper = value.upper()
        try:
            return Status(upper)
        except Exception as e:
            raise ValueError(
                f"Invalid status '{value}'. Allowed: {', '.join([s.value for s in Status])}"
            ) from e

    @field_validator("priority")
    @classmethod
    def priority_must_be_in_range(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not (0 <= value <= 5):
            raise ValueError(
                "Priority must be between 0 and 5 (inclusive) if provided.")
        return value


class Approval(BaseModel):
    """Lightweight approval metadata for Story/Task items."""
    requested_by: Optional[str] = None
    requested_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None


class Story(WorkItem):
    file_path: Optional[str] = None
    # description: Durable what/why (inherited from WorkItem)
    # execution_intent: Ephemeral how/now plan for this iteration
    execution_intent: Optional[str] = Field(
        default=None,
        description="Ephemeral how/now checklist for this iteration (objective, scope, acceptance).",
    )
    # execution_summary: Brief outcome summary after work is done
    execution_summary: Optional[str] = Field(
        default=None,
        description="Brief outcome summary after completion (what changed, where).",
    )
    # approval: Lightweight approval metadata
    approval: Optional[Approval] = Field(
        default=None,
        description="Approval metadata (requested/approved by/at, optional notes).",
    )
    tasks: List['Task'] = Field(default_factory=list)


class Task(WorkItem):
    file_path: Optional[str] = None
    story_id: Optional[str] = None
    # See Story fields for semantics
    execution_intent: Optional[str] = Field(
        default=None,
        description="Ephemeral how/now checklist for this iteration (objective, scope, acceptance).",
    )
    execution_summary: Optional[str] = Field(
        default=None,
        description="Brief outcome summary after completion (what changed, where).",
    )
    approval: Optional[Approval] = Field(
        default=None,
        description="Approval metadata (requested/approved by/at, optional notes).",
    )


Story.model_rebuild()


class Plan(WorkItem):
    stories: List[Story] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_dependencies_exist_and_no_cycles(self, info: ValidationInfo) -> 'Plan':
        # For now, forbids plan-level dependencies to avoid cross-plan graphs
        if getattr(self, 'depends_on', None):
            raise ValueError(
                "Plan.depends_on is not supported; plans cannot depend on other plans. This is intentional.")

        if info.context and info.context.get("skip_dependency_check"):
            logger.debug(
                "Skipping dependency check for Plan validation based on context.")
            return self
        # Load validation at runtime to avoid import resolution issues
        validation_module = importlib.import_module(
            "plan_manager.domain.validation")
        validation_module.validate_plan_dependencies(self.stories)
        return self
