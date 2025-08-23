import os

# --- Constants and Configuration ---

# Determine the workspace root (project root directory)
_workspace_root = os.getcwd()  # Current working directory (project root)
PLAN_FILE_PATH = os.path.join(_workspace_root, 'todo', 'plan.yaml')

ARCHIVE_DIR_PATH = os.path.join(_workspace_root, 'todo', 'archive')
ARCHIVE_PLAN_FILE_PATH = os.path.join(ARCHIVE_DIR_PATH, 'plan_archive.yaml')
ARCHIVED_DETAILS_DIR_PATH = os.path.join(ARCHIVE_DIR_PATH, 'details')
