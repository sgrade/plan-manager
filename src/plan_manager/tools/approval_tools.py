import logging

from plan_manager.services import approval_service
from plan_manager.schemas.outputs import ApproveTaskOut


logger = logging.getLogger(__name__)


def register_approval_tools(mcp_instance) -> None:
    """Register approval tools with the MCP instance."""
    mcp_instance.tool()(approve_task)

# This is a placeholder. In a real MCP server, this would be registered as a tool.


def approve_task() -> ApproveTaskOut:
    """
    Contextually approves the current task. This command is the primary way
    to move a task forward through its lifecycle.
    """
    logger.debug("approve_task tool called.")
    try:
        result = approval_service.approve_current_task()
        return ApproveTaskOut(**result)

    except ValueError:
        # Expected user-flow errors (e.g., no active task). Provide structured guidance.
        reviewable_tasks = approval_service.find_reviewable_tasks()

        if not reviewable_tasks:
            return ApproveTaskOut(success=False, message="There are no tasks to approve.", changelog_snippet=None)

        elif len(reviewable_tasks) == 1:
            task = reviewable_tasks[0]
            local_id = task.id.split(':')[-1]
            msg = (
                f"Task '{task.title}' ({local_id}) is ready for review. "
                f"Set it as current with `set_current_task {local_id}`, then run `approve_task`."
            )
            return ApproveTaskOut(success=False, message=msg, changelog_snippet=None)

        else:
            task_list = "\n".join(
                [f"- {t.title} ({t.id.split(':')[-1]})" for t in reviewable_tasks])
            msg = (
                "Multiple tasks are ready for review. Please set the current task, then run approve_task:\n"
                f"{task_list}"
            )
            return ApproveTaskOut(success=False, message=msg, changelog_snippet=None)

    except KeyError as e:
        return ApproveTaskOut(success=False, message=f"Error: Could not find the specified item. {e}", changelog_snippet=None)
    except RuntimeError as e:
        # Handle data inconsistencies or other specific errors
        return ApproveTaskOut(success=False, message=f"Error: {e}", changelog_snippet=None)

    except Exception as e:
        # Log the full exception for debugging
        logger.exception("An unexpected error occurred during approval.")
        return ApproveTaskOut(success=False, message=f"An unexpected error occurred: {e}", changelog_snippet=None)
