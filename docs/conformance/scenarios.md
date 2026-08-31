---
conformance_suite: plan-manager
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-07 (the pin becomes the product version at release)
updated: 2026-08-07
---

# Scenario suite

Living scenarios for pre-implementation contract review (tabletop),
acceptance drills (live), and regression runs. Each scenario has a
defined initial state, goal, injected complications, and expected end
state — the scenario lineage runs from scenario-based design through
SEI/ATAM's scenario-shaped evaluation to τ-bench-style agent tasks; at
implementation these formalize into machine-executable workflows (the
OpenAPI Arazzo shape: workflows, steps, success criteria). Client classes
per `conformance-classes.md`; each scenario is executed from the seat of
the classes it names. Scenarios A and B validated the target contract
during the design phase.

## A — dev archetype (orchestrator + 2 workers, one doubling as checker)

Classes cast: orchestrator, worker ×2 (one doubling as checker).
Initial: empty PM. Goal: deliver plan "Auth hardening" — S1 "Token
rotation" (T1 "Add KMS call", T2 "Rotate signing keys", T3 "Wire rotation
into login" dep T1+T2); S2 "Audit trail" dep S1 (T4 "Emit auth events",
T5 "Retention job" dep T4). Governing document `charter` (rev 1,
approved); kickoff ruling recorded binding. Policy: `implementation`
requires `[mechanical-suite, cross-model-review]`, auto_create on,
auto_accept off. Jobs pin `charter@1`.

Complications: (1) T2's cross-model-review returns FAIL → full rework
loop (reject → fixup inheriting the target's gate → re-check → green);
(2) charter revised to rev 2 + approved mid-flight; T4's job (pinned @1)
reaches resolution — stale-pin handling exercised; (3) orchestrator
session dies after T3's acceptance — fresh session cold-starts (step 0 if
plan id unknown → `resume` → `list_jobs`) and continues.

Expected end: plan DONE; ≥2 decisions (one superseding, binding
re-asserted); charter@2 approved, @1 approval intact on rev 1; every
task's close carries `changes[]`; governance summaries clean.

## B — ops archetype (orchestrator + 2 competing workers, one doubling as checker)

Initial: plan "Fleet repair", story "Node repairs", 8 identical
independent tasks R1..R8. Goal: repair the fleet unattended. 8 `repair`
jobs (lease 600s, max_attempts=3, idempotency_key set); policy: `repair`
requires `[verify-fix]`, auto_create on, **auto_accept on**.

