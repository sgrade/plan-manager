"""Utilities for interacting with the project plan (todo/plan.yaml)."""

import yaml
import os
import logging
from typing import List, Optional, Dict, Set
from pydantic import BaseModel, Field, ValidationError, model_validator, ValidationInfo
from datetime import datetime, timezone
from plan_manager.story_model import story
from plan_manager.config import PLAN_FILE_PATH, ARCHIVE_PLAN_FILE_PATH, ARCHIVE_DIR_PATH, ARCHIVED_DETAILS_DIR_PATH, _workspace_root

# --- Pydantic Models ---

class Plan(BaseModel):
    stories: List[story] = Field(default_factory=list)
    # Placeholder for potential future top-level fields
    # metadata: Optional[Dict[str, Any]] = None 

    @model_validator(mode='after')
    def check_dependencies_exist_and_no_cycles(self, info: ValidationInfo) -> 'Plan':
        # If context indicates, skip this validation (useful for archive plan)
        if info.context and info.context.get("skip_dependency_check"):
            logging.debug("Skipping dependency check for Plan validation based on context.")
            return self

        story_ids = {story.id for story in self.stories}
        for story in self.stories:
            if story.depends_on:
                for dep_id in story.depends_on:
                    if dep_id not in story_ids:
                        raise ValueError(f"story '{story.id}' has unmet dependency: '{dep_id}'")
                # Basic cycle check (story depending on itself)
                if story.id in story.depends_on:
                    raise ValueError(f"story '{story.id}' cannot depend on itself.")
            # TODO: Implement a more robust graph-based cycle detection if needed
        return self

# --- Core Functions ---

def _ensure_plan_initialized(file_path: str = PLAN_FILE_PATH) -> None:
    """Ensure that the plan file and its parent directory exist.

    Creates the `todo/` directory and an empty plan file if missing.
    """
    plan_dir = os.path.dirname(file_path)
    try:
        os.makedirs(plan_dir, exist_ok=True)
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump({"stories": []}, f, default_flow_style=False, sort_keys=False)
            logging.info(f"Initialized new plan file at {file_path}")
    except Exception as e:
        logging.exception(f"Failed to initialize plan at {file_path}: {e}")
        raise

