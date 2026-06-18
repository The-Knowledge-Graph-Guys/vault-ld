# Vault-LD

*An open format for knowledge two very different readers can share at once: a person editing notes, and a machine reasoning over a graph.*

## RDF in the Vault

Karpathy's "LLM wiki" idea points at something real: a directory of plain Markdown notes is one of the most powerful ways to work with LLMs. It is readable by you, chunkable by a model, and diffable in git, with no database required. The YAML frontmatter at the centre of this approach carries a hidden pattern: it can map onto [YAML-LD](https://json-ld.github.io/yaml-ld/spec/) (JSON-LD with a YAML serialization). Resolve that frontmatter through one shared context and your notes stop being tagged text. They become linked data.

This matters for anyone already invested in RDF-based ontologies. Your business semantics (your classes, properties, and controlled vocabularies) drop straight into the wiki your team already uses, much as [schema.org](https://schema.org) gave web pages a shared vocabulary without asking authors to leave HTML. The benefit runs both ways: business semantics arrive *inside* the wiki, and the ontology gains a human-friendly surface, where classes and properties can be read and edited as notes rather than as raw Turtle.

Both directions work because of the **roundtrip**. Since the frontmatter is YAML-LD, a note and an ontology definition are the *same kind of object*, and either can be projected losslessly to RDF and back. An ontology can enter as Turtle, be edited as Markdown, and leave as Turtle again, or the reverse, with no canonical "real" form privileged over the other.

![Vault-LD](images/Vault-LD.png)

## What's here

- **[[Vault-LD Specification - Linked Data in the Vault|The specification]]**: the normative reference. It defines how frontmatter becomes a knowledge graph (§4) and how any RDF graph round-trips through the vault format with full fidelity (§5), along with terminology, directory structure, and conformance criteria.
- **`Vault-LD Example/`**: a complete, copyable vault that demonstrates every rule in the spec. It holds one ontology (`Culinary`), one controlled vocabulary (`Difficulty Levels`), and one instance (`hummus`), all sharing a single `context.jsonld`.

## A taste

Read this note:

```markdown
---
"@type": "[[Recipe]]"
requiresIngredient: "[[Chickpeas]]"
prepTimeMinutes: 25
---

# Hummus
A smooth purée of chickpeas, tahini, lemon, and garlic.
```

You have just read these triples:

```turtle
<this-file> a :Recipe ;
            :requiresIngredient <Chickpeas> ;
            :prepTimeMinutes 25 .
```

The frontmatter is the graph; the body is prose for human and machine readers. One shared `context.jsonld` supplies the IRIs, datatypes, and prefixes, so authors write short, clean names while the semantics are supplied for them. See the [[Vault-LD Specification - Linked Data in the Vault|specification]] for the full rules.
