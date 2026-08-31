---
module_contracts: plan-manager
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-10 (the pin becomes the product version at release)
updated: 2026-08-10
---

# Module contract cards

The internal architecture of PM as a **modular monolith**: one deployable,
semantics concentrated in the single-writer database, module boundaries
following the CONSUMER structure. Each card is the one-page contract of a
seam that has multiple independent consumers — the internal analog of the
external conformance suite (`docs/conformance/`).

The bar for every card — boundaries exist for
comprehension: a maintainer or agent must be able to reason about the
seam — what it guarantees, what its consumers may assume, what they must
never do — **without opening the implementation**.

| Card | Seam | Primary consumers |
|---|---|---|
| `storage-invariants.md` | Transactional core: unit-of-work + the correctness invariants | every service |
| `job-lifecycle.md` | Job states, claims, leases, fencing | tool layer, acceptance evaluator, awareness |
| `governance-records.md` | Documents/revisions/approvals, decisions, delegations | acceptance evaluator, resume, audit, job creation |
| `acceptance-evaluator.md` | The gate: verdicts, pins, policy, auto-accept | resolve/submit paths, attention |
| `awareness-assembly.md` | Events, attention digest, resume assembly | pollers, UI, export |

Rules:

- Cards are validated from the consumer's seat: each card must stand
  alone, and is reviewed in isolation from the perspective of the
  consuming modules it names. A validated card is then the
  build-and-review baseline for every change touching its seam.
- A change to a seam's contract updates its card in the same commit.
- Boundary enforcement is mechanical (import-lint gate in `verify.sh`:
  tools → services → storage, no reverse imports; the acceptance
  evaluator imports no transport) — the floor, not the goal.
- Not every module gets a card: single-consumer helpers (validation,
  slugs, config, telemetry, UI templates) are governed by unit tests and
  review; a card there would be ceremony.
