# Vault-LD

*An open format for knowledge two very different readers can share at once: a person editing notes, and a machine reasoning over a graph.*

## RDF in the Vault

[Karpathy's "LLM wiki" idea](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) points at something real: a directory of plain Markdown notes is one of the most powerful ways to work with LLMs. It is readable by you, chunkable by a model, and diffable in git, with no database required. The YAML frontmatter at the centre of this approach carries a hidden pattern: it can map onto [YAML-LD](https://json-ld.github.io/yaml-ld/spec/) (JSON-LD with a YAML serialization). Resolve that frontmatter through one shared context and your notes stop being tagged text. They become linked data.

This matters for anyone already invested in RDF-based ontologies. Your business semantics (your classes, properties, and controlled vocabularies) drop straight into the wiki your team already uses, much as [schema.org](https://schema.org) gave web pages a shared vocabulary without asking authors to leave HTML. The benefit runs both ways: business semantics arrive *inside* the wiki, and the ontology gains a human-friendly surface, where classes and properties can be read and edited as notes rather than as raw Turtle.

Both directions work because of the **roundtrip**. Since the frontmatter is YAML-LD, a note and an ontology definition are the *same kind of object*, and either can be projected losslessly to RDF and back. An ontology can enter as Turtle, be edited as Markdown, and leave as Turtle again, or the reverse, with no canonical "real" form privileged over the other.

![Vault-LD](images/Vault-LD.png)

## What's here

- **[SPEC.md](SPEC.md)**: the normative reference. It defines how frontmatter becomes a knowledge graph (§4) and how any RDF graph round-trips through the vault format with full fidelity (§5), along with terminology, directory structure, conformance criteria, and a compatibility profile for lifting OKF-style Markdown bundles into linked data (Appendix B).
- **`Vault-LD Example/`**: a complete, copyable vault that demonstrates every rule in the spec. It holds one ontology (`Culinary`), one controlled vocabulary (`Difficulty Levels`), and one instance (`hummus`). Its root `context.jsonld` composes the Culinary ontology's own context, showing how multiple contexts compose (SPEC §4.2).
- **`vault_to_rdf.py`**: a reference exporter that projects a vault to RDF — see [Exporting to RDF](#exporting-to-rdf) below.
- **`rdf_to_vault.py`**: the reference ingester running the other way, RDF → vault — see [Ingesting RDF](#ingesting-rdf) below. Together the two tools close the roundtrip.

## Exporting to RDF

The repo ships `vault_to_rdf.py`, a small Python tool that reads a vault and emits Turtle, split by layer into two files:

- `schema.ttl` — the schema layer (classes, properties, concepts), each ontology in its own namespace (`cul:`, `diff:`, …),
- `data.ttl` — the instance layer (typed notes) in the data namespace.

It classifies each note by its folder, mints each subject under its ontology's `@base`, resolves frontmatter through the vault's composed `@context`, and flags anything it can't map rather than dropping it. Export the example vault to `build/` in one line:

```sh
pip install rdflib pyyaml && python vault_to_rdf.py "Vault-LD Example" --out-dir build
```

See **[EXPORT.md](EXPORT.md)** for the full usage guide, flags, and how layer classification and context composition work.

## Ingesting RDF

The reverse direction, `rdf_to_vault.py`, projects any RDF graph *into* the vault format (SPEC §5.5) — one note per subject, hierarchy in frontmatter, IRI objects as wiki links. Point it at an existing vault and it updates notes **in place**, preserving bodies, `tags:`, and folder structure, and leaving unchanged notes untouched; point it at an empty directory and it builds the whole vault, synthesizing a composed `context.jsonld` when none exists. Predicates the context doesn't map get a short name coined and added to the right context document; anything the format can't express (blank nodes, language tags) is flagged, never dropped (SPEC §5.6). Import a foreign ontology in one line:

```sh
python rdf_to_vault.py MyVault foreign-ontology.ttl
```

See **[INGEST.md](INGEST.md)** for the full usage guide and the fidelity rules. Because the two tools are inverses, `vault → RDF → vault` is a no-op and `RDF → vault → RDF` is graph-isomorphic.

## A taste

Read this note:

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

The frontmatter is the graph; the body is prose for human and machine readers. One shared `context.jsonld` supplies the IRIs, datatypes, and prefixes, so authors write short, clean names while the semantics are supplied for them. See the [Vault-LD Specification](SPEC.md) for the full rules.

## Contributing

Vault-LD is an open standard and contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Spec changes start life as an issue using the *Spec change proposal* template; fixes to the reference tools, example vault, and docs can go straight to a pull request.

## License

[Apache License 2.0](LICENSE).
