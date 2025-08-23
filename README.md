# Plan Manager

AI-assisted planning (project management) tool with MCP (Model Context Protocol) integration.

## Overview

Plan Manager provides an MCP server interface to interact with user stories defined in a plan with support for dependency management and priority-based sorting.

## Terminology

The following terms from agile project management are used as a reference to represent pieces of work:
- subtask
- task
- user story
- epic
- initiative
- theme

In plan-manager, every plan (equivalent of epic) is a collection of (user) stories; every story is a collection of tasks.

Task is an elementary piece of work, which AI agent does autonomously: see relevant docs of the agent mode in [VS Code](https://code.visualstudio.com/docs/copilot/chat/chat-agent-mode#_use-agent-mode) and [Cursor](https://docs.cursor.com/en/agent/overview).

Cursor agent may further (automatically) divide the tasks into [agent to-dos](https://docs.cursor.com/en/agent/planning#agent-to-dos) (equivalent of subtask).

## Features

- **Planning**: List, create, read, update, delete, and archive user stories
- **Dependency Tracking**: Define story dependencies with topological sorting
- **Priority System**: 0-5 priority levels (0 = highest priority)
- **MCP Integration**: Server-side implementation for AI assistant integration
- **Robust Validation**: Pydantic-based schema validation for data integrity

## Development Environment

This project is configured to run inside a [Dev Container](https://containers.dev/).

**Automatic Installation**: The dev container is configured to automatically install all necessary Python dependencies using `uv` when it's built for the first time. This is handled by the `postCreateCommand` in `.devcontainer/devcontainer.json`.

### Running the Server

Once the dev container is running, start the MCP server from the VS Code terminal:

```bash
PLAN_MANAGER_ENABLE_FILE_LOG=false uv run plan-manager --reload
```

Note: After MCP server is reloaded, Cursor (the client) does not reconnect automatically. To make Cursor reconnect, flip the MCP server switch in Cursor settings to off, then on.

Alternatively, with logging

```bash
uv run plan-manager --reload
```

The server will start on `http://localhost:8000`.

Optional flags if needed:

```bash
  uv run plan-manager --reload \
    --reload-dir src \
    --reload-include '*.py' \
    --reload-exclude 'logs/*' \
    --graceful-timeout 2 \
    --timeout-keep-alive 2
```

### Testing the Server

You can verify that the server is running by sending requests to its endpoints:

```bash
# This should return a 404 Not Found, which is expected.
curl -i http://localhost:8000/

# This should establish an SSE connection for MCP communication.
# You will see a "ping" event every 15 seconds.
curl -i http://localhost:8000/sse
```

### Viewing Logs

-   **Application Log**: The server's detailed application logs are written to `logs/mcp_server_app.log`.
-   **Terminal Output**: The `uvicorn` server prints live logs directly to the terminal where you ran the `uv run plan-manager` command.

### Configuration for Cursor

To allow Cursor to communicate with this server, ensure your global `.cursor/mcp.json` file has an entry like this:

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

If accessing from another Cursor instance on the same Windows host, point to the Docker-host bridge DNS:

```json
{
  "mcpServers": {
    "plan-manager": {
      "transport": "sse",
      "url": "http://host.docker.internal:8000/sse"
    }
  }
}
```

## Available Tools (via MCP)

*   **`list_stories(statuses: str, unblocked: bool = False)`:** Lists stories from `plan.yaml`.
    *   Filters by the comma-separated `statuses` string (e.g., "TODO,IN_PROGRESS").
    *   If `unblocked` is true, only shows `TODO` stories whose dependencies are all `DONE`.
    *   stories are sorted primarily by dependency (topological sort).
    *   Within the items that can be processed (respecting dependencies), stories are further sorted by:
        1.  `priority` (ascending, 0 is highest; stories without priority are treated as lowest).
        2.  `creation_time` (ascending, earlier is higher priority; stories without it are lower).
        3.  story `id` (alphabetical ascending) as a final tie-breaker.
    *   Returns a list of story dictionaries containing `id`, `status`, `title`, `priority` (if set), and `creation_time` (if set). The `title` in the returned dictionary will be prepended with a zero-padded sequential number (e.g., "01. Actual Title") to reflect the primary sort order.
*   **`get_story(story_id: str)`:** Returns the full details of a specific story by its ID.
*   (Replaced) Use `update_story` for status/priority updates too.
    *   `story_id` (string, required): The ID of the story to update.
    *   `new_priority_str` (string, required): The new priority. Valid values: "0", "1", "2", "3", "4", "5". Use "6" to remove priority (sets to null).
*   **`create_story(title: str, priority: str, depends_on: str, notes: str, details_content: str = "")`:** Creates a new story.
    *   `title` (string, required): The human-readable title for the story. Used to generate the ID.
    *   `priority` (string, required): Priority for the story (0-5, 0 is highest). Provide the string "6" to indicate that the priority is not set (will be stored as null).
    *   `depends_on` (string, required): Comma-separated string of story IDs this new story depends on. Provide an empty string "" to indicate no dependencies.
    *   `notes` (string, required): Brief notes for the story. Provide an empty string "" to indicate no notes.
    *   `details_content` (string, optional): Initial markdown content for the story's details file. Useful when using a remote MCP server.
    The new story defaults to `TODO` status. The story ID is automatically generated from the title. The response will include `id`, `title`, `status`, `details`, `priority`, `creation_time`, `notes`, and `depends_on` (if set).
*   **`delete_story(story_id: str)`:** Deletes a story by its ID.
*   **`update_story(story_id: str, title: str | null = null, notes: str | null = null, depends_on: str | null = null, priority: str | null = null, status: str | null = null)`:** Partially updates a story. Only non-null fields are applied.
*   **`archive_done_stories(older_than_days_str: str, max_stories_to_archive_str: str)`:** Archives `DONE` stories from `plan.yaml` to `todo/archive/plan_archive.yaml` and moves their detail files.
    *   `older_than_days_str` (string): Optional. If provided as a numeric string (e.g., "7"), only archives stories completed more than this many days ago. Provide an empty string "" to not filter by age.
    *   `max_stories_to_archive_str` (string): Optional. If provided as a numeric string (e.g., "10"), limits the number of stories archived in one run. Provide an empty string "" for no limit.
    *   It skips stories that have active (non-DONE) stories depending on them.
*   **`delete_archived_story(story_id: str)`:** Deletes a story from the archive (`todo/archive/plan_archive.yaml`) by its ID. Also attempts to delete the associated archived detail file.
