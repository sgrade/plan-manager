---
conformance_suite: plan-manager
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-07 (the pin becomes the product version at release)
updated: 2026-08-07
---

# Conformance classes

Per the W3C QA lineage, a conformance class is a category of consumer
that can claim conformance to a specification, with its own requirements
profile. PM's contract serves the classes below. Each class states: the
contract surface it uses, the **obligations** a conforming member must
meet (these are testable — reviews and drills select scenarios per
class), and the capability profile it runs at in production.

Derivation rule: classes come from the contract itself. A tool serving no
class here is a contract smell; a class need the contract cannot express
is a finding.

## Class: conforming orchestrator

- **Uses**: the full surface; heaviest on `create_work_items`,
  `create_job`, `resolve_job`, `close_task`, `append_decision`,
  `put_document`/`approve_document`, `set_policy`, `poll_events`, `resume`.
- **Testable obligations** (contract-observable): every call carries
  explicit scope ids; rejections carry `reason`; stale pins are either
  acknowledged (recorded) or the job is rejected — never left dangling;
  polling resumes from returned cursors and honors `feed_epoch` resets;
  recovery-time dispatches carry `idempotency_key`.
- **Process obligations** (audited via records, not contract-enforced):
  rulings recorded verbatim via `append_decision`; the stale-pin
  criterion applied with judgment (acknowledge only immaterial diffs);
  the `resume` document maintained at record points.
- **Capability profile**: strong reasoning tier (Opus/GPT-5-class,
  thinking enabled).

## Class: conforming worker

- **Uses**: `claim_job`, `heartbeat_job`, `submit_job`, `get_job`,
  `get_document`, `list_decisions`, `poll_events`; read-only
  `get_work_item`.
- **Testable obligations**: heartbeats at ≤ ⅓ of `lease_seconds` while
  holding a claim; heartbeat precedes any post-interruption submit
  (drill-observable — heartbeat events are noise-suppressed in PM's own
  records); reports conform to the structured shape; submits carry the
  claim's `(agent, attempt)` fence; `prompt_hash` verified on any
  re-fetch (drill-observable — reads emit no events).
- **Process obligations** (audited via records): `result` reported
  honestly; on a stale-claim error, local work abandoned before side
  effects; never resolves/approves/appends decisions; redelivered work
  (`attempt > 1`) treated as potentially partially executed — state
  verified before acting.
- **Capability profile**: the cheapest tier that passes the class's
  scenarios (Sonnet/Flash/fast-code class) — deliberately the
  least-capable supported client; ambiguity this class hits is a contract
  defect, not a client defect.

## Class: conforming checker

- **Uses**: the worker surface, plus `get_job(target,
  include_artifacts=true)` and `list_jobs(target_job_id=…)`.
- **Testable obligations**: fetched the target's report before verdict
  (drill-observable — `get_job` is a read and emits no event; a live
  harness sees the call order); never claims a check on its own
  submission (structurally refused, contract-observable).
- **Process obligations** (audited via records): review conducted against
  the target's PINNED revisions (inherited by the check), not heads;
  verdicts carry findings with evidence; model family ≠ the target
  author's; aliasing to evade independence is a recorded violation.
- **Capability profile**: mid-to-strong tier, model family ≠ the target
  author's (process law from the review discipline).

## Class: conforming solo agent

- **Uses**: `create_work_items`, `get/list/update/delete_work_item`,
  `close_task`, `resume`, `poll_events`. No dispatch machinery.
- **Testable obligations** (contract-observable): every close carries
  non-empty `changes[]`; abandoned work retired by status
  (`CANCELED`/`DEFERRED`) rather than deletion (deletion attempts on
  referenced items are refused anyway).
- **Process obligations** (audited via records): `changes[]` content
  meaningful as the unit's result record; resumes from `resume` +
  `list_work_items` after context loss rather than reconstructing from
  memory.
- **Capability profile**: mid tier (interactive IDE-class agent), human
  in the loop.

## Class: human supervisor (observer)

- **Uses**: the read-only `/ui`; rulings enter the record through the
  orchestrator (`append_decision`, `approve_document`).
- **Obligations**: none testable at the contract; the supervising human
  is the source of rulings, not a conforming client.

## Reserved system identity: `agent://pm/policy`

Not a conformance class — PM itself, recording stage-2 auto-acceptances.
Never a claimant; appears only as a resolver identity with verdict job
ids attached.

## Notes

- Tiers are working defaults; revisit against real deployment data.
- Identity is self-declared until authentication lands: obligations are
  auditable (attribution records), not enforced surfaces — except where
  the contract enforces structurally (fencing, self-check refusal,
  verdict-gated acceptance).
