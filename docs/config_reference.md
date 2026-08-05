# Configuration Reference

Authoritative reference for environment variables used by Plan Manager.

Notes:
- Defaults apply when the variable is unset.
- Restart is required for most changes. If `PLAN_MANAGER_RELOAD` is enabled in dev, the server reloads on file changes, but Cursor (client) may need manual reconnect.

## Core paths
- TODO_DIR (default: `<workspace>/todo`)
  - Base directory storing plans and items
- PLANS_INDEX_FILE_PATH (derived: `$TODO_DIR/plans/index.yaml`)
- PLAN_MANAGER_DB_DIR (default: `<workspace>/db`)
  - SQLite directory (`plan_manager.sqlite3`) and operational lock file

## Backup / Restore CLI
- `pm export [--plan ID] [--out DIR]`
  - Reads one SQLite snapshot transaction and publishes a complete YAML tree with `MANIFEST`
  - Default `--out` is `TODO_DIR`
  - Scoped mode (`--plan`) refuses an existing multi-plan backup target to avoid deleting sibling plan backups
- `pm import [--dry-run] [--replace-plan ID] [--from DIR]`
  - Validates/imports a tree; `--replace-plan` replaces exactly one plan in one transaction
  - Default `--from` is `TODO_DIR`
- Offline guard:
  - `pm` server holds an advisory lock file at `$PLAN_MANAGER_DB_DIR/plan_manager.server.lock`
  - `pm export` and `pm import` probe that lock and refuse while the server is live
- Supported backup contract:
  - `pm export` is the only supported backup path
  - Directly copying/tarring a live DB volume is unsupported (WAL can be torn)
- Exit codes:
  - `0`: success
  - non-zero: failure (problem report on stderr)

## Logging
- LOG_DIR (default: `<workspace>/logs`)
- LOG_FILE_PATH (default: `$LOG_DIR/mcp_server_app.log`)
- LOG_LEVEL (default: `INFO`) — e.g., DEBUG, INFO, WARNING, ERROR
- PLAN_MANAGER_ENABLE_FILE_LOG (default: `false`) — enable file logging
Note: The server prints structured logs to stdout by default; file log is optional.
File logging is an opt-in for development or incident investigation (e.g. set
`PLAN_MANAGER_ENABLE_FILE_LOG=true` and `LOG_DIR=/data/logs` to persist logs onto
a mounted volume across container recreation). There is no log rotation; don't
leave it enabled unattended.
If `LOG_DIR` cannot be created or written, the server keeps running with stdout-only
logging and emits a warning.

## Workflow guardrails
- REQUIRE_APPROVAL_BEFORE_PROGRESS (default: `true`)
  - Gate status changes off TODO via approval flow
- REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS (default: `true`)
  - Require an execution intent/plan before starting
- REQUIRE_CHANGES_BEFORE_DONE (default: `true`)
  - Require changelog entries before DONE

## UI
- PLAN_MANAGER_ENABLE_UI (default: `true`)
  - Enable the read-only supervision UI under `/ui`
- Removed: `PLAN_MANAGER_ENABLE_BROWSER`
  - The legacy `/browse` endpoint and browser flag were removed

## Uvicorn / Server
- HOST (default: `127.0.0.1`)
- PORT (default: `3000`)
- PLAN_MANAGER_RELOAD (default: `false`) — enable dev reload
- RELOAD_DIRS (default: `src`) — comma-separated list
- RELOAD_INCLUDE (default: `*.py`) — comma-separated patterns (sets RELOAD_INCLUDES)
- RELOAD_EXCLUDE (default: `logs/*`) — comma-separated patterns (sets RELOAD_EXCLUDES)
- TIMEOUT_GRACEFUL_SHUTDOWN (default: `3`) — seconds
- TIMEOUT_KEEP_ALIVE (default: `5`) — seconds

Client reconnect tip:
- After a reload, Cursor may not reconnect automatically. Toggle the MCP server in Cursor settings off → on to reconnect.

## Transport security (DNS rebinding protection)
FastMCP validates the `Host` and `Origin` headers and returns HTTP 421/403 for values not on the allowlist. Each entry supports an exact match or a trailing `:*` port wildcard (e.g. `host.docker.internal:*`).
- MCP_ENABLE_DNS_REBINDING_PROTECTION (default: `true`) — set `false` only in trusted networks
- MCP_ALLOWED_HOSTS (default: `127.0.0.1:*,localhost:*,[::1]:*,host.docker.internal:*`) — comma-separated allowed `Host` values
- MCP_ALLOWED_ORIGINS (default: `http://127.0.0.1:*,http://localhost:*,http://[::1]:*,http://host.docker.internal:*`) — comma-separated allowed `Origin` values

The `host.docker.internal:*` defaults let sibling containers (e.g. devcontainers) reach the server. Add custom hostnames here when reaching the server under a different name.

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
