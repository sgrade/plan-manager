"""MCP Server (SSE Transport) for interacting with the project plan.

This module implements an MCP (Model Context Protocol) server that provides
AI assistants with tools to manage stories in a YAML-based project plan.
The server supports story creation, modification, listing, and dependency management.
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
    load_stories,
    save_plan_data,
    find_story_by_id,
    # find_story_index_by_id, # Less used now
    filter_stories,
    ALLOWED_STATUSES,
    PLAN_FILE_PATH,
    ARCHIVE_DIR_PATH,
    ARCHIVED_DETAILS_DIR_PATH,
    load_archive_plan_data,
    save_archive_plan_data,
    _workspace_root,
    remove_archived_story,
    Plan, story, add_story, remove_story
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
    instructions="Manages stories defined in the project's todo/plan.yaml file.",
    sse_path="/sse",
    message_path="/messages/"
)

# --- ID Generation Helper ---

def _generate_id_from_title(title: str) -> str:
    """Generate a suitable story ID from a title.

    Converts a human-readable title into a standardized story ID by:
    1. Converting to lowercase
    2. Keeping only letters, numbers, and spaces
    3. Replacing whitespace sequences with underscores
    4. Converting to uppercase

    Args:
        title: The human-readable story title

    Returns:
        A standardized uppercase story ID

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
def list_stories_handler(statuses: str, unblocked: bool = False) -> list[dict]:
    """Lists stories from plan.yaml, with optional filters, sorted by dependency, priority, and creation time.

    Args:
        statuses: Comma-separated string of statuses to filter by (e.g., "TODO,IN_PROGRESS"). Case-insensitive. REQUIRED.
        unblocked: If true, show only TODO stories whose dependencies are all DONE.

    Returns:
        A list of stories (dictionaries with id, status, title, priority, creation_time) matching the filters, in a topologically sorted order.
    """
    logging.info(f"Handling list_stories: statuses_str='{statuses}', unblocked={unblocked}")

    try:
        all_stories: List[story] = load_stories()
        if not all_stories:
            return []

        # --- Topological Sort ---
        adj: Dict[str, List[str]] = collections.defaultdict(list)
        in_degree: Dict[str, int] = collections.defaultdict(int)
        story_map: Dict[str, story] = {story.id: story for story in all_stories}

        for story in all_stories:
            # Ensure all stories are in in_degree, even if they have no dependencies listed
            _ = in_degree[story.id] # Access to ensure key exists with default 0
            if story.depends_on:
                for dep_id in story.depends_on:
                    adj[dep_id].append(story.id)
                    in_degree[story.id] += 1

        queue = collections.deque()
        for story_id in story_map:
            if in_degree[story_id] == 0:
                queue.append(story_map[story_id])

        sorted_stories_list: List[story] = []

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

            current_story = queue.popleft()
            sorted_stories_list.append(current_story)

            for neighbor_id in adj[current_story.id]:
                in_degree[neighbor_id] -= 1
                if in_degree[neighbor_id] == 0:
                    queue.append(story_map[neighbor_id])

        if len(sorted_stories_list) != len(all_stories):
            # Cycle detected or other inconsistency
            # Log detailed information for debugging
            missing_ids = set(story_map.keys()) - set(t.id for t in sorted_stories_list)
            logging.error(
                f"Cycle detected in story dependencies or graph inconsistency. "
                f"Total stories: {len(all_stories)}, Sorted stories: {len(sorted_stories_list)}. "
                f"stories not sorted (potential cycle members or disconnected): {missing_ids}"
            )
            # Consider how to represent this to the user. For now, returning what was sorted.
            # Or raise an error: raise ValueError("Cycle detected in story dependencies.")
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
        final_filtered_stories: List[story] = []
        all_stories_map_for_filter: Dict[str, story] = {story.id: story for story in sorted_stories_list}

        for story in sorted_stories_list: # Iterate over the already sorted list
            status_match = True
            if actual_statuses_list:
                status_match = story.status in actual_statuses_list

            if not status_match:
                continue

            unblocked_match = True
            if unblocked:
                if story.status != 'TODO':
                    unblocked_match = False
                else:
                    if story.depends_on:
                        for dep_id in story.depends_on:
                            dep_story = story_map.get(dep_id) # Check original map for dependency status
                            if not dep_story or dep_story.status != 'DONE':
                                unblocked_match = False
                                break

            if unblocked_match:
                final_filtered_stories.append(story)

        # Add index to title for display
        indexed_stories_for_display = []
        for i, story_model in enumerate(final_filtered_stories):
            # Create a new dict to avoid modifying the original story model if it's used elsewhere by reference,
            # though in this flow, they are about to be dumped.
            # However, model_dump will be called on story_model, so better to modify a copy if we were to return models.
            # Since we are returning dicts anyway, we can build them here.

            story_dict = story_model.model_dump(
                include={'id', 'status', 'priority', 'creation_time', 'completion_time'},
                exclude_none=True
            )
            story_dict['title'] = f"{i + 1:02d}. {story_model.title}" # Use original title from story_model
            indexed_stories_for_display.append(story_dict)

        result = indexed_stories_for_display # Use the list with modified titles

        logging.info(f"list_stories returning {len(result)} stories after sorting, filtering, and title indexing.")
        return result

    except (FileNotFoundError, yaml.YAMLError, ValidationError) as e:
        logging.exception("Failed to load/validate plan data for list_stories")
        # Re-raise as a generic exception or map to a specific user-facing error?
        # For now, let FastMCP handle it (or raise HTTP exception if needed)
        raise e # Let FastMCP try to handle it
    except Exception as e:
        logging.exception("Unexpected error during list_stories")
        raise e

