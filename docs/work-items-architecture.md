## Work Items Architecture Plan

This document captures the agreed direction for evolving the system to support a three-layer hierarchy (plan → stories → tasks), unify story and task under a common model, and store human-editable artifacts with structured metadata.

### Goals
- Introduce tasks as first-class objects under stories, enabling agent-friendly granularity.
- Unify Story and Task via a shared base ("WorkItem") to centralize status/priority rules and utilities.
- Keep `plan.yaml` as the canonical source of truth; mirror select fields to Markdown files with YAML front matter.
- Maintain incremental migration with minimal disruption to existing behavior.

### Hierarchy
- Plan → Stories → Tasks
- Plan remains a container/aggregate, not a WorkItem.

### Models
- Shared constants:
  - `ALLOWED_STATUSES = {TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED}`

- Base type:
  - `WorkItem` exists and defines common fields: `id`, `title`, `status`, `depends_on: List[str]`, `notes`, `creation_time`, `completion_time`, `priority`.
  - Validators: status whitelist; priority in [0..5].

- Story type (current implementation):
  - `Story(BaseModel)` (not a subclass of `WorkItem` for simplicity right now)
  - Fields: `id`, `title`, `status`, `details`, `depends_on`, `notes`, `creation_time`, `completion_time`, `priority`, `tasks: List[Task]` (embedded).

- Task type:
  - `Task(WorkItem)` with `story_id` (and optionally `details`). `assignee` is a backlog item.

### Identifiers
- Story IDs: slugified from title (current behavior), lowercase underscore format.
- Task IDs: slugified title, unique within story. Global reference form: `storyId:taskId`.

### File Layout (Human-Editable Artifacts)
- Story file: `todo/<story_id>/story.md`
- Task files: `todo/<story_id>/tasks/<task_id>.md`
- Rationale: predictable, scales, keeps story bundle together.

### File Format: Markdown + YAML Front Matter
- Each file starts with a `---` YAML block mirroring the model, followed by free-form Markdown content.
- Include `schema_version: 1` for migration safety.
- Timestamps: ISO 8601 Z (e.g., `2025-08-28T14:03:12Z`).
- Only write non-null fields (keys with `None` are omitted). When transitioning away from DONE, `completion_time` is removed instead of set to `null`.

Example story.md front matter (note: `tasks` lists only task IDs):

```yaml
---
schema_version: 1
kind: story
id: story_a
title: Story A
status: TODO
priority: 2
depends_on: []
notes:
creation_time: 2025-08-28T14:03:12Z
completion_time:
tasks: [story_a:task_1, story_a:task_2]
---
```

Example task.md front matter:

```yaml
---
schema_version: 1
kind: task
id: story_a:task_1
title: Implement parser
status: IN_PROGRESS
priority: 1
depends_on: []
assignee:
notes:
creation_time: 2025-08-28T14:05:00Z
completion_time:
---
```

### Canonical Data and Synchronization
- Canonical: `plan.yaml` (Pydantic models: Plan → Story → Task).
- Mirroring policy:
  - On create/update in plan: update front matter in corresponding Markdown files; preserve body content by default.
  - On delete in plan: best-effort delete associated files.
  - No automatic sync from files → plan. Optionally add a separate "import/sync" tool later.

### Utilities (Generic, Unified)
- File I/O helpers (Markdown + front matter):
  - `save_item_to_file(path: str, item: WorkItem, content: Optional[str] = None, overwrite: bool = False) -> None`
    - Creates dirs; if file exists and `overwrite=False`, merge front matter and keep body; else replace with provided content.
    - Atomic write (temp file + rename).
  - `update_item_file(path: str, item: WorkItem, content: Optional[str] = None) -> None`
    - Merge-only convenience wrapper.
  - `read_item_file(path: str) -> tuple[dict, str]`
    - Parse front matter if present; returns `(front_matter, body)`.

- Back-compat wrappers:
  - `save_story_to_file(...)` → calls `save_item_to_file(..., kind=story)`.
  - Future: `save_task_to_file(...)` → calls `save_item_to_file(..., kind=task)`.

### API/Tooling Changes
- Story CRUD: retain existing endpoints, add calls to file mirroring helpers after successful plan save.
- Task CRUD (new):
  - `create_task(story_id, title, priority="6", depends_on="", notes="")`
  - `get_task(story_id, task_id)`
  - `update_task(story_id, task_id, ...)`
  - `delete_task(story_id, task_id)`
- ID generation: reuse existing slug logic; ensure uniqueness (story scope for tasks).
- Listing and diagnostics:
  - `list_tasks(statuses, story_id=None)`
  - `explain_task_blockers(story_id, task_id)`

### Dependency Semantics
- `depends_on` accepts IDs of same kind or cross-kind:
  - Story depends on story: `storyB`
  - Task depends on task: `storyA:task1`
  - Task depends on story: `storyB`
- Validate existence; disallow self-dependency.

### Migration Plan (Incremental, Low Risk)
1. Phase 1 (models + plan only)
   - Introduce `WorkItem` base and `Task` model; keep `Story` standalone.
   - Extend Plan to hold `tasks` under each `Story` (embedded models).
   - Add CRUD for tasks operating solely on `plan.yaml`.

2. Phase 2 (file mirroring)
   - Implement generic file helpers and integrate into create/update/delete for stories and tasks.
   - Existing `todo/<id>.md` story files remain valid; on touch, migrate to story folder layout.

3. Phase 3 (optional tooling)
   - Add "sync from files" command for manual imports.
   - Add lightweight search/index tooling over front matter for agent prompts.

### Rollback & Safety
- All mirroring is best-effort; plan operations succeed even if file I/O fails.
- Atomic writes prevent partial files.
- Logging at info/warn levels for observability.

### Notes and Backlog
- Decision: `Story.tasks` embeds `Task` objects in the plan; story front matter lists only task IDs.
- Potential additions: labels/tags, epic links, story points, `assignee` on `Task`.
- Access policy: who/what updates front matter vs. plan data (currently plan is canonical; mirroring is best-effort).


