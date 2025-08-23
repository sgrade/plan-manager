"""Command-line tool for updating story status in the project plan.

This script provides a CLI interface to change the status of a specific story,
with validation to ensure only allowed status values are used.

Usage:
    python update_story_status.py story_ID NEW_STATUS

Allowed statuses: TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED
"""

import argparse
import sys

from plan_manager.stories import ALLOWED_STATUSES

from plan_manager.plan_utils import (
    load_plan_data,
    save_plan_data,
    find_story_index_by_id,
    PLAN_FILE_PATH
)

# --- update_story_status Specific Logic ---

def main() -> None:
    """Main entry point for the update_story_status CLI tool."""
    parser = argparse.ArgumentParser(description='Update the status of a specific story in plan.yaml.')
    parser.add_argument('story_id', help='The unique ID of the story to update.')
    parser.add_argument(
        'new_status',
        help=f'The new status for the story. Allowed values: { ", ".join(sorted(list(ALLOWED_STATUSES))) }',
        type=str.upper # Convert status to uppercase for consistency
    )

    args = parser.parse_args()

    # Validate the new status (using imported constant)
    if args.new_status not in ALLOWED_STATUSES:
        print(f"Error: Invalid status '{args.new_status}'.", file=sys.stderr)
        print(f"Allowed statuses are: { ', '.join(sorted(list(ALLOWED_STATUSES))) }", file=sys.stderr)
        sys.exit(1)

    # Load the entire plan data (using utility function)
    plan_data = load_plan_data()
    if plan_data is None:
        sys.exit(1) # Error message already printed by load_plan_data

    stories = plan_data['stories'] # Get the list of stories

    # Find the index of the story to update (using utility function)
    story_index = find_story_index_by_id(stories, args.story_id)

    if story_index is not None:
        old_status = stories[story_index].get('status', 'N/A')
        # Update the status in the loaded data
        stories[story_index]['status'] = args.new_status

        # Save the modified plan data back to the file (using utility function)
        if save_plan_data(plan_data):
            print(f"Successfully updated status for story '{args.story_id}' from '{old_status}' to '{args.new_status}'.")
        else:
            # Error message already printed by save_plan_data
            sys.exit(1)
    else:
        print(f"Error: story with ID '{args.story_id}' not found in {PLAN_FILE_PATH}.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
