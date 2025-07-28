"""Command-line tool for updating task status in the project plan.

This script provides a CLI interface to change the status of a specific task,
with validation to ensure only allowed status values are used.

Usage:
    python update_task_status.py TASK_ID NEW_STATUS

Allowed statuses: TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED
"""

import argparse
import sys

from plan_utils import (
    load_plan_data,
    save_plan_data,
    find_task_index_by_id,
    ALLOWED_STATUSES,
    PLAN_FILE_PATH
)

# --- update_task_status Specific Logic ---

def main() -> None:
    """Main entry point for the update_task_status CLI tool."""
    parser = argparse.ArgumentParser(description='Update the status of a specific task in plan.yaml.')
    parser.add_argument('task_id', help='The unique ID of the task to update.')
    parser.add_argument(
        'new_status',
        help=f'The new status for the task. Allowed values: { ", ".join(sorted(list(ALLOWED_STATUSES))) }',
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

    tasks = plan_data['tasks'] # Get the list of tasks

    # Find the index of the task to update (using utility function)
    task_index = find_task_index_by_id(tasks, args.task_id)

    if task_index is not None:
        old_status = tasks[task_index].get('status', 'N/A')
        # Update the status in the loaded data
        tasks[task_index]['status'] = args.new_status

        # Save the modified plan data back to the file (using utility function)
        if save_plan_data(plan_data):
            print(f"Successfully updated status for task '{args.task_id}' from '{old_status}' to '{args.new_status}'.")
        else:
            # Error message already printed by save_plan_data
            sys.exit(1)
    else:
        print(f"Error: Task with ID '{args.task_id}' not found in {PLAN_FILE_PATH}.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
