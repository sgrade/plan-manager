---
conformance_suite: plan-manager
contract_status: target-design   # NOT the currently served API; flips to
                                 # "served" when the U16 breaking release ships
validates_contract: next-version contract design, draft of record 2026-08-07 (the pin becomes the product version at release)
updated: 2026-08-07
---

# Plan Manager — public interface specification (TARGET contract)

> **contract_status: target-design.** This spec describes the contract
> the next version will ship. The API served TODAY is the v2
> explicit-scope contract — see `docs/usage_guide_agents.md`. Do not
> code against this spec until it flips to `served`.

This document is SELF-CONTAINED: clients need nothing else to use PM.
One MCP endpoint: `/mcp` (Streamable HTTP, stateless). 28 tools.

## 1. Vocabulary and identifiers

- **Work items** are the planning hierarchy: `plan`, `story`, `task`.
  A plan contains stories; a story contains tasks. IDs are slugs: plans
  globally (`auth_hardening`), stories per plan (`token_rotation`), tasks
  per story, addressed fully-qualified as `story_id:local_id`
  (`token_rotation:add_kms_call`). IDs are server-generated from titles.
- **Jobs** are dispatched execution: a job carries an immutable launch
  prompt, is claimed by a worker under a lease, ends in a report and a
  resolution. Jobs, decisions, and delegations use server-assigned
  integer ids. Work items are what you plan; jobs are what agents execute.
- **Documents** are named, versioned artifacts per plan (e.g. `charter`,
  `resume`). Revisions are immutable, numbered 1,2,3…, content-addressed
  (sha256). **Decisions** are an append-only per-plan log of verbatim
  rulings. **Policies** define which check jobs gate acceptance, per job
  kind. **Delegations** record authority transfer.
- Every plan-scoped call carries explicit `plan_id` — with one deliberate
  exception: plan-type work-item reads (`list_work_items(type=plan)`,
  `get_work_item(type=plan, id=…)`) take no `plan_id`, so a fresh session
  can discover plans (cold-start step 0). There is no server-side session
  state, no "current" anything: pin your scope ids in your own context and
  pass them on every call.
- PM is a PULL substrate: it never starts, wakes, or notifies workers.
  Process supervision belongs to your runner; workers discover work via
  `claim_job`/`poll_events` loops (see §4/§9 loop guidance).

## 2. Common call conventions

- **`agent` (string, required on every mutation)**: your identity as a
  URI, e.g. `agent://team-a/orch-1`, `human://roman`. Recorded on every
  write; attribution is the audit trail.
- **Minimal envelopes**: mutations return `{id(s), status, version, seq}`
  plus operation-specific essentials — never full object echoes. Pass
  `detail: true` where offered to get the full object. Reads return
  complete objects.
