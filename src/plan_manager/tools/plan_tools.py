from typing import Optional

from plan_manager.domain.models import Status
from plan_manager.schemas.outputs import OperationResult, PlanListItem, PlanOut
from plan_manager.services.plan_repository import (
    get_current_plan_id,
    set_current_plan_id,
)
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


def register_plan_tools(mcp_instance) -> None:
    """Register plan tools with the MCP instance."""
    mcp_instance.tool()(list_plans)
    mcp_instance.tool()(create_plan)
    mcp_instance.tool()(get_plan)
    mcp_instance.tool()(update_plan)
    mcp_instance.tool()(delete_plan)
    mcp_instance.tool()(set_current_plan)


def create_plan(
    title: str, description: Optional[str] = None, priority: Optional[float] = None
) -> PlanOut:
    """Create a new plan with the specified details.

    Args:
        title: The title of the plan (will be validated and sanitized)
        description: Optional description of the plan
        priority: Optional priority level (0-5, where 5 is highest)

    Returns:
        PlanOut: The created plan with its generated ID and metadata
    """
    # Coerce priority robustly to provide better error messages at the tool boundary
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_create_plan(title, description, coerced_priority)
    return PlanOut(**data)


def get_plan(plan_id: Optional[str] = None) -> PlanOut:
    """Fetch a plan."""
    plan_id = plan_id or get_current_plan_id()
    data = svc_get_plan(plan_id)
    return PlanOut(**data)


def update_plan(
    plan_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[float] = None,
    status: Optional[Status] = None,
) -> PlanOut:
    """Update a plan."""
    coerced_priority = coerce_optional_int(priority, "priority")
    data = svc_update_plan(plan_id, title, description, coerced_priority, status)
    return PlanOut(**data)


def delete_plan(plan_id: str) -> OperationResult:
    """Delete a plan."""
    data = svc_delete_plan(plan_id)
    return OperationResult(**data)


def list_plans(
    statuses: Optional[list[Status]] = None,
    offset: Optional[int] = 0,
    limit: Optional[int] = None,
) -> list[PlanListItem]:
    """List plans with optional status filter and pagination."""
    if statuses is None:
        statuses = []
    data = svc_list_plans(statuses)
    items = [PlanListItem(**d) for d in data]
    start = max(0, offset or 0)
    end = None if limit is None else start + max(0, limit)
    return items[start:end]


def set_current_plan(
    plan_id: Optional[str] = None,
) -> OperationResult | list[PlanListItem]:
    """Set the current plan. If no ID is provided, lists available plans."""
    if plan_id:
        set_current_plan_id(plan_id)
        return OperationResult(success=True, message=f"Current plan set to '{plan_id}'")
    # If no plan_id is provided, list available plans
    return list_plans()