def load_plan_data(file_path: str = PLAN_FILE_PATH) -> Plan:
    """Loads and validates the plan structure from the YAML file using Pydantic.
    
    Raises:
        FileNotFoundError: If the plan file is not found.
        yaml.YAMLError: If the file is not valid YAML.
        ValidationError: If the data does not conform to the Plan schema.
        Exception: For other unexpected loading errors.
    """
    try:
        # Ensure plan exists before loading
        _ensure_plan_initialized(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            if raw_data is None: # Handle empty file case
                raw_data = {} # Default to empty dict to allow Plan(stories=[])

        # Validate the raw data against the Pydantic model
        plan = Plan.model_validate(raw_data) 
        return plan
    except FileNotFoundError as e:
        logging.exception(f"Plan file not found at {file_path}")
        raise e # Re-raise specific exception
    except yaml.YAMLError as e:
        logging.exception(f"Error parsing YAML file {file_path}: {e}")
        raise e # Re-raise specific exception
    except ValidationError as e:
        logging.exception(f"Plan file {file_path} failed schema validation: {e}")
        raise e # Re-raise specific exception
    except Exception as e:
        # Catch-all for other unexpected errors during loading/validation
        logging.exception(f"An unexpected error occurred while loading/validating {file_path}: {e}")
        raise e 

def load_archive_plan_data(file_path: str = ARCHIVE_PLAN_FILE_PATH) -> Plan:
    """Loads and validates the archive plan structure from the YAML file using Pydantic.
    If the archive file does not exist, returns an empty Plan.
    Dependency checks are skipped for the archive plan.
    
    Raises:
        yaml.YAMLError: If the file is not valid YAML.
        ValidationError: If the data does not conform to the Plan schema (excluding inter-story dependencies within archive).
        Exception: For other unexpected loading errors.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            if raw_data is None: # Handle empty file case
                raw_data = {} 
        # Pass context to skip dependency validation for archive plan
        plan = Plan.model_validate(raw_data, context={"skip_dependency_check": True})
        return plan
    except FileNotFoundError:
        logging.info(f"Archive plan file not found at {file_path}. Returning empty plan.")
        return Plan(stories=[]) # Return an empty plan if file not found
    except yaml.YAMLError as e:
        logging.exception(f"Error parsing YAML file {file_path}: {e}")
        raise e
    except ValidationError as e:
        logging.exception(f"Archive plan file {file_path} failed schema validation: {e}")
        raise e
    except Exception as e:
        logging.exception(f"An unexpected error occurred while loading/validating archive {file_path}: {e}")
        raise e

def load_stories(file_path: str = PLAN_FILE_PATH) -> List[story]:
    """Loads and validates the plan, returning just the list of story objects.
    
    Raises: (Propagated from load_plan_data)
        FileNotFoundError, yaml.YAMLError, ValidationError, Exception
    """
    plan = load_plan_data(file_path)
    return plan.stories

def save_plan_data(plan: Plan) -> None:
    """Saves the provided Plan object back to the plan YAML file.

    Args:
        plan: The Pydantic Plan object.

    Raises:
        IOError: If there is an error writing to the file or encoding YAML.
        FileNotFoundError: If the plan file path cannot be determined (should not happen with constant).
    """
    plan_path = PLAN_FILE_PATH # Use the constant directly
    
    try:
        # Dump the Pydantic model to a dictionary suitable for YAML
        # exclude_none=True can make the YAML cleaner by omitting optional fields that are None
        data_to_dump = plan.model_dump(mode='json', exclude_none=True)
        
        # Ensure parent directory exists before writing
        os.makedirs(os.path.dirname(plan_path), exist_ok=True)
        with open(plan_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data_to_dump, f, default_flow_style=False, sort_keys=False)

    except yaml.YAMLError as e:
        logging.exception(f"Error encoding plan data to YAML: {e}")
        raise IOError(f"Error encoding plan data to YAML: {e}") from e
    except OSError as e:
        logging.exception(f"Error writing plan file {plan_path}: {e}")
        raise IOError(f"Error writing plan file {plan_path}: {e}") from e
    except Exception as e: # Catch potential errors during model_dump
        logging.exception(f"Error preparing plan data for saving: {e}")
        raise IOError(f"Error preparing plan data for saving: {e}") from e

def save_archive_plan_data(plan: Plan) -> None:
    """Saves the provided Plan object back to the archive plan YAML file.
       Ensures the archive directory exists.

    Args:
        plan: The Pydantic Plan object.

    Raises:
        IOError: If there is an error writing to the file or encoding YAML.
    """
    archive_file_path = ARCHIVE_PLAN_FILE_PATH
    archive_dir_path = ARCHIVE_DIR_PATH
    
    try:
        # Ensure the archive directory exists
        os.makedirs(archive_dir_path, exist_ok=True)
        logging.info(f"Ensured archive directory exists: {archive_dir_path}")

        data_to_dump = plan.model_dump(mode='json', exclude_none=True)
        
        with open(archive_file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data_to_dump, f, default_flow_style=False, sort_keys=False)
        logging.info(f"Successfully saved archive plan data to {archive_file_path}")

    except yaml.YAMLError as e:
        logging.exception(f"Error encoding archive plan data to YAML: {e}")
        raise IOError(f"Error encoding archive plan data to YAML: {e}") from e
    except OSError as e:
        logging.exception(f"Error writing archive plan file {archive_file_path}: {e}")
        raise IOError(f"Error writing archive plan file {archive_file_path}: {e}") from e
    except Exception as e: 
        logging.exception(f"Error preparing archive plan data for saving: {e}")
        raise IOError(f"Error preparing archive plan data for saving: {e}") from e

# --- story Utility Functions ---

def find_story_index_by_id(stories: List[story], story_id: str) -> Optional[int]:
    """Finds the index of a story in the list by its ID."""
    if not stories:
        return None
    for index, story in enumerate(stories):
        if story.id == story_id: # Access attribute directly
            return index
    return None

def find_story_by_id(stories: List[story], story_id: str) -> Optional[story]:
    """Finds a story object in the list by its ID."""
    index = find_story_index_by_id(stories, story_id)
    if index is not None:
        return stories[index]
    return None

def filter_stories(stories: List[story], statuses: Optional[List[str]] = None, unblocked: bool = False) -> List[story]:
    """Filters story objects based on status and unblocked criteria."""
    if stories is None:
        return [] # Should not happen if load_stories raises correctly
        
    filtered: List[story] = []
    # Create map using story objects for efficient dependency lookup
    all_stories_map: Dict[str, story] = {story.id: story for story in stories if story.id}

    # Normalize statuses input if provided
    normalized_statuses: Optional[Set[str]] = set(s.upper() for s in statuses) if statuses else None

    for story in stories:
        # Status is already validated and normalized by Pydantic model
        story_status = story.status 

        # Status Filter
        status_match = True
        if normalized_statuses:
            status_match = story_status in normalized_statuses

        if not status_match:
            continue

        # Unblocked Filter
        unblocked_match = True
        if unblocked:
            if story_status != 'TODO':
                unblocked_match = False
            else:
                # Use depends_on attribute, guaranteed to be a list by Pydantic
                dependencies = story.depends_on 
                if dependencies:
                    for dep_id in dependencies:
                        dep_story = all_stories_map.get(dep_id)
                        # Dependency status is already normalized
                        if not dep_story or dep_story.status != 'DONE':
                            unblocked_match = False
                            break

        if unblocked_match:
             filtered.append(story)

    return filtered 

def add_story(
    story_id: str,
    title: str,
    depends_on_str: Optional[str] = None, # Comma-separated string
    notes: Optional[str] = None,
    priority: Optional[int] = None
) -> story:
    """Adds a new story to the plan. 
       The details file path is automatically generated as todo/lowercase_id.md.

    Args:
        story_id: The unique ID for the new story.
        title: The title of the new story.
        depends_on_str: Optional comma-separated string of story IDs this story depends on.
        notes: Optional notes for the story.
        priority: Optional priority for the story.

    Returns:
        The created story object.

    Raises:
        ValueError: If a story with the given ID already exists or if dependencies are invalid.
        FileNotFoundError, yaml.YAMLError, ValidationError, IOError: If loading/saving plan fails.
    """
    plan = load_plan_data() # Loads the full Plan object

    # Check if story ID already exists
    if find_story_by_id(plan.stories, story_id):
        raise ValueError(f"story with ID '{story_id}' already exists.")

    # Always auto-generate filename: todo/lowercase_story_id.md
    details_filename = f"{story_id.lower()}.md"
    details_path_to_store = os.path.join('todo', details_filename) # Relative path for storage
    logging.info(f"Determined details path: {details_path_to_store}")

    # --- Dependency Handling (remains the same) ---
    depends_on_list: List[str] = []
    if depends_on_str:
        depends_on_list = [dep.strip() for dep in depends_on_str.split(',') if dep.strip()]
        existing_story_ids = {t.id for t in plan.stories}
        for dep_id in depends_on_list:
            if dep_id not in existing_story_ids:
                raise ValueError(f"Dependency story with ID '{dep_id}' not found.")
            if dep_id == story_id: # Self-dependency
                 raise ValueError(f"story '{story_id}' cannot depend on itself.")

    # Create new story object using the determined details path
    try:
        new_story = story(
            id=story_id,
            title=title,
            status='TODO', 
            details=details_path_to_store, # Use the auto-generated path
            depends_on=depends_on_list,
            notes=notes,
            creation_time=datetime.now(timezone.utc),
            priority=priority
        )
    except ValidationError as e: 
        logging.exception(f"Validation error creating new story '{story_id}': {e}")
        raise ValueError(f"Validation error creating new story '{story_id}': {e}") from e

    plan.stories.append(new_story)
    
    # Save the plan first
    save_plan_data(plan) 
    logging.info(f"Successfully added new story '{story_id}' to plan.yaml.")

    # --- Attempt to create the details file (best effort) ---
    try:
        # Construct absolute path for file creation
        # Ensure details_path_to_store is treated as relative to workspace root
        abs_details_path = os.path.join(_workspace_root, details_path_to_store)
        
        if not os.path.exists(abs_details_path):
            logging.info(f"Details file does not exist, attempting to create: {abs_details_path}")
            # Ensure directory exists (e.g., if details='new_dir/story.md')
            details_dir = os.path.dirname(abs_details_path)
            if details_dir: # Only create if not in root
                os.makedirs(details_dir, exist_ok=True)
            # Create empty file
            with open(abs_details_path, 'w', encoding='utf-8') as f:
                f.write("") # Write empty string to ensure file is created
            logging.info(f"Successfully created empty details file: {abs_details_path}")
        else:
            logging.info(f"Details file already exists, skipping creation: {abs_details_path}")
            
    except OSError as e:
        logging.warning(f"Could not create details file '{abs_details_path}': {e}. story entry in plan.yaml is still created.")
    except Exception as e:
        # Catch any other unexpected errors during file creation
        logging.warning(f"Unexpected error creating details file '{details_path_to_store}': {e}. story entry in plan.yaml is still created.")

    # Return the story object regardless of file creation success/failure
    return new_story 

def remove_story(story_id: str) -> bool:
    """Removes a story from the plan by its ID.

    Args:
        story_id: The unique ID of the story to remove.

    Returns:
        True if the story was found and removed, False otherwise (though should raise KeyError).
        
    Raises:
        KeyError: If the story with the given ID is not found.
        FileNotFoundError, yaml.YAMLError, ValidationError, IOError: If loading/saving plan fails.
    """
    plan = load_plan_data() # Loads the full Plan object
    
    initial_story_count = len(plan.stories)
    
    # Find the index of the story to remove
    story_index = find_story_index_by_id(plan.stories, story_id)
    
    if story_index is None:
        raise KeyError(f"story with ID '{story_id}' not found for deletion.")
        
    # Get details filename before removing, for logging/potential future use
    story_to_remove = plan.stories[story_index]
    details_file = story_to_remove.details
    
    # Remove the story from the list
    del plan.stories[story_index]
    
    if len(plan.stories) == initial_story_count - 1:
        # Save the modified plan
        save_plan_data(plan)
        logging.info(f"Successfully removed story '{story_id}' from plan.yaml.")
        
        # Attempt to delete the associated details file (best effort)
        if details_file:
            abs_details_path = os.path.join(_workspace_root, details_file)
            try:
                if os.path.exists(abs_details_path):
                    os.remove(abs_details_path)
                    logging.info(f"Successfully deleted details file: {abs_details_path}")
                else:
                    logging.info(f"Details file not found, skipping deletion: {abs_details_path}")
            except OSError as e:
                logging.warning(f"Could not delete details file '{abs_details_path}': {e}")
        else:
             logging.info(f"story '{story_id}' had no details file specified, nothing to delete.")
             
        return True # Return True as the primary goal (YAML update) succeeded
    else:
        # This case should ideally not be reachable if index finding and deletion work correctly
        logging.error(f"Failed to remove story '{story_id}' - list length did not decrease.")
        # Maybe raise a different exception here? 
        raise RuntimeError(f"Inconsistency detected while trying to remove story '{story_id}'.") 

def remove_archived_story(story_id: str) -> bool:
    """Removes a story from the archive plan (plan_archive.yaml) by its ID.
       Also attempts to delete the associated archived detail file.

    Args:
        story_id: The unique ID of the story to remove from the archive.

    Returns:
        True if the story was found and removed from plan_archive.yaml.
        Actual deletion of detail file is best effort.
        
    Raises:
        KeyError: If the story with the given ID is not found in the archive plan.
        FileNotFoundError, yaml.YAMLError, ValidationError, IOError: If loading/saving archive plan fails.
        RuntimeError: If an inconsistency is detected during removal from the list.
    """
    archive_plan = load_archive_plan_data() 
    
    initial_story_count = len(archive_plan.stories)
    
    story_index_to_remove: Optional[int] = None
    story_details_path: Optional[str] = None

    for i, story in enumerate(archive_plan.stories):
        if story.id == story_id:
            story_index_to_remove = i
            story_details_path = story.details # This path should be relative to workspace root, like todo/archive/details/file.md
            break
    
    if story_index_to_remove is None:
        raise KeyError(f"story with ID '{story_id}' not found in the archive plan ({ARCHIVE_PLAN_FILE_PATH}).")
        
    # Remove the story from the list
    del archive_plan.stories[story_index_to_remove]
    
    if len(archive_plan.stories) == initial_story_count - 1:
        save_archive_plan_data(archive_plan)
        logging.info(f"Successfully removed story '{story_id}' from archive plan: {ARCHIVE_PLAN_FILE_PATH}.")
        
        # Attempt to delete the associated archived details file (best effort)
        if story_details_path:
            # Ensure _workspace_root is accessible or passed if this util is moved
            # For now, it's a global in plan_utils.py
            abs_details_path = os.path.join(_workspace_root, story_details_path) 
            try:
                if os.path.exists(abs_details_path):
                    # Check if the path is within the expected archived details directory for safety
                    # This helps prevent accidental deletion outside todo/archive/details/
                    normalized_archived_details_dir = os.path.normpath(ARCHIVED_DETAILS_DIR_PATH)
                    normalized_abs_details_path = os.path.normpath(abs_details_path)
                    
                    if normalized_abs_details_path.startswith(normalized_archived_details_dir + os.sep):
                        os.remove(abs_details_path)
                        logging.info(f"Successfully deleted archived detail file: {abs_details_path}")
                    else:
                        logging.warning(f"Attempted to delete detail file '{abs_details_path}' which is outside the designated archive details directory '{ARCHIVED_DETAILS_DIR_PATH}'. Deletion aborted for safety.")
                else:
                    logging.info(f"Archived detail file not found, skipping deletion: {abs_details_path}")
            except OSError as e:
                logging.warning(f"Could not delete archived detail file '{abs_details_path}': {e}")
        else:
             logging.info(f"Archived story '{story_id}' had no details file specified in archive, nothing to delete.")
             
        return True
    else:
        logging.error(f"Failed to remove story '{story_id}' from archive plan - list length did not decrease.")
        raise RuntimeError(f"Inconsistency detected while trying to remove story '{story_id}' from archive plan.") 
