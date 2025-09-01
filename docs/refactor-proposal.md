## Refactor overview

### Context
- This document now distinguishes between the completed refactor (Phase 1) and a proposed follow-up (Phase 2) regarding MCP parameter schemas.

### Problem (addressed in Phase 1)
- Duplicated logic across `story_service.py` and `task_service.py` (ID generation, parsing, dependency checks, file writes, status handling).
- Stringly-typed inputs (comma-delimited `depends_on`, magic priority string "6") scattered inside services.
- Inconsistent validation and status transitions; frontmatter merging repeated inline.

### Phase 1 (Completed): unify CRUD, typed services, centralized rules
- Make service functions the typed, canonical API:
  - `story_service.create_story(title: str, priority: Optional[int], depends_on: list[str], notes: Optional[str])`
  - `story_service.update_story(..., depends_on: Optional[list[str]], priority: Optional[int], status: Optional[Status])`
  - `task_service.create_task(story_id: str, title: str, priority: Optional[int], depends_on: list[str], notes: Optional[str])`
  - `task_service.update_task(..., depends_on: Optional[list[str]], priority: Optional[int], status: Optional[Status])`
  - `task_service.list_tasks(statuses: Optional[list[str]], story_id: Optional[str])`
- Keep MCP tool wrappers as the transport boundary; they parse strings into typed values and register tools with FastMCP.
- Extract shared helpers in `services/shared.py`:
  - `generate_slug`, `parse_status`, `validate_and_save`, `write_story_details`, `write_task_details`, `find_dependents`, `merge_frontmatter_defaults`.
- Centralize validation via `validate_and_save(plan)` (calls domain validation and persists) after mutations.
- Set defaults in `WorkItem` (status=TODO, creation_time=UTC now) so services don’t set them manually.
- Use `apply_status_change` and `rollup_story_status` consistently.
- Use `merge_frontmatter_defaults` in `get_task`/`list_tasks` to avoid repeated frontmatter merging code.

### Phase 1 — Key changes (implemented)
- Services now accept typed inputs; parsing moved to MCP wrappers.
- `create_*`/`update_*`/`delete_*` logic unified; ad hoc dependency checks removed in favor of `validate_and_save` and `find_dependents` for delete.
- Redundant underscored variants removed; single canonical function per operation.
- Frontmatter merging centralized for tasks.

### Phase 1 — Impact
- Less duplication, clearer responsibilities, easier testing.
- Behavior of MCP tools remains compatible (wrappers still accept strings today). Services are typed; wrappers perform normalization.

### Phase 2 (Proposed): structured, typed MCP parameters/outputs
- Goal: change MCP tool parameter schemas to typed inputs (arrays/ints/enums) so wrappers become pass-through and parsing is removed.
- Changes:
  - Update tool signatures in `tools/story_tools.py` and `tools/task_tools.py` to use typed annotations directly (e.g., `Optional[int]`, `list[str]`, `Status | Literal[...]`).
  - Remove parsing helpers from wrappers; pass values straight to services.
  - Optionally define Pydantic response models for structured outputs.
- Backward compatibility: this is a breaking change for clients sending comma-separated strings. Mitigations:
  - Introduce parallel v2 tool names (e.g., `create_story_v2`) temporarily, or coordinate a client update window.
  - Document the new schemas via the MCP-derived JSON schema.
- Reference: MCP structured parameters/outputs pattern (`https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/snippets/servers/structured_output.py`).

### Phase 2 — Scope (if approved)
- Files: `src/plan_manager/tools/story_tools.py`, `src/plan_manager/tools/task_tools.py` (signatures, remove parsing). No service changes required.


### Follow-ups (optional)
- Switch MCP tool parameter schemas to typed inputs (arrays/ints/enums) and drop parsing in wrappers.
- Define Pydantic response models for stronger output contracts (`StoryOut`, `TaskOut`, `TaskListItem`).