@mcp.tool()
def get_story(story_id: str) -> dict:
    """Returns full details for a specific story by its ID."""
    logging.info(f"Handling get_story: story_id={story_id}")
    try:
        stories: List[story] = load_stories()
        story: Optional[story] = find_story_by_id(stories, story_id)
        if not story:
            raise KeyError(f"story with ID '{story_id}' not found.")
        return story.model_dump(mode='json', exclude_none=True)
    except Exception as e:
        logging.exception("Unexpected error during get_story")
        raise e


@mcp.tool()
def update_story(
    story_id: str,
    title: Optional[str] = None,
    notes: Optional[str] = None,
    depends_on: Optional[str] = None, # CSV of story IDs; None means no change
    priority: Optional[str] = None,   # "0"-"5" or "6" to unset; None means no change
    status: Optional[str] = None      # TODO/IN_PROGRESS/DONE/BLOCKED/DEFERRED; None means no change
) -> dict:
    """Partially updates a story. Only non-None fields are applied.

    Rules:
    - `priority`: string semantics as elsewhere ("6" unsets)
    - `depends_on`: CSV of story IDs; validates existence and prevents self-dependency
    - `status`: applies completion_time rules like update_story_status_handler
    - story ID cannot be changed.
    Returns updated story dict.
    """
    logging.info(
        f"Handling update_story (partial): id={story_id}, title={title is not None}, notes={notes is not None}, "
        f"depends_on={depends_on is not None}, priority={priority is not None}, status={status is not None}"
    )

    try:
        plan: Plan = load_plan_data()
        stories: List[story] = plan.stories

        # Find story and index
        target_index: Optional[int] = None
        for i, t in enumerate(stories):
            if t.id == story_id:
                target_index = i
                break
        if target_index is None:
            raise KeyError(f"story with ID '{story_id}' not found.")

        story_obj = stories[target_index]

        # Apply title
        if title is not None:
            story_obj.title = title

        # Apply notes
        if notes is not None:
            story_obj.notes = notes if notes != "" else None

        # Apply depends_on
        if depends_on is not None:
            dep_list: List[str] = [d.strip() for d in depends_on.split(',') if d.strip()]
            # Validate existence and self-dependency
            existing_ids = {t.id for t in stories}
            for dep in dep_list:
                if dep not in existing_ids:
                    raise ValueError(f"Dependency story with ID '{dep}' not found.")
                if dep == story_id:
                    raise ValueError(f"story '{story_id}' cannot depend on itself.")
            story_obj.depends_on = dep_list

        # Apply priority (empty string means no change)
        if priority is not None:
            if priority.strip() == "":
                pass
            elif priority == "6":
                story_obj.priority = None
            else:
                try:
                    numeric_priority = int(priority)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid priority string: '{priority}'. Must be a whole number (0-5), or '6' to remove priority."
                    ) from e
                story_obj.priority = numeric_priority

        # Apply status (empty string means no change)
        if status is not None:
            if status.strip() == "":
                pass
            else:
                new_status_upper = status.upper()
                if new_status_upper not in ALLOWED_STATUSES:
                    raise ValueError(
                        f"Invalid status '{status}'. Allowed: {', '.join(sorted(list(ALLOWED_STATUSES)))}"
                    )
                old_status = story_obj.status
                story_obj.status = new_status_upper
                if new_status_upper == 'DONE' and old_status != 'DONE':
                    story_obj.completion_time = datetime.now(timezone.utc)
                elif new_status_upper != 'DONE' and old_status == 'DONE':
                    story_obj.completion_time = None

        # Persist
        plan.stories[target_index] = story_obj
        save_plan_data(plan)

        return story_obj.model_dump(mode='json', exclude_none=True)

    except Exception as e:
        logging.exception(f"Unexpected error during update_story (partial) for '{story_id}': {e}")
        raise e

