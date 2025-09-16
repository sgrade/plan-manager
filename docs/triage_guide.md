# Triage Guide

This guide standardizes severity labels and SLAs for Plan Manager issues.

## Labels
- type:bug — defect in behavior
- type:enhancement — improvement or polish
- type:docs — documentation only
- area:* — component or subsystem (e.g., area:tools, area:server, area:docs)
- needs-info — missing reproduction or details
\n+Performance topics: use `area:performance` in addition to `type:enhancement` unless there is a clear functional defect (then use `type:bug`).

## Severity (Priority)
- P0 — Crash/data loss/security; blocks primary flows.
- P1 — Broken but with workaround; major UX or correctness impact.
- P2 — Minor issue/polish; does not block shipping.
\n+Examples:
- P1: Feature works but is unacceptably slow for typical inputs; or incorrect output with readily available workaround.
- P2: Minor latency regression in non-critical path; cosmetic misalignment.

## SLAs (targets)
- P0 — Acknowledge: 24h; Fix: 72h or hotfix plan.
- P1 — Acknowledge: 48h; Plan/Fix: within one iteration.
- P2 — Batch and address during polish windows.

## Triage Routine
- Initial: apply labels, set P0/P1/P2, add repro steps or mark needs-info.
- Weekly: review new/untriaged items; re-evaluate severities; assign owners.

## Dashboards
- Saved views for: P0 open, P1 open, needs-info, and by area.

### Accessing views in Plan Manager
- Plan overview: run `report plan`.
- Backlog by priority: run `list_tasks` and scan for `priority` (0 is highest).
- Needs‑info and area: reflect labels in titles/descriptions; group via stories.

Note: First‑class filters are planned in future iterations.
