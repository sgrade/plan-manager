# Contributing

Thanks for your interest in Plan Manager. Development setup and project
conventions live in [`docs/contributing.md`](docs/contributing.md); this
file covers the **licensing and provenance requirements** for
contributions.

## License of contributions

By contributing, you agree that:

- **Code contributions** are licensed under the
  [Apache License 2.0](LICENSE).
- **Documentation contributions** are licensed under
  [CC-BY-4.0](LICENSE-docs).

We do not require a CLA. We use the
[Developer Certificate of Origin (DCO)](https://developercertificate.org/).

## Sign-off — required on every commit

Every commit must carry a `Signed-off-by:` trailer attesting you have
the right to contribute it under the project license:

    Signed-off-by: Jane Doe <jane@example.com>

Produce it automatically with `git commit -s` (set `git config user.name`
and `git config user.email` first). The DCO check blocks merges when any
human-authored commit lacks a valid sign-off. (Automated dependency and
release bots are exempt.)

## Signed commits — required

Every commit must also be GPG-signed. PRs containing unsigned commits
will be asked to amend and force-push the PR branch. The default branch
enforces verified signatures server-side.

## Workflow

1. Fork, then create a feature branch off `develop`.
2. Open a PR against `develop` (not `main` — `main` is release-only).
3. CI must be green: tests, DCO sign-off, and signed commits.
4. A maintainer merges once green; releases flow `develop` → `main`.
