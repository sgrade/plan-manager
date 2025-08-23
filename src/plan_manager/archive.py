"""Archive-related MCP tools (registration done via register_archive_tools)."""

from typing import Optional, List, Dict
import os
import shutil
import logging
import yaml
from pydantic import ValidationError
from datetime import datetime, timedelta, timezone
from plan_manager.plan_utils import load_plan_data, load_archive_plan_data, save_plan_data, save_archive_plan_data, find_story_by_id, remove_archived_story
from plan_manager.story_model import story
from plan_manager.config import ARCHIVED_DETAILS_DIR_PATH, _workspace_root
import collections

def register_archive_tools(mcp_instance) -> None:
    """Register archive tools with the given FastMCP instance."""
    mcp_instance.tool()(archive_done_stories)
    mcp_instance.tool()(delete_archived_story)

def archive_done_stories(
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
        logging.exception(f"Critical error during archive_done_stories: {e}")
        # Ensure a consistent error structure is returned
        return {
            "success": False,
            "message": f"Critical error in archival process: {str(e)}",
            "archived_ids": archived_ids, # May contain partially processed stories
            "skipped_ids_due_to_dependencies": skipped_ids_due_to_dependencies,
            "errors": errors_encountered + [f"Critical: {str(e)}"]
        }

def delete_archived_story(story_id: str) -> dict:
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
