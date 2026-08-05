# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from typing import TYPE_CHECKING

from plan_manager.domain.models import Status
from plan_manager.schemas.outputs import OperationResult, PlanListItem, PlanOut
from plan_manager.services.plan_service import (
    create_plan as svc_create_plan,
)
from plan_manager.services.plan_service import (
    delete_plan as svc_delete_plan,
)
from plan_manager.services.plan_service import (
    get_plan as svc_get_plan,
)
from plan_manager.services.plan_service import (
    list_plans as svc_list_plans,
)
from plan_manager.services.plan_service import (
    update_plan as svc_update_plan,
)
from plan_manager.tools.util import coerce_optional_int

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_plan_tools(mcp_instance: "FastMCP") -> None:
    """Register plan tools with the MCP instance."""
    mcp_instance.tool()(list_plans)
    mcp_instance.tool()(create_plan)
    mcp_instance.tool()(get_plan)
    mcp_instance.tool()(update_plan)
    mcp_instance.tool()(delete_plan)


def create_plan(
    title: str, description: str | None = None, priority: float | None = None
) -> PlanOut:
    """Create a new plan with the specified details.

    Args:
        title: The title of the plan (will be validated and sanitized)
        description: Optional description of the plan
        priority: Optional priority level (0-5, where 0 is highest priority)

    Returns:
        PlanOut: The created plan with its generated ID and metadata
    """
    # Coerce priority robustly to provide better error messages at the tool boundary
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_create_plan(title, description, coerced_priority)
    return PlanOut(**data)


def get_plan(plan_id: str) -> PlanOut:
    """Fetch a plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
    """
    data = svc_get_plan(plan_id)
    return PlanOut(**data)


def update_plan(
    plan_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: float | None = None,
    status: Status | None = None,
) -> PlanOut:
    """Update a plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
        title: Updated plan title.
        description: Updated plan description.
        priority: Updated plan priority as an integer.
        status: Updated plan status.
    """
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_update_plan(plan_id, title, description, coerced_priority, status)
    return PlanOut(**data)


def delete_plan(plan_id: str) -> OperationResult:
    """Delete a plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.
    """
    data = svc_delete_plan(plan_id)
    return OperationResult(**data)


def list_plans(
    statuses: list[Status] | None = None,
    offset: int | None = 0,
    limit: int | None = None,
) -> list[PlanListItem]:
    """List plans with optional status filter and pagination."""
    if statuses is None:
        statuses = []
    data = svc_list_plans(statuses)
    items = [PlanListItem(**d) for d in data]
    start = max(0, offset or 0)
    end = None if limit is None else start + max(0, limit)
    return items[start:end]
