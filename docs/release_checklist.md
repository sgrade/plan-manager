# Release Checklist

This checklist ensures release quality. Most release mechanics are automated by [release-please](https://github.com/googleapis/release-please).

## Pre-Release Quality Gates

Complete all items before merging the release-please PR.

### Code Quality
- [ ] No open P0 issues; all P1s triaged with owners
- [ ] All CI checks passing (tests, lint, type-check, security)
- [ ] Test coverage meets threshold (40%+)
- [ ] No known regressions from previous version

### Documentation
- [ ] Usage guide reflects new features/changes
- [ ] API changes documented
- [ ] Breaking changes clearly documented with migration guide
- [ ] README updated if needed

### Manual QA (Core Flows)
- [ ] Create plan → create stories → create tasks → create steps → start_task (TODO→IN_PROGRESS)
- [ ] submit_pr → review summary displays → approve_pr or request_pr_changes → merge_pr (DONE)
- [ ] report (plan/story) shows expected guidance and summaries
- [ ] set_current_* messages guide user correctly (no auto-actions)

### Logging & Telemetry
- [ ] Structured logs for critical actions present
- [ ] Correlation ID middleware active; corr_id appears in mutation logs
- [ ] Telemetry counters/timers sampled correctly when enabled

### Release Notes
- [ ] Release-please generated changelog is accurate
- [ ] Breaking changes are highlighted
- [ ] Known limitations documented
- [ ] Upgrade steps provided (if needed)

## Release Process (Automated)

The project uses release-please for automated releases:

1. **Development**: Commit changes using [Conventional Commits](https://www.conventionalcommits.org/)
2. **Merge to main**: Push to main or merge develop → main
3. **Release PR created**: Release-please automatically creates a PR with:
   - Version bump in `pyproject.toml`
   - Updated `CHANGELOG.md`
   - Release notes
4. **Review**: Complete this checklist ✓
5. **Merge Release PR**: Merging triggers automatic:
   - Git tag creation
   - GitHub Release
   - Artifact build and upload

See [contributing.md](./contributing.md#release-process) for detailed workflow.

## Manual Release (Exceptional Circumstances Only)

**When to use:** Only in exceptional cases such as:
- Critical hotfix needed when GitHub Actions is down
- Emergency security patch
- Need to release from a fork without release-please configured

**Normal process:** Use the automated release-please workflow above.

### Manual Steps

If you must release manually, follow these steps:

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
