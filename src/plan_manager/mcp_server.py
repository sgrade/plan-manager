"""MCP Server (SSE Transport) for interacting with the project plan.

This module implements an MCP (Model Context Protocol) server that provides
AI assistants with tools to manage tasks in a YAML-based project plan.
The server supports task creation, modification, listing, and dependency management.
"""

import sys
import os
import logging
import yaml
from typing import List, Optional, Dict, Any
import re
import collections
from datetime import datetime, timezone, timedelta
import shutil

# Project Setup - Ensure the tools directory is in the path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.dirname(script_dir)
sys.path.insert(0, tools_dir)

# --- Imports ---

# MCP SDK Imports
from mcp.server.fastmcp import FastMCP
import mcp.types as types
from pydantic import ValidationError

# ASGI Imports
from starlette.applications import Starlette
from starlette.routing import Mount, Route
# from starlette.responses import PlainTextResponse, JSONResponse # For error handling
# from starlette.exceptions import HTTPException # For error handling
import uvicorn

# Local Utility Imports
from plan_manager.plan_utils import (
    load_plan_data,
    load_tasks,
    save_plan_data,
    find_task_by_id,
    # find_task_index_by_id, # Less used now
    filter_tasks,
    ALLOWED_STATUSES,
    PLAN_FILE_PATH,
    ARCHIVE_DIR_PATH,
    ARCHIVED_DETAILS_DIR_PATH,
    load_archive_plan_data,
    save_archive_plan_data,
    _workspace_root,
    remove_archived_task,
    Plan, Task, add_task, remove_task
)

# --- Logging Setup ---
LOG_DIR = os.path.join(os.getcwd(), 'logs')
LOG_FILE_PATH = os.path.join(LOG_DIR, 'mcp_server_app.log')
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

ENABLE_FILE_LOG = os.getenv("PLAN_MANAGER_ENABLE_FILE_LOG", "true").lower() in ("1","true","yes","on")
if ENABLE_FILE_LOG:
    file_handler = logging.FileHandler(LOG_FILE_PATH)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

logging.info(f"MCP server application logging configured. App logs will also be in: {LOG_FILE_PATH}")

# --- MCP Server Initialization ---
mcp = FastMCP(
    name="plan-manager",
    instructions="Manages tasks defined in the project's todo/plan.yaml file.",
    sse_path="/sse",
    message_path="/messages/"
)

# --- ID Generation Helper ---

def _generate_id_from_title(title: str) -> str:
    """Generate a suitable task ID from a title.

    Converts a human-readable title into a standardized task ID by:
    1. Converting to lowercase
    2. Keeping only letters, numbers, and spaces
    3. Replacing whitespace sequences with underscores
    4. Converting to uppercase

    Args:
        title: The human-readable task title

    Returns:
        A standardized uppercase task ID

    Raises:
        ValueError: If title is empty or results in empty ID after processing
    """
    if not title:
        raise ValueError("Title cannot be empty when generating an ID.")

    # Lowercase, keep only letters, numbers, spaces, replace others with space
    id_str = title.lower()
    id_str = re.sub(r'[^a-z0-9\s]+', ' ', id_str)

    # Replace whitespace sequences with single underscore, strip leading/trailing underscores
    id_str = re.sub(r'\s+', '_', id_str.strip())

    # Convert to uppercase
    generated_id = id_str.upper()

    if not generated_id:
        raise ValueError(f"Title '{title}' resulted in an empty ID after processing.")

    return generated_id

# --- Tool Definitions (using @mcp.tool()) ---