@mcp.tool()
def create_story(
    # story_id: str, # Removed story_id parameter
    title: str,
    priority: str,                 # Priority is now a REQUIRED string. Sentinel value "6" means not set.
    depends_on: str,               # Depends_on is now a REQUIRED string. Sentinel value "" means not set.
    notes: str,                    # Notes is now a REQUIRED string. Sentinel value "" means not set.
    details_content: str = ""      # Optional: initial markdown content for the details file
) -> dict:
    """Creates a new story in the plan.yaml file.
     The story ID and details file path will be automatically generated from the title.

    Args:
        title: The human-readable title for the story. Used to generate the ID.
        priority: Priority for the story (0-5, 0 is highest). REQUIRED string.
                  Provide the string "6" to indicate that the priority is not set (will be stored as null).
        depends_on: Comma-separated string of story IDs this story depends on. REQUIRED string.
                    Provide an empty string "" to indicate no dependencies.
        notes: Brief notes for the story. REQUIRED string.
               Provide an empty string "" to indicate no notes.

    Returns:
        A dictionary indicating success and including the created story's ID and title,
        or an error dictionary if creation failed (though errors are typically exceptions).
        Example: {"success": True, "message": "story 'ID' created.", "story": {"id": "ID", "title": "TITLE"}}
    """
    logging.info(f"Handling create_story: title=\'{title}\', priority_str=\'{priority}\', depends_on_str=\'{depends_on}\', notes_str=\'{notes}\'")

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

        # Call the utility function to add the story
        created_story_model: story = add_story(
            story_id=generated_id,
            title=title,
            depends_on_str=actual_depends_on, # Pass processed string or None
            notes=actual_notes,               # Pass processed string or None
            priority=numeric_priority
        )

        # If initial details content provided, write it now so remote clients don't need direct FS access
        try:
            if details_content is not None and created_story_model.details:
                abs_details_path = os.path.join(_workspace_root, created_story_model.details)
                os.makedirs(os.path.dirname(abs_details_path), exist_ok=True)
                with open(abs_details_path, 'w', encoding='utf-8') as f:
                    _ = f.write(details_content)
        except Exception as e_write:
            logging.warning(f"Failed to write initial details content for story '{created_story_model.id}': {e_write}")

        msg = f"Successfully created story '{created_story_model.id}' with title '{created_story_model.title}'. Details file: {created_story_model.details}"
        logging.info(msg)
        return {
            "success": True,
            "message": msg,
            "story": created_story_model.model_dump(include={'id', 'title', 'status', 'details', 'priority', 'creation_time', 'notes', 'depends_on'}, exclude_none=True)
        }

    except ValueError as e: # Catches ID generation errors, duplicate ID, invalid dependencies, or story creation validation errors
        logging.error(f"ValueError during create_story (ID: '{generated_id}' if generated): {e}")
        # Let FastMCP handle it, or consider raising an HTTPException for client
        raise e
    except (FileNotFoundError, yaml.YAMLError, ValidationError, IOError) as e:
        # Catches plan loading/saving/validation errors from plan_utils
        logging.error(f"Error related to plan file during create_story (ID: '{generated_id}' if generated): {e}")
        raise e
    except Exception as e: # Catch-all for other unexpected issues
        logging.exception(f"Unexpected error during create_story (ID: '{generated_id}' if generated): {e}")
        raise e

