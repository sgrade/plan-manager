# Configuration Reference

Authoritative reference for environment variables used by Plan Manager.

Notes:
- Defaults apply when the variable is unset.
- Restart is required for most changes. If `PLAN_MANAGER_RELOAD` is enabled in dev, the server reloads on file changes, but Cursor (client) may need manual reconnect.

## Core paths
- TODO_DIR (default: `<workspace>/todo`)
  - Base directory storing plans and items
- PLANS_INDEX_FILE_PATH (derived: `$TODO_DIR/plans/index.yaml`)

## Logging
- LOG_DIR (default: `<workspace>/logs`)
- LOG_FILE_PATH (default: `$LOG_DIR/mcp_server_app.log`)
- LOG_LEVEL (default: `INFO`) — e.g., DEBUG, INFO, WARNING, ERROR
- PLAN_MANAGER_ENABLE_FILE_LOG (default: `false`) — enable file logging
Note: The server prints structured logs to stdout by default; file log is optional.

## Workflow guardrails
- REQUIRE_APPROVAL_BEFORE_PROGRESS (default: `true`)
  - Gate status changes off TODO via approval flow
- REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS (default: `true`)
  - Require an execution intent/plan before starting
- REQUIRE_EXECUTION_SUMMARY_BEFORE_DONE (default: `true`)
  - Require an execution summary before DONE

## UI / Browser
- PLAN_MANAGER_ENABLE_BROWSER (default: `true`)
  - Enable the `/browse` endpoint for viewing files

## Uvicorn / Server
- HOST (default: `127.0.0.1`)
- PORT (default: `3000`)
- PLAN_MANAGER_RELOAD (default: `false`) — enable dev reload
- RELOAD_DIRS (default: `src`) — comma-separated list
- RELOAD_INCLUDE (default: `*.py`) — comma-separated patterns
- RELOAD_EXCLUDE (default: `logs/*`) — comma-separated patterns
- TIMEOUT_GRACEFUL_SHUTDOWN (default: `3`) — seconds
- TIMEOUT_KEEP_ALIVE (default: `5`) — seconds

Client reconnect tip:
- After a reload, Cursor may not reconnect automatically. Toggle the MCP server in Cursor settings off → on to reconnect.

## Docs / Agent guides
- USAGE_GUIDE_REL_PATH (default: `docs/usage_guide_agents.md`)
- PROJECT_WORKFLOW_REL_PATH (default: `docs/project_workflow.md`)

## Telemetry
- PLAN_MANAGER_TELEMETRY_ENABLED (default: `false`) — enable lightweight counters/timers
- PLAN_MANAGER_TELEMETRY_SAMPLE_RATE (default: `1.0`) — 0.0..1.0 sampling

## Examples
```bash
# Enable dev reload and verbose logs
export PLAN_MANAGER_RELOAD=true
export LOG_LEVEL=DEBUG

# Write logs to file
export PLAN_MANAGER_ENABLE_FILE_LOG=true
export LOG_DIR=/var/log/plan-manager

# Change todo directory
export TODO_DIR=$PWD/.pm_todo
```