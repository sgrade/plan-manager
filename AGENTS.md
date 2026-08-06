# AGENTS.md

Guides AI agents developing Plan Manager.

## Quick Setup
- First run in a clone: `./scripts/setup-dev.sh` (the devcontainer does this for you)
- Start server: `uv run pm` → `http://localhost:3000/mcp`
- Verify everything: `./scripts/verify.sh` (~7s: lint, types, security, tests, build)
- Details: `docs/contributing.md`

## Key Constraints
- Pre-1.0 project: working features > polish (see @focused-development.mdc)
- MCP protocol: core functionality, don't modify without reason
- Test isolation: all tests use temp directories (see `tests/conftest.py`)
- YAGNI strictly: don't add features "just in case"
- Explicit scope: there is NO global `current` plan. Every plan-scoped tool call
  carries `plan_id`, and workflow mutations also carry `task_id`, so concurrent
  agents never share hidden server state (see `docs/architecture.md`)

## Architecture
- Domain models: `src/plan_manager/domain/`
- Services: business logic in `src/plan_manager/services/`
- Tools: MCP tools in `src/plan_manager/tools/`
- Tests: `tests/` (see conftest.py for isolation)

## Working Agreements
- **The maintainer commits and pushes.** Propose the commit; never run `git commit`
  or `git push` yourself.
- `scripts/verify.sh` is the single definition of every check; the pre-push hook
  and all five CI jobs call it. Change checks there, not in the workflow files.
- If you add a gate, prove it fails before trusting it when it passes. Several
  checks in this repo were once green while doing nothing at all.
- Get a fresh-context review before calling substantial work done.
- Never create scratch files under `src/` — the dev server's reloader picks them
  up and can wedge the running server. Use `/tmp`.
- After the venv changes (e.g. `uv sync` onto a new Python), restart `uv run pm`;
  a live process keeps the old interpreter and its reloads then fail.

## Development Flow
1. Changes to server require reload (Cursor won't auto-reconnect)
2. To reconnect: toggle MCP switch in Cursor settings (off → on)
3. Granularity: task = commit, story = push, epic = `--ff-only` merge to `main`
   (see `docs/contributing.md`)

## Resources Exposed to Clients
- `usage_guide_agents.md` - for agents using Plan Manager
- `project_workflow.md` - workflow diagrams
