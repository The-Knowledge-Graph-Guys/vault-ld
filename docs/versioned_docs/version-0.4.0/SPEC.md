# Vault-LD Specification - Linked Data in the Vault

*An open format for knowledge two very different readers can share at once: a person editing notes, and a machine reasoning over a graph.*

> For the motivation behind Vault-LD and a worked example, see the [README](index.md). This document is the normative reference.

## 1. Overview

Vault-LD treats a directory of Markdown notes as an RDF graph: each note's YAML frontmatter, read as [YAML-LD](https://json-ld.github.io/yaml-ld/spec/) (JSON-LD with a YAML serialization) through one shared context, becomes that note's triples. Because the frontmatter is YAML-LD, a note and an ontology definition are the *same kind of object*, and either can be projected losslessly to RDF and back. An ontology can enter as Turtle, be edited as Markdown, and leave as Turtle again, or the reverse, with no canonical "real" form privileged over the other.

![Vault-LD](images/Vault-LD.png)

This document specifies that roundtrip in two inverse halves. **§4, frontmatter as a knowledge graph,** shows how the YAML at the top of a note becomes RDF triples linked to ontologies and vocabularies. **§5, the RDF ⇄ vault-format roundtrip,** shows how any RDF graph is projected into this directory-of-files shape and exported back out with full fidelity. The remaining sections fix terminology (§2), show the directory structure at a glance (§3), list the conformance criteria (§6), and relate the format to existing standards (§7).

## 2. Terminology

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used in the sense of [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

- **Vault**: the directory of Markdown files, opened as a knowledge base by a host tool (Obsidian, Notion, or any editor).
- **Note / file**: one Markdown document. In linked-data terms it is one RDF *resource* (one subject).
- **Frontmatter**: the YAML block delimited by `---` at the top of a note. Read as YAML-LD, it is the note's triples.
- **Context**: the shared JSON-LD `@context` that maps short field names and prefixes to IRIs for the whole vault. It is conventionally rooted in `context.jsonld`, but **MAY** be composed of several documents: a context value that is an *array* pulls in further context documents by reference (JSON-LD composition), so each ontology can ship its own self-contained context (§4.2).
- **Vault format**: the resource-per-file representation, namely frontmatter triples (one subject per file) plus a documentation body.
- **Schema layer / instance layer**: definitions (classes, properties, concepts) versus the typed notes that conform to them.
- **Source of truth**: the serialization a given deployment designates as authoritative for an asset (Markdown, Turtle, or another). This is a per-asset, per-deployment choice, not fixed by this format.
- **Generated artifact**: whichever serialization a deployment derives from the source of truth (e.g. a `.ttl` exported from Markdown, or Markdown generated from a hand-maintained `.ttl`). It is treated as read-only *in that deployment*, in whichever direction generation runs.

## 3. Structure at a Glance

A vault is a tree of Markdown files plus a composed context (a root document and one per ontology/vocabulary):

```
context.jsonld                     # the root @context - composes the contexts below
Ontologies/
  Culinary/
    context.jsonld                 # Culinary's own namespace (@base) + term definitions
    Culinary.md                    # the ontology resource (owl:Ontology)
    Classes/
      Recipe.md                    # owl:Class - subClassOf declared in frontmatter
      CreativeWork.md
      Ingredient.md
    Properties/
      requiresIngredient.md        # owl:ObjectProperty
      prepTimeMinutes.md           # owl:DatatypeProperty
Vocabularies/
  DifficultyLevels/
    context.jsonld                 # the vocabulary's own namespace (@base)
    DifficultyLevels.md            # skos:ConceptScheme
    Beginner.md                    # skos:Concept - topConceptOf declared in frontmatter
    NoCook.md                      # skos:Concept - broader: [[Beginner]] (concept-to-concept)
Recipes/
  hummus.md                        # an instance: type: "[[Recipe]]"
```

The root `context.jsonld` carries the cross-cutting core (shared prefixes, the data `@base`, and the structural RDFS/OWL/SKOS terms) and *composes* each ontology's and vocabulary's own context by reference. Every ontology or vocabulary ships a `context.jsonld` beside its notes that declares its own namespace (`@base`) and any domain terms it coins (§4.2); a vocabulary whose predicates are all generic SKOS may declare only its `@base`. The `Classes/` and `Properties/` folders group resources **by kind**, and in their canonical form are flat. A class's place in the `subClassOf` tree (and a concept's place in the `broader`/`narrower` tree) is declared in its frontmatter and nowhere else; nesting a schema file inside a folder named after its parent is organisation, not modelling (§5.2). Folders never shape identity either: every note mints from its file name alone (§4.5), and placement travels through `vld:path` on export (§5.4).

There is nothing else to install. The directory *is* the knowledge base, and it is self-describing: every name a file uses resolves through the composed context, which travels with the vault.

## 4. Frontmatter as a Knowledge Graph

### 4.1 The note is the subject

Each file is one RDF resource. Its frontmatter key/value pairs are predicate/object pairs about that resource; the body is documentation for human and machine readers that is deliberately **not** part of the triple set (§5.3). Read this note:

```markdown
---
type: "[[Recipe]]"
requiresIngredient: "[[Chickpeas]]"
prepTimeMinutes: 25
---

# Hummus
A smooth purée of chickpeas, tahini, lemon, and garlic.
```

You have just read these triples:

