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

The server will start on `http://localhost:8000/mcp`.

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
  http://localhost:8000/mcp \
| sed -n 's/^data: //p' \
| jq
```

### Configuration for Cursor

To allow Cursor to communicate with this server, ensure your global `.cursor/mcp.json` file has an entry like this:

```json
{
  "mcpServers": {
      "plan-manager": {
        "url": "http://localhost:8000/mcp"
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
      "url": "http://host.docker.internal:8000/mcp"
    }
  }
}
```

### Viewing Logs

-   **Application Log**: The server's detailed application logs are written to `logs/mcp_server_app.log`.
-   **Terminal Output**: The `uvicorn` server prints live logs directly to the terminal where you ran the `uv run plan-manager` command.