- **`expected_version` (int)**: required on `update_work_item`, and on
  `set_policy` only when UPDATING an existing row (omit on first write of a
  kind's policy). Mismatch → structured conflict error; re-read and retry.
- **Identity is self-declared** (no authentication in this deployment
  phase): the `agent` string is recorded, permanent, and auditable — the
  non-submitter rules are tamper-evident, not tamper-proof, until real
  identity lands. Do not treat them as a security boundary.
- **Errors**: failures raise MCP errors (`isError=true`). The error text
  includes `structured_recovery=` JSON: `{message, recovery: [steps…]}`
  naming the current server state, so one read fixes your next call.
- **Statuses.** Work items store `TODO | DONE | DEFERRED | CANCELED`.
  Reads also return derived `display_status`: `BLOCKED` (unmet
  `depends_on`), `IN_PROGRESS` (a live CLAIMED job at this scope),
  `PENDING_REVIEW` (a SUBMITTED job at this scope). Story/plan status
  rolls up from tasks/stories; CANCELED and DEFERRED children are
  excluded from the rollup denominator (DONE requires all remaining
  children DONE and at least one such child). Jobs move
  `OPEN → CLAIMED → SUBMITTED → ACCEPTED | REJECTED`, plus `CANCELED`
  (withdrawn from OPEN/CLAIMED/SUBMITTED/EXPIRED) and `EXPIRED` (lease
  lapsed with attempts exhausted; reopenable). REJECTED and ACCEPTED are
  terminal — a mis-resolved job is remedied by creating a new job (prompt
  immutability makes that one call), never by reopening.
- **Reference conventions** for `refs`/`ruling_ref`: `decision:<id>`,
  `job:<id>`, `task:<story:local>`, `doc:<name>@<rev>`, or a URI.
- Deletion is for created-in-error only; it REFUSES if jobs reference the
  work item. Retire finished/abandoned things by status, never deletion.

## 3. Work-item tools (the hierarchy)

### create_work_items
`(agent, type: plan|story|task, items: [{title, description?, priority?(0-5, 0 highest), depends_on?, acceptance_criteria?}], plan_id?, story_id?)`
Bulk-first: one or many of ONE type under ONE parent, one transaction.
`plan` needs no parent; `story` needs `plan_id`; `task` needs `plan_id` +
`story_id`. `acceptance_criteria` valid only for stories. `depends_on`:
stories reference story ids; tasks reference task ids (`story:local` or
local-within-same-story) or story ids; a SAME-BATCH sibling is referenced
as `"#<index>"` (its 0-based position in `items[]` — the server resolves
to the real id, so one call expresses a whole dependent unit table).
Unresolvable references block readiness. Returns `{ids[]` (in input
order)`, version(s), seq}`. IDs are slugified titles (collisions get a
`-2` suffix) — always read `ids[]` back, never construct them.

### get_work_item
`(type, plan_id?, id)` → the full work item (incl. `display_status`,
`changes[]` for closed tasks). `plan_id` omitted for `type=plan`. Tasks:
`id` fully-qualified (`story:local`).

### list_work_items
`(type, plan_id?, statuses?, story_id?, ready?, offset?, limit?)` →
compact rows ({id, title, status, display_status, priority}). `plan_id`
omitted for `type=plan` — this is how a fresh session discovers plans.
`statuses` accepts stored AND derived values (server computes).
`ready=true` (tasks): dependencies all DONE.

### update_work_item
`(agent, type, plan_id, id, expected_version, title?, description?, priority?, depends_on?, status?, acceptance_criteria?)`
`status` accepts only `TODO | DEFERRED | CANCELED` (DONE has exactly one
path: `close_task`). Version mismatch → conflict error.

### delete_work_item
`(agent, type, plan_id, id)` — created-in-error only; refuses when jobs
reference the item or dependents exist.

### close_task
`(agent, plan_id, task_id, changes: [string], artifacts?: [{name, content?|blob_hash?, encoding?}])`
The single path to task DONE. `changes[]` is the result record (drives
story/plan rollups). Inline artifact `content` is stored content-addressed.
Closing is deliberately independent of job acceptance (the lean solo flow
needs it) — but it is never silent: the response and the `task.closed`
event carry a computed `governance` summary `{accepted, rejected, open,
submitted}` counting this task's jobs, so closing over a FAIL verdict is
visible in the record. Governed flows close after acceptance — that is
process law, which this summary makes auditable. Transition is
CAS-guarded: TODO→DONE fires exactly once; a concurrent second close gets
a structured error. Returns `{task_id, status, governance, blob_hashes?,
seq}`.

## 4. Job tools (dispatch and execution)

Jobs attach to a scope: `scope: {kind: plan|story|task, story_id?, task_id?}`.

### create_job
`(agent, plan_id, jobs: [{kind, objective, prompt, scope, pins?, target_job_id?, requires_target_submitted?, priority?, lease_seconds?(default 1800), max_attempts?(default 1)}], idempotency_key?)`
One or many. `kind` is a free string; the vocabulary is per-plan (your
policy defines what gates what) with common conventions:
`implementation`, `fixup`, `unit-review`, `mechanical-suite`,
`phase-audit`, `research`. Kinds are matched exactly (a typo silently
misses policy and filters; check `get_policy` for the kinds that gate
acceptance). `objective` ≤ 200 chars
(shows in lists). `prompt` is the full launch prompt — **immutable once
created**; stored content-addressed; changing a job = cancel + create
new. `scope.task_id` is the LOCAL id with `story_id` alongside. `pins`
pin document revisions (`{name, rev}` — validated to exist at creation)
or external immutable refs (`{uri}` — recorded, not resolvable by PM).
`target_job_id` marks checks/fixups; checks set
`requires_target_submitted: true` (claimable only while the target is
SUBMITTED), fixups leave it false. `priority` defaults from the scope
task's priority, else 3. `idempotency_key` (unique per plan): replaying
the same key returns the previously created ids instead of duplicating —
use it whenever dispatching from recovery. NOTE on `max_attempts > 1`:
redelivery makes execution AT-LEAST-ONCE — opt in only for idempotent
work, and write it to be safely re-runnable. Returns `{ids[], seq}`.

### claim_job
`(agent, plan_id, job_id?, kinds?)`
Without `job_id`: claims the highest-priority READY job (priority 0
first; FIFO within a band; `kinds` filters exactly). With `job_id`:
claims that job iff READY. READY = (OPEN, or CLAIMED with lapsed lease
and attempts remaining) ∧ scope dependencies DONE ∧ (checks) target still
SUBMITTED. A check whose target was claimed by YOU is refused (no
self-checks — structural). `attempt` numbering: first claim = 1; every
successful claim increments. Returns `{job_id, kind, objective, scope,
target_job_id?, attempt, lease_expires_at, prompt, prompt_hash, pins}` —
everything needed to work without a follow-up read; verify `prompt_hash`
if you re-fetch. Zero rows → structured error naming why (nothing ready /
lost race / blocked / lease held / attempts exhausted). Loop guidance:
drive wakeups from `poll_events` and back off with jitter on empty claims
— do not busy-poll.

### heartbeat_job
`(agent, plan_id, job_id, attempt)` — re-leases to `now + lease_seconds`
(the job's own value); call at ≤ ⅓ of `lease_seconds`. Fenced by
supersession, not by the clock: it succeeds on a lapsed-but-unreclaimed
claim (revives it) and fails only once another claim superseded yours.
Returns `{job_id, attempt, lease_expires_at, seq}`.
**Wake-up protocol**: after ANY interruption, heartbeat FIRST — before
resuming side effects. A stale-claim error means you were superseded:
abandon the work immediately (PM fences reports, it cannot fence your
side effects — the heartbeat-first rule is what closes that window).

### submit_job
`(agent, plan_id, job_id, attempt, report: {result: pass|fail|partial|blocked, findings[], actions_taken[], proposals[], recommendation(string), artifacts?: [{name, content?|blob_hash?, encoding?}]})`
Writes the report once, CLAIMED → SUBMITTED. Fenced by
`(agent, attempt)`: after a lease reclaim, the superseded worker's submit
is refused (stale-claim error) — its report is discarded, never merged.
A lapsed lease that nobody reclaimed can still submit (grace — until the
lazy sweep materializes EXPIRED on an attempts-exhausted job): late work
is still real work, and the record should say so; fencing exists to
prevent CONFLICTING records, not to punish slowness. Artifacts: inline
`content` is UTF-8 text (binary: base64 + `encoding:"base64"`), ≤256 KB
per artifact; stored content-addressed, hashes returned. Returns
`{job_id, status, blob_hashes?, seq}`.

### resolve_job
`(agent, plan_id, job_id, decision: accepted|rejected, reason(required for rejected), acknowledge_stale_pins?: [name])`
`accepted` is REFUSED unless (a) for every check kind required for this
job (see §7 for which policy row governs, incl. fixups), a check job
targeting this job — itself SUBMITTED or ACCEPTED — has a PASS report
from an agent ≠ this job's claimant (the PASS qualifier governs both
branches; the NEWEST verdict per check kind governs when several exist)
— and
(b) every pinned document still matches its head revision, or you
explicitly acknowledge the named stale pins (recorded verbatim).
Acknowledgment criterion: acknowledge only when the pinned-revision diff
is immaterial to this job; when in doubt, reject and redispatch with
fresh pins — either way the record shows your choice. `rejected` is never
blocked and requires `reason` (the fixup author needs it); rework =
create a `fixup` job targeting this one, embedding the failing verdict
verbatim in its prompt. Resolution records resolver, verdict job ids, pin
staleness, acknowledgments. Returns `{job_id, status, resolution, seq}`.

### cancel_job
`(agent, plan_id, job_id, reason?)` — from OPEN/CLAIMED/SUBMITTED/EXPIRED.

### reopen_job
`(agent, plan_id, job_id, additional_attempts?=1)` — EXPIRED (or
lapsed-CLAIMED) → OPEN with `max_attempts = attempt + additional_attempts`.
REJECTED/ACCEPTED are terminal: a mis-resolution is remedied by creating
a fresh job (same prompt — one call), never by reopening.

### get_job
`(plan_id, job_id, include_prompt?=false, include_artifacts?=false)` →
full job record (scope, target, report, resolution, timestamps). Prompt
and artifact CONTENTS only on request (largest payloads);
`include_artifacts=true` inlines the report's artifact contents — the
checker's path to hash-referenced evidence.

### list_jobs
`(plan_id, statuses?, kinds?, scope?, target_job_id?, claimed_by?, ready?, offset?, limit?)`
→ compact rows: `{job_id, kind, objective, status, scope,
target_job_id?, priority, attempt, max_attempts, lease_expires_at?}`.
`scope` filter = the `create_job` scope object, matched exactly.
`claimed_by` finds your own jobs after a restart. `ready=true` = the
claim predicate, read-only.

**Checks and fixups (how review jobs behave):**

- Policy-created checks (see §7) get a generated prompt containing: the
  target job reference, the instruction to read the target's report via
  `get_job(target, include_artifacts=true)`, and the check kind's
  convention text. Checks INHERIT the target's `pins` — review against
  what the work was built against, not head.
- A job with `target_job_id` whose own kind has no policy row is gated by
  its TARGET's kind policy: fixups inherit the gate of what they fix (a
  rework cycle re-runs the same checks on the fixup's submission).
- Checks never require resolution: their report is their value. They
  leave the attention digest with their target; when a target leaves
  SUBMITTED (resolved or canceled), its still-OPEN checks are
  auto-canceled (`job.canceled`, reason `target_resolved`).
- A crashed or mis-rejected check is replaced by manually creating a new
  check job targeting the same submission (auto-create fires only once,
  at submission time).

## 5. Decision tools (append-only rulings)

### append_decision
`(agent, plan_id, verbatim_quote, consequence, decided_on?, refs?, binding?=false, supersedes_id?)`
Immutable once written; corrections append with `supersedes_id`
(same plan only). `binding` is per-entry and never inherited across
supersession. Returns `{id, seq}`.

### list_decisions
`(plan_id, binding_only?=false, offset?, limit?)` → entries newest-first.
`binding_only` returns the currently-binding set (binding ∧ not
superseded).

## 6. Document tools (versioned artifacts)

### put_document
`(agent, plan_id, name, content, parent_rev?)`
Creates rev 1 (no `parent_rev`) or appends the next revision —
`parent_rev` must equal the current head or you get a conflict (re-read,
rebase, retry). Content stored content-addressed. Returns
`{name, rev, content_hash, seq}`.

### get_document
`(plan_id, name, rev?)` → `{content, rev, content_hash, is_head,
approvals[]}`. Omit `rev` for head.

### diff_document
`(plan_id, name, rev_a, rev_b)` → unified diff (computed, not stored).

### approve_document
`(agent, plan_id, name, rev, ruling_ref?)` — approval bound to that exact
revision + digest; approvals never float to newer revisions.

Conventions: `resume` is the well-known handover document (sections:
Current state · Next action · Waiting-on/risks · Pinned revisions),
maintained by the coordinating agent at record points. Documents retire
by a final revision carrying a RETIRED banner — there is no delete.

## 7. Policy tools (acceptance gates)

### set_policy
`(agent, plan_id, on_kind, required_checks: [kind…], auto_create?=true, auto_accept?=false, expected_version?)`
One row per job kind; `expected_version` only when updating an existing
row. On `submit_job` of a matching kind (or of a targeted job that
inherits this kind's gate — see §4 checks), PM auto-creates one OPEN
check job per required kind (targeting the submission,
`requires_target_submitted=true`, default `max_attempts=1`) unless a live
check of that kind already targets it (pre-create your own to override
the generated prompt). `auto_accept=true`: PM records acceptance itself
(resolver `agent://pm/policy`) the moment the last required PASS verdict
lands — unless pins are stale: then the job stays SUBMITTED, PM emits
`job.autoaccept_blocked`, and the attention digest names the stale pins
(machines have no acknowledgment path; a human/orchestrator resolves).
A kind may appear as `on_kind` or inside `required_checks`, never both.

### get_policy
`(plan_id)` → all policy rows.

## 8. Delegation tools (authority records)

### create_delegation
`(agent, plan_id, scope: {kind: plan|story, story_id?}, delegate, authority: [verbatim grant lines], via_delegation_id?)`
Records the grant; `via_delegation_id` chains multi-hop authority. PM
records, it does not enforce authority.

### revoke_delegation
`(agent, plan_id, delegation_id, reason?)` — revocation is a timestamp.

### list_delegations
`(plan_id, active_only?=true)`.

## 9. Awareness tools

### poll_events
`(after_seq, plan_id?, limit?)` → `{events[], latest_seq, feed_epoch}`.
Events are appended transactionally with every mutation; `seq` is a
global monotonic cursor — poll `after_seq=latest_seq` in a loop; omit
`plan_id` to watch all plans in one poll. If the response signals an
epoch change or your cursor is ahead (restore happened), re-read state
and resume from the returned `latest_seq`. Event types:
`work_item.*`, `job.created/claimed/heartbeat/submitted/resolved/expired/reopened/canceled`,
`job.lease_lapsed` (lease lapsed with attempts remaining — the job is
re-claimable; emitted by the lazy sweep), `job.autoaccept_blocked`
(auto-accept refused on stale pins), `decision.appended`,
`document.revised/approved`, `delegation.created/revoked`, `task.closed`
(carries the governance summary), `policy.changed`. Heartbeat events are
noise-suppressed (emitted only when the lease was in its final third)
and excluded from `poll_events` unless `include_noise=true`. Refused
calls (e.g., a fenced stale submit) are NOT mutations and emit nothing —
the observable is the successor's `job.claimed` with a higher `attempt`.

### resume
`(plan_id)` — the cold-start read: `{resume_document (latest rev + hash +
approval state, or null if never authored), binding_decisions[],
document_heads{name→rev/hash}, attention, latest_seq}`. `attention` is
computed; each item is `{class, job_id?, kind?, scope?, detail}` with
classes: `ready` (claimable jobs), `in_flight` (claims with lease
health), `awaiting_resolution` (SUBMITTED non-check jobs; missing
verdicts / stale pins named), `expired`, `unapproved_pinned_head`
(documents pinned by a LIVE job whose head revision lacks approval).
Checks with terminal targets never appear. Drill: step 0 if you lack a plan id —
`list_work_items(type=plan)`; then `resume` + `list_jobs`
(+ `list_decisions` for history) reconstructs full working state; no
other transport exists. Keep the `resume` document fresh by rewriting it
at record points — after every resolution, close, or decision batch;
`attention` is live regardless, so a stale narrative degrades gracefully.

## 10. Worked micro-example

Dispatch one unit: `create_work_items(task…)` → `create_job(kind=
implementation, scope=task, prompt=…, pins=[{charter,3}])` → worker:
`claim_job` (gets prompt) → works → `submit_job(report)` → policy
auto-creates `cross-model-review` check job → checker (different agent):
`claim_job(job_id=check)` → `submit_job(report result=pass)` →
orchestrator: `resolve_job(accepted)` → `close_task(changes=[…])`.
