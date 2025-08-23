"""Command-line tool for listing and filtering stories from the project plan.

This script provides a CLI interface to list stories with various filtering options
including status filtering and dependency-based unblocked story filtering.

Usage:
    python list_stories.py [--status STATUS] [--unblocked]
"""

import argparse
import sys

from plan_utils import load_stories, filter_stories

# --- list_stories Specific Logic ---

def display_story_list(stories: list[dict], title: str = "Listing stories") -> None:
    """Display a formatted list of stories to stdout.

    Args:
        stories: List of story dictionaries containing id, status, and title
        title: Header title to display above the story list
    """
    if not stories:
        print(f"{title}: None found.")
        return

    print(f"{title}:")
    print("-" * (len(title) + 1))
    for story in stories:
        story_id = story.get('id', 'N/A')
        status = story.get('status', 'N/A')
        story_title = story.get('title', 'N/A')
        print(f"[{story_id}] ({status}) {story_title}")

def main() -> None:
    """Main entry point for the list_stories CLI tool."""
    parser = argparse.ArgumentParser(description='List stories from plan.yaml, with optional filters.')
    parser.add_argument(
        '--status',
        action='append',
        help='Filter by status (e.g., TODO, IN_PROGRESS). Can be used multiple times.',
        type=str.upper # Convert status to uppercase for case-insensitivity
    )
    parser.add_argument(
        '--unblocked',
        action='store_true',
        help='Show only TODO stories whose dependencies are all DONE.'
    )

    args = parser.parse_args()

    all_stories = load_stories() # Use utility function
    if all_stories is None:
        sys.exit(1) # Error message already printed by load_stories

    # Use utility function for filtering
    filtered_stories = filter_stories(all_stories, statuses=args.status, unblocked=args.unblocked)

    # --- Determine display title ---
    display_title = "Listing stories"
    filters_applied = []
    if args.status:
        filters_applied.append(f"status={'/'.join(args.status)}")
    if args.unblocked:
        filters_applied.append("unblocked")

    if filters_applied:
        display_title += f" matching: { ' & '.join(filters_applied) }"
    # --- End Determine display title ---

    display_story_list(filtered_stories, title=display_title)

if __name__ == "__main__":
    main()
