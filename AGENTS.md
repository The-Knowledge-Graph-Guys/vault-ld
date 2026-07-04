# AGENTS.md — working on Vault-LD with an agent

Vault-LD is a specification (SPEC.md) plus reference tools (`scripts/`) for
reading a vault of Markdown notes as an RDF graph. Before changing anything,
read what governs your change: SPEC.md for the format, SECURITY.md for the
trust model, CONTRIBUTING.md for the PR flow.

## Record your rationale in HISTORY.md

Every substantive change adds a short entry under `## [Unreleased]` in
HISTORY.md, **in the same PR as the change**: what changed, *why* — the
constraint, failure, or design pressure that motivated it — and any
alternative that was considered and rejected. Match the voice and density of
the existing entries.

This is the repo's institutional memory, and it is load-bearing: contributors
are expected to point their own agent at HISTORY.md (plus `git log`) to
produce commits and PRs that match this repo's standards. Work whose
reasoning isn't recorded there is invisible to the next agent. Mechanical
changes (typo fixes, dependency bumps, CI plumbing) don't need an entry.

## House standards

- **PR titles are conventional commits** (`feat:` / `fix:` / `feat!:` /
  `docs:` / `ci:` …). PRs are squash-merged: the title becomes the commit on
  `main` and the release-notes line, and its type decides the version bump.
  CI rejects non-conforming titles.
- **Machine-owned files — never edit by hand:** everything release-please
  writes lives in `.github/` — `version.txt`, `CHANGELOG.md`, and
  `.release-please-manifest.json` are written by its release PRs only.
- **Security guarantees are pinned as tests** (`scripts/test_security.py`,
  run via `make test` in CI). Never weaken or delete a test to make work
  pass; a new guarantee ships with the test that pins it, in the same PR.
- **`make test` and `make roundtrip` must be green** before proposing a
  change. The roundtrip (vault → RDF → vault → RDF) is the spec's core
  invariant (SPEC §5.6).
- **Pin the supply chain:** GitHub Actions by full commit SHA (bump the SHA
  and its trailing version comment together), Python dependencies to exact
  versions in `scripts/requirements.txt`.
- **Workflows triggered by PRs hold read-only tokens** — never add a
  writable permission to a workflow that runs unmerged content (SECURITY.md).
- **Spec changes start as issues**, not PRs (CONTRIBUTING.md), and use
  RFC 2119/8174 key words deliberately in normative text.
