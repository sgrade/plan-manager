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

"A task represents a discrete unit of work" ([source](https://langchain-ai.github.io/langgraph/concepts/functional_api/#task)), specifically a unit of work for an AI agent. See more in the docs of [Copilot](https://docs.github.com/en/copilot/get-started/features#agent-mode) and [Cursor](https://docs.cursor.com/en/agent/overview).

Cursor agent may divide a task into [agent to-dos](https://docs.cursor.com/en/agent/planning#agent-to-dos) (equivalent of subtask).

## Features

- **Planning**: List, create, read, update, delete, and archive user stories
- **Dependency Tracking**: Define story dependencies with topological sorting
- **Priority System**: 0-5 priority levels (0 = highest priority)
- **MCP Integration**: Server-side implementation for AI assistant integration
- **Robust Validation**: Pydantic-based schema validation for data integrity
- **Workflow Hints**: `workflow_status` returns structured `actions` to guide client agents

## Development Environment

This project is configured to run inside a [Dev Container](https://containers.dev/).

**Automatic Installation**: The dev container is configured to automatically install all necessary Python dependencies using `uv` when it's built for the first time. This is handled by the `postCreateCommand` in `.devcontainer/devcontainer.json`.

### Running the Server

Once the dev container is running, start the MCP server from the VS Code terminal:

```bash
uv run pm
```

The server will start on `http://localhost:3000/mcp`.

Automatic server reload for the dev environment is configured in the `devcontainer.json` by setting `PLAN_MANAGER_RELOAD` to `true`.

Note: After MCP server is reloaded, Cursor (the client) does not reconnect automatically. To make Cursor reconnect, flip the MCP server switch in Cursor settings to off, then on.

### Testing the Server

You can verify that the server is running by sending requests to its endpoints:

```bash
# This should return a 404 Not Found, which is expected.
curl -i http://localhost:3000/
```

JSON responce is expected on the below request.

```bash
curl -sN \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"initialize",
    "params":{
      "protocolVersion":"2025-03-26",
      "capabilities":{},
      "clientInfo":{"name":"curl","version":"0"}
    }
  }' \
  http://localhost:3000/mcp \
| sed -n 's/^data: //p' \
| jq
```

### Configuration for Cursor IDE

To allow Cursor to communicate with this server, ensure your global `.cursor/mcp.json` file has an entry like this:

```json
{
  "mcpServers": {
      "plan-manager": {
        "url": "http://localhost:3000/mcp"
      }
  }
}
```

### Quickstart: Planning + Execution (for agents)

- Planning:
  - Use prompt `planning_suggest_work_items(description)` to classify MAJOR/MINOR/PATCH and propose Plan/Story/Tasks
  - Create items with tools (`create_plan`, `create_story`, `create_task`) and approve via `approve_item_tool`

- Execution (per task):
  - Get `workflow_status` and follow `actions` (structured hints)
  - If missing intent: prompt `execution_intent_template` → `request_approval_tool`
  - After approval: `update_task(status=IN_PROGRESS)`
  - After work: prompt `execution_summary_template` → `update_task(status=DONE, execution_summary)`
  - Changelog: `publish_changelog_tool` returns markdown for client-side append

### Guardrails

- Approval requirement can be toggled via env var in the server:

```bash
REQUIRE_APPROVAL_BEFORE_PROGRESS=true  # default true
```

If accessing from another Cursor instance (devcontainer) on the same host, point to the Docker-host bridge DNS:

```json
{
  "mcpServers": {
    "plan-manager": {
      "url": "http://host.docker.internal:3000/mcp"
    }
  }
}
```

### Logging

-   **Terminal Output**: By default the logs are written to stdout as [recommended](https://12factor.net/logs).
-   **Log file**: If you need the logs in a file, set `PLAN_MANAGER_ENABLE_FILE_LOG` to `true` in the devcontainer.json. The server's detailed application logs will be written to `logs/mcp_server_app.log` (configurable).
