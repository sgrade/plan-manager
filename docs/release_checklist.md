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

### Commands: Tagging and Artifacts (dry-run)

Use these commands to validate tagging and artifact generation without pushing or publishing.

1) Verify a clean working tree and inspect the latest tag

```bash
git status --porcelain
git describe --tags --abbrev=0 || echo "none"
```

2) Pick a candidate beta tag (ensure consistency with `pyproject.toml` version)

```bash
# Example: if pyproject shows 0.5.5 and you intend a beta pre-release for 0.5.6
export CANDIDATE_TAG=v0.5.6-beta.1
git rev-parse -q --verify "refs/tags/$CANDIDATE_TAG" >/dev/null && echo "EXISTS" || echo "AVAILABLE"
```

3) Build artifacts locally (no publish)

```bash
rm -rf dist build
uv build
ls -lh dist/
```

4) Validate artifact integrity and contents

```bash
# Checksums
shasum -a 256 dist/*

# Peek inside sdist (tar.gz)
tar -tzf dist/*.tar.gz | head -n 20

# Peek inside wheel
unzip -l dist/*.whl | head -n 30
```

5) Tagging (dry-run guidance)

Do not push in a dry-run. If you want to fully simulate the command locally, you can create an annotated tag and then delete it:

```bash
# Create annotated tag locally (do not push during dry-run)
git tag -a "$CANDIDATE_TAG" -m "Beta pre-release $CANDIDATE_TAG"

# Verify it exists locally
git tag --list "$CANDIDATE_TAG"

# Cleanup (remove local tag after verification)
git tag -d "$CANDIDATE_TAG"
```

6) Publishing (real release, optional later)

When ready to release (after sign-offs), push the tag and publish to your chosen index:

```bash
# Push the tag
git tag -a "$CANDIDATE_TAG" -m "Beta pre-release $CANDIDATE_TAG"
git push origin "$CANDIDATE_TAG"

# Publish (configure credentials in environment beforehand)
uv publish
```

## Sign-off
- [ ] Maintainer approval
- [ ] Release manager approval

Notes:
- If PLAN_MANAGER_RELOAD is used in dev, remind users to reconnect the MCP client after server reload.
- Prefer attaching the corr_id to reproduction steps when filing issues during QA.