Complications: (1) worker crashes mid-job (no heartbeat) — lease lapses,
`job.lease_lapsed` observed, another worker reclaims at attempt 2;
(2) the crashed worker returns holding stale claim data, follows the
wake-up protocol (heartbeat first) OR naively submits — fenced stale-claim
refusal either way, no event (successor's claim is the observable);
(3) one job exhausts attempts → EXPIRED → orchestrator `reopen_job`
with one more attempt; (4) a self-check claim attempt is refused
structurally; (5) one no-longer-needed duplicate job is withdrawn via
`cancel_job`; (6) the orchestrator coordinates exclusively via
`poll_events` + `resume` (no direct worker contact) and closes tasks
only after their jobs' acceptances appear in the stream.

Expected end: all jobs ACCEPTED by auto-accept (resolver
`agent://pm/policy`, observed in `job.resolved` events) or canceled; the
ORCHESTRATOR then closes the 8 tasks DONE (closing never happens by
itself); every redelivery, lapse, and refusal visible in the event
stream or explained by it.

## C — lean solo path (solo agent + human; no dispatch machinery)

Initial: empty PM. Goal: a single agent + human deliver a small plan with
ZERO jobs, policies, documents, or delegations — the contract's minimum
viable workflow.

Script: `create_work_items` bulk with same-batch `"#index"` dependencies
(plan, 1 story, 4 tasks in ONE call each level) → work → `close_task`
with `changes[]` per task → mid-way, the agent's session resets and
resumes from `resume` + `list_work_items` alone. Complications: (1) a
task with an unmet dependency shows `display_status: BLOCKED`, and
closing it anyway SUCCEEDS — closing is deliberately independent of
dependency state (the record shows the out-of-order close; nothing
polices it); (2) one task is abandoned — retired via
`update_work_item(status=CANCELED)`, and rollups exclude it; (3) a
created-in-error task is hard-deleted (no jobs reference it — succeeds);
(4) a concurrent duplicate `close_task` gets the CAS refusal; (5) an
`update_work_item` with a stale `expected_version` gets the structured
conflict and retries after a re-read.

Expected end: plan DONE with 3 DONE + 1 CANCELED tasks; zero jobs in
`list_jobs`; the governance summary on every close shows zeros (and that
is fine — solo is a first-class flow).

## D — governance and handover (orchestrator, sub-orchestrator, 1 worker)

Initial: plan "Compliance hardening" with 2 stories. Goal: exercise the
records that make delegation and rulings auditable.

Script: charter + `dispositions` documents authored and approved; three
binding decisions appended (one later superseded — binding NOT inherited,
re-asserted explicitly); orchestrator delegates story S2 to a
sub-orchestrator via `create_delegation` (verbatim authority list); the
sub-orchestrator dispatches S2's jobs, resolves them, and its own
delegation chain is extended one hop (`via_delegation_id`) for a helper;
work pins `charter@2`; the delegation is later revoked; a fresh auditor
session reconstructs WHO did WHAT under WHOSE authority purely from
`list_delegations` + `list_decisions` + `poll_events` + resolutions.

Complications: (1) approvals never float: after revising to @2,
`get_document(rev=2)` shows an EMPTY approvals list until @2 is approved,
while `get_document(rev=1)` retains its approval; the audit step also
runs `diff_document(1, 2)` to ground the change; (2) a job pinned to a
superseded charter reaches
resolution → fail-closed acknowledge-or-reject exercised with the
decision log explaining the choice; (3) the revoked delegate attempts a
resolve — it SUCCEEDS mechanically (identity is honor-system; recorded)
and the audit reconstruction must flag it via the revocation timestamp
ordering, demonstrating tamper-EVIDENT vs tamper-proof.

Expected end: audit narrative reconstructible from records alone; all
S2 work ACCEPTED under recorded (revoked-or-live) authority; decision log
shows the supersession chain.

## Coverage map (scenario × contract surface)

| Contract surface | A | B | C | D |
|---|---|---|---|---|
| Work-item CRUD + bulk + `#index` deps | ✓ | | ✓ | ✓ |
| `close_task` + rollups + governance summary | ✓ | ✓ | ✓ | |
| Job lifecycle (create/claim/submit/resolve/cancel) | ✓ | ✓ | | ✓ |
| Leases, heartbeat, fencing, wake-up protocol | | ✓ | | |
| Redelivery, EXPIRED, reopen, idempotency_key | | ✓ | | |
| Checks + policy gates | ✓ | ✓ | | |
| Rework/fixup gate inheritance | ✓ | | | |
| auto_accept + `agent://pm/policy` + self-check refusal | | ✓ | | |
| `expected_version` conflict path | | | ✓ | |
| `diff_document` | | | | ✓ |
| Documents, revisions, digest-bound approvals | ✓ | | | ✓ |
| Decisions, binding set, supersession | ✓ | | | ✓ |
| Pins + stale-pin resolution paths | ✓ | | | ✓ |
| Delegations + multi-hop chain + revocation | | | | ✓ |
| Events, polling, cold start (`resume`, step 0) | ✓ | ✓ | ✓ | ✓ |
| Retire-by-status, hard-delete guards | | | ✓ | |
| Error/recovery envelopes (CAS, stale claim, refusals) | ✓ | ✓ | ✓ | ✓ |

Gaps a future scenario E would need: export/import round-trip and
feed_epoch restore semantics (operational, live-mode only); multi-plan
cross-interference (two plans, one orchestrator pool); priority-band
claim-ordering assertions (0-highest FIFO-within-band, live-mode
measurable); `heartbeat_job` noise-suppression observability.
