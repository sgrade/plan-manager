---
module_contract: plan-manager/awareness-assembly
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-10
updated: 2026-08-10
---

# Module contract: awareness assembly

**Purpose.** How anyone — orchestrator, worker, UI, a fresh session with
nothing — learns what is happening and what needs action, without private
channels: an append-only event feed with a gap-free cursor, a computed
attention digest, and the one-call cold start.

## Contract

- **Event feed**: every mutation's event is appended in that mutation's
  transaction (outbox invariant). `poll_events(after_seq, plan_id?,
  limit?)` → `{events, latest_seq, feed_epoch}`; `seq` is global,
  monotonic, gap-free under the single writer; omit `plan_id` to watch
  everything in one poll. `feed_epoch` changes only on continuity loss
  (lossy restore): epoch change or a future cursor ⇒ re-read state,
  resume from `latest_seq`. Event types are a closed registry
  (work_item.*, job.* incl. lease_lapsed and autoaccept_blocked,
  decision.appended, document.revised/approved, delegation.*,
  task.closed + governance summary, policy.changed). Heartbeats are
  noise-suppressed and excluded unless `include_noise`. Refused calls
  emit nothing — the observable for a fenced stale submit is the
  successor's `job.claimed` with a higher attempt.
- **Attention digest** (computed, never stored): `ready` (claimable
  jobs), `in_flight` (claims + lease health), `awaiting_resolution`
  (SUBMITTED non-check jobs, with missing verdicts and stale pins named
  by the acceptance evaluator's own computation), `expired`,
  `unapproved_pinned_head` (live-pinned documents whose head lacks
  approval). Checks with terminal targets never appear.
- **Resume** (cold start): resume document (latest rev + hash + approval
  state, or explicit null if never authored — never an error), the
  currently-binding decision set, document heads, the attention digest,
  `latest_seq`. Drill: plan discovery (step 0, when the id is unknown) →
  `resume` → `list_jobs` (+ `list_decisions` for history). No other
  transport exists.
- **Optional push path** (post-implementation option): the event log
  exposed as `resource://events` with standard resource-updated
  notifications; polling remains the primary, universally supported
  contract.

## Consumers and what they may assume

- **Orchestrators/pollers**: cursor loops never miss or duplicate events
  within an epoch; one poll can watch all plans.
- **UI**: renders from the same repositories and derived statuses
  (display_status), read-only; recent-events panels are bounded reads of
  the same feed.
- **Export/import**: must preserve `seq` and `feed_epoch` for cursors to
  survive restore; a lossy path mints a new epoch — never silently.

## Non-goals

Event replay as state reconstruction (state lives in rows; events are
awareness, not the source of truth); per-consumer event queues or
acknowledgments; retention policy (deferred until size demands it — prune
from the head only, preserving monotonicity).
