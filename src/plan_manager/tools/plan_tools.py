from typing import List, Optional

from plan_manager.services.plan_service import (
    create_plan as svc_create_plan,
    get_plan as svc_get_plan,
    update_plan as svc_update_plan,
    delete_plan as svc_delete_plan,
    list_plans as svc_list_plans,
)
from plan_manager.schemas.inputs import (
    CreatePlanIn, GetPlanIn, UpdatePlanIn, DeletePlanIn, ListPlansIn, SetCurrentPlanIn,
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


def create_plan(payload: CreatePlanIn) -> PlanOut:
    """Create a plan."""

    data = svc_create_plan(
        payload.title, payload.description, payload.priority)
    return PlanOut(**data)


def get_plan(payload: Optional[GetPlanIn] = None) -> PlanOut:
    """Fetch a plan."""
    plan_id = payload.plan_id if payload else get_current_plan_id()
    data = svc_get_plan(plan_id)
    return PlanOut(**data)


def update_plan(payload: UpdatePlanIn) -> PlanOut:
    """Update a plan."""
    data = svc_update_plan(payload.plan_id, payload.title,
                           payload.description, payload.priority, payload.status)
    return PlanOut(**data)


def delete_plan(payload: DeletePlanIn) -> OperationResult:
    """Delete a plan."""
    data = svc_delete_plan(payload.plan_id)
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


def set_current_plan(payload: Optional[SetCurrentPlanIn] = None) -> OperationResult | List[PlanListItem]:
    """Set the current plan. If no ID is provided, lists available plans."""
    if payload and payload.plan_id:
        set_current_plan_id(payload.plan_id)
        return OperationResult(success=True, message=f"Current plan set to '{payload.plan_id}'")
    else:
        # If no plan_id is provided, list available plans
        return list_plans()
