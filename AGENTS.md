# AGENTS.md

Guides AI agents developing Plan Manager.

## Quick Setup
- Start server: `uv run pm` → `http://localhost:3000/mcp`
- Run tests: `uv run pytest`
- Details: `docs/contributing.md`

## Key Constraints
- Pre-1.0 project: working features > polish (see @focused-development.mdc)
- MCP protocol: core functionality, don't modify without reason
- Test isolation: all tests use temp directories (see `tests/conftest.py`)
- YAGNI strictly: don't add features "just in case"

## Architecture
- Domain models: `src/plan_manager/domain/`
- Services: business logic in `src/plan_manager/services/`
- Tools: MCP tools in `src/plan_manager/tools/`
- Tests: `tests/` (see conftest.py for isolation)

## Development Flow
1. Changes to server require reload (Cursor won't auto-reconnect)
2. To reconnect: toggle MCP switch in Cursor settings (off → on)
3. Run tests before committing: `uv run pytest`

## Resources Exposed to Clients
- `usage_guide_agents.md` - for agents using Plan Manager
- `project_workflow.md` - workflow diagrams