```turtle
@prefix : <https://example.org/> .

:Hummus a :Recipe ;
        :requiresIngredient :Chickpeas ;
        :prepTimeMinutes 25 .
```

### 4.2 The context is shared and external, by design

A note **MUST NOT** carry its own `@context` block. The context lives *outside* the notes, and is the single source of truth for:

- the **base namespace** (e.g. `https://example.org/`),
- **prefix → namespace** mappings (`owl:`, `rdfs:`, `skos:`, `dcterms:`, `sdo:` for schema.org, and the local `ex:`),
- **term definitions**: short frontmatter field names mapped to full IRIs, with datatype or IRI coercion.

So `prepTimeMinutes: 25` can be typed as `xsd:integer`, and `subClassOf` can be coerced to an IRI reference, *without* the author writing any of that. Authors write short, clean names; the context supplies the semantics. A name not present in the context is not part of the shared vocabulary; to make it first-class, add it to the context.

This externalization is intentional: the model is defined outside the notes, every file stays terse, and the vault remains diffable and human-scannable.

**The context MAY be composed of several documents.** Following JSON-LD's own mechanism, a context value that is an *array* applies its entries left-to-right, with later entries overriding earlier ones, and a string entry is a *reference* to another context document resolved relative to the document that names it. This lets the root `context.jsonld` hold the cross-cutting core — prefixes, `@base`, and the structural terms (`label`, `subClassOf`, `domain`, `broader`, …) — and then pull in each ontology's own self-contained context, exactly as a published ontology ships a `context.jsonld` defining its terms:

```json
{
  "@context": [
    { "@base": "https://example.org/", "owl": "…", "label": "rdfs:label", "subClassOf": { "@id": "rdfs:subClassOf", "@type": "@id" } },
    "Ontologies/Culinary/context.jsonld",
    "Vocabularies/DifficultyLevels/context.jsonld"
  ]
}
```

Each referenced ontology context also declares the **`@base` for its own namespace** — the scoped base its members are minted under (§4.5, §5.4):

```json
{ "@context": { "@base": "https://example.org/culinary#", "cul": "https://example.org/culinary#",
                "requiresIngredient": { "@id": "cul:requiresIngredient", "@type": "@id" } } }
```

Composition is transparent to authors: every short name still resolves through one effective context, whichever file physically defines it. The benefit is modularity — an ontology owns its vocabulary *and its namespace*, the root merely lists the ontologies it composes — without giving any note a local `@context`.

> **Scoped bases: how notes become JSON-LD documents.** A vault is not a pile of free-standing JSON-LD documents; it is a recipe for assembling them. A Vault-LD tool processes each note as one ordinary JSON-LD expansion — the note's frontmatter against the composed context — with the expansion's **base IRI** chosen per note: the `@base` declared in the context of the note's governing ontology or vocabulary folder, or the data namespace for instance notes (§4.5, §5.4). Everything inside that expansion is standard JSON-LD 1.1; term and prefix definitions compose exactly as JSON-LD specifies (left-to-right, later entries overriding earlier). The format's own contribution is the assembly rule that *selects* the base from the folder structure.
>
> One interoperability consequence must be stated plainly: JSON-LD 1.1 directs a processor to **ignore `@base` in a referenced context** — the keyword only takes effect in a document's own inline context, or as a processing option. The `@base` entries in the folder contexts are therefore read by Vault-LD tools, not by generic JSON-LD processors. A stock processor given the composed context and a note's raw frontmatter resolves every *term* identically, but resolves relative subject IRIs against the root's base, not the folder's. Reproducing the vault's subject IRIs requires the assembly rule — equivalently, calling an off-the-shelf JSON-LD library with the composed context as the expansion context and the governing folder's `@base` as the `base` option, after the wiki-link resolution of §4.4.1, which no JSON-LD option supplies.

When composing contexts, a tool **SHOULD** warn if a later context redefines a term or prefix **with a different definition than** one an earlier context already established: JSON-LD's override semantics make the shadowing legal, but across independently authored ontologies a *conflicting* redefinition is almost always an accidental name collision, and it is silent by default. An identical re-declaration — the normal signature of self-contained ontology contexts, which re-declare the common prefixes they use — is benign and warrants no warning.

### 4.3 The field-naming contract

| Concern                       | Rule                        | Example                                        |
| ----------------------------- | --------------------------- | ---------------------------------------------- |
| Type declaration              | wiki link to the class      | `type: "[[Recipe]]"`                           |
| Object property (→ resource)  | wiki link                   | `requiresIngredient: "[[Chickpeas]]"`          |
| Datatype property (→ literal) | plain scalar                | `prepTimeMinutes: 25`, `published: 2026-06-17` |
| External-vocabulary term (in a **value**) | prefixed CURIE  | `subClassOf: [ sdo:Recipe ]`                   |
| Field name (the **key**)      | bare short alias, never prefixed | `comment:` not `rdfs:comment:`            |

A prefix's place is on a *value* that references a foreign vocabulary (the `sdo:Recipe` row), never on a *key*. Keys are always the bare short alias the context defines: write `comment:`, and the context's term definition (`"comment": "rdfs:comment"`) expands it to `rdfs:comment` on resolution. Writing `rdfs:comment:` as a key inlines a mapping the context already owns, breaks the "model defined in one place" principle, and won't match the short names the vault's tooling and queries expect.

