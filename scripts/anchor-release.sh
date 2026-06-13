#!/usr/bin/env bash
#
# anchor-release.sh — add provenance to a published release, LOCALLY.
#
# release-please cuts releases in CI and creates a lightweight, unsigned
# tag. Rather than put a GPG key on CI runners, the maintainer runs this
# once locally right after a release to:
#
#   1. Replace that release's lightweight tag with a SIGNED ANNOTATED tag
#      at the SAME commit (the commit SHA and the GitHub Release are
#      unchanged; only the tag object is upgraded).
#   2. Write an OpenTimestamps proof for the tag under provenance/ and
#      commit it on the current branch (run this from `develop`).
#
# Note: the tag ruleset protects tags from deletion and overwrite for
# everyone except the repo admin (ruleset bypass), so the maintainer can
# re-sign a release tag here without putting a signing key on CI. Run
# from the repo root, on `develop`, with the GPG agent unlocked.
#
# Usage:   scripts/anchor-release.sh <VERSION>
# Example: scripts/anchor-release.sh plan-manager-v0.12.0
#
# Follow-up (24-48h later, after the Bitcoin calendar confirms):
#   ots upgrade provenance/<VERSION>.sha.ots && \
#     git add provenance/<VERSION>.sha.ots && \
#     git commit -m "chore(provenance): upgrade OTS proof for <VERSION>" && git push

set -euo pipefail

VERSION="${1:-}"
[ -n "$VERSION" ] || { echo "usage: scripts/anchor-release.sh <VERSION>  (e.g. plan-manager-v0.12.0)" >&2; exit 1; }

command -v gpg >/dev/null || { echo "error: gpg not found" >&2; exit 1; }
command -v ots >/dev/null || { echo "error: ots not found — pip install opentimestamps-client" >&2; exit 1; }

git fetch --tags origin >/dev/null 2>&1 || true
git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null \
  || { echo "error: tag '$VERSION' not found locally or on origin" >&2; exit 1; }

commit="$(git rev-list -n1 "$VERSION")"
echo "Anchoring $VERSION at commit ${commit:0:12}"

# 1. Upgrade the lightweight tag to a signed annotated tag (same commit).
if [ "$(git cat-file -t "$VERSION")" = "tag" ] && git tag -v "$VERSION" >/dev/null 2>&1; then
  echo "  $VERSION is already a signed annotated tag — leaving it."
else
  git tag -d "$VERSION"
  git tag -s "$VERSION" "$commit" -m "$VERSION"
  git push --force origin "$VERSION"
  echo "  re-signed $VERSION (annotated, GPG-signed) at the same commit"
fi

# 2. OpenTimestamps proof, committed on the current branch.
mkdir -p provenance
git rev-parse "$VERSION" > "provenance/$VERSION.sha"
ots stamp "provenance/$VERSION.sha"
git add "provenance/$VERSION.sha" "provenance/$VERSION.sha.ots"
git commit -m "chore(provenance): OpenTimestamps proof for $VERSION"
git push
echo "Done. In 24-48h: ots upgrade provenance/$VERSION.sha.ots (then commit + push)."
