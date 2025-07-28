"""Command-line tool for listing and filtering tasks from the project plan.

This script provides a CLI interface to list tasks with various filtering options
including status filtering and dependency-based unblocked task filtering.

Usage:
    python list_tasks.py [--status STATUS] [--unblocked]
"""

import argparse
import sys

from plan_utils import load_tasks, filter_tasks

# --- list_tasks Specific Logic ---

def display_task_list(tasks: list[dict], title: str = "Listing tasks") -> None:
    """Display a formatted list of tasks to stdout.

    Args:
        tasks: List of task dictionaries containing id, status, and title
        title: Header title to display above the task list
    """
    if not tasks:
        print(f"{title}: None found.")
        return

    print(f"{title}:")
    print("-" * (len(title) + 1))
    for task in tasks:
        task_id = task.get('id', 'N/A')
        status = task.get('status', 'N/A')
        task_title = task.get('title', 'N/A')
        print(f"[{task_id}] ({status}) {task_title}")

def main() -> None:
    """Main entry point for the list_tasks CLI tool."""
    parser = argparse.ArgumentParser(description='List tasks from plan.yaml, with optional filters.')
    parser.add_argument(
        '--status',
        action='append',
        help='Filter by status (e.g., TODO, IN_PROGRESS). Can be used multiple times.',
        type=str.upper # Convert status to uppercase for case-insensitivity
    )
    parser.add_argument(
        '--unblocked',
        action='store_true',
        help='Show only TODO tasks whose dependencies are all DONE.'
    )

    args = parser.parse_args()

    all_tasks = load_tasks() # Use utility function
    if all_tasks is None:
        sys.exit(1) # Error message already printed by load_tasks

    # Use utility function for filtering
    filtered_tasks = filter_tasks(all_tasks, statuses=args.status, unblocked=args.unblocked)

    # --- Determine display title ---
    display_title = "Listing tasks"
    filters_applied = []
    if args.status:
        filters_applied.append(f"status={'/'.join(args.status)}")
    if args.unblocked:
        filters_applied.append("unblocked")

    if filters_applied:
        display_title += f" matching: { ' & '.join(filters_applied) }"
    # --- End Determine display title ---

    display_task_list(filtered_tasks, title=display_title)

if __name__ == "__main__":
    main()
