# Ingesting RDF into a Vault — `rdf_to_vault.py`

`rdf_to_vault.py` is the inverse of [`vault_to_rdf.py`](EXPORT.md): it projects an
RDF graph *into* the vault format (SPEC §5.5). Every subject becomes one Markdown
note whose YAML frontmatter carries that subject's triples, resolved through the
vault's composed `@context`. Run the two tools in opposite directions and the
graph survives the roundtrip untouched (SPEC §5.6).

Use it when:

- **Turtle is the source of truth** — an ontology maintained in `.ttl` gets a
  human-editable Markdown face, regenerated after every change;
- **importing foreign RDF** — any ontology, SKOS vocabulary, or instance data
  becomes a browsable vault, with a context synthesized on first ingest.

## Requirements

- Python 3.10+, [`rdflib`](https://rdflib.readthedocs.io/) and [`PyYAML`](https://pyyaml.org/)
- `vault_to_rdf.py` next to it (the context machinery is shared)

```sh
pip install rdflib pyyaml
```

## Usage

```sh
python scripts/rdf_to_vault.py <vault> <rdf-file>... [--context PATH] [--data-ns IRI] [--nest]
```

Round-trip the bundled example:

```sh
python scripts/vault_to_rdf.py "Vault-LD Example" --source --out-dir build
python scripts/rdf_to_vault.py "Vault-LD Example" build/schema.ttl build/data.ttl   # → 11 unchanged
```

(The `--source` flag makes the export a roundtrip face — the default export is
a query-only artifact whose placement can't be restored; see EXPORT.md.)

Import a foreign ontology into a brand-new vault (context synthesized):

```sh
python scripts/rdf_to_vault.py MyVault foreign-ontology.ttl
```

| Flag | Default | Meaning |
|---|---|---|
| `vault` (positional) | — | vault root directory, created if missing |
| `rdf` (positional, repeatable) | — | RDF file(s) to ingest — any format rdflib recognises by extension (`.ttl`, `.nt`, `.jsonld`, …) |
| `--context` | `<vault>/context.jsonld` | the root context document; when neither exists, one is **synthesized** from a standard core plus the graph's own namespaces |
| `--data-ns` | the root context's `@base` | explicit vault-root base for instance subjects (must match the export's); replaces the root `@base` only — a data folder's own `context.jsonld` still governs its subtree. Also the `@base` of a synthesized context |
| `--nest` | off | organise newly created schema files into hierarchy-derived subfolders instead of the flat canonical layout (see below) |

## How it decides what goes where

**Kind is determined by `rdf:type`**, and placement follows SPEC §5.1:

| Subject typed | Written to |
|---|---|
| `owl:Ontology` | `Ontologies/{Name}/{Name}.md` |
| `owl:Class` / `rdfs:Class` | `Ontologies/{Name}/Classes/{ClassName}.md` — flat, the canonical form (§5.1); with `--nest`, nested under its single-local-parent chain |
| any OWL/RDF property type | `Ontologies/{Name}/Properties/{propertyName}.md` |
| `skos:ConceptScheme` | `Vocabularies/{Scheme}/{Scheme}.md` |
| `skos:Concept` | `Vocabularies/{Scheme}/{Concept}.md` — flat at the vocabulary's top level, the canonical form (§5.1); with `--nest`, non-top concepts nest under their `skos:broader` chain |
| anything else (instances) | the file the IRI names, at the context root (`<base>hummus` → `hummus.md`); foreign IRIs fall back to `{TypeName}s/{name}.md` (e.g. a `lib:Book` → `Books/`) — but almost every instance arrives with a `vld:path` hint instead (see below) |

Two placements outrank the table. A subject carrying a **`vld:path
"<path>.md"` triple** — the true path the export records whenever the graph
alone could not reconstruct a file's location (SPEC §5.4 step 7) — is written
to exactly that path, and the triple is consumed: it never appears in
frontmatter, because on the vault side the path is simply where the file sits.
And an **existing note** for the subject wins over everything (see below).

Schema subjects are grouped into ontology/vocabulary folders **by namespace**: the
folder is named after the `owl:Ontology` / `skos:ConceptScheme` subject minted in
that namespace (or a name derived from the namespace, with a warning, when the
graph declares none). Each new folder gets a `context.jsonld` declaring the
namespace as its scoped `@base`, and the root context is extended to compose it
(SPEC §4.2).

**`--nest` is folder management, not modelling.** On a fresh build it lays
schema files out along the declared hierarchy — each class under its single
local parent, recursively (`Classes/CreativeWork/Recipe.md`), top concepts at
the vocabulary's top level, everything else under its `broader` chain. This
changes nothing in the graph (SPEC §5.2 keeps folders meaningless) and is
deliberately **not part of the spec** — it's this tool's convenience for
browsing a large ontology, and other tools are free to organise differently.
A later `--source` export records whatever layout exists via `vld:path`,
so a nested vault still round-trips 1:1.

**Existing notes win over canonical placement.** If a note already minting the
subject's IRI exists anywhere in the vault, it is updated *in place*, so
regeneration never reshuffles your structure. A note whose frontmatter would
not change is not rewritten at all, keeping `git status` quiet on a no-op
regeneration.

**Identity is checked, not assumed** (§4.5): after choosing a path, the tool
computes the IRI a forward export would mint for it — the file name alone
against the governing `@base`, percent-encoded, exactly as the exporter
mints. File names are chosen by percent-*decoding* the IRI, so an exported
`Red%20Lentil%20Soup` comes back as `Red Lentil Soup.md`. Only when the
re-minted IRI differs from the subject's actual IRI does the note get an
explicit `id` — the full absolute IRI, which export uses verbatim.

## How the frontmatter is built

The correspondences of §5.5, read right-to-left from the export:

- each predicate becomes its **short context name** (`rdfs:label` → `label:`);
  a predicate with no short name gets one **coined from its localname and added
  to the context** — to the ontology's own `context.jsonld` when the predicate
  lives in that namespace, to the root context otherwise (flagged as a warning);
- IRI objects become **`[[wiki links]]`** when the target is a note in the vault
  (before or after this run), and **CURIEs** otherwise (`sdo:Recipe`); when
  several notes share the target's name, the link is written **path-qualified**
  (`[[Ingredients/Chickpeas]]`) so it resolves unambiguously (SPEC §4.4.1);
- literals become **plain scalars**; datatypes are supplied by the context's
  coercions, never written inline. Integers, booleans, doubles, dates and
  dateTimes round-trip natively; other datatypes get a coercion added to the
  coined term's definition;
- multi-valued predicates (and terms declared `"@container": "@set"`) become
  flow lists: `subClassOf: [ "[[CreativeWork]]", sdo:Recipe ]`;
- hierarchy is **always written explicitly** into frontmatter
  (`subClassOf` / `broader` / `topConceptOf`) — frontmatter is its only
  carrier (SPEC §5.2); with `--nest` the folder layout mirrors it too, but
  that is shelving, not semantics;
- when the context aliases the JSON-LD keywords (`type:` for `@type`, `id:`
  for `@id`; SPEC §4.3), notes are written with the aliased spelling — plain
  YAML keys, no quoting; a synthesized context declares both aliases.

## What is preserved on regeneration

Per SPEC §5.6 and the conformance rules (§6):

- **bodies are never clobbered** — the frontmatter block is replaced, everything
  below the closing `---` stays; a freshly ingested note starts with an empty body;
- **non-context frontmatter keys** (`tags:`, `aliases:`, …) belong to the
  Markdown face, not the graph, and are kept;
- a **valid explicit `id`** already pinned in a note is kept (one that resolves to the subject's IRI against the governing `@base`).

## Warnings

Nothing is dropped silently (SPEC §5.6). You will see a warning for:

- a predicate not in the context (a term is coined and the context extended);
- a **blank node** (subject or object) — the vault format has no representation
  for anonymous resources;
- a **language-tagged literal** — the tag cannot be expressed in frontmatter;
- a literal whose datatype disagrees with its term's coercion (retyped on export);
- an IRI object on a term without `@id` coercion (exported as a string);
- a namespace with no `owl:Ontology`/`skos:ConceptScheme` subject (folder name derived);
- an **ambiguous note name** (two notes share it) — links to those notes are
  emitted **path-qualified** so they resolve unambiguously (SPEC §4.4.1);
- a **file collision** (a subject's canonical path already belongs to another
  subject) — the note gets a suffixed name (`-2`), pinned by an explicit `@id`;
- a subject with no `rdf:type` (a forward export will skip that note).

> **Note** This is the *ingest* direction (RDF → Vault), used when Turtle is the
> source of truth or when importing foreign RDF. In that arrangement the Markdown
> face is the generated, read-only side: edit the `.ttl` and re-ingest, don't
> patch the notes (SPEC §5.5). The bodies you write below the frontmatter are
> yours either way — regeneration preserves them (§5.6).