**Keyword aliases make the keys plain YAML.** YAML reserves `@` at the start of a plain scalar, so the JSON-LD keywords `@type` and `@id` would have to be written quoted (`"@type":`) in every note — the one piece of YAML awkwardness the format would otherwise force on every author. A context **MAY** therefore alias them, using JSON-LD 1.1's own *keyword aliasing*:

```json
{ "type": "@type", "id": "@id" }
```

A conforming tool **MUST** honour keyword aliases declared in the composed context, treating the aliased and keyword spellings identically on input; a tool that generates the Markdown face **SHOULD** write the aliased spelling when one is declared. The example vault declares both, which is why its notes read `type: "[[Recipe]]"` and `id:` with no quoting; a vault whose context declares no alias writes the quoted keywords. An alias is a context-owned name like any other: the shadowing rules of §4.2 apply to it, and a domain ontology that wants `type` or `id` as its own term simply must not alias over it.

**Host-tool keys are not triples.** Some frontmatter keys belong to the host editor, not the graph: `tags`, `aliases`, and `cssclasses` in Obsidian are the common cases. These are affordances of the editing surface. While such a key is *unmapped*, a conforming tool **MUST NOT** emit it as a triple and **MUST NOT** warn about it as an unmapped construct; it is known and deliberately outside the graph. A deployment **MAY** promote one by mapping it in the context (`tags` to `dcat:keyword`, say), at which point it becomes an ordinary term like any other — emitted, round-tripped, and shadow-checked (§4.2) exactly as any term is.

### 4.4 Wiki links are the edges

`[[Target]]` is how one node references another, and it does two jobs at once. As linked data it is the object IRI: on export `[[Recipe]]` becomes the URI `:Recipe`. As a tool affordance it is a real, clickable, **bidirectional** link, so the same keystroke that asserts a triple also lights up graph view and backlinks. This is why object properties and `@type` are **always** wiki links and never plain strings: the format refuses to make you choose between machine meaning and human navigation.

Strictly, the wiki-link syntax is a Vault-LD *extension* to YAML-LD: `"[[Recipe]]"` is a plain string until the resolution step (§4.4.1) rewrites it as an IRI reference. A generic YAML-LD processor sees a string where a Vault-LD tool sees an edge; conformant processing therefore means applying §4.4.1 before, or as part of, JSON-LD expansion.

#### 4.4.1 Link grammar and resolution

A wiki link is `[[name]]`, optionally carrying a path (`[[path/to/name]]`), an alias (`[[name|display text]]`), or a fragment (`[[name#Heading]]`). For the graph:

- the **alias** is display-only and **MUST** be ignored for resolution;
- a **path** disambiguates only: resolution uses the final segment (the note name), and when several participating notes share a name, a tool **SHOULD** use the path to select among them;
- a **fragment** addresses a location inside a note, not a resource; the graph edge resolves to the note itself, and a tool **MAY** warn that the fragment was discarded.

A link resolves to the participating note whose file name equals the link's note name, and the object IRI is that note's identity: its explicit `@id` when declared, its minted IRI otherwise (§4.5). Two participating notes sharing a file name make bare links to that name ambiguous — and, since identity mints from the file name (§4.5), they collide on one IRI unless at least one declares an `@id`; a tool **MUST** warn, and authors **SHOULD** disambiguate with an explicit `@id` (for identity) and a path-qualified link (for the reference). A link that names no participating note is **dangling**: a tool **MUST** flag it (§5.6) and **MAY** still mint an IRI for the missing target in the data namespace so the edge is preserved rather than dropped.

The same grammar governs link *generation*. A tool that writes wiki links (§5.5) **SHOULD** emit a path-qualified link whenever the bare note name is ambiguous among participating notes, so that the link it writes resolves — under the rules above — to the note it means. Generation and resolution are two halves of one contract: whatever one tool emits, the other must resolve back to the same IRI.

A note with no frontmatter, or whose frontmatter lacks `@type`, does **not** participate in the graph; it is an ordinary document. A link from a participating note to such a note is dangling in the sense above, even though the file exists and the link navigates perfectly well in the host tool.

### 4.5 Identity

Identity is minted from the **file name alone** — never from the folder path. One rule covers both layers: the IRI is the governing `@base` + the file name without `.md`, where the governing context is the nearest `context.jsonld` at or above the note's folder — analogously to how JSON-LD resolves a relative `@id`, though which base applies is Vault-LD's own assembly rule (the scoped-base rule of §4.2), not stock JSON-LD behaviour. Only the vault-root context is mandatory; per-ontology and per-vocabulary contexts are optional refinements.

- **Schema notes** (under `Ontologies/` and `Vocabularies/`): `Recipe.md` resolved against its ontology's scoped `@base` becomes `cul:Recipe`. The `Classes/` and `Properties/` folders never enter the IRI: that folder structure is standardised (§5.1) and the naming convention (classes PascalCase, properties camelCase) already tells a reader the kind, so the path would add no information.
- **Instance notes** (everything else): `hummus.md` under a root `@base` of `https://example.org/` becomes `<https://example.org/hummus>` — wherever in the vault the file sits. `Recipes/` is shelving, not naming.

A file name may contain characters that are not legal in an IRI (spaces are the common case); when minting an identity from a file name, a tool **MUST** percent-encode the offending characters per RFC 3987, so `Red Lentil Soup.md` mints `.../Red%20Lentil%20Soup`. An explicit `id` sidesteps encoding entirely. Most notes need no identifier at all and remain addressable regardless.

