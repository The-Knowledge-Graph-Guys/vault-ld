# Changelog

All notable changes to the Vault-LD specification and its reference tools are
documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions track the specification, with the tools evolving alongside it.

## [0.2.0] — 2026-07-03

### Specification

#### Identity (§4.5)
- **One minting rule for every note**: the IRI is the governing `@base` + the
  file name alone, without `.md`. Folders never enter any IRI — `Recipes/` is
  shelving, not naming. Moving a note never re-mints its identity; only
  renaming does.
- The **governing context** is formalised as the nearest `context.jsonld` at
  or above the note (the scoped-base assembly rule, §4.2). Only the vault-root
  context is mandatory; per-ontology, per-vocabulary, and nested data-folder
  contexts are optional refinements that govern their subtrees.
- An explicit `id` **MUST be a full absolute IRI** (`http(s)://…`), used
  verbatim. It disambiguates same-named files (which otherwise mint the same
  IRI and merge), pins an identity across renames, and can place a subject in
  any namespace. Relative values are non-conforming.
- Non-IRI-safe file names (spaces, most commonly) are **percent-encoded** on
  minting and percent-decoded on ingest, so `Red Lentil Soup.md` round-trips
  without a pin.

#### Placement roundtrip (§5.4, §5.5)
- **`vld:path "<path>.md"`** — Vault-LD's own string-valued property, the
  sole term of the `vld:` namespace
  (`https://github.com/The-Knowledge-Graph-Guys/vault-ld#`) — carries the
  true, context-relative location
  of every note the graph could not otherwise reconstruct — every pinned note,
  every instance not sitting directly in its governing context's folder, and
  every schema note away from the flat placement of §5.1. The triple exists
  only on the RDF side: it materialises on export and dissolves back into file
  placement on ingest, never appearing in frontmatter. File placement is now
  part of roundtrip fidelity (§5.6).
- Emitting the placement triples is required only of a **roundtrip-face**
  export; an export produced purely for querying — a read-only artifact —
  omits them (§5.4 step 7).

#### Hierarchy (§5.2)
- **Frontmatter is the only carrier** of `subClassOf` / `subPropertyOf` /
  `broader` / `topConceptOf`; a tool MUST NOT derive hierarchy from folder
  nesting. Nesting a schema file is purely organisational.
- `skos:topConceptOf` joins the frontmatter contract, with the
  concept-vs-scheme distinction (`broader` links concept to concept, never to
  the scheme) made explicit.
- Canonical, reconstructable schema placement is the **flat form of §5.1**
  (classes in `Classes/`, properties in `Properties/`, concepts at the
  vocabulary top level). Folder organisation beyond that is deliberately a
  tool's own affair, outside the spec — any layout round-trips via
  `vld:path`.

#### Keywords and the context (§4.2, §4.3)
- **Keyword aliasing**: the context maps `type` → `@type` and `id` → `@id`
  (JSON-LD 1.1 §4.1.7), so notes read as plain YAML keys with no quoting.
  Conforming tools honour declared aliases on input and write them on output.
- **Host-tool keys** (`tags`, `aliases`, `cssclasses`) are recognised as
  editor affordances: never emitted as triples, never warned about, and
  promotable to first-class terms by mapping them in the context.
- **Context composition** hardened: array contexts compose by reference with
  left-to-right override; a conflicting redefinition of an established term or
  prefix warns (an identical re-declaration stays silent); the scoped-`@base`
  rule is framed as Vault-LD's assembly rule above stock JSON-LD, with the
  interoperability consequence (generic processors ignore `@base` in
  referenced contexts) stated plainly.

#### Wiki links (§4.4.1)
- Full **link grammar**: paths disambiguate, aliases are display-only,
  fragments resolve to the note. Generation and resolution are two halves of
  one contract — ambiguous names are emitted path-qualified and resolved
  right-aligned on segment boundaries; dangling links are flagged, never
  dropped.

#### Conformance and compatibility (§6, Appendix B)
- Conformance checklist expanded to cover name-only minting, absolute `id`,
  frontmatter-only hierarchy, `vld:path` handling, and body
  preservation; conforming exporter / ingester / roundtrip tool defined.
- **Appendix B: lifting an OKF bundle** — a compatibility profile turning a
  Google Open Knowledge Format bundle into a conforming vault without
  modifying a single bundle file.

### Tools
- **`scripts/rdf_to_vault.py`** — the reference ingester (RDF → vault),
  closing the roundtrip: one note per subject, in-place updates that preserve
  bodies and host keys, context synthesis and term coining for unmapped
  predicates, `vld:path` consumption, and percent-decoded file names.
  Opt-in `--nest` lays fresh schema files out along the declared hierarchy —
  a folder-management convenience, not spec behaviour.
- Tooling moved to **`scripts/`**, with a root **`Makefile`**
  (`make roundtrip` = export → rehydrate → rebuild → graph-isomorphic
  compare), `scripts/compare_builds.py`, and `scripts/requirements.txt`.
- `--data-ns` on both tools is now an explicit override for the **vault-root
  base only**; nested data-folder contexts still govern their subtrees.
- Exporter defaults to **query-only output** — a lean, read-only `.ttl` with
  no placement bookkeeping; `--source` opts into the roundtrip face that
  emits the `vld:path` triples (used by `make roundtrip`).
- Makefile venv paths work on Windows (`venv/Scripts/`) as well as Unix
  (`venv/bin/`); added a `make query` target for the default lean export.
- Exporter warnings sharpened: same-IRI merges suggest an explicit absolute
  `id`, ambiguous names suggest path-qualified links, non-absolute `id`
  values are flagged and recovered.

### Project
- Open-source governance: Apache-2.0 **LICENSE**, **CONTRIBUTING.md** (spec
  changes start as issues), **CODE_OF_CONDUCT.md**, issue and PR templates.

## [0.1.0] — 2026-07-02

Initial release of the specification and the reference exporter.

- **The format**: a directory of Markdown notes read as an RDF graph — each
  note's YAML frontmatter, interpreted as YAML-LD through one shared, external
  `context.jsonld`, is that note's triples; the body is documentation for
  human and machine readers, deliberately not converted to RDF.
- **Resource-per-file**: one note = one subject. Two layers, one mechanism:
  the schema layer under `Ontologies/` and `Vocabularies/` (classes,
  properties, concept schemes, concepts) and the instance layer everywhere
  else, linked by `@type` wiki links.
- **Wiki links are the edges**: `[[Target]]` is simultaneously the object IRI
  and a clickable, bidirectional link in the host tool (Obsidian, Notion, any
  editor).
- **Identity**: a note's IRI is its file name resolved against its namespace's
  `@base` — ontologies and vocabularies declare scoped bases in their own
  composed contexts, instances resolve against the data base; an explicit
  `@id` pins a stable IRI.
- **Hierarchy lives in the frontmatter**: `subClassOf` / `subPropertyOf` /
  `broader` as wiki links; the `Classes/` folder is flat and folders carry no
  formal meaning.
- **The roundtrip**: export (vault → Turtle, split into `schema.ttl` and
  `data.ttl`) and ingest (RDF → vault) specified as inverses, with neither
  serialization privileged as source of truth; unmapped constructs are
  flagged, never silently dropped.
- **Reference exporter** `vault_to_rdf.py` and the bundled example vault
  (Culinary ontology, DifficultyLevels vocabulary, recipe instances).
- Conformance criteria (§6), relationship to existing work (§7), and a
  minimal copyable example bundle (Appendix A).
