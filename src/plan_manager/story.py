import logging
import os
import yaml
import re

from typing import List, Optional
from pydantic import ValidationError
from datetime import datetime, timezone

from plan_manager.story_model import Story, ALLOWED_STATUSES
from plan_manager.plan import Plan, load_plan_data, save_plan_data, add_story_to_plan, remove_story_from_plan
from plan_manager.stories import load_stories
from plan_manager.stories_utils import find_story_by_id
from plan_manager.config import _workspace_root


logger = logging.getLogger(__name__)


def register_story_tools(mcp_instance) -> None:
    """Register story tools with the given FastMCP instance."""
    mcp_instance.tool()(create_story)
    mcp_instance.tool()(get_story)
    mcp_instance.tool()(update_story)
    mcp_instance.tool()(delete_story)


def create_story(
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
        created_story_model: Story = add_story_to_plan(
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


def get_story(story_id: str) -> dict:
    """Returns full details for a specific story by its ID."""
    logging.info(f"Handling get_story: story_id={story_id}")
    try:
        stories: List[Story] = load_stories()
        story: Optional[Story] = find_story_by_id(stories, story_id)
        if not story:
            raise KeyError(f"story with ID '{story_id}' not found.")
        return story.model_dump(mode='json', exclude_none=True)
    except Exception as e:
        logging.exception("Unexpected error during get_story")
        raise e


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
        stories: List[Story] = plan.stories

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
        # remove_story_from_plan returns True on success, raises KeyError/other exceptions on failure
        remove_story_from_plan(story_id)
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