Because the folder never enters the IRI, moving a note **never** re-mints its identity; only renaming the file does. The corollary is that two notes with the same file name under the same governing context mint the **same IRI** — a collision. This is what the explicit `id` is for. A note **MAY** declare one through `id` (the alias of `@id`, §4.3), and the value **MUST** be a **full absolute IRI** (`http(s)://…`), used verbatim:

```yaml
id: https://example.org/recipes/red-lentil-soup
```

An explicit `id` overrides name-based minting entirely: it disambiguates same-named notes, pins an identity that survives even a rename, and can place a subject in any namespace — the value is not resolved against any base, so there is nothing relative to get wrong. A relative value is **non-conforming**.

Minting says nothing about *location*, so location must travel separately: on export, any note whose place on disk the graph could not otherwise reconstruct carries its true path as a `vld:path` triple, and ingest puts the file back exactly where it was (§5.4, §5.5). In practice that is most notes — the price of location-free identity is that placement is data, not derivation.

#### Example: identity by file name

The note lives at `Recipes/Soups/red-lentil-soup.md`, governed by the root context (`@base: https://example.org/`):

```yaml
---
type: "[[Recipe]]"
requiresIngredient: "[[Lentils]]"
difficulty: "[[Beginner]]"
---
```

Minted IRI: `<https://example.org/red-lentil-soup>` — the file name, `.md` dropped; the `Recipes/Soups/` path never enters the IRI. Moving the file changes nothing; renaming it to `red-lentil-dahl.md` would re-mint it as `<https://example.org/red-lentil-dahl>`. On export the location travels as `vld:path "Recipes/Soups/red-lentil-soup.md"` (§5.4).

#### Example: the same note with an explicit `id`

Same file, same location — `Recipes/Soups/red-lentil-soup.md`:

```yaml
---
id: https://example.org/recipes/red-lentil-soup
type: "[[Recipe]]"
requiresIngredient: "[[Lentils]]"
difficulty: "[[Beginner]]"
---
```

Minted IRI: `<https://example.org/recipes/red-lentil-soup>` — the `id`, verbatim. Neither the file's name nor its location participates, so the note can be renamed or moved freely without changing identity, and a second `red-lentil-soup.md` elsewhere in the vault no longer collides with it.

### 4.6 Two layers, one mechanism

The same YAML-LD mechanism carries both the **schema layer** (definitions: `@type: owl:Class`, `owl:ObjectProperty`, `skos:Concept`, and so on) and the **instance layer** (typed notes: `type: "[[Recipe]]"`). An instance links to its schema through the `@type` wiki link, so data and the model that types it are never more than a click apart.

## 5. The RDF ⇄ Vault-Format Roundtrip

"**Vault format**" means: a directory of Markdown files, one file per RDF resource, where frontmatter carries the triples and the body carries extended documentation. An ontology, a SKOS vocabulary, or any RDF graph can be projected into this shape and exported back. This section gives the rules, showing each one against a concrete file first.

### 5.1 Resource-per-file

| RDF resource | Vault file |
|---|---|
| `owl:Ontology` | `Ontologies/{Name}/{Name}.md` |
| `owl:Class` | `Ontologies/{Name}/Classes/{ClassName}.md` |
| `owl:ObjectProperty` / `owl:DatatypeProperty` | `Ontologies/{Name}/Properties/{propertyName}.md` |
| `skos:ConceptScheme` | `Vocabularies/{Scheme}/{Scheme}.md` |
| `skos:Concept` | `Vocabularies/{Scheme}/{Concept}.md` |

Classes are PascalCase, properties camelCase; the file name **MUST** equal the resource name. Folders group resources by kind; nesting within `Classes/` or a vocabulary folder is purely organisational and asserts nothing (§5.2). The flat form above is the canonical, reconstructable placement — any other layout travels via `vld:path` (§5.4).

### 5.2 Hierarchy: frontmatter is the only carrier

Hierarchical axioms are **declared in frontmatter as wiki links**, and frontmatter is the only carrier:

- a class's `subClassOf` field ⇒ its `rdfs:subClassOf`,
- a property's `subPropertyOf` field ⇒ its `rdfs:subPropertyOf`,
- a concept's `broader` field ⇒ its `skos:broader`,
- a top concept's `topConceptOf` field ⇒ its `skos:topConceptOf`.

Note the SKOS distinction the last two rows encode: `broader` relates a concept to a **parent concept** (both ends are `skos:Concept`; `skos:broader` is a sub-property of `skos:semanticRelation`, whose domain and range are concepts). Membership of the *scheme* is a different predicate: a concept at the top of its tree points at the `skos:ConceptScheme` with `topConceptOf`, never with `broader`. Pointing `broader` at a scheme entails, wrongly, that the scheme is itself a concept.

So this note:

```yaml
---
type: owl:Class
label: Recipe
subClassOf: [ "[[CreativeWork]]", sdo:Recipe ]
---
```

asserts `:Recipe rdfs:subClassOf :CreativeWork, sdo:Recipe`, regardless of where the file sits.

**Folder placement asserts nothing.** Nesting a schema file inside a folder named after another class or concept is organisation, not modelling: a tool **MUST NOT** derive `subClassOf`, `subPropertyOf`, `broader`, or `topConceptOf` from where a file sits. A nested class whose frontmatter declares no parent simply has no parent. A folder path could never have carried the job anyway:

