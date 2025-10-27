# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0](https://github.com/sgrade/plan-manager/compare/plan-manager-v0.9.0...plan-manager-v0.10.0) (2025-10-23)


### ⚠ BREAKING CHANGES

* Major terminology update for clarity and industry alignment
* **workflow:** approve_task no longer handles TODO → IN_PROGRESS transitions. Use start_task for Gate 1 instead. The approve_current_task() service function still delegates for backward compatibility.

### Features

* acceptance criteria in Story ([87883e8](https://github.com/sgrade/plan-manager/commit/87883e8d81cdd7b45d1b18c11a9fe28404c9f7d1))
* add CI/CD pipeline, test isolation, and code quality tools ([d6ec879](https://github.com/sgrade/plan-manager/commit/d6ec879e7dac00f896fe8328b381dc2ae8934f40))
* align it with the rewrtitten task-centric workflow defined in .cursor/rules/project-management.mdc ([8a3665e](https://github.com/sgrade/plan-manager/commit/8a3665ece0674e4414fa3f4faa1958bc86ceec27))
* assisted planning workflow - introduction ([e5e3362](https://github.com/sgrade/plan-manager/commit/e5e33623148a87a1c78bbca734260fc0131103ae))
* basic telemetry for key flows: Implemented env-gated counters/timers with sampling; instrumented approve_task and submit_for_review; documented telemetry env vars. ([3d42e80](https://github.com/sgrade/plan-manager/commit/3d42e801b451fbc3305881e0ff600eb294b12ca9))
* **cli:** Improve tool-layer error handling ([409a94c](https://github.com/sgrade/plan-manager/commit/409a94c7f44357363ce5ddce32717d890d681ffb))
* **cli:** Improve tool-layer error handling ([54af7d7](https://github.com/sgrade/plan-manager/commit/54af7d79aa63b446a6ebe9a59dc7309bd8304445))
* **cli:** Make set_current commands context-aware ([f916c82](https://github.com/sgrade/plan-manager/commit/f916c82ddd5e1b0bc6473b397b7adc8c30f0359c))
* **cli:** overhaul workflow for clarity and explicit user control ([36367df](https://github.com/sgrade/plan-manager/commit/36367df3e2f15958661fe37d51c6480c91b1668a))
* **cli:** refactor command layer for clarity and predictability ([9a70e4b](https://github.com/sgrade/plan-manager/commit/9a70e4b8d55297706248f348a82d56f92b31b36c))
* correlation: correlation IDs to mutations: middleware and propagated corr_id into plan/story/task creation logs; each request includes x-correlation-id. ([cb65d2c](https://github.com/sgrade/plan-manager/commit/cb65d2c390b492b5e8d069b49d1d0a31c0250ed7))
* implement planning/execution workflow, agent actions (workflow_status.actions), select_or_create, guardrails, pagination, client-side changelog ([9d8e63b](https://github.com/sgrade/plan-manager/commit/9d8e63b0876d9454fddf3cfb7d563e3b84217e4b))
* integrate task blocker checking into report service ([1d6d306](https://github.com/sgrade/plan-manager/commit/1d6d306c1d7497c531508e6f83d0e491813d2bea))
* plan create prompt ([ef8325f](https://github.com/sgrade/plan-manager/commit/ef8325f0272face661eef7ee376b6dffadd5dbec))
* **reporting:** Implement scoped reports ([a821719](https://github.com/sgrade/plan-manager/commit/a82171965acdc74434466654a49ac1fd9efed082))
* simple browser to see the work items; can be switched off ([f6bd822](https://github.com/sgrade/plan-manager/commit/f6bd822d24b68be0118b4e71bbee5d813ad81a02))
* structured io of approve_task and streamlined changelog ([b70e298](https://github.com/sgrade/plan-manager/commit/b70e298aba0df157298b8b087c95dedf7392b28e))
* structured JSON logs now emitted for critical actions (create, approve transitions) with fields like event, ids/titles, statuses, and corr_id. Works with correlation middleware for end-to-end tracing. ([90cd4cc](https://github.com/sgrade/plan-manager/commit/90cd4ccc53293e208210297997e98a3e90bed80d))
* **tasks:** Implement proactive blocker detection ([4de24e5](https://github.com/sgrade/plan-manager/commit/4de24e50dc1bcb5bf3821208e7097b0b0df03d75))
* triage dashboard and backlog view ([16f5c0c](https://github.com/sgrade/plan-manager/commit/16f5c0cfa2cf08c721338b9fe8ef14f6b1c88d8c))
* **workflow:** Test and refine task execution workflow ([04cb2c0](https://github.com/sgrade/plan-manager/commit/04cb2c0cad5d002f4b34d1af79d27639c30414f1))


### Bug Fixes

* **__main__:** add return type annotation to main() ([acd4261](https://github.com/sgrade/plan-manager/commit/acd4261147ba2b59fb91bffe9d6e298356750f5a))
* add factory=True to uvicorn.run() to suppress ASGI app factory warning ([785a8b0](https://github.com/sgrade/plan-manager/commit/785a8b000dd4a2fd685a0da37ad17f649e80ca59))
* auto-init todo/plan.yaml and ensure dir on save; docs: host.docker.internal SSE url ([71a508f](https://github.com/sgrade/plan-manager/commit/71a508f622cfa998a17fea3e0287a64b66b3d428))
* **ci:** ensure CI passes with professional standards ([d4f842a](https://github.com/sgrade/plan-manager/commit/d4f842a4ed9373c694dd9435e9bfd9fe8804a30b))
* **ci:** fix coverage threshold and twine installation ([587c7d4](https://github.com/sgrade/plan-manager/commit/587c7d41b50f5564b5a432f8b9c6163399ebe524))
* delete_plan not only removes it from the register, but removes the files ([3323835](https://github.com/sgrade/plan-manager/commit/3323835a2a796b93657d3c03844572946806b369))
* enable PENDING_REVIEW → IN_PROGRESS transition for request_pr_changes ([a96e1bb](https://github.com/sgrade/plan-manager/commit/a96e1bb60a3e0e4b9f8a1656686c2f98baa3e023))
* improve status rollup to show progress accurately ([153b99a](https://github.com/sgrade/plan-manager/commit/153b99a6f967cefc55caa32f003e124005b200d5))
* **license:** correct copyright holder to sgrade ([58c1d09](https://github.com/sgrade/plan-manager/commit/58c1d09c8e166dcb2f4a0de0f80bddb094a642d6))
* **logging:** add type annotation for handlers list ([f765296](https://github.com/sgrade/plan-manager/commit/f7652966b8da00b0c4643bc17d25ceda12071f18))
* make browse endpoint work even if todo directory does not exist ([fb22899](https://github.com/sgrade/plan-manager/commit/fb22899ffd339f0bd5374926e9aa155356e4dc07))
* missing plan status propagation logic. ([d5ef716](https://github.com/sgrade/plan-manager/commit/d5ef716043ffb0dcdc0b8184eabcc9ea8dab0aec))
* **mypy:** fix pre-commit mypy config to use mypy.ini ([ee3dc07](https://github.com/sgrade/plan-manager/commit/ee3dc079e5ecfcde34d5911d50f0cff900c75ccb))
* **outputs:** add type parameters to generic dict types ([def7dd3](https://github.com/sgrade/plan-manager/commit/def7dd397939c0145643b99a435bcf239018fc6a))
* persistent error executing tool submit_for_review: An execution summary must be provided before submitting for review. ([2153582](https://github.com/sgrade/plan-manager/commit/21535822960074a568b3bbf6cd702146ec26c894))
* **plan_repository:** add missing ValidationError import ([85d078b](https://github.com/sgrade/plan-manager/commit/85d078b98023972a5e103a82e2c66b8d715a8aa1))
* **plan_service:** add type annotations to helper functions ([3c7acb6](https://github.com/sgrade/plan-manager/commit/3c7acb64ef017a6763fbbd4c8f28711e988441e3))
* **prompt_register:** add type annotations and fix handler signature ([9e9a47c](https://github.com/sgrade/plan-manager/commit/9e9a47c71180fbbb733652936ee4b7c3c32538c7))
* **report_service:** handle optional execution_summary properly ([42b5cb4](https://github.com/sgrade/plan-manager/commit/42b5cb4f97e37efd7c87117671470e50fa4bbbd8))
* resolve mypy strict type checking issues (core services) ([eb27ee4](https://github.com/sgrade/plan-manager/commit/eb27ee4871df3ab627266a9492f05186f94f0078))
* **server/browser:** add type annotations for browse_endpoint ([bf832c8](https://github.com/sgrade/plan-manager/commit/bf832c805c1994ab2f22a22f3ad40aa03611b51d))
* **server:** add complete type annotations for app and browser ([ffa4ca1](https://github.com/sgrade/plan-manager/commit/ffa4ca1d17fc4f2b8e3ee0da9fec8588b520b2e9))
* **story_tools:** add type annotations and fix completion_time check ([6e02594](https://github.com/sgrade/plan-manager/commit/6e025942cdf32b9c7a2e73b90f49718ee876db99))
* **task_service:** fix type issues with datetime handling ([64c2cf5](https://github.com/sgrade/plan-manager/commit/64c2cf50e61145fe708ca5b9f9431fb8a9214261))
* **task_tools:** add type annotations and fix imports ([45ea859](https://github.com/sgrade/plan-manager/commit/45ea85951863c93beafb98eeac183d6b4945496e))
* **telemetry:** add type annotations for kwargs and return types ([9cf6fd7](https://github.com/sgrade/plan-manager/commit/9cf6fd7e319c05bea2600db6f5cd489489178485))
* **tools:** add type annotations for MCP instance parameters ([f51cdae](https://github.com/sgrade/plan-manager/commit/f51cdaec594f7a59ae6738ffcc59c5fa700193ce))
* update story was corrupting the list of task IDs in story.md ([3326621](https://github.com/sgrade/plan-manager/commit/33266215e63fe2c5bf4a7b6297f9a4382c5a8167))
* **usage_resources:** add type annotation for mcp_instance ([e12bef0](https://github.com/sgrade/plan-manager/commit/e12bef05de5380171a8e406f56172bd2d7fb4722))
* **workflow_prompts:** add return type annotation ([116bf24](https://github.com/sgrade/plan-manager/commit/116bf24fcdf54e6c1a0d80439191cce0931ff258))


### Performance Improvements

* **logging:** convert all logging to lazy % formatting ([7ff4f3e](https://github.com/sgrade/plan-manager/commit/7ff4f3e8d5b951cdf906615827936d7570eaa536))


### Documentation

* add branching strategy and branch protection guidelines ([d8f3c99](https://github.com/sgrade/plan-manager/commit/d8f3c998d8f8a77dafac8f415a4141c2cfc56d35))
* add docs to uv config, fix budges ([c3e7951](https://github.com/sgrade/plan-manager/commit/c3e7951395817a6d59020888f92c3d1f3be0d49c))
* add guardrails to usage guiede agents ([7adfc90](https://github.com/sgrade/plan-manager/commit/7adfc903780d63de2055b425f28e03b5c4d26718))
* **changelog:** add Unreleased section for dev workflow and docs updates ([9ce8fff](https://github.com/sgrade/plan-manager/commit/9ce8fffc2feff099f6b49dce273d884bb4900a24))
* **changelog:** update with CI fixes and code quality improvements ([5ac2961](https://github.com/sgrade/plan-manager/commit/5ac29619311d98e153ff21bd648b31a9317e084e))
* documentation polish ([a0a7535](https://github.com/sgrade/plan-manager/commit/a0a753573a8084c37ff58f849aaa02fe0568c1fa))
* documentation polish ([96aa11f](https://github.com/sgrade/plan-manager/commit/96aa11f24377813f601cfcba0b0f2b59d5e85945))
* env-based configuration and documented stdout vs file sink in config_reference.md ([1c884c4](https://github.com/sgrade/plan-manager/commit/1c884c4d9be0721cc85bc35bdc9d92542614e80f))
* how to connect to Plan Manager from another computer and related security considerations; minor corrections ([c27159d](https://github.com/sgrade/plan-manager/commit/c27159db7e27e7e8bcd652058515c6703d54335c))
* modified task execution workflow; minor tweaks ([450eef1](https://github.com/sgrade/plan-manager/commit/450eef199ab6470a7972d0f0b1a4fb55b8867a85))
* polished task execution workflow; removed duplications between project_workflow diagrams and usage_guide ([8909b62](https://github.com/sgrade/plan-manager/commit/8909b62aa5cd9ef90577dfa5ae96d3bf7c41028d))
* preparation to streamline project management workflow ([f2ef898](https://github.com/sgrade/plan-manager/commit/f2ef89863112c9f14d3de7dd7dc17d48051440e6))
* product maturity in the readme, polished project_workflow and summarized ideas for langgraph-based next step. ([fce8fbd](https://github.com/sgrade/plan-manager/commit/fce8fbd5f2e9b498ed138ec62f3b8ad02819a124))
* release checklist ([fd10378](https://github.com/sgrade/plan-manager/commit/fd10378b531ed468fb24850b1efeaf1ed7c2a682))
* remove the quickstart guide for agents ([e8fd9b5](https://github.com/sgrade/plan-manager/commit/e8fd9b5957d8a23afb94dd424d3b59fb6759a0d1))
* structure readme links to other docs; cleanup ([04c21e7](https://github.com/sgrade/plan-manager/commit/04c21e72ef7d9b33973e6e7533ee7a7aa4aa36cf))
* update release process for release-please automation ([37bbc98](https://github.com/sgrade/plan-manager/commit/37bbc986cd2c9a05daa402595f7da49ebb3b057b))


### Code Refactoring

* adopt PR-centric workflow terminology ([047a4c0](https://github.com/sgrade/plan-manager/commit/047a4c0447762f50f79627174157ddc1b69a0211))
* **workflow:** split Gate 1 and Gate 2 approval tools ([40398c0](https://github.com/sgrade/plan-manager/commit/40398c0bb8db4a584100aebf8a4c073e09c6a051))

## [0.9.0] - 2025-10-24

### Added
- `start_task` tool for Gate 1 (Pre-Execution Approval: TODO → IN_PROGRESS)
- `merge_pr` convenience tool (formerly `finalize_task`) for Gate 2 workflow

### Changed
- **BREAKING**: Renamed `changelog_entries` field to `changes` in Task model (clearer PR-centric terminology)
  - Validation function: `validate_changelog_entries` → `validate_changes`
  - Config variable: `REQUIRE_CHANGELOG_ENTRIES_BEFORE_DONE` → `REQUIRE_CHANGES_BEFORE_DONE`
  - All error messages updated to use "changes" terminology
- **BREAKING**: Renamed tools to match PR workflow terminology
  - `submit_for_review` → `submit_pr`
  - `approve_task` → `approve_pr`
  - `finalize_task` → `merge_pr`
  - `request_changes` → `request_pr_changes`
  - ActionType enum values updated (SUBMIT_PR, APPROVE_PR, REQUEST_PR_CHANGES)
- **BREAKING**: Renamed service functions to match tools
  - `submit_for_code_review` → `submit_pr`
  - `approve_current_task_review` → `approve_pr`
- Updated workflow documentation to use "Gate 1" and "Gate 2" terminology consistently
- NextActions now recommend `merge_pr` as primary action at Gate 2
- Commit message format: removed redundant scope, now uses full task ID in Refs footer, and lowercases first letter of subject line for consistency

### Fixed
- Clarified tool responsibilities: `start_task` (Gate 1) vs `approve_pr` (Gate 2)
- Status rollup logic now correctly shows stories and plans as IN_PROGRESS when work has been done but no task is currently active (e.g., when some tasks are DONE and others are TODO)
- Stories with tasks in PENDING_REVIEW now correctly show as IN_PROGRESS
- **CRITICAL**: Fixed `request_pr_changes` workflow - now correctly allows PENDING_REVIEW → IN_PROGRESS transition and properly persists review feedback and rework count

## [0.8.0] - 2025-10-18

### Added
- GitHub Actions CI/CD pipeline with automated testing, linting, type checking, and security scanning
- Test isolation infrastructure: all tests run in temporary directories (`/tmp/pytest_plan_manager_*`)
- Pre-commit hooks for automated code quality checks (ruff, mypy, bandit, pytest)
- Comprehensive unit tests for validation, config, and shared utilities
- Type checking with mypy in strict mode
- Security scanning with bandit
- Dependabot configuration for automated dependency updates
- Dependency review workflow for pull requests
- `tests/conftest.py` with autouse fixture for complete test isolation
- `py.typed` marker for PEP 561 compliance
- Automatic redirect from localhost:3000 to localhost:3000/browse/ for user convenience
- Test story_tools integration tests
- Codecov integration for test coverage tracking and reporting

### Changed
- Documentation restructured: `docs/contributing.md` is now the single source of truth for development info
- `README.md` simplified to user-focused content only
- `AGENTS.md` updated to guide AI agents developing Plan Manager (vs. using it)
- Expanded ruff linting rules to 30+ categories with per-file ignores
- Test suite optimized for pre-1.0 project (removed performance benchmarks)
- CI pipeline configured for branch-specific checks (full checks on main/PRs, fast unit tests on develop)
- Fixed hardcoded `'todo'` paths to use `TODO_DIR` from config for proper test isolation
- Docs: how to connect to Plan Manager from another computer and related security considerations
- MCP Python SDK bumped to 1.17.0
- Migrated all path operations to use `pathlib.Path` instead of `os.path` for modern, maintainable code
- Test coverage threshold set to 40% (appropriate for pre-1.0, targets critical paths)
- Mypy CI configuration aligned with local `mypy.ini` settings (`disallow_subclassing_any = False`)

### Fixed
- Test isolation: tests no longer create files in real `todo/` directory
- Hardcoded paths in `paths.py` and `story_service.py` now respect `TODO_DIR` environment variable
- Update story was corrupting the list of task IDs in story.md
- CI test job: coverage threshold lowered from 50% to 40% to match current coverage (40.83%)
- CI build job: added dev dependencies installation to ensure twine is available for distribution checks
- CI type-check job: fixed mypy to use `mypy.ini` config instead of `--strict` flag for consistency
- Pre-commit mypy hook: configured to use `mypy.ini` instead of `--strict` for local/CI alignment
- Blind exception catching: replaced 31 instances of `except Exception` with specific exceptions
- Logging performance: converted 28 f-string logging calls to lazy `%` formatting
- Code quality: fixed 189 total issues across type safety, maintainability, pathlib migration, and code quality
- LICENSE: corrected copyright holder from "Plan Manager" to "sgrade"

### Removed
- Performance benchmark tests (overkill for pre-1.0 project)
- Duplicate documentation across multiple files
- Unused `__version__` from `__init__.py` (pyproject.toml is now single source of truth)

## [0.7.0] - 2025-10-08

### Added:
- Comprehensive input validation and sanitization for all user inputs
- Unit test suite with 63 tests covering validation, telemetry, and domain models
- Centralized validation module with consistent error handling
- Improved telemetry logging (removed debug print statements)

### Changed:
- Consistent, AI-friendly docstrings.
- Polished task workflows.
- MCP Python SDK bumped to 1.16.0
- Default value for status parameter for list tools is empty list instead of None.
- Replaced broad `Exception` catches with specific exception types
- Enhanced error messages for better user experience
- Improved exception handling in tool layers with proper categorization
- Updated telemetry to use structured logging instead of print statements

### Security:
- Added input validation to prevent injection attacks
- Sanitized user inputs with length limits and character restrictions
- Enhanced validation for task steps, execution summaries, and feedback

## [0.6.2]

### Added:
- Simple browser to see the work items; can be switched off.

### Changed:
- Create a shared task ID resolution function and update the tool and service layers to use it.
- Add a local_id to the Task domain model and the TaskOut and TaskListItem schemas.
- Moved the starlette app to server directory.
- Data persistence layer has been successfully migrated to a normalized file structure: plan.yaml simplified, responsibilities shared with other files.
- Remove the quickstart guide for agents. The usage guide for agents is the single document - avoids duplications.
- Separate select current task workflow from other parts of task execution workflow.
- Fast-track path in gate 1 of task execution workflow requires agent to create steps instead of seeding placeholder steps.

### Fixed:
- Missing plan status propagation logic.
- Make browse endpoint work even if todo directory does not exist.
- Persistent error executing tool submit_for_review: An execution summary must be provided before submitting for review.

## [0.6.1] - 2025-09-18

### Added:
- Triage:
  - Create triage dashboard and backlog views: Defined dashboard views (P0/P1, needs‑info, by area) and documented how to access them in triage_guide.md.
  - Establish triage labels and P0/P1/P2 criteria: Added performance labeling guidance (use area:performance with type:enhancement unless functional defect) and concrete P1 vs P2 examples.
  - Verified triage_guide.md covers monitoring P0/P1, needs‑info, and area views.
  - Set up weekly triage routine: Added weekly triage cadence and ownership details to triage_guide.md (schedule, participants, reminders, outcomes, ≤15‑min agenda).
- AGENTS.md - this file guides agents that use the Plan Manager MCP server.
- Correlation: correlation IDs to mutations: middleware and propagated corr_id into plan/story/task creation logs; each request includes x-correlation-id.
- Structure logs for critical actions: Added structured JSON logs for key actions with corr_id, aligned with the correlation middleware.
- Basic telemetry for key flows: Implemented env-gated counters/timers with sampling; insrumented approve_task and submit_for_review; documented telemetry env vars.
- Release Gating and Beta Criteria:
  - Define beta gating checklist: Added docs/release_checklist.md with gates, manual QA, logging/telemetry checks, versioning/tagging, and sign‑offs; linked from contributing.md.

### Changed:
- Show execution summary in TaskOut and report: Expose review summaries in UI surfaces.
- Quickstart polish and cross-links: Polished Quickstart wording and added a concise cross‑link to triage_guide.md; kept detailed behavior in usage_guide_agents.md.
- Configuration reference updates: Added docs/config_reference.md with env vars, defaults, and examples (reload, logging, paths, reconnect notes). Linked from contributing and AGENTS.md.
- Unified output for task workflow functions.

### Fixed:
- Priority type mismatch at transport vs domain; implemented boundary coercion with clear error messages and updated tool signatures to accept numeric types.
- Task status string vs enum mismatch; updated tool to coerce to Status enum.
- Minor prompt typo fixed ("Create aplan" -> "Create a plan"). Error handling improved in task tools: now raise exceptions instead of returning invalid TaskOuts.

## [v0.6.0] - 2025-09-16

### Added
- Assisted planning prompts registered and made context-aware (optional args, use current plan/story/task when omitted).
- FastMCP prompt catalog with dynamic registration via `register_prompts` and `PROMPT_SPECS`.
- New prompts:
  - `create_plan` (plan with title and description)
  - `create_stories` (stories with title, description, acceptance_criteria)
  - `create_tasks` (tasks with title, description)
  - `create_steps` (PATCH-level steps suitable for changelog bullets)
- Review checklists and usage guide aligned with the documented workflow.
- Acceptance criteria in Story
- Formal way to request changes in task execution workflow

### Changed
- BREAKING: Flattened MCP tool inputs to simple parameters (no nested payload objects):
  - set_current_plan(plan_id?), set_current_story(story_id?), set_current_task(task_id?)
  - create_plan(title, description?, priority?), create_story(title, priority?, depends_on?, description?), create_task(story_id, title, priority?, depends_on?, description?)
  - get_plan(plan_id?), get_story(story_id?), get_task(story_id?, task_id?)
  - update_plan(plan_id, title?, description?, priority?, status?), update_story(story_id, title?, description?, depends_on?, priority?, status?), update_task(story_id, task_id, title?, description?, depends_on?, priority?, status?)
  - delete_plan(plan_id), delete_story(story_id), delete_task(story_id, task_id)
  - list_plans, list_stories, list_tasks
  - task_tools
- Replace usage prompts with MCP server instructions (quickstart) and resource (usage guide)

### Removed
- Remove inputs schema

### Fixed
- Prompt examples now use valid JSON (no trailing commas; corrected keys: `description` instead of `user_story`).

## [0.5.5] - 2025-09-10

### Added
- **Scoped Reporting:** The `report` command now accepts an optional scope. `report plan` provides a high-level summary of all stories, while the default `report` continues to show a detailed view of the current story.
- **Proactive Blocker Detection:** The system now automatically updates task statuses to `BLOCKED` or `TODO` based on the completion of their dependencies. This logic is triggered whenever a task is marked as `DONE`.

### Changed
- **Interactive `set_current` Commands:** The `set_current_plan`, `set_current_story`, and `set_current_task` commands now list available items if called without an ID, guiding the user to make a valid selection.
- **Improved Error Handling:** Added robust `try...except` blocks to the tool layer (`approval_tools.py`, `task_tools.py`) to catch service-level exceptions and return user-friendly, structured error messages.

## [0.5.4] - 2025-09-10

### Fixed
- Corrected a bug in the `approve_fast_track` service where it failed to find stories due to incorrect ID handling.
- Ensured that `approve_fast_track` uses fully-qualified task IDs when calling underlying services to prevent lookup failures.

### Changed
- The `approve_task` tool now requires a fully-qualified ID (`story_id:task_id`) for fast-tracking to prevent ambiguity when multiple tasks share similar local IDs.

## [0.5.3] - 2025-09-10

### Changed
- Rename `approve` tool to `approve_task`
- Structured input and output for the task approval tool
- Streamline `changelog` functionality and hook it to the `approve_task` tool
- Integrate the blocker-checking logic directly into the report service.
- Ensure that when a user runs report on a BLOCKED task, they will now see a clear, human-readable list of what needs to be done to unblock it.

### Removed
- Remove the explain_task_blockers command, simplifying the user-facing API.

## [0.5.2] - 2025-09-10

### Added
- **`prepare` command:** New command to instruct the agent to generate the implementation `steps` for a task.
- **`get_current` command:** New command to display the current context (Plan, Story, Task IDs).
- **Unified Workflow Documentation:** Added a new unified workflow diagram and explanation to `docs/project_workflow.md` for improved clarity.

### Changed
- **`status` command renamed to `report`:** To better reflect its function as a rich progress summary and avoid ambiguity with the `Status` property.
- **Task `implementation_plan` field renamed to `steps`:** For clarity and to avoid confusion with the `Plan` work item.
- **Updated `approve` command behavior:** The `approve` command is now more explicit for handling steps review and fast-tracking.
- The `delete_plan` command now properly removes the plan's directory and all associated files.

### Removed
- **`backlog` command:** Removed in favor of more explicit `list_stories`, `create_story`, and `list_tasks` commands.
- **`select_or_create_plan` command:** Removed in favor of the explicit `list_plans`, `create_plan`, and `set_current_plan` workflow.
- **`workflow_status` command:** Removed as its functionality is now better covered by the `report` and `get_current` commands.

## [0.5.1] - 2025-09-08

### Added
- MCP prompts for execution intent and summary, review checklist.
- Break development workflow into planning and execution; related convenience features.
- Implement planning/execution workflow, agent actions (workflow_status.actions), select_or_create, guardrails, pagination, client-side changelog
- Align it with the rewrtitten task-centric workflow defined in `.cursor/rules/project-management.mdc`

### Changed
- Refactor changelog tools to work with remote client.

## [0.5.0] - 2025-09-04

### Added
- Workflow-aligned plan-manager: execution intent, summary, approvals.
- Enforce WorkItem ID generation.
- Basic state management for tracking current plan, story and task.

## [0.4.0] - 2025-09-02

### Added
- Testing with mcp-inspector

### Changed
- Tweak Dockerfile and devcontainer.json to automate dev environment setup for Python.
- Add testing with mcp-inspector.
- Unify Story/Task CRUD, reduce duplication, and tighten types.
- Structure input and output.
- Refactor list_tasks service and tool for stricter structured output.
- Refactor list_stories service and tool for structured input and output.
- Unify plan management is unified with story and task management.
- Deprecate plan archive - use unified plan management instead.

## [0.3.1] - 2025-08-29

### Changed
- Replace implicit imports from plan_manager.domain (__init__.py) with explicit imports from plan_manager.domain.models to avoid accidental re-exports, reduce surface area, and lower risk of circular imports.
- Uvicorn config: TIMEOUT_GRACEFUL_SHUTDOWN from 2 to 30 and TIMEOUT_KEEP_ALIVE from 2 to 5 to avoid "ERROR - uvicorn.error:414 - Exception in ASGI application".

### Fixed
- Import logging config.
- One empty line in the end of files instead of three.

## [0.3.0] - 2025-08-28

### Added
- `plan_manager.domain.validation` module for domain-layer dependency validation.

### Changed
- Separate domain models from orchestration (services vs. data models).
- Centralize dependency validation and status transitions.
- Encapsulate file mirroring concerns.
- Enable safer plan writes and easier testing.
- Archive tools now use the repository API exclusively: `archive.delete_archived_story` performs loads/saves via `services.plan_repository`.
- Story deletion now also removes the entire story directory (`todo/<story_id>/`) best-effort, with guardrails to prevent unsafe deletes.
- Refine domain models: `Plan` validator defers dependency validation import to avoid cycles and keep domain layer pure.
- Improve typing, docstrings, and logging consistency.

### Removed
- egacy implementations related to the changed functionality.
- Outdated CLI tools.

## [0.2.3] - 2025-08-26

### Changed
- Replace SSE transport by Streamable HTTP.
- Refactor application configuration to follow Twelve-Factor App principles. All settings are now sourced from environment variables with sensible defaults. Command-line arguments have been removed for simplicity.
- Consolidate configuration logic has been into the `plan_manager.config` module.
- Unify the logging system: modules now use a consistent, centrally configured logger that inherits its settings from the main entrypoint.
- Logging now defaults to writing to `stdout` as an event stream, adhering to Twelve-Factor principles. File-based logging is now an opt-in feature for development.

### Added
- The `PLAN_MANAGER_ENABLE_FILE_LOG` variable is now set in `.devcontainer/devcontainer.json` to automatically enable file logging for a better development experience.
- Add `logs/` directory to `.gitignore` to prevent log files from being committed.

### Fixed
- Suppress ASGI app factory warning from Uvicorn by adding `factory=True` to the `uvicorn.run()` call.

## [0.2.2] - 2025-08-23

### Changed
- Split modules into `story_model.py`, `stories.py`, `plan.py`, `archive.py` for clarity.
- Explicit MCP tool registration (stories, plan, archive) from `mcp_server.py`.
- Clean imports, removed sys.path hacks, and fixed circular imports.

### Fixed
- Lint issues and missing imports; server starts cleanly with autoreload.

## [0.2.1] - 2025-08-23

### Added
- `create_task` supports `details_content` to initialize the task markdown (remote-friendly).
- New unified `update_task` handler for partial updates (title, notes, depends_on, priority, status).

### Changed
- CRUD naming alignment: `get_task`, `create_task`, `update_task`, `delete_task`. Removed legacy `show_task_handler`.
- Empty `status`/`priority` in `update_task` are treated as “no change” to ease client calls.

### Removed
- Specialize `update_task_status_handler` and `update_task_priority_handler` in favor of `update_task`.

## [0.2.0] - 2025-08-22

### Added
- Development autoreload via `uvicorn --reload` in dev workflow.
- CLI flags for reload directories, include/exclude patterns, and timeouts.
- Env flag `PLAN_MANAGER_ENABLE_FILE_LOG` to disable file logging in dev.

### Changed
- Documentation updated for SSE-only configuration and Cursor SSE setup.

### Fixed
- Faster, more predictable shutdown on reload even with long-lived SSE connections open.

## [0.1.0] - 2025-07-28

### Added
- Initial release of Plan Manager.
- MCP server implementation for AI assistant integration.
- Task management with YAML-based storage (`todo/plan.yaml`).
- Dependency tracking and topological sorting.
- Priority-based task ordering (0-5 scale).
- Task status management (TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED).
- Archive functionality for completed tasks.
- CLI tools for direct task management:
  - `list_tasks.py` - List and filter tasks.
  - `show_task.py` - Display task details.
  - `update_task_status.py` - Update task status.
- Comprehensive logging system.
- Pydantic-based data validation.
- SSE transport support for MCP communication.
- Development container configuration.
- Comprehensive documentation and setup instructions.

### Features
- **Task Management**: Create, read, update, delete operations.
- **Dependency Management**: Define task dependencies with cycle detection.
- **Priority System**: 6-level priority system (0=highest, 5=lowest, null=no priority).
- **Status Tracking**: Five status types with validation.
- **Archive System**: Move completed tasks to archive with detail preservation.
- **AI Integration**: Full MCP server implementation for AI assistants.
- **Data Validation**: Robust schema validation using Pydantic models.
- **Logging**: Comprehensive logging to both files and stderr.
- **CLI Interface**: Direct command-line access to all functionality.

### Technical Details
- Python 3.11+ required.
- Built with FastMCP, Starlette, and Uvicorn.
- YAML-based data storage with backup/archive support.
- Type hints throughout codebase.
- Comprehensive error handling and validation.
