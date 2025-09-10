import logging
from typing import Optional

from plan_manager.services import approval_service
from plan_manager.schemas.inputs import ApproveTaskIn
from plan_manager.schemas.outputs import ApproveTaskOut


logger = logging.getLogger(__name__)


def register_approval_tools(mcp_instance) -> None:
    """Register approval tools with the MCP instance."""
    mcp_instance.tool()(approve_task)

# This is a placeholder. In a real MCP server, this would be registered as a tool.


def approve_task(payload: Optional[ApproveTaskIn] = None) -> ApproveTaskOut | str:
    """
    Contextually approves the current task. This command is the primary way
    to move a task forward through its lifecycle.
    """
    item_id = payload.item_id if payload else None
    logger.debug(f"approve_task tool called with item_id: {item_id!r}")
    try:
        # Case 1: Fast-track approval
        if item_id:
            result = approval_service.approve_fast_track(item_id=item_id)
            return ApproveTaskOut(**result)

        # Case 2: Standard approval (no item specified)
        result = approval_service.approve_active_task()
        return ApproveTaskOut(**result)

    except ValueError:
        # This is an expected error, e.g., "No active task". We now make it smarter.
        reviewable_tasks = approval_service.find_reviewable_tasks()

        if not reviewable_tasks:
            return "There is no tasks to approve."

        elif len(reviewable_tasks) == 1:
            task = reviewable_tasks[0]
            local_id = task.id.split(':')[-1]
            return f"Task '{task.title}' ({local_id}) is ready for review. To approve it, run `approve_task {local_id}` or set it as the current task first."

        else:
            task_list = "\n".join(
                [f"- {t.title} ({t.id.split(':')[-1]})" for t in reviewable_tasks])
            return f"Multiple tasks are ready for review. Please specify which one to approve_task:\n{task_list}"

    except (KeyError, RuntimeError) as e:
        # Handle data inconsistencies or other specific errors
        return f"Error: {e}"

    except Exception as e:
        # Log the full exception for debugging
        logger.exception("An unexpected error occurred during approval.")
        return f"An unexpected and unhandled error occurred: {e}"