- **Multiple inheritance.** A folder path encodes exactly one parent; `subClassOf: [ "[[A]]", "[[B]]" ]` encodes many.
- **Cross-ontology superclasses.** A wiki link can point at a class defined in another ontology (e.g. a domain class whose parent is `[[Thing]]` in a shared core ontology); a folder cannot reach across ontology trees.
- **Cheap re-parenting.** Changing a class's parent is a one-line frontmatter edit and a clean diff, not a physical file move.

Nesting never changes identity either: schema notes mint from the file name alone (§4.5), so moving a schema file changes where it is shelved and nothing about the graph.

Placement still matters to the **roundtrip**, just not to the graph. The reconstructable default is the flat form of §5.1 — classes directly in `Classes/`, properties in `Properties/`, concepts at their vocabulary's top level — and a file anywhere else travels with a `vld:path` path on export, so any placement round-trips 1:1 (§5.4). Beyond that default, folder organisation is a tool's own affair, deliberately outside this spec: an ingester **MAY** lay files out however suits its users — nested under declared parents, grouped by type, or anything else — because whatever the layout, the source path records it. (The reference ingester offers hierarchy-derived nesting as exactly such a convenience; see its documentation.) The path records where the file *is*; it never implies what the graph *says*.

### 5.3 Triples in the frontmatter, prose in the body

#### Example: a property definition

```yaml
---
type: owl:ObjectProperty
label: requires ingredient                 # → rdfs:label
comment: "Links a recipe to an ingredient it depends on."   # → rdfs:comment
domain: [ "[[Recipe]]" ]                    # → rdfs:domain
range:  [ "[[Ingredient]]" ]                # → rdfs:range
tags: [ owl-property, Culinary ]
---
# requiresIngredient
Use for the principal ingredients a dish cannot be made without;
optional garnishes SHOULD be modelled with a separate, weaker property.
```

The **frontmatter** is the formal triples (short field names, resolved through the context). The **body** is documentation, and it is deliberately **not converted to RDF**; only the frontmatter is. The division is intentional, and it mirrors how a webpage using JSON-LD puts only its most relevant metadata in the structured block while the article text stays in the HTML: the graph carries the structured facts, the body carries the prose around them.

This body is not dead weight. It is valuable context for **both human readers and LLMs**: the narrative, examples, edge cases, and rationale that a triple store has no room for but a model reading the file consumes directly. An LLM working in the vault reads the body as readily as the frontmatter, so a definition's nuance lives exactly where the reasoning happens. If a fact belongs in the graph, it goes in the frontmatter (e.g. `comment:` → `rdfs:comment`); if it is explanatory prose for a reader, it stays in the body. Notes **MAY** therefore carry as much narrative as their authors like, with no cost to the formal model and no leakage into it.

A consequence: the body lives only in the Markdown serialization and does not survive a roundtrip through Turtle. See §5.6 for what that means for fidelity.

### 5.4 Forward direction: Vault → RDF (export)

An export tool walks the vault and emits Turtle. The transform is mechanical:

