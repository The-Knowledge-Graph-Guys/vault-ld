# Contributing to Vault-LD

Vault-LD is an open standard, published so the community can evolve it. Contributions of every size are welcome, from typo fixes to new normative sections.

## The two kinds of contribution

**1. Changes to the specification (normative text in `SPEC.md`)**

Please **open an issue first** using the *Spec change proposal* template. Normative changes affect every conforming implementation, so they need discussion before wording. A good proposal states:

- the problem: what the spec currently gets wrong, leaves ambiguous, or cannot express;
- the proposed behaviour, ideally with a frontmatter/RDF example of both the current and the proposed outcome;
- who is affected: exporters, ingesters, or both.

Once there's rough consensus on the issue, submit a pull request.

**2. Everything else.** The reference tools (`scripts/vault_to_rdf.py`, `scripts/rdf_to_vault.py`), the example vault, the guides (`EXPORT.md`, `INGEST.md`), the README, typos, broken links: a direct pull request is fine, no issue needed.

## How to submit a pull request

1. Fork the repository and create a branch from `main`.
2. Make your change.
3. Keep the three layers in sync (the golden rule of this repo). A normative change usually touches all of:
   - `SPEC.md` (the rule),
   - `Vault-LD Example/` (a file demonstrating the rule),
   - the reference tools (code implementing the rule).
4. Verify the roundtrip still holds:

   ```sh
   pip install rdflib pyyaml
   python scripts/vault_to_rdf.py "Vault-LD Example" --out-dir build
   python scripts/rdf_to_vault.py RoundtripVault build/schema.ttl
   python scripts/rdf_to_vault.py RoundtripVault build/data.ttl
   ```

   Vault to RDF back to vault must be a no-op, and RDF to vault back to RDF must be graph-isomorphic (SPEC §5).
5. Open the pull request against `main`. The template will ask you to confirm the sync and roundtrip checks.

## PR titles, versioning, and the changelog

Releases are automated with [release-please](https://github.com/googleapis/release-please).
Pull requests are squash-merged and the PR title becomes the commit message,
so every title must be a [conventional commit](https://www.conventionalcommits.org)
— CI enforces the format:

| Title type | Example | Version bump on release |
|---|---|---|
| `feat:` | `feat: add SHACL export` | minor — 0.`y`.0 |
| `fix:` | `fix: percent-encode fragment anchors` | patch — 0.2.`z` |
| `feat!:` / `fix!:` — or any type with a `BREAKING CHANGE:` footer in the PR description | `feat!: fold vld:path into dcterms` | major — `x`.0.0 |
| `docs:`, `test:`, `ci:`, `chore:`, `refactor:`, `build:` | `docs: clarify §4.5 minting` | none |

Never edit the files release-please owns (all under `.github/` —
`version.txt`, `CHANGELOG.md`, `.release-please-manifest.json`) — it
generates them from merged PR titles. It maintains a running release PR that accumulates every
change merged since the last release; a maintainer merging that release PR is
what cuts the release — the version bump (the highest change in the batch
wins), the changelog entries, the `vX.Y.Z` tag, and the GitHub release, in
one step.

The machine ledger is deliberately terse. The narrative record — what a
release means and why the work happened — is **HISTORY.md**: add your
rationale under `## [Unreleased]` as part of your PR (see AGENTS.md if an
agent is doing the writing).

### Cutting a release (maintainers)

The open release PR's title names the version it will cut. Before merging it:

1. Open a small `docs:`-titled PR that stamps HISTORY.md — retitle
   `## [Unreleased]` to `## [X.Y.Z] — date` and add a fresh empty
   `## [Unreleased]` above it — and snapshots the docs site:
   `cd docs && npm run snapshot -- X.Y.Z` (commit the generated
   `versioned_docs/`, `versioned_sidebars/`, and `versions.json`).
2. Merge the release PR. Tag, GitHub release, and changelog are automatic.

The snapshot freezes that version's pages on the site: the latest release
serves at the site root, older releases stay in the version dropdown, and
`main`'s live state is browsable as "Next (unreleased)".

## Conformance language

The spec uses RFC 2119/8174 key words (**MUST**, **SHOULD**, **MAY**). Use them deliberately in normative text, and not at all in explanatory prose.

## Licensing

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](https://github.com/The-Knowledge-Graph-Guys/vault-ld/blob/main/LICENSE), the same license as the project. There is no CLA.

## Questions

Not sure whether something is a bug in a tool or an ambiguity in the spec? Open an issue and say so. Clarifying ambiguity is one of the most valuable contributions to a young standard.
