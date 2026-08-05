# Architecture

## Storage

Plan Manager persists runtime state in SQLite, managed by `src/plan_manager/storage/` and accessed through repository primitives (`storage/repositories.py`) inside service unit-of-work transactions.

- DB engine: SQLite with WAL mode enabled.
- Main entities: plans, stories, tasks, per-plan state pointers, and events.
- Validation and status rollups run in services; writes are transactional via `storage/uow.py`.

The legacy YAML tree under `TODO_DIR` is no longer the runtime source of truth. It remains for migration input (`pm import`) and as a future export target.

## Deployment Modes

### Development (devcontainer)

```
uv run pm  →  uvicorn on 127.0.0.1:3000
```

Cursor connects via `.cursor/mcp.json` with `"url": "http://localhost:3000/mcp"`. The process is not managed by Cursor; start and stop it manually.

### Production (Docker Compose)

A production `Dockerfile` at the repo root builds a minimal image. Intended to run alongside other MCP services via Docker Compose (e.g., in a `~/tools` setup):

```yaml
plan-manager:
  build:
    context: https://github.com/sgrade/plan-manager.git
    dockerfile: Dockerfile
  environment:
    - HOST=0.0.0.0
    - PLAN_MANAGER_DB_DIR=/data
    - TODO_DIR=/legacy
  volumes:
    - plan-manager-db:/data
    - ~/.local/share/plan-manager:/legacy
  ports:
    - "8105:3000"
  restart: unless-stopped
```

Warning: publishing a port (for example `8105:3000`) makes the unauthenticated `/ui` supervision page world-readable to anything that can reach that host/network. Prefer loopback-only binding unless the network is trusted.

`HOST=0.0.0.0` is required so the server is reachable from outside the container (the default `127.0.0.1` only binds to loopback).

`/health` returns `{"status": "ok"}` for Docker healthchecks and probes.

## Known Limitations

### Explicit scope model

Plan Manager no longer has a global current-plan pointer. Every plan-scoped tool call must include `plan_id` explicitly, and workflow mutations additionally require explicit `task_id`. This makes calls deterministic under concurrent multi-agent usage because scope is carried in arguments, not hidden server state.

Per-plan `current_story_id` and `current_task_id` remain available for discovery helpers (for example `get_current` and next-action suggestions), but they are not used as implicit selectors for correctness-critical mutations.

### No file locking

Concurrent writes to the same plan files are not serialized. Atomic writes (`file_mirror.atomic_write`) prevent partial writes but don't prevent race conditions between clients.
