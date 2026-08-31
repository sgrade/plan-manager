---
module_contract: plan-manager/acceptance-evaluator
contract_status: target-design
validates_contract: next-version contract design, draft of record 2026-08-10
updated: 2026-08-10
---

# Module contract: acceptance evaluator (the gate)

**Purpose.** The one place PM refuses on governance grounds: acceptance
of a job is recorded only when the required non-submitter verdicts exist
and the pinned ground truth hasn't silently moved. Defects historically
concentrate at this seam — its contract is written to be read closely,
and changes here deserve the most scrutiny.

## Inputs (all read inside the acceptance transaction)

- The target job: kind, claimant, status (must be SUBMITTED), pins.
- The governing policy row: the job's own kind, or — when the job carries
  `target_job_id` and its kind has no row — its TARGET's kind (fixups
  inherit the gate of what they fix).
- Check jobs targeting this job: per required check kind, the NEWEST one
  that is SUBMITTED or ACCEPTED with `report.result = 'pass'` and
  `claimed_by ≠` the target's claimant.
- Document heads for every pin (staleness = pinned rev ≠ head).

## Outputs

- **Refusal** (structured): names exactly the missing verdict kinds
  and/or the stale pins. Refusals are not mutations and emit no event.
- **Resolution record**: decision, resolver identity, verdict job ids,
  per-pin staleness, verbatim acknowledgments, timestamp — written with
  the status flip in one transaction (`status='SUBMITTED'` in the
  predicate; racing resolvers produce exactly one resolution).

## Rules

1. `accepted` requires (a) all required PASS verdicts from non-submitters
   AND (b) fresh pins — or explicit `acknowledge_stale_pins` naming each
   stale pin, recorded verbatim.
2. `rejected` is never blocked and requires `reason`. Rework = a new
   fixup job targeting this one; the fixup's own submission re-enters
   this gate under the inherited policy.
3. **Auto-accept** (policy `auto_accept=true`): fires the moment the last
   required PASS verdict lands; resolver `agent://pm/policy`; NO
   acknowledgment path — stale pins block it, emit
   `job.autoaccept_blocked`, and leave the job SUBMITTED for a hands
   resolution.
4. On submission of a gated kind: auto-create one OPEN check job per
   required kind (target set, `requires_target_submitted`, pins inherited
   from the target, generated brief) unless a live check of that kind
   already targets the submission.
5. When a target leaves SUBMITTED: its still-OPEN checks are auto-
   canceled (`target_resolved`). Checks themselves never require
   resolution and are exempt from policy (no checks-on-checks — validated
   at `set_policy`: a kind is `on_kind` XOR in `required_checks`).

## Consumers and what they may assume

- **resolve_job / submit_job tools**: thin mappers; all gate logic lives
  here and nowhere else.
- **Awareness**: renders awaiting-resolution items with the SAME
  missing-verdict/stale-pin computation (one implementation, two
  surfaces).
- **Honesty boundary**: non-submitter checks are structural under
  RECORDED identity — self-declared `agent` strings make them
  tamper-evident, not tamper-proof, until authentication lands.

## Non-goals

Judging report quality (process law: checker skills, review discipline);
conditional/branching policies (flat list per kind, deliberately);
transport concerns (this module imports none — lint-enforced).