@mcp.tool()
def list_tasks_handler(statuses: str, unblocked: bool = False) -> list[dict]:
    """Lists tasks from plan.yaml, with optional filters, sorted by dependency, priority, and creation time.

    Args:
        statuses: Comma-separated string of statuses to filter by (e.g., "TODO,IN_PROGRESS"). Case-insensitive. REQUIRED.
        unblocked: If true, show only TODO tasks whose dependencies are all DONE.

    Returns:
        A list of tasks (dictionaries with id, status, title, priority, creation_time) matching the filters, in a topologically sorted order.
    """
    logging.info(f"Handling list_tasks: statuses_str='{statuses}', unblocked={unblocked}")

    try:
        all_tasks: List[Task] = load_tasks()
        if not all_tasks:
            return []

        # --- Topological Sort ---
        adj: Dict[str, List[str]] = collections.defaultdict(list)
        in_degree: Dict[str, int] = collections.defaultdict(int)
        task_map: Dict[str, Task] = {task.id: task for task in all_tasks}

        for task in all_tasks:
            # Ensure all tasks are in in_degree, even if they have no dependencies listed
            _ = in_degree[task.id] # Access to ensure key exists with default 0
            if task.depends_on:
                for dep_id in task.depends_on:
                    adj[dep_id].append(task.id)
                    in_degree[task.id] += 1

        queue = collections.deque()
        for task_id in task_map:
            if in_degree[task_id] == 0:
                queue.append(task_map[task_id])

        sorted_tasks_list: List[Task] = []

        while queue:
            # Sort the current queue based on priority, creation_time, and id
            # Priority: 0-5 (0 is highest), None is lowest (treat as 6 for sorting)
            # Creation time: Earlier is better (None is later)
            # ID: Alphabetical ascending
            queue_list = sorted(
                list(queue),
                key=lambda t: (
                    t.priority if t.priority is not None else 6, # Lower prio number is better
                    t.creation_time is None, # False (has time) before True (no time)
                    t.creation_time if t.creation_time is not None else datetime.max.replace(tzinfo=timezone.utc),
                    t.id
                )
            )
            queue = collections.deque(queue_list)

            current_task = queue.popleft()
            sorted_tasks_list.append(current_task)

            for neighbor_id in adj[current_task.id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(task_map[neighbor_id])

        if len(sorted_tasks_list) != len(all_tasks):
            # Cycle detected or other inconsistency
            # Log detailed information for debugging
            missing_ids = set(task_map.keys()) - set(t.id for t in sorted_tasks_list)
            logging.error(
                f"Cycle detected in task dependencies or graph inconsistency. "
                f"Total tasks: {len(all_tasks)}, Sorted tasks: {len(sorted_tasks_list)}. "
                f"Tasks not sorted (potential cycle members or disconnected): {missing_ids}"
            )
            # Consider how to represent this to the user. For now, returning what was sorted.
            # Or raise an error: raise ValueError("Cycle detected in task dependencies.")
            # For now, we'll proceed with what could be sorted, but this indicates a data issue.

        # --- Filtering (applied *after* topological sort) ---
        actual_statuses_list: Optional[List[str]] = None
        if statuses: # statuses is required, but handle if it's an empty string from user
            parsed_statuses = [s.strip().upper() for s in statuses.split(',') if s.strip()]
            if parsed_statuses:
                actual_statuses_list = parsed_statuses
            else:
                logging.warning("Statuses string was effectively empty after parsing; no status filter applied.")
        else: # Should not happen if arg is truly required by MCP framework, but defensive
             logging.warning("Statuses argument was None/empty; no status filter applied.")


        # Apply filters to the topologically sorted list
        final_filtered_tasks: List[Task] = []
        all_tasks_map_for_filter: Dict[str, Task] = {task.id: task for task in sorted_tasks_list}

        for task in sorted_tasks_list: # Iterate over the already sorted list
            status_match = True
            if actual_statuses_list:
                status_match = task.status in actual_statuses_list

            if not status_match:
                continue

            unblocked_match = True
            if unblocked:
                if task.status != 'TODO':
                    unblocked_match = False
                else:
                    if task.depends_on:
                        for dep_id in task.depends_on:
                            dep_task = task_map.get(dep_id) # Check original map for dependency status
                            if not dep_task or dep_task.status != 'DONE':
                                unblocked_match = False
                                break

            if unblocked_match:
                final_filtered_tasks.append(task)

        # Add index to title for display
        indexed_tasks_for_display = []
        for i, task_model in enumerate(final_filtered_tasks):
            # Create a new dict to avoid modifying the original Task model if it's used elsewhere by reference,
            # though in this flow, they are about to be dumped.
            # However, model_dump will be called on task_model, so better to modify a copy if we were to return models.
            # Since we are returning dicts anyway, we can build them here.

            task_dict = task_model.model_dump(
                include={'id', 'status', 'priority', 'creation_time', 'completion_time'},
                exclude_none=True
            )
            task_dict['title'] = f"{i + 1:02d}. {task_model.title}" # Use original title from task_model
            indexed_tasks_for_display.append(task_dict)

        result = indexed_tasks_for_display # Use the list with modified titles

        logging.info(f"list_tasks returning {len(result)} tasks after sorting, filtering, and title indexing.")
        return result

    except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
        logging.exception("Failed to load/validate plan data for list_tasks")
        # Re-raise as a generic exception or map to a specific user-facing error?
        # For now, let FastMCP handle it (or raise HTTP exception if needed)
        raise e # Let FastMCP try to handle it
    except Exception as e:
        logging.exception("Unexpected error during list_tasks")
        raise e

@mcp.tool()
def show_task_handler(task_id: str) -> dict:
    """Shows full details for a specific task.

    Args:
        task_id: The ID of the task to show.

    Returns:
        A dictionary containing all details of the found task.
    """
    logging.info(f"Handling show_task: task_id={task_id}")
    try:
        tasks: List[Task] = load_tasks()
        task: Optional[Task] = find_task_by_id(tasks, task_id)

        if task:
            logging.info(f"show_task found task: {task_id}")
            # Return the full task details as a dictionary
            return task.model_dump(mode='json', exclude_none=True)
        else:
            logging.warning(f"show_task did not find task: {task_id}")
            # Raise KeyError as before, let FastMCP handle it
            raise KeyError(f"Task with ID '{task_id}' not found.")

    except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
        logging.exception("Failed to load/validate plan data for show_task")
        raise e # Let FastMCP handle it
    except KeyError as e: # Catch the KeyError explicitly if needed, or let it propagate
         raise e
    except Exception as e:
        logging.exception("Unexpected error during show_task")
        raise e

@mcp.tool()
def update_task_status_handler(task_id: str, new_status: str) -> dict:
    """Updates the status of a specific task.

    Args:
        task_id: The ID of the task to update.
        new_status: The new status. Case-insensitive.
                    Allowed: TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED

    Returns:
        A dictionary indicating success with a message.
    """
    logging.info(f"Handling update_task_status: task_id={task_id}, new_status={new_status}")

    # Pydantic model validator for Task handles status validation now.
    # We still need to check here *before* loading if the input is potentially valid.
    status_upper = new_status.upper()
    if status_upper not in ALLOWED_STATUSES:
        msg = f"Invalid status '{new_status}'. Allowed: { ', '.join(sorted(list(ALLOWED_STATUSES))) }"
        logging.error(msg)
        raise ValueError(msg)

    try:
        plan: Plan = load_plan_data()
        tasks: List[Task] = plan.tasks

        # Find the task object
        task_to_update: Optional[Task] = None
        task_index: Optional[int] = None
        for i, task in enumerate(tasks):
            if task.id == task_id:
                task_to_update = task
                task_index = i
                break

        if task_to_update is None or task_index is None:
            msg = f"Task with ID '{task_id}' not found."
            logging.warning(msg)
            raise KeyError(msg)

        old_status = task_to_update.status

        # Update the status on the Pydantic model
        task_to_update.status = status_upper

        # Handle completion_time based on new status
        if status_upper == 'DONE' and old_status != 'DONE':
            task_to_update.completion_time = datetime.now(timezone.utc)
            logging.info(f"Task '{task_id}' marked DONE. Completion time set to {task_to_update.completion_time.isoformat()}.")
        elif status_upper != 'DONE' and old_status == 'DONE':
            task_to_update.completion_time = None
            logging.info(f"Task '{task_id}' moved from DONE to {status_upper}. Completion time removed.")

        plan.tasks[task_index] = task_to_update

        # Save the updated Plan object
        save_plan_data(plan)

        msg = f"Successfully updated status for task '{task_id}' from '{old_status}' to '{status_upper}'."
        logging.info(msg)
        return {"success": True, "message": msg}

    except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
        # Handle loading/validation errors
        logging.exception(f"Failed to load/validate plan data for update_task_status: {e}")
        raise e # Let FastMCP handle it
    except (KeyError, ValueError, IOError) as e:
        # Handle errors specific to the update process (not found, invalid status (redundant?), save failed)
        logging.exception(f"Error during task status update: {e}")
        raise e # Let FastMCP handle it
    except Exception as e:
        logging.exception("Unexpected error during update_task_status")
        raise e

@mcp.tool()
def update_task_priority_handler(task_id: str, new_priority_str: str) -> dict:
    """Updates the priority of a specific task.

    Args:
        task_id: The ID of the task to update.
        new_priority_str: The new priority as a string.
                          Valid values are "0", "1", "2", "3", "4", "5".
                          Use "6" to remove the priority (set to null/None).

    Returns:
        A dictionary indicating success with a message.
    """
    logging.info(f"Handling update_task_priority: task_id={task_id}, new_priority_str={new_priority_str}")

    numeric_priority: Optional[int] = None
    if new_priority_str == "6":
        numeric_priority = None
        logging.info(f"Priority string for task '{task_id}' is \"6\", interpreting as remove priority (None).")
    elif not new_priority_str:
        msg = f"Priority string for task '{task_id}' cannot be empty. Use \"6\" to remove priority."
        logging.error(msg)
        raise ValueError(msg)
    else:
        try:
            numeric_priority = int(new_priority_str)
            # Pydantic model validator for Task will handle the 0-5 range check.
            # We only need to ensure it\'s a convertible int here if not "6".
            if not (0 <= numeric_priority <= 5): # We can pre-check here for a better error message
                 msg = f"Invalid priority value '{new_priority_str}\' for task '{task_id}\'. Must be a whole number between 0 and 5, or \"6\" to remove priority."
                 logging.error(msg)
                 raise ValueError(msg)
        except ValueError as e:
            # If int() conversion failed or our pre-check failed
            msg = f"Invalid priority string '{new_priority_str}\' for task '{task_id}\'. Must be a whole number (0-5), or \"6\" to remove priority."
            logging.error(msg)
            # Raise a new ValueError to ensure our message is used, or re-raise if it\'s already our specific message.
            if "Invalid priority value" in str(e) or "Invalid priority string" in str(e) : # Avoid re-wrapping our own error
                 raise e
            raise ValueError(msg) from e


    try:
        plan: Plan = load_plan_data()
        tasks: List[Task] = plan.tasks

        task_to_update: Optional[Task] = None
        task_index: Optional[int] = None
        for i, task_obj in enumerate(tasks):
            if task_obj.id == task_id:
                task_to_update = task_obj
                task_index = i
                break

        if task_to_update is None or task_index is None:
            msg = f"Task with ID '{task_id}\' not found for priority update."
            logging.warning(msg)
            raise KeyError(msg)

        old_priority = task_to_update.priority

        # Update the priority on the Pydantic model
        # This will trigger the validator in the Task model if the numeric_priority is invalid (e.g. 7)
        # though our initial check for 0-5 should catch most direct numeric issues.
        task_to_update.priority = numeric_priority

        plan.tasks[task_index] = task_to_update

        save_plan_data(plan)

        msg = f"Successfully updated priority for task '{task_id}\' from '{old_priority if old_priority is not None else 'Not set'}\' to '{numeric_priority if numeric_priority is not None else 'Not set'}\'."
        logging.info(msg)
        return {"success": True, "message": msg, "task_id": task_id, "new_priority": numeric_priority}

    except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
        logging.exception(f"Failed to load/validate plan data for update_task_priority: {e}")
        raise e
    except (KeyError, ValueError, IOError) as e: # Includes our own ValueErrors from string validation
        logging.exception(f"Error during task priority update for '{task_id}\': {e}")
        raise e
    except Exception as e:
        logging.exception(f"Unexpected error during update_task_priority for '{task_id}\'")
        raise e

@mcp.tool()
def create_task_handler(
    # task_id: str, # Removed task_id parameter
    title: str,
    priority: str,                 # Priority is now a REQUIRED string. Sentinel value "6" means not set.
    depends_on: str,               # Depends_on is now a REQUIRED string. Sentinel value "" means not set.
    notes: str                     # Notes is now a REQUIRED string. Sentinel value "" means not set.
) -> dict:
    """Creates a new task in the plan.yaml file.
     The task ID and details file path will be automatically generated from the title.

    Args:
        title: The human-readable title for the task. Used to generate the ID.
        priority: Priority for the task (0-5, 0 is highest). REQUIRED string.
                  Provide the string "6" to indicate that the priority is not set (will be stored as null).
        depends_on: Comma-separated string of task IDs this task depends on. REQUIRED string.
                    Provide an empty string "" to indicate no dependencies.
        notes: Brief notes for the task. REQUIRED string.
               Provide an empty string "" to indicate no notes.

    Returns:
        A dictionary indicating success and including the created task's ID and title,
        or an error dictionary if creation failed (though errors are typically exceptions).
        Example: {"success": True, "message": "Task 'ID' created.", "task": {"id": "ID", "title": "TITLE"}}
    """
    logging.info(f"Handling create_task: title=\'{title}\', priority_str=\'{priority}\', depends_on_str=\'{depends_on}\', notes_str=\'{notes}\'")

    generated_id = ""
    numeric_priority: Optional[int] = None
    actual_depends_on: Optional[str] = None
    actual_notes: Optional[str] = None

    try:
        # Handle priority string: "6" means None, otherwise convert to int.
        if priority == "6":
            numeric_priority = None
            logging.info("Priority string is \"6\", interpreting as no priority set (None).")
        elif not priority:
            raise ValueError("Priority string cannot be empty. Use \"6\" for no priority.")
        else:
            try:
                numeric_priority = int(priority)
            except ValueError as e:
                raise ValueError(f"Invalid priority string: \'{priority}\'. Must be a whole number (0-5), or \"6\" for no priority.") from e

        # Handle depends_on string: "" means None.
        if depends_on == "":
            actual_depends_on = None
            logging.info("depends_on string is empty, interpreting as no dependencies (None).")
        else:
            actual_depends_on = depends_on

        # Handle notes string: "" means None.
        if notes == "":
            actual_notes = None
            logging.info("notes string is empty, interpreting as no notes (None).")
        else:
            actual_notes = notes

        # Generate ID from title first
        generated_id = _generate_id_from_title(title)
        logging.info(f"Generated ID '{generated_id}' from title '{title}'")

        # Call the utility function to add the task
        created_task_model: Task = add_task(
            task_id=generated_id,
            title=title,
            depends_on_str=actual_depends_on, # Pass processed string or None
            notes=actual_notes,               # Pass processed string or None
            priority=numeric_priority
        )

        msg = f"Successfully created task '{created_task_model.id}' with title '{created_task_model.title}'. Details file: {created_task_model.details}"
        logging.info(msg)
        return {
            "success": True,
            "message": msg,
            "task": created_task_model.model_dump(include={'id', 'title', 'status', 'details', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)
        }

    except ValueError as e: # Catches ID generation errors, duplicate ID, invalid dependencies, or task creation validation errors
        logging.error(f"ValueError during create_task (ID: '{generated_id}' if generated): {e}")
        # Let FastMCP handle it, or consider raising an HTTPException for client
        raise e
    except (FileNotFoundError, yaml.YAMLError, ValidationError, IOError) as e:
        # Catches plan loading/saving/validation errors from plan_utils
        logging.error(f"Error related to plan file during create_task (ID: '{generated_id}' if generated): {e}")
        raise e
    except Exception as e: # Catch-all for other unexpected issues
        logging.exception(f"Unexpected error during create_task (ID: '{generated_id}' if generated): {e}")
        raise e

@mcp.tool()
def delete_task_handler(task_id: str) -> dict:
    """Deletes a task from the plan.yaml file by its ID.
       Also attempts to delete the associated details markdown file (best effort).

    Args:
        task_id: The unique ID of the task to delete.

    Returns:
        A dictionary indicating success or failure.
        Example: {"success": True, "message": "Task 'ID' deleted."}
    """
    logging.info(f"Handling delete_task: id='{task_id}'")
    try:
        # remove_task returns True on success, raises KeyError/other exceptions on failure
        remove_task(task_id)
        msg = f"Successfully deleted task '{task_id}'."
        logging.info(msg)
        return {"success": True, "message": msg}
    except KeyError as e:
        # Task not found
        logging.warning(f"Failed to delete task '{task_id}': {e}")
        raise e # Let FastMCP handle KeyError
    except (FileNotFoundError, yaml.YAMLError, ValidationError, IOError, RuntimeError) as e:
        # Handle errors from loading/saving plan or inconsistency during remove
        logging.exception(f"Failed to delete task '{task_id}': {e}")
        raise e # Let FastMCP handle these
    except Exception as e:
        # Catch-all for other unexpected errors
        logging.exception(f"Unexpected error deleting task '{task_id}': {e}")
        raise e

@mcp.tool()
def archive_done_tasks_handler(
    older_than_days_str: str, # String representation of int, or empty string for no filter
    max_tasks_to_archive_str: str # String representation of int, or empty string for no limit
) -> dict:
    """Archives DONE tasks from plan.yaml to an archive file and moves their detail files.

    Args:
        older_than_days_str: Optional. If provided as a numeric string (e.g., "7"), only archive tasks completed more than this many days ago.
                             Provide an empty string "" to not filter by age.
        max_tasks_to_archive_str: Optional. If provided as a numeric string (e.g., "10"), limit the number of tasks archived in one run.
                                Provide an empty string "" for no limit.

    Returns:
        A dictionary with a summary of the archiving operation, e.g.,
        {"success": True, "message": "Archived X tasks.", "archived_ids": [...], "skipped_ids_due_to_dependencies": [...]}
    """

    older_than_days: Optional[int] = None
    if older_than_days_str:
        try:
            older_than_days = int(older_than_days_str)
            if older_than_days < 0:
                raise ValueError("older_than_days must be a non-negative integer if provided.")
        except ValueError as e:
            logging.error(f"Invalid older_than_days_str: '{older_than_days_str}'. {e}")
            raise ValueError(f"Invalid older_than_days_str: '{older_than_days_str}'. Must be a non-negative integer string or empty. Details: {e}")

    max_tasks_to_archive: Optional[int] = None
    if max_tasks_to_archive_str:
        try:
            max_tasks_to_archive = int(max_tasks_to_archive_str)
            if max_tasks_to_archive < 0:
                 raise ValueError("max_tasks_to_archive must be a non-negative integer if provided.")
        except ValueError as e:
            logging.error(f"Invalid max_tasks_to_archive_str: '{max_tasks_to_archive_str}'. {e}")
            raise ValueError(f"Invalid max_tasks_to_archive_str: '{max_tasks_to_archive_str}'. Must be a non-negative integer string or empty. Details: {e}")

    logging.info(
        f"Handling archive_done_tasks: older_than_days={older_than_days} (from_str='{older_than_days_str}'), "
        f"max_tasks_to_archive={max_tasks_to_archive} (from_str='{max_tasks_to_archive_str}')"
    )

    archived_ids: List[str] = []
    skipped_ids_due_to_dependencies: List[str] = []
    errors_encountered: List[str] = []

    try:
        # 1. Load main plan
        main_plan = load_plan_data()
        # 2. Load or initialize archive plan
        archive_plan = load_archive_plan_data()

        # 3. Ensure archive directories exist
        # ARCHIVE_DIR_PATH is ensured by save_archive_plan_data
        # We need to ensure ARCHIVED_DETAILS_DIR_PATH for moving files
        os.makedirs(ARCHIVED_DETAILS_DIR_PATH, exist_ok=True)
        logging.info(f"Ensured archived details directory exists: {ARCHIVED_DETAILS_DIR_PATH}")

        # Create a lookup for active tasks and their dependencies
        active_task_dependencies: Dict[str, List[str]] = collections.defaultdict(list)
        non_done_tasks_ids = set()
        for task in main_plan.tasks:
            if task.status != 'DONE':
                non_done_tasks_ids.add(task.id)
                if task.depends_on:
                    for dep_id in task.depends_on:
                        active_task_dependencies[dep_id].append(task.id)

        tasks_to_potentially_archive: List[Task] = []

        # 4. Identify DONE tasks in main plan
        for task in main_plan.tasks:
            if task.status == 'DONE':
                # 5. Filter by older_than_days
                if older_than_days is not None:
                    if task.completion_time is None:
                        logging.debug(f"Skipping task {task.id} (DONE) for 'older_than' filter: no completion_time.")
                        continue # Cannot apply filter if no completion time
                    # Ensure completion_time is offset-aware for comparison
                    completion_time_aware = task.completion_time
                    if completion_time_aware.tzinfo is None:
                         completion_time_aware = completion_time_aware.replace(tzinfo=timezone.utc)

                    if (datetime.now(timezone.utc) - completion_time_aware) < timedelta(days=older_than_days):
                        logging.debug(f"Skipping task {task.id} (DONE) for 'older_than' filter: completed too recently.")
                        continue

                # 6. Check for active dependencies on this DONE task
                if task.id in active_task_dependencies:
                    dependant_active_tasks = [tid for tid in active_task_dependencies[task.id] if tid in non_done_tasks_ids]
                    if dependant_active_tasks:
                        logging.info(f"Skipping task {task.id} (DONE) for archival: Active tasks {dependant_active_tasks} depend on it.")
                        skipped_ids_due_to_dependencies.append(task.id)
                        continue

                tasks_to_potentially_archive.append(task)

        # Sort by completion_time (oldest first) to ensure we archive oldest if max_tasks_to_archive is set
        tasks_to_potentially_archive.sort(key=lambda t: (t.completion_time is None, t.completion_time))

        # 7. If max_tasks_to_archive, limit the number
        tasks_to_archive_this_run: List[Task] = []
        if max_tasks_to_archive is not None and max_tasks_to_archive >= 0: # Allow 0 to mean "archive none"
            tasks_to_archive_this_run = tasks_to_potentially_archive[:max_tasks_to_archive]
        else:
            tasks_to_archive_this_run = tasks_to_potentially_archive

        if not tasks_to_archive_this_run:
            logging.info("No tasks eligible for archival in this run.")
            return {
                "success": True,
                "message": "No tasks were eligible for archival.",
                "archived_ids": [],
                "skipped_ids_due_to_dependencies": skipped_ids_due_to_dependencies,
                "errors": errors_encountered
            }

        # 8. For each task to archive:
        current_main_tasks_list = list(main_plan.tasks) # Operate on a copy for removal

        for task_to_archive in tasks_to_archive_this_run:
            try:
                # a. Remove from main plan's task list (from the copy)
                task_found_in_main = False
                for i, t in enumerate(current_main_tasks_list):
                    if t.id == task_to_archive.id:
                        del current_main_tasks_list[i]
                        task_found_in_main = True
                        break
                if not task_found_in_main:
                    logging.warning(f"Task {task_to_archive.id} was selected for archival but not found in main plan list during removal. Skipping.")
                    errors_encountered.append(f"Task {task_to_archive.id} not found in main plan during removal.")
                    continue

                # b. Add to archive plan's task list
                # Check for duplicates in archive first (should be rare but good practice)
                if not find_task_by_id(archive_plan.tasks, task_to_archive.id):
                    archive_plan.tasks.append(task_to_archive)
                else:
                    logging.warning(f"Task {task_to_archive.id} already exists in archive. Skipping add, but will proceed with main plan removal and detail file move.")
                    # Potentially update the existing archived task if needed, or just log. For now, log.
                    errors_encountered.append(f"Task {task_to_archive.id} already in archive. Not re-added.")


                # c. Move detail file
                if task_to_archive.details:
                    # Construct absolute paths: _workspace_root comes from plan_utils
                    source_detail_path_rel = task_to_archive.details # e.g., todo/task_id.md
                    source_detail_path_abs = os.path.join(_workspace_root, source_detail_path_rel)

                    # Destination path construction
                    detail_filename = os.path.basename(source_detail_path_rel)
                    dest_detail_path_abs = os.path.join(ARCHIVED_DETAILS_DIR_PATH, detail_filename)

                    if os.path.exists(source_detail_path_abs):
                        try:
                            shutil.move(source_detail_path_abs, dest_detail_path_abs)
                            logging.info(f"Moved detail file for {task_to_archive.id} from {source_detail_path_abs} to {dest_detail_path_abs}")
                            # Update task's details path to reflect new location in the archived copy
                            task_to_archive.details = os.path.relpath(dest_detail_path_abs, _workspace_root).replace(os.sep, '/')

                        except Exception as e_move:
                            logging.error(f"Error moving detail file {source_detail_path_abs} for task {task_to_archive.id}: {e_move}")
                            errors_encountered.append(f"Error moving details for {task_to_archive.id}: {e_move}")
                            # Decide if this is a critical failure. For now, continue archiving the task entry.
                    else:
                        logging.warning(f"Source detail file {source_detail_path_abs} for task {task_to_archive.id} not found. Skipping move.")

                archived_ids.append(task_to_archive.id)

            except Exception as e_task_loop:
                logging.exception(f"Error processing task {task_to_archive.id} for archival: {e_task_loop}")
                errors_encountered.append(f"Error archiving task {task_to_archive.id}: {e_task_loop}")
                # Remove from archived_ids if it was added prematurely
                if task_to_archive.id in archived_ids:
                    archived_ids.remove(task_to_archive.id)
                # Continue to next task if possible

        # Update the main plan's tasks with the modified list
        main_plan.tasks = current_main_tasks_list

        # 9. Save both plan.yaml and plan_archive.yaml
        if archived_ids: # Only save if something actually changed
            save_plan_data(main_plan)
            save_archive_plan_data(archive_plan)
            logging.info(f"Successfully saved main and archive plans after archiving {len(archived_ids)} tasks.")
        else:
            logging.info("No tasks were actually moved to archive, skipping save operations.")

        # 10. Return summary
        msg = f"Archived {len(archived_ids)} task(s)."
        if skipped_ids_due_to_dependencies:
            msg += f" Skipped {len(skipped_ids_due_to_dependencies)} task(s) due to active dependencies."
        if errors_encountered:
            msg += f" Encountered {len(errors_encountered)} error(s) during archival."

        final_success_status = not bool(errors_encountered) # Success if no errors

        return {
            "success": final_success_status,
            "message": msg,
            "archived_ids": archived_ids,
            "skipped_ids_due_to_dependencies": skipped_ids_due_to_dependencies,
            "errors": errors_encountered
        }

    except Exception as e:
        logging.exception(f"Critical error during archive_done_tasks_handler: {e}")
        # Ensure a consistent error structure is returned
        return {
            "success": False,
            "message": f"Critical error in archival process: {str(e)}",
            "archived_ids": archived_ids, # May contain partially processed tasks
            "skipped_ids_due_to_dependencies": skipped_ids_due_to_dependencies,
            "errors": errors_encountered + [f"Critical: {str(e)}"]
        }

@mcp.tool()
def delete_archived_task_handler(task_id: str) -> dict:
    """Deletes a task from the archive plan (plan_archive.yaml) by its ID.
       Also attempts to delete the associated archived detail file.

    Args:
        task_id: The unique ID of the task to delete from the archive.

    Returns:
        A dictionary indicating success or failure.
        Example: {"success": True, "message": "Archived task 'ID' deleted."}
    """
    logging.info(f"Handling delete_archived_task: id='{task_id}'")
    try:
        # remove_archived_task returns True on success or raises exceptions on failure
        remove_archived_task(task_id)
        msg = f"Successfully deleted archived task '{task_id}'."
        logging.info(msg)
        return {"success": True, "message": msg}
    except KeyError as e:
        # Task not found in archive
        logging.warning(f"Failed to delete archived task '{task_id}': {e}")
        raise e # Let FastMCP handle KeyError, it will translate to an error for the client
    except (FileNotFoundError, yaml.YAMLError, ValidationError, IOError, RuntimeError) as e:
        # Handle errors from loading/saving archive plan or inconsistency during remove
        logging.exception(f"Failed to delete archived task '{task_id}': {e}")
        raise e # Let FastMCP handle these
    except Exception as e:
        # Catch-all for other unexpected errors
        logging.exception(f"Unexpected error deleting archived task '{task_id}': {e}")
        raise e

# --- ASGI Application Setup ---
# Create the Starlette app and mount the MCP SSE handler at the root
app = Starlette(
    debug=True,
    routes=[
        # Mount the app provided by FastMCP at the root
        # It will internally handle routes like /mcp/sse and /mcp/messages/
        Mount('/', app=mcp.sse_app()),
    ]
)
