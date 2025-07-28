"""Command-line tool for displaying detailed information about a specific task.

This script provides a CLI interface to view the complete details of a single task
from the project plan, including title, status, dependencies, notes, and other metadata.

Usage:
    python show_task.py TASK_ID
"""

import argparse
import sys

from plan_utils import load_tasks, find_task_by_id, PLAN_FILE_PATH

def display_task(task: dict) -> None:
    """Display detailed information about a task in a readable format.

    Args:
        task: Task dictionary containing task details and metadata
    """
    print(f"--- Task Details --- ID: {task.get('id', 'N/A')} ---")
    print(f"Title:    {task.get('title', 'N/A')}")
    print(f"Status:   {task.get('status', 'N/A')}")

    details = task.get('details')
    if details:
        print(f"Details:  {details}")

    notes = task.get('notes')
    if notes:
        print(f"Notes:    {notes}")

    depends_on = task.get('depends_on')
    if depends_on:
        print(f"Depends On: {', '.join(depends_on)}")
    print("-------------------------")

def main() -> None:
    """Main entry point for the show_task CLI tool."""
    parser = argparse.ArgumentParser(description='Show details for a specific task from plan.yaml.')
    parser.add_argument('task_id', help='The unique ID of the task to display.')

    args = parser.parse_args()

    tasks = load_tasks() # Use utility function
    if tasks is None:
        sys.exit(1) # Error message already printed by load_tasks

    task = find_task_by_id(tasks, args.task_id) # Use utility function

    if task:
        display_task(task)
    else:
        print(f"Error: Task with ID '{args.task_id}' not found in {PLAN_FILE_PATH}.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
