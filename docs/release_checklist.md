# Beta Release Checklist

Keep this checklist versioned with the codebase. Complete all items before tagging a beta release.

## Gates (must pass)
- [ ] No open P0 issues; all P1s triaged with owners
- [ ] Structured logs and telemetry enabled as needed for diagnosis
- [ ] Manual QA checklist completed for core flows across supported platforms
- [ ] Release notes drafted with known limitations and upgrade steps
- [ ] Tagging and artifact publishing dry-run succeeds end-to-end

## Manual QA (core flows)
- [ ] Create plan → create stories → create tasks → create steps → approve_task (TODO→IN_PROGRESS)
- [ ] submit_for_review → review summary displays → approve_task (DONE)
- [ ] report (plan/story) shows expected guidance and summaries
- [ ] set_current_* messages guide user correctly (no auto-actions)

## Docs
- [ ] Quickstart concise and linked to usage guide and triage guide
- [ ] Usage guide reflects pause-after-selection and review behavior
- [ ] Triage guide up to date (labels, severities, dashboards, cadence)
- [ ] Config reference documents logging/telemetry and reload/reconnect

## Logging & Telemetry
- [ ] Correlation ID middleware active; corr_id appears in mutation logs
- [ ] Structured JSON logs for critical actions present
- [ ] Telemetry counters/timers sampled correctly when enabled

## Versioning & Tagging
- [ ] CHANGELOG Unreleased section finalized for this beta
- [ ] Tag prepared (e.g., v0.6.0-beta.N) and artifact generation commands validated
- [ ] Artifacts validated (format, contents, integrity)

## Sign-off
- [ ] Maintainer approval
- [ ] Release manager approval

Notes:
- If PLAN_MANAGER_RELOAD is used in dev, remind users to reconnect the MCP client after server reload.
- Prefer attaching the corr_id to reproduction steps when filing issues during QA.
