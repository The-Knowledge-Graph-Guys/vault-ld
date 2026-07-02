# Exporting a Vault to RDF — `vault_to_rdf.py`

`vault_to_rdf.py` projects a Vault-LD vault (a directory of Markdown notes, per
the [SPEC](SPEC.md)) into RDF. It reads each note's YAML frontmatter as YAML-LD
through the vault's composed `@context`, then emits **two Turtle files split by
layer**:

| File | Holds | Namespaces |
|---|---|---|
| `schema.ttl` | the schema layer — classes, properties, ontologies, concept schemes, concepts | one per ontology/vocabulary, e.g. `cul:` `https://example.org/culinary#`, `diff:` `https://example.org/difficulty#` |
| `data.ttl`   | the instance layer — typed notes (recipes, ingredients, …) | the data namespace, e.g. `data:` `https://example.org/data/` |

Each ontology/vocabulary lives in **its own namespace**, declared as the `@base`
in that ontology's context. Cross-references between layers are preserved: an
instance's `@type` and object properties point across into the relevant ontology
namespace, so the two files together are one graph.

## Requirements

- Python 3.10+
- [`rdflib`](https://rdflib.readthedocs.io/) and [`PyYAML`](https://pyyaml.org/):

```sh
pip install rdflib pyyaml
```

## Usage

```sh
python vault_to_rdf.py <vault> [--context PATH] [--out-dir DIR] [--schema-ns IRI] [--data-ns IRI]
```

Run against the bundled example vault:

```sh
python vault_to_rdf.py "Vault-LD Example" --out-dir build
```

| Flag | Default | Meaning |
|---|---|---|
| `vault` (positional) | — | path to the vault root directory |
| `--context` | `<vault>/context.jsonld` | the root context document |
| `--out-dir` | `.` | where to write `schema.ttl` and `data.ttl` |
| `--data-ns` | `https://example.org/data/` | instance-layer namespace IRI |
| `--schema-ns` | `https://example.org/schema/` | fallback base for a schema folder whose context declares no `@base` |

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

**A subject's IRI is its file name resolved against the `@base` of its
namespace** — per the scoped-base rule (SPEC §4.2 deviation note, §4.5):

- each ontology/vocabulary folder uses the `@base` declared in *its own*
  `context.jsonld` (read in isolation, so each keeps a scoped base): `Recipe.md`
  under `Ontologies/Culinary/` → `cul:Recipe`, `Beginner.md` under
  `Vocabularies/DifficultyLevels/` → `diff:Beginner`;
- data-layer notes resolve against `--data-ns` → `data:hummus`;
- only the **file name** is used, never the folder path, so moving a file
  between folders doesn't change its IRI; characters not legal in an IRI
  (spaces, most commonly) are percent-encoded (SPEC §4.5);
- an explicit `@id` in frontmatter overrides all of this and is honoured as-is.

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
  minted, in the data namespace);
- a referenced context file is **missing** or **remote**;
- two participating notes **share a file name**, making bare wiki links to that
  name ambiguous (SPEC §4.4.1).

Host-editor keys (`tags`, `aliases`, `cssclasses`) are skipped **silently**:
they are affordances of the editing surface, not unmapped constructs
(SPEC §4.3). Wiki links are resolved per the SPEC §4.4.1 grammar: aliases
(`[[name|shown]]`) and fragments (`[[name#Heading]]`) are stripped, and a
path-qualified link (`[[path/to/name]]`) resolves by its final segment.

## Example output

For the bundled example vault, `data.ttl` is:

```turtle
@prefix cul: <https://example.org/culinary#> .
@prefix data: <https://example.org/data/> .
@prefix diff: <https://example.org/difficulty#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

data:hummus a cul:Recipe ;
    cul:difficulty diff:Beginner ;
    cul:prepTimeMinutes 25 ;
    cul:requiresIngredient data:Chickpeas .

data:Chickpeas a cul:Ingredient ;
    rdfs:label "Chickpeas" .
```

> **Note** This is the *export* direction (Vault → RDF), which assumes Markdown
> is the source of truth. The generated `.ttl` files are read-only artifacts:
> edit the notes and regenerate, don't patch the Turtle (SPEC §5.4). For the
> opposite direction — RDF → Vault, when Turtle is the source of truth or when
> importing foreign RDF — see [`rdf_to_vault.py`](INGEST.md).
