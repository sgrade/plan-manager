## Refactor Proposal: Services, Utilities, and Clean Code Improvements

This document proposes incremental refactors to improve clarity, maintainability, and testability, without changing current behavior.

### Objectives
- Separate domain models from orchestration (services vs. data models)
- Centralize dependency validation and status transitions
- Encapsulate file mirroring concerns
- Improve typing, docstrings, and logging consistency
- Enable safer plan writes and easier testing
- Keep implementation simple and stateless where possible (12‑factor aligned)

### Proposed Structure (function-first, stateless)

```
src/plan_manager/
  domain/
    models.py              # Story, Task, Status enum (re-export in __init__)
  services/                # prefer function-based modules (stateless)
    plan_repository.py     # load/save plan, optional file locking helper
    story_service.py       # story CRUD, rollup, validations (functions)
    task_service.py        # task CRUD, dependency checks, blockers (functions)
    validation.py          # graph/dependency checks utils
    status.py              # transitions for status/completion_time
  io/
    file_mirror.py         # front matter read/write for stories/tasks
    paths.py               # slugify, file path helpers
  tools/
    story_tools.py         # thin MCP wrappers
    task_tools.py          # thin MCP wrappers
```

Initial step can be non-invasive: create `services/` and `io/` modules and move logic (functions). Prefer deleting superseded code over keeping wrappers. If other areas (e.g., archiving) break, temporarily comment them out and fix in a later pass.

### Key Changes

1) Domain and Services
- Keep `Story`, `Task`, `Plan` as Pydantic models (pure data).
- Provide repository/service as stateless functions (no in-memory state/caches).
- Optional file lock helper only around writes if/when needed.
- Story/Task service functions:
  - Validate inputs (dependencies, uniqueness)
  - Apply status transitions via `status.py`
  - Persist once at the end (single save per operation)
  - Trigger file mirroring via `file_mirror.py`

2) Validation
- Extract dependency checks to `validation.py`:
  - Validate story depends_on
  - Validate task depends_on (local and fully-qualified)
  - Guard self-dependency
  - Optional simple cycle detection per story (DAG check)
- `Plan` model validator calls into `validation.py` to enforce invariants.

3) File Mirroring
- `file_mirror.py`:
  - `write_story(story: Story, body: str | None)`
  - `write_task(task: Task, body: str | None)`
  - `update_story_front_matter(story)`, `update_task_front_matter(task)`
  - Internally normalize datetimes to ISO Z; ensure `schema_version` and `kind`.
- `paths.py` provides `slugify`, `story_file_path(story_id)`, `task_file_path(story_id, local_task_id)`.

4) Status Modeling (do now)
- Introduce `Status(Enum)` with values `TODO`, `IN_PROGRESS`, `DONE`, `BLOCKED`, `DEFERRED`.
- Models accept `Status | str`; validators normalize to `Status` internally; MCP/tool I/O returns uppercase strings for wire-compat.
- `status.py` helpers:
  - `apply_status_change(obj, new_status: Status)` sets/unsets `completion_time` appropriately.
  - `rollup_story_status(story)` derives story status from embedded tasks.

5) MCP Tools
- Move logic out of tools; tools call services and return DTOs.
- Keep current tool signatures for compatibility.

6) Typing, Docstrings, Logging
- Add explicit return types for all public functions.
- Use concise Google-style docstrings.
- Keep logs at info for lifecycle and warning for best-effort failures; include IDs in messages.

7) Safety and Testing (current phase scope)
- Prefer stateless, idempotent operations; add a simple file lock helper only if concurrency issues appear.
- Tests (minimal for now):
  - One MCP E2E smoke test covering story→tasks→blockers→rollup lifecycle.
  - A couple of focused unit tests for dependency validation and status transitions.
  - Defer broader test coverage until after upcoming model/workflow/archiving refactors.

### Incremental Plan

1. Extract `file_mirror.py` and `paths.py`; update current code to use them.
2. Create `PlanRepository` and adapt load/save usage.
3. Move task logic into `TaskService`; tools call service.
4. Move story logic into `StoryService`; tools call service.
5. Introduce `Status` enum and `status.py` helpers; update models and services to use them.
6. Extract validation logic to `validation.py`; keep `Plan` validator delegating to it.
7. Add tests alongside services; keep behavior identical.

### Follow-ups and Alignment Items

- Story front matter tasks list
  - Desired: `tasks` should contain only task IDs (e.g., `[story_a:task_1, story_a:task_2]`).
  - Rationale: smaller files, no duplication; plan remains canonical for full task data.
  - Action: when writing a `Story` front matter, map `tasks` → `[t.id for t in story.tasks]`.

- ID generation
  - Desired: standardize on `io/paths.py#slugify` for both stories and tasks.
  - Rationale: single source of truth, consistent slugs.
  - Action: replace local slugify logic in services with `paths.slugify`.

- Enum serialization in front matter (implemented)
  - Change: front-matter writing uses `model_dump(mode='json', exclude_none=True)` to serialize `Status` enums as strings before YAML dump.
  - Outcome: prevents YAML errors like "cannot represent an object <Status.DONE: 'DONE'>".

- Docstrings and typing (quick hygiene)
  - Desired: concise Google-style docstrings and explicit return types for public functions in `services/` and `io/`.
  - Rationale: readability, discoverability, easier maintenance.
  - Action: short pass adding docstrings and return types where missing.

- Legacy helpers in `plan.py`
  - Current: legacy `load_plan_data/save_plan_data/add_story_to_plan/remove_story_from_plan` retained for archive flows.
  - Desired: consolidate plan I/O in `services/plan_repository.py` and remove legacy helpers.
  - Action (medium-term): refactor `archive.py` to use `plan_repository` and then remove legacy helpers from `plan.py`.

### Non-Goals (for now)
- No behavior changes to external MCP tool surfaces.
- No migration of stored data formats beyond already adopted front matter layout.
- No introduction of long-lived in-memory state or caches (12‑factor aligned).

- Risk: Refactor causing regressions.
  - Mitigation: Incremental steps with smoke tests; remove superseded functions immediately; if dependent modules break, comment them out and schedule fixes.
- Risk: Over-abstraction.
  - Mitigation: Favor functions over classes, keep modules small, avoid unnecessary layers. Stay stateless (12‑factor). Add abstractions only when a concrete need emerges.


