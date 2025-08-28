from typing import List, Optional

from plan_manager.domain.models import Story


def find_story_index_by_id(stories: List[Story], story_id: str) -> Optional[int]:
    """Finds the index of a story in the list by its ID."""
    if not stories:
        return None
    for index, story in enumerate(stories):
        if story.id == story_id: # Access attribute directly
            return index
    return None


def find_story_by_id(stories: List[Story], story_id: str) -> Optional[Story]:
    """Finds a story object in the list by its ID."""
    index = find_story_index_by_id(stories, story_id)
    if index is not None:
        return stories[index]
    return None
