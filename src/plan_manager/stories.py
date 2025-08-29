import logging
import yaml
import collections
from datetime import datetime, timezone
from typing import List, Optional, Dict

from pydantic import ValidationError

from plan_manager.domain.models import Story
from plan_manager.services import plan_repository as plan_repo


logger = logging.getLogger(__name__)


def register_stories_tools(mcp_instance) -> None:
    """Register plan-related tools with the given FastMCP instance."""
    mcp_instance.tool()(list_stories)


def list_stories(statuses: str, unblocked: bool = False) -> list[dict]:
    """Lists stories from plan.yaml, with optional filters, sorted by dependency, priority, and creation time.

    Args:
        statuses: Comma-separated string of statuses to filter by (e.g., "TODO,IN_PROGRESS"). Case-insensitive. REQUIRED.
        unblocked: If true, show only TODO stories whose dependencies are all DONE.

    Returns:
        A list of stories (dictionaries with id, status, title, priority, creation_time) matching the filters, in a topologically sorted order.
    """
    logging.info(f"Handling list_stories: statuses_str='{statuses}', unblocked={unblocked}")

    try:
        all_stories: List[Story] = load_stories()
        if not all_stories:
            return []

        # --- Topological Sort ---
        adj: Dict[str, List[str]] = collections.defaultdict(list)
        in_degree: Dict[str, int] = collections.defaultdict(int)
        story_map: Dict[str, Story] = {story.id: story for story in all_stories} # Map of id to story

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

        sorted_stories_list: List[Story] = []

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
        final_filtered_stories: List[Story] = []
        # all_stories_map_for_filter: Dict[str, story] = {story.id: story for story in sorted_stories_list}

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


def load_stories() -> List[Story]:
    """Load the plan and return the list of stories."""
    plan = plan_repo.load()
    return plan.stories
