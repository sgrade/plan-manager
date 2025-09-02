from typing import List

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
from plan_manager.services.plan_repository import set_current_plan_id


def register_plan_tools(mcp_instance) -> None:
    mcp_instance.tool()(create_plan)
    mcp_instance.tool()(get_plan)
    mcp_instance.tool()(update_plan)
    mcp_instance.tool()(delete_plan)
    mcp_instance.tool()(list_plans)
    mcp_instance.tool()(set_current_plan)


def create_plan(payload: CreatePlanIn) -> PlanOut:
    data = svc_create_plan(payload.plan_id, payload.title,
                           payload.description, payload.priority)
    return PlanOut(**data)


def get_plan(payload: GetPlanIn) -> PlanOut:
    data = svc_get_plan(payload.plan_id)
    return PlanOut(**data)


def update_plan(payload: UpdatePlanIn) -> PlanOut:
    data = svc_update_plan(payload.plan_id, payload.title,
                           payload.description, payload.priority, payload.status)
    return PlanOut(**data)


def delete_plan(payload: DeletePlanIn) -> OperationResult:
    data = svc_delete_plan(payload.plan_id)
    return OperationResult(**data)


def list_plans(payload: ListPlansIn) -> List[PlanListItem]:
    data = svc_list_plans(payload.statuses)
    return [PlanListItem(**d) for d in data]


def set_current_plan(payload: SetCurrentPlanIn) -> OperationResult:
    set_current_plan_id(payload.plan_id)
    return OperationResult(success=True, message=f"Current plan set to '{payload.plan_id}'")
