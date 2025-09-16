# Contributing

## Core guidelines

Keep the server simple: tools enforce workflow; prompts are convenience only; roots/elicitation are client-side.

## Conventions

Commit messages: [https://www.conventionalcommits.org](https://www.conventionalcommits.org)

Semantic Versioning: [https://semver.org](https://semver.org)

Changelog: [https://keepachangelog.com](https://keepachangelog.com)

## Triage

Refer to the Triage Guide for labels, severity definitions, SLAs, and routine:
see [triage_guide.md](./triage_guide.md).

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

### Testing the Server

You can verify that the server is running by sending requests to its endpoints:

```bash
# This should return a 404 Not Found, which is expected.
curl -i http://localhost:3000/
```

This is expected because the root path has no route.

A JSON response is expected on the below request. 

Note: jq is required for the below to work.

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

To test with MCP-Inspector, check [../dev/mcp-inspector/README.md](../dev/mcp-inspector/README.md)

### Logging

-   **Terminal Output**: By default the logs are written to stdout as [recommended](https://12factor.net/logs).
-   **Log file**: If you need the logs in a file, set `PLAN_MANAGER_ENABLE_FILE_LOG` to `true` in the devcontainer.json. The server's detailed application logs will be written to `logs/mcp_server_app.log` (configurable).
