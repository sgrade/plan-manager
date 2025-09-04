from typing import Union

from plan_manager.schemas.inputs import RequestApprovalIn, ApproveItemIn
from plan_manager.schemas.outputs import StoryOut, TaskOut
from plan_manager.services.approval_service import request_approval, approve_item


def register_approval_tools(mcp_instance) -> None:
    """Register approval tools with the MCP instance."""
    mcp_instance.tool()(request_approval_tool)
    mcp_instance.tool()(approve_item_tool)


def request_approval_tool(payload: RequestApprovalIn) -> Union[StoryOut, TaskOut]:
    """Request approval for a story or task."""
    data = request_approval(
        payload.item_type, payload.item_id, payload.execution_intent)
    # decide return shape by key presence
    if 'story_id' in data or 'depends_on' in data and 'story_id' not in data:
        return StoryOut(**data)
    return TaskOut(**data)


def approve_item_tool(payload: ApproveItemIn) -> Union[StoryOut, TaskOut]:
    """Approve or reject a story or task for progress."""
    data = approve_item(payload.item_type, payload.item_id,
                        payload.approved, payload.notes)
    if 'story_id' in data or 'depends_on' in data and 'story_id' not in data:
        return StoryOut(**data)
    return TaskOut(**data)
