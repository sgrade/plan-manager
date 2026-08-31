---
conformance_suite: plan-manager
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-07 (the pin becomes the product version at release)
updated: 2026-08-07
---

# Plan Manager conformance suite

The project-owned artifact set that defines what it means to use PM's
contract correctly, and that validates the contract from the consumer's
side across the whole lifecycle — pre-implementation contract review,
acceptance drills at implementation, and standing regression afterward.

The vocabulary is deliberately not ours. It follows the established
conformance lineage:

- **Conformance suite** — the umbrella term as used for conformance test
  suites by the W3C QA Framework (conformance clauses, 2005), the
  Kubernetes conformance program, and the Model Context Protocol's own
  official conformance test suite (2026). The Java world's equivalent is
  the Technology Compatibility Kit (TCK, late 1990s) — "kit" appears here
  only as that historical parallel.
- **Conformance classes** — W3C's term for the categories of consumers a
  specification serves, each with its own requirements profile. Our
  client roles and capability tiers are conformance classes.
- **Scenarios** — the established term from scenario-based design through
  SEI/ATAM's scenario-shaped evaluation to τ-bench-style agent tasks; the
  OpenAPI Initiative's **Arazzo** specification (multi-step API workflows,
  v1.1, 2026) is the standards-track formalization target when these
  become machine-executable at implementation.
- **Living documentation** (Specification by Example, Adzic) — the
  maintenance philosophy: these artifacts stay current because the
  process uses them, not because someone remembers to update them.

## Contents

| Artifact | Established term | What it is |
|---|---|---|
| `interface-spec.md` | Interface specification (the contract's normative statement) | The public contract, self-contained — what clients may rely on |
| `conformance-classes.md` | Conformance classes (W3C QA lineage) | The consumer categories the contract serves: obligations, surface, capability profile per class |
| `scenarios.md` | Scenario suite | Scripted client journeys (defined initial state, complications, expected end) + the coverage map |

The suite is deliberately self-contained: everything needed to build
against the contract, test a client against it, or extend the suite is
in these three artifacts.

## Versioning rules

- Frontmatter on every artifact, four fields: `conformance_suite`,
  `contract_status` (`target-design` until the new contract ships, then
  `served`), `validates_contract` (the pin: design ref now, product
  version after release), `updated`.
- Deliberately NO independent suite version number — the suite versions
  with the product.
- **A change to the contract updates this suite in the same commit.**
  Once the contract ships, the CI inventory check verifies
  `interface-spec.md` against the served tool registry; class and
  scenario freshness is enforced by review and by regression drills
  — a previously green scenario failing in regression is the doc-rot
  alarm.

## Lifecycle

Created during the next version's design phase and hardened by
client-side contract review before any code existed. Finalized —
not created — during implementation: the spec flips to `served`
with the breaking release; the scenario suite doubles as the
acceptance-drill scripts and the standing regression suite; per-class
conformance obligations select which scenarios each client class must
pass.
