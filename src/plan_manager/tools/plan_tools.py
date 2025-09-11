from typing import List, Optional

from plan_manager.services.plan_service import (
    create_plan as svc_create_plan,
    get_plan as svc_get_plan,
    update_plan as svc_update_plan,
    delete_plan as svc_delete_plan,
    list_plans as svc_list_plans,
)
from plan_manager.domain.models import Status
from plan_manager.schemas.inputs import (
    ListPlansIn,
)
from plan_manager.schemas.outputs import PlanOut, PlanListItem, OperationResult
from plan_manager.services.plan_repository import set_current_plan_id, get_current_plan_id


def register_plan_tools(mcp_instance) -> None:
    """Register plan tools with the MCP instance."""
    mcp_instance.tool()(list_plans)
    mcp_instance.tool()(create_plan)
    mcp_instance.tool()(get_plan)
    mcp_instance.tool()(update_plan)
    mcp_instance.tool()(delete_plan)
    mcp_instance.tool()(set_current_plan)


def create_plan(title: str, description: Optional[str] = None, priority: Optional[int] = None) -> PlanOut:
    """Create a plan."""

    data = svc_create_plan(
        title, description, priority)
    return PlanOut(**data)


def get_plan(plan_id: Optional[str] = None) -> PlanOut:
    """Fetch a plan."""
    plan_id = plan_id or get_current_plan_id()
    data = svc_get_plan(plan_id)
    return PlanOut(**data)


def update_plan(plan_id: str, title: Optional[str] = None, description: Optional[str] = None, priority: Optional[int] = None, status: Optional[Status] = None) -> PlanOut:
    """Update a plan."""
    data = svc_update_plan(plan_id, title,
                           description, priority, status)
    return PlanOut(**data)


def delete_plan(plan_id: str) -> OperationResult:
    """Delete a plan."""
    data = svc_delete_plan(plan_id)
    return OperationResult(**data)


def list_plans(payload: Optional[ListPlansIn] = None) -> List[PlanListItem]:
    """List plans."""
    statuses = payload.statuses if payload else None
    data = svc_list_plans(statuses)
    items = [PlanListItem(**d) for d in data]
    if payload:
        start = max(0, payload.offset or 0)
        end = None if payload.limit is None else start + max(0, payload.limit)
        return items[start:end]
    return items


def set_current_plan(plan_id: Optional[str] = None) -> OperationResult | List[PlanListItem]:
    """Set the current plan. If no ID is provided, lists available plans."""
    if plan_id:
        set_current_plan_id(plan_id)
        return OperationResult(success=True, message=f"Current plan set to '{plan_id}'")
    # If no plan_id is provided, list available plans
    return list_plans()
