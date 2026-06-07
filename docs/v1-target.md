# Plan Manager v1 — Target State

The desired end-state for the plan-manager refactoring.
Use this document to validate architecture, design, and implementation decisions.

## 1. Vision

**Plan Manager is persistent shared memory for multi-agent systems.**

It gives stateless agents three things no framework or memory service provides together:

1. **Persistent context** — agents resume, not restart. Durable state, checkpoints, and event logs survive beyond context windows and sessions. Any agent in any framework can pick up where it or another agent left off.

2. **Coordination** — agents collaborate, not collide. Claims prevent duplicate work. Events provide mutual awareness. Attention surfaces what needs action. This is the missing coordination layer between agents.

3. **Collective knowledge** — the system gets smarter over time. Raw interactions are consolidated into durable, searchable knowledge. Knowledge belongs to the system, not individual agents.

### 1.1 What PM is NOT

- Not an agent framework (doesn't compete with LangGraph, AutoGen, CrewAI)
- Not a memory service for individual agents (doesn't compete with Mem0, Zep)
- Not a task manager with a fixed methodology

PM is the **shared infrastructure layer** that sits between agent frameworks and memory services, filling the gap neither addresses: shared state with coordination.

### 1.2 Positioning

In the MCP + A2A ecosystem:
- **MCP** = agent-to-tool (vertical: agent connects down to tools)
- **A2A** = agent-to-agent (horizontal: agent connects to peer agents)
- **PM** = shared state (the coordination substrate agents read/write together)

### 1.3 v2 direction

v1 establishes lean instances with shared memory, coordination, and knowledge for agent clusters. v2 evolves this into a **neural self-organizing network**: instances discover each other, negotiate roles, and route knowledge dynamically based on relevance. v1 primitives are designed to enable this transition:

| v1 primitive | v2 evolution |
|---|---|
| Context metadata (domain, description) | Instance identity / agent card — enables discovery |
| Event summaries to coordination PM | Inter-instance protocol — enables knowledge routing |
| Knowledge retrieval with scope filtering | Cross-instance queries — enables neural routing |
| Hierarchical clusters (explicit tree) | Self-organizing mesh with dynamic topology |

## 2. Principles

| # | Principle | Meaning |
|---|-----------|---------|
| P1 | **Shared state, not methodology** | Core provides persistent context, coordination, and knowledge. How work is organized (plans, incidents, runbooks) is a plugin concern. |
| P2 | **Agent-first, human-supervisory** | Agents are primary actors. Humans observe, guide, and intervene at any granularity. The system makes supervision easy (dashboard, attention, cross-context overview). |
| P3 | **Framework-agnostic** | PM works with any agent framework (LangGraph, AutoGen, CrewAI, OpenAI SDK, Claude/MCP) via universal primitives and framework-specific adapters. |
| P4 | **Plug-and-play** | Agents shouldn't need to "learn" PM. PM speaks the language agents already understand: put/get state, append/read events, save/load checkpoints. |
| P5 | **Structure is emergent** | Works with zero upfront structure (inductive/agile) and full upfront plans (deductive/waterfall). Transitions are fluid. |
| P6 | **Library-first, adapters are thin** | Core is a Python library. MCP, CLI, Dashboard, framework adapters are thin wrappers over the same Python API. |
| P7 | **Lean instances, clustered scaling** | Each PM instance serves a small cluster of tightly-coupled agents. Scaling = more instances connected hierarchically, not bigger instances. |
| P8 | **YAGNI** | Ship what's needed now. Design for extensibility, don't build it preemptively. |

## 3. Core primitives

### 3.1 Contexts

An isolated workspace for a unit of work (a project, an incident, an investigation). The boundary of shared state for a cluster of agents.

- **Lifecycle**: create, list, get, archive, unarchive.
- **Scoping**: session binding (set once) + per-call override. No global singleton "current" that affects all clients.
- **Storage**: each context is a directory under the data root.
- **Metadata**: id (slug), title, description, created_at, updated_at, status (active/archived), plugin namespaces in use.
- **Discovery**: `list_contexts` supports filtering by status (default: active), text search across title/description (`query` parameter), and sorting by last activity. Agents find the right context without knowing the ID in advance.
- **Archiving**: status flip in metadata (active → archived). Data stays on disk, fully readable. Archived contexts are hidden from default listings and read-only (core refuses writes). Reactivatable via unarchive — no data loss.

### 3.2 State

Namespaced structured data within a context. The shared mutable state that agents read and write.

- Each plugin gets a subdirectory: `{context_dir}/{plugin_namespace}/`.
- Core enforces namespace isolation — a plugin cannot write outside its namespace.
- Validation is each plugin's responsibility via Pydantic models (Pydantic-as-convention).
- Core provides read/write primitives for plugin state. Plugins define the schema.
- File format: YAML (human-readable, git-friendly) with markdown for long-form content.
- **Universal API**: `put(namespace, key, value)` / `get(namespace, key)` alongside domain-specific plugin tools. Framework adapters map to this.

### 3.3 Events

Append-only activity log at two levels: per-context and global.

- Every state mutation is logged: what changed, when, by whom (optional `actor` string), why (optional `reason` string).
- **Per-context log**: events scoped to a single context. Supports `get_events(context_id, since=N)` for context-specific catch-up.
- **Global log**: every event from every context, with `context_id` attached. Supports `get_events(since=N)` (no context scope) for cross-context awareness. Dual-write: every event appends to both its context log and the global log.
- Sequence numbers are monotonic (per-context sequences are independent; global sequence is its own monotonic counter).
- Events are the primary mechanism for agents to stay aware without re-reading all state.
- **Reconciliation pattern**: an orchestrator polls the global stream once, filters client-side, and dispatches agents — O(1) polling, not O(N) per context. Follows the Kubernetes watch API pattern.
- Events include the plugin namespace (e.g., `dev`, `ops`) for client-side filtering by domain.

### 3.4 Checkpoints

Versioned snapshots of state within a context, enabling resume and rollback.

- `save_checkpoint(context_id, label=None)` → captures full state snapshot with a sequence number.
- `load_checkpoint(context_id, checkpoint_id=None)` → restores state from a snapshot (latest if no ID specified).
- `list_checkpoints(context_id)` → available snapshots with timestamps and labels.
- Checkpoints enable the "working memory save/restore" pattern: an agent saves state before a risky operation and rolls back if it fails.
- Framework adapters map checkpoints to their native interface (e.g., LangGraph's `BaseCheckpointSaver`).

### 3.5 Attention (derived, not stored)

"What needs action right now?" is a **computed query** over current state, not a separate data structure. The state itself is the blackboard.

- Core provides `get_attention(plugin=None, context_id=None)` — returns a prioritized list of items needing action across contexts.
- Attention rules are plugin-defined: each plugin declares what "needs attention" means for its state (e.g., unclaimed tasks, new incidents, stale items, items blocked by now-resolved dependencies).
- Short-term memory = attention query (computed from live state). Long-term memory = event log (append-only history).
- No separate blackboard data structure. No sync problem. State is the single source of truth.

### 3.6 Multiple orchestrators

Orchestrators operate at three levels, each with natural isolation:

- **Context orchestrator**: bound to one context (e.g., one agent managing the "infra-migration" project). Watches context-specific events via `get_events(context_id=X, since=N)`. No contention with orchestrators in other contexts — context scoping is the primary isolation.
- **Domain orchestrator**: watches the global stream filtered by plugin namespace (e.g., an ops orchestrator watching all `ops.*` events across contexts). Can spawn context orchestrators when new work appears (e.g., new incident → spin up an incident handler for that context).
- **Meta-orchestrator**: watches the global stream unfiltered. The human dashboard serves this role. A dispatch agent could too.

When multiple orchestrators operate at the same level and scope, **claims** prevent duplicate work: an orchestrator writes `claimed_by` to the work item's state. Others see the claim and skip. No distributed locks — claiming is a normal state mutation logged as an event.

## 4. Memory model

PM implements a cognitive memory architecture mapped from human memory research:

| Memory tier | PM mechanism | Lifecycle |
|---|---|---|
| **Working memory** (agent's active context) | State + Checkpoints. Agents read state into their context window, reason, write results back. PM extends working memory beyond the context window. | Read/write during active work |
| **Episodic memory** (what happened) | Event log. Append-only, timestamped, attributed. Complete record of all interactions. | Append-only, never modified |
| **Semantic memory** (extracted knowledge) | Knowledge plugin. Facts, entities, relationships extracted from events and consolidated into searchable knowledge. | Built by consolidation pipeline |
| **Procedural memory** (how to do things) | Plugin state: dev workflows, ops runbooks, documented procedures. | Managed by methodology plugins |

### 4.1 Knowledge consolidation pipeline

The knowledge plugin turns raw events into durable knowledge:

```
Events (episodic memory)
    │
    ├── 1. Noise filtering — skip heartbeats, acks, read-only queries
    ├── 2. Extraction — LLM-based fact/entity extraction from high-signal events
    ├── 3. Dedup/merge — compare against existing knowledge, decide ADD/UPDATE/INVALIDATE/NOOP
    ├── 4. Storage — with metadata: timestamp, importance, source, scope, embedding
    └── 5. Background consolidation — decay, promotion, pruning, reflection
```

**Consolidation triggers** (configurable per instance):
- **Importance-based** (default): when the sum of importance scores for recent events crosses a threshold. Follows the Stanford Generative Agents pattern — consolidate when enough important things happen, not on a timer.
- **Event-based**: on every write (inline extraction). Higher cost, lower latency.
- **Scheduled**: periodic batch processing. Lower cost, higher latency.

**Retrieval** uses composite scoring:
```
score = (semantic_weight × similarity) + (recency_weight × decay) + (importance_weight × importance)
```
Weights are configurable per use case (ops favors recency; dev favors importance; research favors semantic similarity).

### 4.2 Knowledge plugin backends

The knowledge plugin defines the interface. The backend is swappable:

- **Built-in** (default): file-based, keyword search, importance scoring, decay. No ML dependencies. Lean.
- **Mem0 backend** (optional): full extraction pipeline, graph memory, vector search. Best-in-class fact recall.
- **Graphiti/Zep backend** (optional): temporal knowledge graph, bi-temporal queries, entity evolution tracking.

Default is lean (no external dependencies). Power backends for teams that need best-in-class recall.

## 5. Plugin architecture

### 5.1 What a plugin is

A plugin is a Python module that:

1. **Declares a namespace** (e.g., `dev`, `ops`, `knowledge`, `report`).
2. **Provides Pydantic models** for its state.
3. **Registers tool functions** that operate on its namespaced state.
4. **Declares attention rules** (what "needs attention" means for its state).
5. **Optionally provides MCP resources, prompts, and dashboard templates.**

### 5.2 Plugin contract

```python
@runtime_checkable
class Plugin(Protocol):
    namespace: str

    def get_tools(self) -> list[Tool]: ...
    def get_models(self) -> dict[str, type[BaseModel]]: ...
    def get_attention_rules(self) -> list[AttentionRule]: ...
    def on_context_create(self, context_id: str) -> None: ...
    def on_context_archive(self, context_id: str) -> None: ...
```

### 5.3 Plugin loading

- **Tier 1 (v1)**: Bundled plugins, loaded from an explicit dict. Explicit opt-in via configuration or CLI flag (`--plugins dev,ops,knowledge,report`).
- **Tier 2 (future)**: External plugins via `importlib.metadata` entry points. Pip-installable. ~10 lines to add when needed.

### 5.4 Tool namespacing

- Core tools are unprefixed: `create_context`, `list_contexts`, `get_events`, `save_checkpoint`, `get_attention`, etc.
- Plugin tools are prefixed: `dev.create_task`, `ops.create_incident`, `knowledge.recall`, `report.status`.
- MCP adapter exposes all loaded tools with their namespace prefix.
- CLI adapter maps to subcommands: `pm dev create-task`, `pm ops create-incident`.

### 5.5 Native vs external plugins

- **Native plugins**: Python modules bundled with plan-manager (or installable as separate packages). Use the plugin API directly.
- **External plugins**: Independent MCP servers, agent skills, or other tools that interact with plan-manager through its MCP or CLI interface. Not managed by the plugin loader — they're independent clients.

## 6. v1 plugins

### 6.1 `dev` — Structured Development

Extracted from current plan-manager. Provides the Plan → Story → Task methodology.

**State model:**
- Plan: id, title, description, priority, status, stories.
- Story: id, title, description, acceptance_criteria, status, tasks, depends_on (other stories).
- Task: id, title, description, status, steps, changes, review_feedback, depends_on.

**Workflow gates** (retained from current):
- Steps required before starting a task.
- Changes required before submitting for review.
- Review/approval flow (submit PR → approve/request changes → merge).

**Status roll-up:** Task status changes propagate to story and plan status.

**Tools:** CRUD for plans, stories, tasks. Workflow actions (start_task, submit_pr, approve_pr, etc.).

### 6.2 `ops` — Operations

Supports incident response, maintenance tasks, and operational workflows.

**State model:**
- Incident: id, title, severity, status (detected/investigating/mitigating/resolved/postmortem), timeline, assignee.
- Action: id, description, status (pending/in_progress/done), actor, result, timestamp.
- Runbook: id, title, steps, current_step (for guided execution).

**Key differences from dev:**
- Timeline-driven (events and actions over time) vs plan-driven (hierarchical decomposition).
- Severity-based prioritization vs priority numbers.
- No gates — ops is reactive, not ceremonial.

**Tools:** Incident lifecycle (create, update severity, add action, resolve). Runbook execution (start, advance step, complete).

### 6.3 `knowledge` — Collective Knowledge

Turns raw agent interactions into durable, searchable knowledge.

**Capabilities:**
- Consolidation: extract facts, entities, relationships from the event log.
- Recall: retrieve relevant knowledge given a query, scored by semantic relevance + recency + importance.
- Governance: decay stale knowledge, resolve contradictions, maintain freshness.

**Tools:** `knowledge.recall(query, scope=None)`, `knowledge.store(fact, importance=None)`, `knowledge.consolidate(context_id=None)`.

**Backend-swappable:** Built-in (file-based, keyword search) or Mem0/Graphiti for vector-powered recall. See section 4.2.

### 6.4 `report` — Reporting

Cross-cutting plugin that reads state from other plugins and produces summaries.

**Capabilities:**
- Cross-context status overview (all contexts at a glance).
- Per-context status report (what's done, in progress, blocked).
- Changelog generation (extracted from current plan-manager).
- Commit message generation (extracted from current plan-manager).

**Design note:** This plugin has read access to other plugins' state (by convention — it imports their models to deserialize their data). It does not modify other plugins' state.

## 7. Adapters

### 7.1 MCP adapter

- Exposes core + loaded plugin tools as MCP tools.
- Exposes MCP resources (usage guides, plugin docs).
- Exposes MCP prompts (plugin-provided).
- Runs on Starlette via Streamable HTTP at `/mcp` (same as today).
- Tool names use dot-notation for namespacing: `dev.create_task`.

### 7.2 CLI adapter

- Exposes core + loaded plugin tools as CLI subcommands.
- Entry point: `pm` (same as today, extended).
- Structure: `pm <namespace> <command> [args]` (e.g., `pm dev create-task --title "..."`)
- Core commands: `pm context create`, `pm context list`, `pm events --since 42`, `pm checkpoint save`.
- Output: JSON by default. `--human` flag for readable text output.
- Skills-friendly: non-interactive, structured output, clear exit codes, idempotent where possible.

### 7.3 Framework adapters

Thin wrappers that map PM's universal primitives to framework-native interfaces:

| Framework | Adapter maps to | What it wraps |
|---|---|---|
| LangGraph | `BaseCheckpointSaver` + `BaseStore` | Checkpoints + State |
| AutoGen | `save_state()` / `load_state()` target | Checkpoints + State |
| CrewAI | `StorageBackend` for Memory | State + Knowledge |
| OpenAI SDK | `Session` interface | Events + State |

**v1 scope:** Build one adapter (for the framework actively in use). Design the pattern so others are ~50-100 lines each.

### 7.4 Dashboard (server-rendered HTML)

- Read-only web interface for human supervision and review.
- Served by the existing Starlette server alongside MCP.
- Routes:
  - `/dashboard` — all contexts overview (status, last activity, attention flags).
  - `/dashboard/{context}` — context detail (plugin state: stories, incidents, etc.).
  - `/dashboard/{context}/{item}` — item detail (full description, sub-items, history).
- Server-rendered HTML with Jinja2 templates. No frontend framework.
- Auto-refresh on overview page.
- Later: forms for human actions (approve, reassign). Read-only first.

## 8. Cluster architecture

PM is designed for clustered deployment where each instance stays lean:

```
Cluster A (e.g. infra team)             Cluster B (e.g. product team)
┌──────────────────────────┐            ┌──────────────────────────┐
│ Agent 1 ←→ PM-A ←→ Agent 2 │         │ Agent 4 ←→ PM-B ←→ Agent 5 │
│            Agent 3          │         │            Agent 6          │
└──────────┬───────────────┘            └──────────┬───────────────┘
           │                                        │
           └──────────── PM-Coord ──────────────────┘
                   (coordination instance)
```

- **Cluster instance**: serves 2-5 tightly-coupled agents sharing one knowledge domain. One data directory, one process.
- **Coordination instance**: another PM instance at a higher level. Has contexts for each sub-cluster. Receives summarized events from sub-clusters.
- **Knowledge flows up** (cluster → coordination) via summarization and reflection.
- **Knowledge flows down** (coordination → cluster) via retrieval.
- **v2 evolution**: hierarchical tree → self-organizing mesh. Instances discover peers, negotiate roles, route knowledge by relevance.

## 9. Non-functional requirements

| # | Requirement | Implementation |
|---|-------------|----------------|
| N1 | **File-backed storage** (default) | All state is files. Git-friendly, transparent, human-readable. Docker volumes work out of the box. Services depend on repository interfaces (Python protocols), not file operations directly. |
| N2 | **Backend upgrade path** | Repository interfaces are designed to map cleanly to Redis data structures (Streams for events, Hashes for state, Sorted Sets for attention). Upgrade path: files → SQLite (if concurrency hurts) → Redis (if scale/push demands). Not built for v1. |
| N3 | **Concurrency safety** | Atomic writes (temp file + rename). Last-writer-wins. Claims for coordination. Event log provides conflict visibility. |
| N4 | **Low ceremony** | One command to create a context and start working. No mandatory upfront structure. |
| N5 | **Observable** | Cross-context status via CLI (`pm report status`), Dashboard (`/dashboard`), and attention queries. |
| N6 | **Skills-friendly CLI** | Non-interactive. JSON default. `--human` flag. Clear exit codes. Idempotent where possible. |

## 10. Scoping model

How agents and humans specify which context they're operating in:

- **Session binding**: An agent calls `set_context(id)` at the start of its session. Subsequent calls default to this context.
- **Per-call override**: Any tool call can include `context_id` parameter to operate on a different context.
- **Priority**: explicit parameter > session binding > error (no implicit default).
- **No global singleton**: unlike today's "current plan", session binding is per-connection, not global server state.

## 11. What is NOT in v1

These are explicitly deferred. The architecture supports them without redesign.

| Item | Trigger to build |
|------|-----------------|
| **Research plugin** | Active research/exploration use case demands it |
| **Full interactive Web UI (SPA)** | Dashboard proves insufficient for supervision |
| **HTTP REST API (separate product)** | Remote/distributed agent access needed |
| **Push notifications (SSE/WebSocket)** | Polling becomes a bottleneck |
| **Cross-context hard dependencies** | Soft links prove insufficient |
| **Auth/access control** | Multi-tenant or security-sensitive deployment |
| **Participant registry** | Need to formally track agent identity beyond `actor` strings |
| **Distributed locking** | Last-writer-wins proves insufficient for concurrency |
| **Redis/SQLite backends** | File-based concurrency or performance becomes a bottleneck |
| **Self-organizing instance mesh (v2)** | Hierarchical clustering proves insufficient |

## 12. Migration from current plan-manager

The current plan-manager codebase maps to the new structure:

| Current | Target |
|---------|--------|
| `domain/models.py` (Plan, Story, Task) | `plugins/dev/models.py` |
| `services/plan_service.py`, `story_service.py`, `task_service.py` | `plugins/dev/services/` |
| `services/plan_repository.py`, `state_repository.py` | Core state management + `plugins/dev/` repository |
| `services/activity_repository.py` | Core event log |
| `services/changelog_service.py`, `services/report_service.py` | `plugins/report/` |
| `tools/*.py` | `plugins/dev/tools.py` + `plugins/report/tools.py` |
| `server/app.py` | `adapters/mcp/` + `adapters/dashboard/` |
| `io/paths.py`, `io/file_mirror.py` | Core I/O layer (retained, generalized) |
| Global "current plan" in `index.yaml` | Per-session context binding (core) |
| `prompts/` | `plugins/dev/prompts.py` |
| `resources/` | Core resources + plugin-contributed resources |

## 13. Success criteria

The refactoring is successful when:

1. **Plug-and-play works**: An agent using any framework can connect to PM and start reading/writing state without learning PM-specific concepts. The universal API (put/get/append/checkpoint) just works.
2. **Ops works**: An agent can manage an incident (create, track actions, resolve) through the ops plugin without touching dev concepts.
3. **Dev works**: All current plan-manager functionality is preserved in the dev plugin.
4. **Multi-context**: Two agents can work on different contexts simultaneously without interference.
5. **Human supervision**: A human can open `/dashboard`, see all active contexts, drill into any one, read story/incident details, and understand what's happening — without asking an agent.
6. **Agent catch-up**: An agent returning to a context can call `get_events(since=N)` and understand what changed without re-reading all state.
7. **Knowledge builds**: The knowledge plugin extracts durable facts from agent interactions that are retrievable in future sessions.
8. **Skills work**: An agent skill can run `pm ops create-incident --title "..." --severity high` and get structured JSON back.
9. **Plugin isolation**: Adding the ops plugin required zero changes to core or the dev plugin.
10. **Cluster-ready**: Two PM instances can operate independently. A coordination instance can receive event summaries from sub-clusters.
