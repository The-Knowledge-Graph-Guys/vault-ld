# Exporting a Vault to RDF — `vault_to_rdf.py`

`vault_to_rdf.py` projects a Vault-LD vault (a directory of Markdown notes, per
the [SPEC](../SPEC.md)) into RDF. It reads each note's YAML frontmatter as YAML-LD
through the vault's composed `@context`, then emits **two Turtle files split by
layer**:

| File | Holds | Namespaces |
|---|---|---|
| `schema.ttl` | the schema layer — classes, properties, ontologies, concept schemes, concepts | one per ontology/vocabulary, e.g. `cul:` `https://example.org/culinary#`, `diff:` `https://example.org/difficulty#` |
| `data.ttl`   | the instance layer — typed notes (recipes, ingredients, …) | the vault base (the root context's `@base`), e.g. `https://example.org/` |

Each ontology/vocabulary lives in **its own namespace**, declared as the `@base`
in that ontology's context. Cross-references between layers are preserved: an
instance's `type` and object properties point across into the relevant ontology
namespace, so the two files together are one graph.

## Requirements

- Python 3.10+
- [`rdflib`](https://rdflib.readthedocs.io/) and [`PyYAML`](https://pyyaml.org/):

```sh
pip install rdflib pyyaml
```

## Usage

```sh
python scripts/vault_to_rdf.py <vault> [--context PATH] [--out-dir DIR] [--schema-ns IRI] [--data-ns IRI] [--source]
```

Run against the bundled example vault:

```sh
python scripts/vault_to_rdf.py "Vault-LD Example" --out-dir build
```

| Flag | Default | Meaning |
|---|---|---|
| `vault` (positional) | — | path to the vault root directory |
| `--context` | `<vault>/context.jsonld` | the root context document |
| `--out-dir` | `.` | where to write `schema.ttl` and `data.ttl` |
| `--data-ns` | the root context's `@base` | explicit vault-root base for instance subjects; replaces the root `@base` only — a data folder's own `context.jsonld` still governs its subtree |
| `--schema-ns` | `https://example.org/schema/` | fallback base for a schema folder whose context declares no `@base` |
| `--source` | off | emit the `vld:path` placement triples that make the export a roundtrip face; without it the output is a lean, read-only query artifact (see below) |

## How it decides what goes where

**Layer is determined by folder location** (SPEC §3, §5.1), not by guessing
from `@type`:

- notes under `Ontologies/` and `Vocabularies/` → **schema** layer,
- everything else with frontmatter → **data** layer.

The acceptable-type list is used **only as an error bound**: given a note's
location the tool knows what kind of resource it ought to be
(`Classes/` → `owl:Class`, `Properties/` → an OWL property type, the ontology
file → `owl:Ontology`, a vocabulary scheme → `skos:ConceptScheme`, the rest of a
vocabulary → `skos:Concept`). If a note's `@type` isn't an expected type for its
folder, the tool **warns** rather than silently mis-modelling it.

**A subject's IRI is minted from its location, against the `@base` of its
governing context** — per the scoped-base rule (SPEC §4.2, §4.5):

- **schema notes** use the **file name alone**, resolved against the `@base`
  declared in *their own* ontology's/vocabulary's `context.jsonld` (read in
  isolation, so each keeps a scoped base): `Recipe.md` under
  `Ontologies/Culinary/` → `cul:Recipe`, `Beginner.md` under
  `Vocabularies/DifficultyLevels/` → `diff:Beginner`. The `Classes/` and
  `Properties/` folders — and any organisational nesting inside them (SPEC
  §5.2) — never enter the IRI;
- **instance notes** use the **file name alone** too, against the `@base` of
  the governing context (the nearest `context.jsonld` above them, usually the
  vault root): `Recipes/hummus.md` → `<https://example.org/hummus>` — the
  folder path never enters the IRI;
- characters not legal in an IRI (spaces, most commonly) are percent-encoded
  (SPEC §4.5);
- an explicit `id` in frontmatter overrides name-based minting: the value is a
  **full absolute IRI** (`http(s)://…`), used verbatim — this is how two
  same-named files avoid minting the same IRI.

**The default export is a query artifact, not a roundtrip face.** The common
use of a `.ttl` export is as a read-only engine to query against, so by
default the output carries the graph's content and nothing else.

**`--source` makes the export a roundtrip face**: it adds a
`vld:path "<path>.md"` triple — Vault-LD's own string-valued property, in the
`vld:` namespace `https://github.com/The-Knowledge-Graph-Guys/vault-ld#` —
for every note whose location the graph
can't otherwise reconstruct (SPEC §5.4 step 7) — most notes, since identity
carries no location: every pinned note, every instance not sitting directly in
its governing context's folder, and every schema note away from the flat
placement of §5.1 — so ingest can restore every file 1:1. The graph *content*
is identical either way; `--source` only adds the placement bookkeeping. A
default (sourceless) export cannot restore the vault's folder structure on
ingest, which is exactly why it should stay read-only.

**Folder nesting is never read as hierarchy** (SPEC §5.2): `subClassOf`,
`broader`, and `topConceptOf` come from frontmatter and nowhere else. Nesting
a schema file is purely organisational; if its placement doesn't match what
its declared hierarchy implies, the true path simply travels as
`vld:path` so the location round-trips.

If a schema folder's context declares no `@base`, the tool falls back to
`--schema-ns` + the ontology name.

## How the context is resolved

The tool follows JSON-LD context composition (SPEC §4.2). The root
`context.jsonld` may set its `@context` to an **array**:

```json
{
  "@context": [
    { "@base": "https://example.org/", "label": "rdfs:label", "...": "..." },
    "Ontologies/Culinary/context.jsonld"
  ]
}
```

- **object** entries are merged inline;
- **string** entries are references to other context files, resolved relative to
  the document that names them, and merged recursively;
- entries apply left-to-right, so **later entries override earlier ones**.

This lets each ontology ship its own self-contained `context.jsonld` (its domain
vocabulary and its namespace, via `@base`) while the root simply lists the
contexts it composes. A referenced context's `@base` scopes only its own
ontology's subjects — it does not override the root's base in the merged context.
Remote (`http(s)://`) references are reported, not fetched.

## Warnings

The tool prints warnings to stderr instead of dropping anything silently
(SPEC §5.6). You will see one when:

- a frontmatter field is **not defined in the context** (it is skipped — add it
  to the context to make it first-class);
- a schema-folder note carries an **unexpected `@type`** for its location;
- a wiki link is **dangling** (its target note isn't found — the IRI is still
  minted, under the vault base);
- an explicit `id` is **not an absolute IRI** (non-conforming, SPEC §4.5 — the
  value must be a full `http(s)://…` IRI; a relative value is flattened
  against the governing `@base` as recovery);
- a referenced context file is **missing** or **remote**;
- two participating notes **share a file name**, making bare wiki links to that
  name ambiguous (SPEC §4.4.1) — or mint the **same IRI**, silently merging
  into one subject;
- two composed contexts define the **same term or prefix differently** — the
  later definition wins (SPEC §4.2); an identical re-declaration stays silent.

Host-editor keys (`tags`, `aliases`, `cssclasses`) are skipped **silently**
while unmapped: they are affordances of the editing surface, not unmapped
constructs (SPEC §4.3). A deployment that maps one in the context has
*promoted* it, and it exports like any other term. Wiki links are resolved per the SPEC §4.4.1 grammar: aliases
(`[[name|shown]]`) and fragments (`[[name#Heading]]`) are stripped, and a
path-qualified link (`[[path/to/name]]`) selects among same-named notes by
matching its path against each note's vault-relative path (right-aligned on
segment boundaries, the way Obsidian's shortest-sufficient-path links work).
Keyword aliases declared in the context (`type:` for `@type`, `id:` for
`@id`; SPEC §4.3) are honoured on input — the aliased and quoted spellings
read identically.

## Example output

For the bundled example vault, the default (query-only) `data.ttl` is:

```turtle
@prefix cul: <https://example.org/culinary#> .
@prefix data: <https://example.org/> .
@prefix diff: <https://example.org/difficulty#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

data:hummus a cul:Recipe ;
    cul:difficulty diff:Beginner ;
    cul:prepTimeMinutes 25 ;
    cul:requiresIngredient data:Chickpeas .

data:Chickpeas a cul:Ingredient ;
    rdfs:label "Chickpeas" .
```

With `--source`, each instance additionally carries its shelf location —
`data:hummus` gains `vld:path "Recipes/hummus.md"`, `data:Chickpeas`
gains `vld:path "Ingredients/Chickpeas.md"` — which is what lets an
ingest rebuild the folder structure.

The `data:` prefix is bound to the vault base for condensed output — local
names are file stems (SPEC §4.5), so every unpinned instance compacts to
`data:name`.

> **Note** This is the *export* direction (Vault → RDF), which assumes Markdown
> is the source of truth. The generated `.ttl` files are read-only artifacts:
> edit the notes and regenerate, don't patch the Turtle (SPEC §5.4). For the
> opposite direction — RDF → Vault, when Turtle is the source of truth or when
> importing foreign RDF — see [`rdf_to_vault.py`](INGEST.md).
