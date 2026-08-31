---
module_contract: plan-manager/governance-records
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-10
updated: 2026-08-10
---

# Module contract: governance records

**Purpose.** The tamper-evident memory: what binds (documents at pinned
revisions), what was ruled (decisions, verbatim), who held authority
(delegations). This module makes governance MECHANICALLY CHECKABLE; it
never evaluates or enforces process (that split is the design's stance:
memory, not police — the one exception, pin-staleness at acceptance,
belongs to the acceptance evaluator).

## Contract

- **Documents**: named per plan; revisions are an immutable chain
  (rev 1,2,3…; content sha256-addressed in shared blobs; write requires
  `parent_rev == head` or structured conflict). Diffs computed on demand,
  never stored. No delete — retirement is a final revision with a RETIRED
  banner. `resume` is a well-known name with content conventions.
- **Approvals**: bound to `(name, rev, content_hash)` — the four-column
  FK makes a hash/revision mismatch unrepresentable. Approvals NEVER
  float to newer revisions.
- **Decisions**: append-only `{decided_on, verbatim_quote, consequence,
  refs, binding, supersedes_id, author}`. The stored quote is never
  trimmed or normalized. Corrections append with same-plan
  `supersedes_id`; `binding` is per-entry and never inherited across
  supersession. The currently-binding set is a DERIVED query
  (binding ∧ not superseded) — nothing separate to drift.
- **Delegations**: verbatim authority grant lines; `via_delegation_id`
  chains multi-hop authority; revocation is a timestamp. PM records the
  chain; whether the grantor actually held what it granted stays process
  law until authentication exists.

## Consumers and what they may assume

- **Job creation**: validates document pins resolve to existing
  revisions with matching hashes at create time.
- **Acceptance evaluator**: compares each pin against the document head
  inside the acceptance transaction; reads approvals never mutates.
- **Resume/awareness**: reads heads, binding set, approval state; the
  unapproved-pinned-head attention item = documents pinned by a live job
  whose head lacks approval.
- **Audit**: reconstructs who/what/under-whose-authority purely from
  delegations + decisions + events + resolutions — revocation-timestamp
  ordering exposes post-revocation acts (tamper-EVIDENT, not proof).

## Non-goals

Document merge/branching (linear history only); decision editing of any
kind; authority EVALUATION (recorded, not enforced); blob garbage
collection (deferred until a real size problem exists).