1. Walk every `.md` file and read its frontmatter.
2. Resolve each short frontmatter field to its full predicate via the (composed) context.
3. Convert each `[[Wiki link]]` to a full URI by resolving the target note's own identity.
4. Read `subClassOf` / `subPropertyOf` / `broader` from frontmatter (wiki links), like any other predicate; folder placement is ignored for *hierarchy*.
5. Decide each note's **layer from its folder**: notes under `Ontologies/` and `Vocabularies/` are the schema layer, everything else is the instance layer (§3, §5.1).
6. Mint each subject per §4.5 (non-IRI-safe characters percent-encoded): the **file name alone**, without `.md`, against the governing `@base` — a schema note's ontology/vocabulary base (a *scoped base per ontology*: `https://example.org/culinary#` for Culinary, `https://example.org/difficulty#` for Difficulty Levels), an instance note's nearest data context base. Folders never enter any IRI. A note with an explicit `id` mints as that absolute IRI, verbatim.
7. When the export is a **roundtrip face**, emit for each note whose actual location an ingester could **not** reconstruct from the graph one extra triple — `vld:path "<context-relative path>.md"` — carrying the note's true location so ingest can restore the file 1:1 (§5.5). `vld:` is Vault-LD's own namespace, `https://github.com/The-Knowledge-Graph-Guys/vault-ld#`, and `vld:path` is its only term: a plain string-valued property defined by this specification. Since identity carries no location (§4.5), that is most notes: every pinned note, every instance not sitting directly in its governing context's folder, and every schema note away from the flat placement of §5.1. Only notes at their reconstructable default — an unpinned instance at the context root, a flatly placed schema note — need no such triple. An export produced **purely for querying** — a read-only artifact that will never be ingested back — **MAY** omit these triples entirely, trading placement fidelity for a leaner graph.
8. Emit by **layer** to two Turtle files (`schema.ttl`, `data.ttl`) with standard `@prefix` headers. A layer may contain several ontology namespaces; cross-references (an instance's `type`, a property's `domain`, a class's external alignment) simply carry the relevant prefix, so the files together are one graph.

For `Recipe.md` (Culinary ontology, schema layer) the output is:

```turtle
@prefix cul: <https://example.org/culinary#> .
cul:Recipe a owl:Class ;
    rdfs:label "Recipe" ;
    rdfs:comment "A set of instructions for preparing a dish." ;
    rdfs:subClassOf cul:CreativeWork , sdo:Recipe .
```

and the instance at `Recipes/hummus.md` (data layer) reaches across into the Culinary and Difficulty namespaces — minted from its file name, with its shelf location travelling as `vld:path`:

```turtle
@prefix cul:  <https://example.org/culinary#> .
@prefix diff: <https://example.org/difficulty#> .
@prefix data: <https://example.org/data/> .
@prefix vld:  <https://github.com/The-Knowledge-Graph-Guys/vault-ld#> .
data:hummus a cul:Recipe ;
    cul:requiresIngredient data:Chickpeas ;
    cul:difficulty diff:Beginner ;
    cul:prepTimeMinutes 25 ;
    vld:path "Recipes/hummus.md" .
```

This is the export direction *when Markdown is the designated source of truth*, the common case for human-curated wikis and a common convention. In that arrangement the generated `.ttl` (and any derived overview/diagram artifacts) are **read-only**: tools and authors **MUST** edit the source `.md` files and regenerate, never patch the export. But the direction is a deployment choice, not a law of the format: where Turtle is the source of truth (§5.5, e.g. a SHACL-rich ontology), the Markdown is the generated, read-only side instead. The rule is "do not edit the generated face," whichever face that is.

### 5.5 Reverse direction: RDF → Vault (ingest)

This is the direction taken both when importing foreign RDF and when **Turtle is the standing source of truth**, for example a SHACL-rich ontology maintained in `.ttl` with this Markdown view generated from it. Ingest simply inverts the same rules:

1. one subject ⇒ one `.md` file, placed by inverting §4.5's minting. A subject carrying a `vld:path "<path>.md"` triple is written to exactly that path (relative to the folder of the context whose `@base` its path was recorded against), and the triple is **consumed** — it never appears in frontmatter, because on the vault side the path is simply where the file sits. An instance IRI that extends a known `@base` names the file — `<base>hummus` ⇒ `hummus.md`, at the source path when one travels, at the context folder's root otherwise. An IRI that extends no known base cannot be reproduced by name-based minting, so the note gets it as an explicit `id` (the full absolute IRI, §4.5). A schema subject lands in the flat `Classes/` or `Properties/` folder under its namespace's ontology folder; the localname ⇒ the file name. Names are percent-**decoded**: an ingester **SHOULD** reverse the encoding of §4.5 when choosing file names, so `Red%20Lentil%20Soup` becomes `Red Lentil Soup.md` and mints back to the identical IRI without an explicit `id`;
2. `rdfs:subClassOf` / `rdfs:subPropertyOf` / `skos:broader` / `skos:topConceptOf` ⇒ an explicit `subClassOf` / `subPropertyOf` / `broader` / `topConceptOf` frontmatter field whose values are `[[Wiki links]]` — frontmatter is the only carrier of hierarchy (§5.2) — and placement is the flat form of §5.1 unless a `vld:path` path or an existing note dictates otherwise (an ingester **MAY** offer richer organisational layouts as a convenience, §5.2; the exported source path preserves whatever it builds);
3. every other predicate, including `rdfs:comment`, ⇒ a short frontmatter field (added to the context if new); an IRI-valued object ⇒ a `[[Wiki link]]` **when the IRI is a note in the vault** (a subject this ingest is materialising, or one an existing note claims via `@id`), and a prefixed CURIE otherwise, exactly as §4.3 places external-vocabulary terms in values (`subClassOf: [ "[[CreativeWork]]", sdo:Recipe ]`); literals ⇒ scalars (datatypes supplied by the context);
4. the body is **not** populated from the graph. It is left for human- or model-authored prose, so on a pure ingest it starts empty; only the frontmatter is round-tripped (§5.3).

The frontmatter rules are symmetric on purpose: the same correspondences read in either direction. The body is the one asymmetry: it is born in Markdown and has no RDF counterpart to ingest from.

### 5.6 Roundtrip fidelity

```
            ◀──ingest───
RDF (Turtle)              Markdown files (frontmatter triples + body docs)
            ───export──▶
```

**Neither side is the privileged original.** The frontmatter and the Turtle are two serializations of the same graph; a deployment names one of them the source of truth (§5.4 and §5.5), and the other is the generated, read-only face. Fidelity is a property of the *graph*, not of either file. A roundtrip is faithful for everything the field-naming contract can express: types, labels, comments, domain and range, sub-class and sub-property, and any context-mapped predicate. **File placement round-trips too**: identity carries no location (§4.5), so any note not at its reconstructable default spot travels with a `vld:path` triple — a triple that exists only on the RDF side, materialising on export and dissolving back into the file's location on ingest. A construct with no short-name mapping is **out of scope** until it is added to the context, and a conforming tool **MUST** flag such a construct rather than silently drop it. This incompleteness is recoverable: extend the context and the construct becomes first-class.

The **body is the one deliberate asymmetry**. It carries no triples, so it has no representation in Turtle and does not survive a Markdown → RDF → Markdown roundtrip. That is by design (§5.3): the body is enrichment for human and machine readers attached to the Markdown serialization, not part of the graph being round-tripped. A deployment that keeps Turtle as its source of truth therefore treats the Markdown bodies as first-class, vault-resident content that the `.ttl` neither holds nor overwrites on regeneration.

## 6. Conformance

A note participates correctly in linked data when:

- [ ] `@type` (written directly or via a declared alias such as `type:`, §4.3) is present and is a wiki link (instances) or a CURIE such as `owl:Class` (definitions).
- [ ] object properties use `[[Wiki links]]`; datatype properties use plain scalars (their datatype, including dates, is supplied by the context, not written inline).
- [ ] frontmatter field names are the short forms defined in the context (no inline `rdfs:` / `owl:` prefixes on field names).
- [ ] every prefix or term used resolves through the active context — the shared vault context, an optional per-file `@context` layered over it (§4.2), an `@vocab` default, or a declared prefix (host-tool keys such as `tags`, `aliases`, and `cssclasses` excepted; §4.3); a term resolved by none of these is flagged, not dropped.
- [ ] identity mints from the file name alone against the governing `@base`; folders never enter any IRI (§4.5).
- [ ] an explicit `id`, when present, is a full absolute IRI (`http(s)://…`), used verbatim — never a relative reference (§4.5).
- [ ] for definitions: hierarchy lives only in frontmatter (`subClassOf` / `subPropertyOf` / `broader` / `topConceptOf` wiki links); folder nesting in the schema tree carries no hierarchy and never changes identity — non-canonical placement round-trips via `vld:path` (§5.2, §4.5, §5.4).
- [ ] on a roundtrip-face export, a note whose location the graph cannot reconstruct (a pinned note, an instance not directly in its governing context's folder, or schema placement away from the flat form of §5.1) carries a `vld:path "<path>.md"` triple — omittable only in a query-only, read-only export (§5.4); on ingest that triple is consumed into file placement and **never** written into frontmatter (§5.5).
- [ ] the generated face (whichever serialization a deployment derives: the `.ttl` when Markdown is source, the Markdown when Turtle is source) is treated as read-only; edits go to the source of truth and are regenerated.
- [ ] body text is never emitted as RDF, and a generator that produces the Markdown face **MUST** preserve existing bodies rather than clobber them on regeneration.

A tool **MAY** implement one direction only: it is a **conforming exporter** when it implements §5.4, and a **conforming ingester** when it implements §5.5, in each case honouring §5.6 (flag unmapped constructs, do not drop; preserve bodies) and the link-resolution rules of §4.4.1. A **conforming roundtrip tool** implements both directions as inverses and privileges neither serialization as source of truth.

## 7. Relationship to Existing Work

This format does not invent a data model. It composes existing ones and chooses where each lives:

- **JSON-LD / YAML-LD** provide the data model and the `@context` mechanism. The contribution here is to put the context *outside* the documents and let plain YAML frontmatter be the serialization.
- **RDF / Turtle** is the shared interchange model. The vault and the Turtle are two editable faces of one RDF graph; either may be the source of truth, and the Markdown-with-YAML-LD form is simply one more RDF serialization alongside Turtle, JSON-LD, and the rest.
- **OWL / RDFS** supply the schema vocabulary for classes and properties; this spec only says *where* those definitions are stored and *how* hierarchy is encoded (frontmatter wiki links, not folders).
- **SKOS** supplies controlled vocabularies; concept schemes and concepts are stored as ordinary notes like everything else.
- **Wiki links**, native to Obsidian and Notion, are reused as the IRI-reference mechanism, which is what makes the same files navigable by hand.
- **Markdown bundle formats**, such as Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf) (OKF), standardise the *envelope*: a directory of Markdown files with YAML frontmatter, one required `type` field, everything else producer-defined. They deliberately stop short of shared semantics, so two producers' bundles share a file format but not a vocabulary. Vault-LD is complementary rather than competing: it is the semantic layer such a bundle can adopt without changing its files. Appendix B gives the lift.
- **Agent-maintained Markdown wikis** (the pattern popularised by Karpathy's "LLM wiki" sketch and its many implementations) demonstrate the same substrate from the tooling side: persistent, interlinked notes that an LLM reads, extends, and lints, governed by prose conventions in a schema document. Vault-LD supplies what prose conventions cannot enforce: formal types, declared hierarchy, and a context that makes every field machine-resolvable, so the wiki's structure can be validated and queried rather than trusted.

The format's only original move is insisting that all of these share one directory and one effective context (composed from however many documents) so that a graph can be read, edited, and handed on without any of them being privileged over the others.

## Appendix A: A Minimal Example Bundle

A complete, copyable vault with one ontology, one vocabulary, and one instance.

**`context.jsonld`** — the root context: the cross-cutting core, then references composing each ontology's and vocabulary's own context (§4.2).
```json
{
  "@context": [
    {
      "@base": "https://example.org/",
      "type": "@type",
      "id": "@id",
      "owl": "http://www.w3.org/2002/07/owl#",
      "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
      "skos": "http://www.w3.org/2004/02/skos/core#",
      "xsd": "http://www.w3.org/2001/XMLSchema#",
      "sdo": "https://schema.org/",
      "label": "rdfs:label",
      "comment": "rdfs:comment",
      "prefLabel": "skos:prefLabel",
      "definition": "skos:definition",
      "subClassOf":    { "@id": "rdfs:subClassOf",    "@type": "@id", "@container": "@set" },
      "subPropertyOf": { "@id": "rdfs:subPropertyOf", "@type": "@id", "@container": "@set" },
      "broader":       { "@id": "skos:broader",       "@type": "@id" },
      "topConceptOf":  { "@id": "skos:topConceptOf",  "@type": "@id" },
      "inScheme":      { "@id": "skos:inScheme",      "@type": "@id" },
      "domain": { "@id": "rdfs:domain", "@type": "@id" },
      "range":  { "@id": "rdfs:range",  "@type": "@id" }
    },
    "Ontologies/Culinary/context.jsonld",
    "Vocabularies/DifficultyLevels/context.jsonld"
  ]
}
```

**`Ontologies/Culinary/context.jsonld`** — the ontology's own vocabulary *and* namespace (`@base`).
```json
{
  "@context": {
    "@base": "https://example.org/culinary#",
    "cul": "https://example.org/culinary#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "requiresIngredient": { "@id": "cul:requiresIngredient", "@type": "@id" },
    "difficulty":         { "@id": "cul:difficulty",         "@type": "@id" },
    "prepTimeMinutes":    { "@id": "cul:prepTimeMinutes",    "@type": "xsd:integer" }
  }
}
```

**`Vocabularies/DifficultyLevels/context.jsonld`** — the vocabulary's namespace; its predicates (`prefLabel`, `definition`, `broader`) are the generic SKOS terms from the core.
```json
{
  "@context": {
    "@base": "https://example.org/difficulty#",
    "diff": "https://example.org/difficulty#"
  }
}
```

**`Ontologies/Culinary/Classes/Recipe.md`**
```yaml
---
type: owl:Class
label: Recipe
comment: "A set of instructions for preparing a dish."
subClassOf: [ "[[CreativeWork]]", sdo:Recipe ]   # local + external parents, both in frontmatter
tags: [ owl-class, Culinary ]
---
# Recipe
The unit of culinary knowledge: ingredients plus method.
```

**`Ontologies/Culinary/Properties/requiresIngredient.md`**
```yaml
---
type: owl:ObjectProperty
label: requires ingredient
comment: "Links a recipe to an ingredient it depends on."
domain: [ "[[Recipe]]" ]
range:  [ "[[Ingredient]]" ]
tags: [ owl-property, Culinary ]
---
# requiresIngredient
```

**`Vocabularies/DifficultyLevels/Beginner.md`**
```yaml
---
type: skos:Concept
prefLabel: beginner
definition: "Approachable for a first-time cook; few steps, common ingredients."
topConceptOf: "[[DifficultyLevels]]"         # scheme membership; broader is concept-to-concept only
tags: [ skos-concept, DifficultyLevels ]
---
# Beginner
```

**`Vocabularies/DifficultyLevels/NoCook.md`**
```yaml
---
type: skos:Concept
prefLabel: no-cook
definition: "Needs no heat at all; assembly only."
broader: "[[Beginner]]"                      # concept hierarchy in frontmatter, like subClassOf
tags: [ skos-concept, DifficultyLevels ]
---
# No-Cook
```

**`Recipes/hummus.md`**
```yaml
---
type: "[[Recipe]]"
requiresIngredient: "[[Chickpeas]]"
difficulty: "[[Beginner]]"
prepTimeMinutes: 25
---
# Hummus
A smooth purée of chickpeas, tahini, lemon, and garlic.
```

A handful of notes, a composed context, no server, and a graph you can read with your eyes or export to Turtle on demand.

## Appendix B: Lifting an OKF Bundle (Compatibility Profile)

Google's [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf) (OKF) describes a directory of Markdown files with YAML frontmatter in which exactly one field, `type`, is required and every other field is producer-defined. That is already the physical shape of a Vault-LD vault; what an OKF bundle lacks is the context that gives its names shared meaning. This appendix defines the lift: how an OKF bundle becomes a conforming Vault-LD vault **without modifying a single bundle file**.

1. **Add a root `context.jsonld`.** The keyword aliasing of §4.3 does the whole job: the context maps OKF's bare `type` key onto `@type` — the same alias the example vault itself declares — and declares a default vocabulary for the producer's terms:

   ```json
   {
     "@context": {
       "@base": "https://example.org/bundle/",
       "@vocab": "https://example.org/bundle/vocab#",
       "type": "@type"
     }
   }
   ```

   Every OKF note now reads as YAML-LD: its `type: concept` becomes an `@type` whose value resolves under `@vocab`, and each producer-defined field resolves under `@vocab` until it is given a proper term definition.

2. **Promote `type` values to classes as needed.** Each distinct `type` string in the bundle names a class implicitly. To make one first-class, create the class note (`Ontologies/{Name}/Classes/{Type}.md`, §5.1) and, where the producer's string and the class name differ, map the string to the class IRI in the context. Nothing forces this step: an unpromoted `type` still yields a consistent, queryable `@type` triple under `@vocab`.

3. **Promote producer-defined fields the same way.** A field gains datatype or IRI coercion, and a place in a shared vocabulary, by receiving a term definition in the context (§4.2, §5.6). Until then it resolves under `@vocab` as an unrefined but present predicate.

4. **Reserved files participate like any note.** OKF reserves `index.md` and `log.md`. Under this profile they carry no special graph semantics: like every other note, they participate in the graph exactly when they carry typed frontmatter (§4.4.1) and stay outside it otherwise.

5. **Body links stay navigational.** OKF encodes its graph as ordinary Markdown links in the body; Vault-LD's triples live in frontmatter only (§5.3). The lift therefore captures the bundle's *frontmatter* facts. A producer who wants a body link to become an edge promotes it to a frontmatter property, at which point it is a wiki link like any other (§4.4).

The direction of travel is incremental: an untouched OKF bundle plus the three-line context above is already valid linked data at coarse grain, and every promotion step (a class note here, a term definition there) sharpens it without ever breaking the files for tools that only understand OKF.
