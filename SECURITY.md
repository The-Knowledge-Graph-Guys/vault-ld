# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately via
[GitHub Security Advisories](https://github.com/The-Knowledge-Graph-Guys/vault-ld/security/advisories/new)
rather than opening a public issue. We will acknowledge reports as quickly as
we can and coordinate a fix and disclosure with you.

## Trust model

Vault-LD is a format for *sharing* knowledge, so the reference tooling treats
both sides of the roundtrip as untrusted input:

- **A vault** may be cloned from anywhere. Its notes, frontmatter, and
  `context.jsonld` documents are attacker-controllable content.
- **An RDF file** to be ingested may come from a foreign ontology. Every
  triple in it — including `vld:path` placement hints — is
  attacker-controllable content.

The reference scripts (`scripts/vault_to_rdf.py`, `scripts/rdf_to_vault.py`)
therefore guarantee:

- **No network I/O.** Export refuses to fetch remote `@context` documents;
  ingest disables outbound requests for the whole process before parsing, so
  hostile RDF cannot trigger remote fetches (SSRF). Ingest accepts an
  explicit opt-out, **`--unsafe-allow-network`**, for RDF that references
  public contexts you have verified as trustworthy (e.g. schema.org's) — a
  fetched document shapes how every triple is interpreted, so the flag
  prints a warning banner and pauses for five seconds before proceeding,
  giving you a window to cancel with Ctrl-C. Never use it on RDF from a
  source you do not trust.
- **Reads and writes stay inside the vault.** Context references, `vld:path`
  placement hints, and copied context files are rejected if they are
  absolute, contain `..`, or resolve outside the tree they belong to. Notes
  reached through symlinks are skipped.
- **Bounded parsing.** Frontmatter is parsed with a YAML SafeLoader variant
  that additionally refuses aliases (no "billion laughs" expansion) and is
  capped at 1 MiB per note — the cap binds *before* the file is read into
  memory, so an oversized note cannot exhaust it either. `context.jsonld`
  documents are capped at 4 MiB, and malformed frontmatter, undecodable
  notes, or unparseable context JSON skip the input instead of aborting the
  sweep (an unusable *root* context is a hard error — it decides where
  subjects mint — and is never overwritten).
- **No frontmatter injection.** Every generated YAML key and value is either
  verified to re-parse to exactly itself or emitted quoted, so a hostile IRI
  localname (a newline, a `: `) becomes inert data, never an extra
  frontmatter line. File stems derived from IRI localnames additionally strip
  path separators, control characters, and leading dots (`..` is a path
  step, not a name), and every note write is re-checked against the vault
  root before it happens.
- **No code execution surface.** The tools never invoke `eval`, `exec`,
  `pickle`, or a shell on vault or RDF content.

Anything rejected under these rules is reported as a warning — refused input
fails closed, never silently clamped to a different location.

## Regression testing

Each guarantee above is pinned as an executable test in
`scripts/test_security.py` (run with `make test`), and CI runs the suite on
every push and pull request — a change that weakens a patch fails CI before
it reaches review. New security fixes must land with their exploit added to
that suite. The CI workflow itself runs with a read-only token and pins its
actions to full commit SHAs.

## Dependencies

`scripts/requirements.txt` pins exact versions. When bumping, review the
rdflib and PyYAML changelogs/advisories — in particular, ingest relies on
network access staying disabled regardless of rdflib's own remote-fetch
defaults.

## Supported versions

Security fixes land on `main`. Use the latest release of the spec and
tooling.
