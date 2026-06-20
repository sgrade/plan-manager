# Architecture

## Storage

All data is file-based under `TODO_DIR` (default: `./todo`).

```
TODO_DIR/
├── plans/
│   └── index.yaml          # lists all plans, tracks `current` plan ID
├── <plan_id>/
│   ├── plan.yaml            # plan manifest
│   ├── state.yaml           # current_story_id, current_task_id
│   ├── activity.yaml        # activity log
│   └── <story_id>/
│       ├── story.md         # story with YAML frontmatter
│       └── tasks/
│           └── <task_id>.md # task with YAML frontmatter
```

No database is used. Repositories read/write these files directly via `io.file_mirror` (atomic writes).

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
    - TODO_DIR=/data
  volumes:
    - ~/.local/share/plan-manager:/data
  ports:
    - "8105:3000"
  restart: unless-stopped
```

`HOST=0.0.0.0` is required so the server is reachable from outside the container (the default `127.0.0.1` only binds to loopback).

`/health` returns `{"status": "ok"}` for Docker healthchecks and probes.

## Known Limitations

### Single active project

`index.yaml` stores one global `current` plan ID. Tools that omit `plan_id` default to this value. All connected clients share the same `current` plan — there is no per-session or per-workspace scoping.

**Impact**: the server handles one active project at a time. If two Cursor workspaces connect simultaneously, they compete over which plan is "current."

**Workaround**: run a second container instance with a different port and volume — no code changes needed.

**Future**: proper multi-project support would require session-scoped plan context.

### No file locking

Concurrent writes to the same plan files are not serialized. Atomic writes (`file_mirror.atomic_write`) prevent partial writes but don't prevent race conditions between clients.