### Removed unapproved handlers: get_story_details_handler, set_story_details_handler

@mcp.tool()
def delete_story(story_id: str) -> dict:
    """Deletes a story from the plan.yaml file by its ID.
       Also attempts to delete the associated details markdown file (best effort).

    Args:
        story_id: The unique ID of the story to delete.

    Returns:
        A dictionary indicating success or failure.
        Example: {"success": True, "message": "story 'ID' deleted."}
    """
    logging.info(f"Handling delete_story: id='{story_id}'")
    try:
        # remove_story returns True on success, raises KeyError/other exceptions on failure
        remove_story(story_id)
        msg = f"Successfully deleted story '{story_id}'."
        logging.info(msg)
        return {"success": True, "message": msg}
    except KeyError as e:
        # story not found
        logging.warning(f"Failed to delete story '{story_id}': {e}")
        raise e # Let FastMCP handle KeyError
    except (FileNotFoundError, yaml.YAMLError, ValidationError, IOError, RuntimeError) as e:
        # Handle errors from loading/saving plan or inconsistency during remove
        logging.exception(f"Failed to delete story '{story_id}': {e}")
        raise e # Let FastMCP handle these
    except Exception as e:
        # Catch-all for other unexpected errors
        logging.exception(f"Unexpected error deleting story '{story_id}': {e}")
        raise e

