# Plan Manager

AI-assisted task planning and management tool with MCP (Model Context Protocol) integration.

## Overview

Plan Manager provides an MCP server interface to interact with project tasks defined in `todo/plan.yaml`. It enables AI assistants like Cursor to programmatically create, list, view, and update task statuses, with support for dependency management and priority-based sorting.

## Features

- **Task Management**: Create, update, delete, and archive tasks
- **Dependency Tracking**: Define task dependencies with topological sorting
- **Priority System**: 0-5 priority levels (0 = highest priority)
- **MCP Integration**: Server-side implementation for AI assistant integration
- **CLI Tools**: Direct command-line task management scripts
- **Robust Validation**: Pydantic-based schema validation for data integrity

## Plan Manager (`plan_manager/`)

This tool provides an [MCP](https://github.com/modelcontextprotocol) server interface to interact with the project's task plan defined in `todo/plan.yaml`. It allows creating and deleting tasks, listing, viewing, and updating task statuses programmatically, primarily intended for use with AI assistants like Cursor.

### Setup and Environment

The Plan Manager tool, located in `tools/plan_manager/`, is managed using [uv](https://docs.astral.sh/uv/) and requires Python 3. Dependencies are defined in `tools/pyproject.toml`. The `todo/plan.yaml` file it interacts with is parsed and validated against a Pydantic schema to ensure data integrity.

**Automated Setup (Dev Container):**

*   **Virtual Environment & Dependencies:** When the development container is built, the `.devcontainer/Dockerfile` installs `uv` and then uses `uv sync --directory /tools` to create the virtual environment (if it doesn't exist) at `tools/venv` and install dependencies based on `tools/pyproject.toml`. This process is part of the image creation.

**Run the server:**

uv run python -m plan_manager

**Test if the server runs:**

Note: from inside containers, use `host.docker.internal` instead of `localhost`.

curl -i http://localhost:8000/

Expected: HTTP/1.1 404 Not Found

curl -i http://localhost:8000/sse

Expected: ping every 15 seconds

**Viewing Logs:**

*   **Supervisor Logs:** `supervisord` manages its own logs and the stdout/stderr of the `pm` service.
    *   Main `supervisord` log: `/workspaces/plan-manager/tools/logs/supervisord_main.log`
    *   `pm` service stdout log: `/workspaces/plan-manager/tools/logs/pm_supervisor.log`
    *   `pm` service stderr log: `/workspaces/plan-manager/tools/logs/pm_supervisor.err.log`
*   **Application Log:** The Python application itself also logs to `/workspaces/plan-manager/tools/logs/mcp_server_app.log`.
*   **Docker Logs:** You can still view the container's main output (which will include `supervisord`'s primary output) using `docker logs <container_name_or_id>`. For live logs: `docker logs -f <container_name_or_id>`.

**Checking Status and Managing the Service:**

From a terminal *inside* the dev container, you can use `supervisorctl` to manage the `pm` service:
*   **Check status:**
    ```bash
    sudo supervisorctl -s unix:///tmp/supervisor.sock status pm
    # or using the config file:
    # sudo supervisorctl -c /workspaces/plan-manager/tools/plan_manager/supervisord.conf status pm
    ```
*   **Restart the service:**
    ```bash
    sudo supervisorctl -s unix:///tmp/supervisor.sock restart pm
    ```
*   **Stop the service:**
    ```bash
    sudo supervisorctl -s unix:///tmp/supervisor.sock stop pm
    ```
*   **Start the service (if stopped):**
    ```bash
    sudo supervisorctl -s unix:///tmp/supervisor.sock start pm
    ```

If `uvicorn` is started with `reload=True` (as configured in `tools/plan_manager/__main__.py`), it will also monitor Python files for changes and automatically restart the server when code is updated. `supervisord` will ensure the `pm` process itself is restarted if it crashes.

**Manual Interaction (Legacy/Direct Debugging - Generally Not Needed):**

The following instructions are for direct manual execution, which should generally not be needed as `supervisord` now handles the server. If you do run manually for deep debugging, ensure the `supervisord`-managed service is stopped (`sudo supervisorctl -s unix:///tmp/supervisor.sock stop pm`) to avoid port conflicts.

*   **Manually Running the Server (from `/workspaces/plan-manager/tools/` directory):**
    ```bash
    python -m plan_manager
    ```
    This will run the server in the foreground. Press `Ctrl+C` to stop it. Or, using `uv`:
    ```bash
    uv run python -m plan_manager
    ```

### Configuration (for Cursor)

To allow Cursor to communicate with this server, ensure your `.cursor/mcp.json` file has an entry like this:

```json
{
  "mcpServers": {
      // ... other servers ...
      "plan-manager": {
        "transport": "sse",
        "url": "http://localhost:8000/sse"
      }
  }
}
```

### Available Tools (via MCP)

*   **`list_tasks_handler(statuses: str, unblocked: bool = False)`:** Lists tasks from `plan.yaml`.
    *   Filters by the comma-separated `statuses` string (e.g., "TODO,IN_PROGRESS").
    *   If `unblocked` is true, only shows `TODO` tasks whose dependencies are all `DONE`.
    *   Tasks are sorted primarily by dependency (topological sort).
    *   Within the items that can be processed (respecting dependencies), tasks are further sorted by:
        1.  `priority` (ascending, 0 is highest; tasks without priority are treated as lowest).
        2.  `creation_time` (ascending, earlier is higher priority; tasks without it are lower).
        3.  Task `id` (alphabetical ascending) as a final tie-breaker.
    *   Returns a list of task dictionaries containing `id`, `status`, `title`, `priority` (if set), and `creation_time` (if set). The `title` in the returned dictionary will be prepended with a zero-padded sequential number (e.g., "01. Actual Title") to reflect the primary sort order.
*   **`show_task_handler(task_id: str)`:** Shows the full details of a specific task by its ID.
*   **`update_task_status_handler(task_id: str, new_status: str)`:** Updates the status of a specific task. Allowed statuses are `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`, `DEFERRED`.
*   **`update_task_priority_handler(task_id: str, new_priority_str: str)`:** Updates the priority of a specific task.
    *   `task_id` (string, required): The ID of the task to update.
    *   `new_priority_str` (string, required): The new priority. Valid values: "0", "1", "2", "3", "4", "5". Use "6" to remove priority (sets to null).
*   **`create_task_handler(title: str, priority: str, depends_on: str, notes: str)`:** Creates a new task.
    *   `title` (string, required): The human-readable title for the task. Used to generate the ID.
    *   `priority` (string, required): Priority for the task (0-5, 0 is highest). Provide the string "6" to indicate that the priority is not set (will be stored as null).
    *   `depends_on` (string, required): Comma-separated string of task IDs this new task depends on. Provide an empty string "" to indicate no dependencies.
    *   `notes` (string, required): Brief notes for the task. Provide an empty string "" to indicate no notes.
    The new task defaults to `TODO` status. The task ID is automatically generated from the title. The response will include `id`, `title`, `status`, `details`, `priority`, `creation_time`, `notes`, and `depends_on` (if set).
*   **`delete_task_handler(task_id: str)`:** Deletes a task by its ID.
*   **`archive_done_tasks_handler(older_than_days_str: str, max_tasks_to_archive_str: str)`:** Archives `DONE` tasks from `plan.yaml` to `todo/archive/plan_archive.yaml` and moves their detail files.
    *   `older_than_days_str` (string): Optional. If provided as a numeric string (e.g., "7"), only archives tasks completed more than this many days ago. Provide an empty string "" to not filter by age.
    *   `max_tasks_to_archive_str` (string): Optional. If provided as a numeric string (e.g., "10"), limits the number of tasks archived in one run. Provide an empty string "" for no limit.
    *   It skips tasks that have active (non-DONE) tasks depending on them.
*   **`delete_archived_task_handler(task_id: str)`:** Deletes a task from the archive (`todo/archive/plan_archive.yaml`) by its ID. Also attempts to delete the associated archived detail file.

---

### Manual Script Usage Examples

(Assuming virtual environment is active or using the full path to venv python)

*   **Show task details:**
    ```bash
    python tools/plan_manager/show_task.py <TASK_ID>
    ```
*   **List tasks (e.g., unblocked TODOs):**
    ```bash
    python tools/plan_manager/list_tasks.py --unblocked
    ```
*   **Update task status:**
    ```bash
    python tools/plan_manager/update_task_status.py <TASK_ID> <NEW_STATUS>
    ```

*   **Delete task:**
    ```bash
    python tools/plan_manager/delete_task.py <TASK_ID>
    ```

### MCP Server Integration

The `mcp_server.py` script provides the core functionality as tools usable directly by the Cursor AI Assistant.

*   **Configuration:** The server is configured for this project in `.cursor/mcp.json` (see "Configuration (for Cursor)" section above) and runs using the `.venv` Python environment, started automatically in the dev container.
*   **Verification:** Check Cursor's MCP settings (Command Palette -> Search for "MCP", or Settings UI) to ensure the `plan-manager` server is listed and enabled.
*   **AI Usage:** You can ask the AI Assistant to use the tools:
    *   "Use plan-manager to list all TODO tasks."
    *   "Show the details for task IMPLEMENT_SNAPSHOTS using plan-manager."
    *   "Update the status of REFACTOR_REPORT_GENERATION to IN_PROGRESS with plan-manager."
    *   "Create a new task with ID MY_NEW_TASK and title 'Figure out MCP integration' using plan-manager."
*   **Output:** Note that when used via MCP, the tools return structured JSON data to the AI, not the formatted text printed by the manual scripts.
