---
module_contract: plan-manager/job-lifecycle
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-10
updated: 2026-08-10
---

# Module contract: job lifecycle

**Purpose.** Jobs are the dispatch-and-execution record: an immutable
launch prompt, a claim under lease, one fenced report, one resolution.
This module owns the state machine and claim semantics; it does NOT judge
work (that is the acceptance evaluator's seam).

## States and transitions

```
OPEN ──claim──▶ CLAIMED ──submit──▶ SUBMITTED ──accept──▶ ACCEPTED
  ▲               │ lease lapse:                └─reject──▶ REJECTED
  │               │  attempts left → stays CLAIMED, re-claimable
  │               │  attempts exhausted → EXPIRED (sweep materializes)
  └──reopen── EXPIRED
CANCELED ◀── OPEN | CLAIMED | SUBMITTED | EXPIRED
ACCEPTED / REJECTED / CANCELED are terminal. Mis-resolution ⇒ new job
(same prompt hash), never reopening a terminal state.
```

## Contract

- **Immutability ratchet**: kind, objective (≤200), prompt (content-
  addressed), pins, scope, target are frozen at creation. Changing a job
  = cancel + create. `idempotency_key` dedupes recovery-time dispatch.
- **Claim**: one CAS statement; readiness = (OPEN ∨ lapsed-CLAIMED with
  attempts remaining) ∧ scope deps DONE ∧ (checks) target SUBMITTED ∧
  NOT self-check (claimant ≠ target's claimant). Priority 0 first, FIFO
  within band. Claim envelope carries kind/objective/scope/target/
  attempt/lease/prompt+hash/pins — a worker needs no second read.
- **Lease & fencing**: `attempt` is the fencing token (first claim = 1).
  Heartbeat re-leases to now + lease_seconds; fenced by supersession,
  not clock (revives a lapsed-unreclaimed claim). Submit is fenced the
  same way and writes the report exactly once; a superseded submit is
  refused and discarded. Grace: lapsed-but-unreclaimed may still submit.
- **Report**: `{result: pass|fail|partial|blocked, findings, actions_taken,
  proposals, recommendation, artifacts[]}`; inline artifact content
  (≤256 KB, UTF-8/base64) is content-addressed on write.
- **Reopen**: EXPIRED (or lapsed-CLAIMED) → OPEN with
  `max_attempts = attempt + additional_attempts` — budget explicit,
  history never reset.

## Consumers and what they may assume

- **Tool layer**: maps envelopes/errors 1:1; adds no lifecycle logic.
- **Acceptance evaluator**: reads SUBMITTED jobs, their claimants,
  reports, pins; may flip SUBMITTED → ACCEPTED/REJECTED only through the
  storage acceptance invariant.
- **Awareness**: derives lease health, ready counts, EXPIRED lists from
  stored state + clock; never mutates.
- **Derivations**: rework_count = fixup jobs targeting jobs at the task's
  scope; review_feedback = check reports (two-hop via target).

## Non-goals

Scheduling policy beyond priority+FIFO (no aging, no quotas); worker
process management (PM never starts or wakes anyone); merging superseded
work (fencing discards, by design).