@mcp.tool()
def archive_done_stories_handler(
    older_than_days_str: str, # String representation of int, or empty string for no filter
    max_stories_to_archive_str: str # String representation of int, or empty string for no limit
) -> dict:
    """Archives DONE stories from plan.yaml to an archive file and moves their detail files.

    Args:
        older_than_days_str: Optional. If provided as a numeric string (e.g., "7"), only archive stories completed more than this many days ago.
                             Provide an empty string "" to not filter by age.
        max_stories_to_archive_str: Optional. If provided as a numeric string (e.g., "10"), limit the number of stories archived in one run.
                                Provide an empty string "" for no limit.

    Returns:
        A dictionary with a summary of the archiving operation, e.g.,
        {"success": True, "message": "Archived X stories.", "archived_ids": [...], "skipped_ids_due_to_dependencies": [...]}
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

    max_stories_to_archive: Optional[int] = None
    if max_stories_to_archive_str:
        try:
            max_stories_to_archive = int(max_stories_to_archive_str)
            if max_stories_to_archive < 0:
                 raise ValueError("max_stories_to_archive must be a non-negative integer if provided.")
        except ValueError as e:
            logging.error(f"Invalid max_stories_to_archive_str: '{max_stories_to_archive_str}'. {e}")
            raise ValueError(f"Invalid max_stories_to_archive_str: '{max_stories_to_archive_str}'. Must be a non-negative integer string or empty. Details: {e}")

    logging.info(
        f"Handling archive_done_stories: older_than_days={older_than_days} (from_str='{older_than_days_str}'), "
        f"max_stories_to_archive={max_stories_to_archive} (from_str='{max_stories_to_archive_str}')"
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

        # Create a lookup for active stories and their dependencies
        active_story_dependencies: Dict[str, List[str]] = collections.defaultdict(list)
        non_done_stories_ids = set()
        for story in main_plan.stories:
            if story.status != 'DONE':
                non_done_stories_ids.add(story.id)
                if story.depends_on:
                    for dep_id in story.depends_on:
                        active_story_dependencies[dep_id].append(story.id)

        stories_to_potentially_archive: List[story] = []

        # 4. Identify DONE stories in main plan
        for story in main_plan.stories:
            if story.status == 'DONE':
                # 5. Filter by older_than_days
                if older_than_days is not None:
                    if story.completion_time is None:
                        logging.debug(f"Skipping story {story.id} (DONE) for 'older_than' filter: no completion_time.")
                        continue # Cannot apply filter if no completion time
                    # Ensure completion_time is offset-aware for comparison
                    completion_time_aware = story.completion_time
                    if completion_time_aware.tzinfo is None:
                         completion_time_aware = completion_time_aware.replace(tzinfo=timezone.utc)

                    if (datetime.now(timezone.utc) - completion_time_aware) < timedelta(days=older_than_days):
                        logging.debug(f"Skipping story {story.id} (DONE) for 'older_than' filter: completed too recently.")
                        continue

                # 6. Check for active dependencies on this DONE story
                if story.id in active_story_dependencies:
                    dependant_active_stories = [tid for tid in active_story_dependencies[story.id] if tid in non_done_stories_ids]
                    if dependant_active_stories:
                        logging.info(f"Skipping story {story.id} (DONE) for archival: Active stories {dependant_active_stories} depend on it.")
                        skipped_ids_due_to_dependencies.append(story.id)
                        continue

                stories_to_potentially_archive.append(story)

        # Sort by completion_time (oldest first) to ensure we archive oldest if max_stories_to_archive is set
        stories_to_potentially_archive.sort(key=lambda t: (t.completion_time is None, t.completion_time))

        # 7. If max_stories_to_archive, limit the number
        stories_to_archive_this_run: List[story] = []
        if max_stories_to_archive is not None and max_stories_to_archive >= 0: # Allow 0 to mean "archive none"
            stories_to_archive_this_run = stories_to_potentially_archive[:max_stories_to_archive]
        else:
            stories_to_archive_this_run = stories_to_potentially_archive

        if not stories_to_archive_this_run:
            logging.info("No stories eligible for archival in this run.")
            return {
                "success": True,
                "message": "No stories were eligible for archival.",
                "archived_ids": [],
                "skipped_ids_due_to_dependencies": skipped_ids_due_to_dependencies,
                "errors": errors_encountered
            }

        # 8. For each story to archive:
        current_main_stories_list = list(main_plan.stories) # Operate on a copy for removal

        for story_to_archive in stories_to_archive_this_run:
            try:
                # a. Remove from main plan's story list (from the copy)
                story_found_in_main = False
                for i, t in enumerate(current_main_stories_list):
                    if t.id == story_to_archive.id:
                        del current_main_stories_list[i]
                        story_found_in_main = True
                        break
                if not story_found_in_main:
                    logging.warning(f"story {story_to_archive.id} was selected for archival but not found in main plan list during removal. Skipping.")
                    errors_encountered.append(f"story {story_to_archive.id} not found in main plan during removal.")
                    continue

                # b. Add to archive plan's story list
                # Check for duplicates in archive first (should be rare but good practice)
                if not find_story_by_id(archive_plan.stories, story_to_archive.id):
                    archive_plan.stories.append(story_to_archive)
                else:
                    logging.warning(f"story {story_to_archive.id} already exists in archive. Skipping add, but will proceed with main plan removal and detail file move.")
                    # Potentially update the existing archived story if needed, or just log. For now, log.
                    errors_encountered.append(f"story {story_to_archive.id} already in archive. Not re-added.")


                # c. Move detail file
                if story_to_archive.details:
                    # Construct absolute paths: _workspace_root comes from plan_utils
                    source_detail_path_rel = story_to_archive.details # e.g., todo/story_id.md
                    source_detail_path_abs = os.path.join(_workspace_root, source_detail_path_rel)

                    # Destination path construction
                    detail_filename = os.path.basename(source_detail_path_rel)
                    dest_detail_path_abs = os.path.join(ARCHIVED_DETAILS_DIR_PATH, detail_filename)

                    if os.path.exists(source_detail_path_abs):
                        try:
                            shutil.move(source_detail_path_abs, dest_detail_path_abs)
                            logging.info(f"Moved detail file for {story_to_archive.id} from {source_detail_path_abs} to {dest_detail_path_abs}")
                            # Update story's details path to reflect new location in the archived copy
                            story_to_archive.details = os.path.relpath(dest_detail_path_abs, _workspace_root).replace(os.sep, '/')

                        except Exception as e_move:
                            logging.error(f"Error moving detail file {source_detail_path_abs} for story {story_to_archive.id}: {e_move}")
                            errors_encountered.append(f"Error moving details for {story_to_archive.id}: {e_move}")
                            # Decide if this is a critical failure. For now, continue archiving the story entry.
                    else:
                        logging.warning(f"Source detail file {source_detail_path_abs} for story {story_to_archive.id} not found. Skipping move.")

                archived_ids.append(story_to_archive.id)

            except Exception as e_story_loop:
                logging.exception(f"Error processing story {story_to_archive.id} for archival: {e_story_loop}")
                errors_encountered.append(f"Error archiving story {story_to_archive.id}: {e_story_loop}")
                # Remove from archived_ids if it was added prematurely
                if story_to_archive.id in archived_ids:
                    archived_ids.remove(story_to_archive.id)
                # Continue to next story if possible

        # Update the main plan's stories with the modified list
        main_plan.stories = current_main_stories_list

        # 9. Save both plan.yaml and plan_archive.yaml
        if archived_ids: # Only save if something actually changed
            save_plan_data(main_plan)
            save_archive_plan_data(archive_plan)
            logging.info(f"Successfully saved main and archive plans after archiving {len(archived_ids)} stories.")
        else:
            logging.info("No stories were actually moved to archive, skipping save operations.")

        # 10. Return summary
        msg = f"Archived {len(archived_ids)} story(s)."
        if skipped_ids_due_to_dependencies:
            msg += f" Skipped {len(skipped_ids_due_to_dependencies)} story(s) due to active dependencies."
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
        logging.exception(f"Critical error during archive_done_stories_handler: {e}")
        # Ensure a consistent error structure is returned
        return {
            "success": False,
            "message": f"Critical error in archival process: {str(e)}",
            "archived_ids": archived_ids, # May contain partially processed stories
            "skipped_ids_due_to_dependencies": skipped_ids_due_to_dependencies,
            "errors": errors_encountered + [f"Critical: {str(e)}"]
        }

@mcp.tool()
def delete_archived_story_handler(story_id: str) -> dict:
    """Deletes a story from the archive plan (plan_archive.yaml) by its ID.
       Also attempts to delete the associated archived detail file.

    Args:
        story_id: The unique ID of the story to delete from the archive.

    Returns:
        A dictionary indicating success or failure.
        Example: {"success": True, "message": "Archived story 'ID' deleted."}
    """
    logging.info(f"Handling delete_archived_story: id='{story_id}'")
    try:
        # remove_archived_story returns True on success or raises exceptions on failure
        remove_archived_story(story_id)
        msg = f"Successfully deleted archived story '{story_id}'."
        logging.info(msg)
        return {"success": True, "message": msg}
    except KeyError as e:
        # story not found in archive
        logging.warning(f"Failed to delete archived story '{story_id}': {e}")
        raise e # Let FastMCP handle KeyError, it will translate to an error for the client
    except (FileNotFoundError, yaml.YAMLError, ValidationError, IOError, RuntimeError) as e:
        # Handle errors from loading/saving archive plan or inconsistency during remove
        logging.exception(f"Failed to delete archived story '{story_id}': {e}")
        raise e # Let FastMCP handle these
    except Exception as e:
        # Catch-all for other unexpected errors
        logging.exception(f"Unexpected error deleting archived story '{story_id}': {e}")
        raise e

# --- ASGI Application Setup ---
# SSE transport only
app = Starlette(
    debug=True,
    routes=[
        Mount('/', app=mcp.sse_app()),
    ]
)
