"""Command-line tool for displaying detailed information about a specific story.

This script provides a CLI interface to view the complete details of a single story
from the project plan, including title, status, dependencies, notes, and other metadata.

Usage:
    python show_story.py story_ID
"""

import argparse
import sys

from plan_utils import load_stories, find_story_by_id, PLAN_FILE_PATH

def display_story(story: dict) -> None:
    """Display detailed information about a story in a readable format.

    Args:
        story: story dictionary containing story details and metadata
    """
    print(f"--- story Details --- ID: {story.get('id', 'N/A')} ---")
    print(f"Title:    {story.get('title', 'N/A')}")
    print(f"Status:   {story.get('status', 'N/A')}")

    details = story.get('details')
    if details:
        print(f"Details:  {details}")

    notes = story.get('notes')
    if notes:
        print(f"Notes:    {notes}")

    depends_on = story.get('depends_on')
    if depends_on:
        print(f"Depends On: {', '.join(depends_on)}")
    print("-------------------------")

def main() -> None:
    """Main entry point for the show_story CLI tool."""
    parser = argparse.ArgumentParser(description='Show details for a specific story from plan.yaml.')
    parser.add_argument('story_id', help='The unique ID of the story to display.')

    args = parser.parse_args()

    stories = load_stories() # Use utility function
    if stories is None:
        sys.exit(1) # Error message already printed by load_stories

    story = find_story_by_id(stories, args.story_id) # Use utility function

    if story:
        display_story(story)
    else:
        print(f"Error: story with ID '{args.story_id}' not found in {PLAN_FILE_PATH}.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
