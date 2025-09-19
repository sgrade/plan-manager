# AGENTS.md

This file guides agents that use the Plan Manager MCP server.

## Usage
- Quickstart: see `docs/quickstart_agents.md` (concise)
- Full guide: see `docs/usage_guide_agents.md` (details)
- Triage policy and dashboards: see `docs/triage_guide.md`

## Setup
- Start server: `uv run pm`
- Endpoint: `http://localhost:3000/mcp`
- Details: `docs/contributing.md`

Note: After MCP server is reloaded, Cursor (the client) does not reconnect automatically. To make Cursor reconnect, flip the MCP server switch in Cursor settings to off, then on.
