# IANA registration: the `Vault-LD` Markdown variant

Vault-LD notes are identified as `text/markdown; charset=UTF-8; variant=Vault-LD`
([SPEC §8](../SPEC.md#8-media-type)). This file holds the registration request
for the IANA [Markdown Variants](https://www.iana.org/assignments/markdown-variants/)
registry, created by [RFC 7763 §6.1](https://www.rfc-editor.org/rfc/rfc7763#section-6.1).
That registry is first-come, first-served: any level of documentation is
enough and there is no expert review. Two rules matter:

- IANA checks that every reference and contact address works when it
  registers the entry, so the links below must already resolve.
- The identifier is permanent; "not even case may be changed" (RFC 7763 §6.1.2).
  `Vault-LD` is the spelling used throughout the spec. Changing the entry later
  needs IETF Review.

## How to submit

1. Fill in the **[TO CONFIRM]** fields below. Use a role address for contact
   details (it is published), not a personal one.
2. Cut a release that contains §8, and put its tag in the References URL.
3. Submit through IANA's general protocol registry request form,
   <https://www.iana.org/form/protocol-assignment>, naming the "Markdown Variants"
   registry and pasting the template. The registry page doesn't name a
   submission channel, so if the form doesn't fit, email the template to
   `iana@iana.org` with the subject "Markdown Variants registration: Vault-LD".
4. When IANA confirms, record the date and ticket number below and link the
   registry entry from the spec.

Status: **not yet submitted**

## Registration template (RFC 7763 §6.1)

```
Identifier: Vault-LD

Name: Vault-LD (Linked Data in the Vault)

Description: A Markdown note whose YAML frontmatter is YAML-LD: one RDF
  resource per file, frontmatter keys are predicates, and [[wiki links]] are
  IRI references. Field names and prefixes resolve through a shared JSON-LD
  context kept outside the note; the body is human documentation and is not
  part of the RDF graph. A directory of such notes (a "vault") is an RDF graph
  that round-trips losslessly to Turtle and other RDF serializations.
  The body follows CommonMark with the wiki-link extension used by Obsidian;
  any Markdown processor can render it.

Additional Parameters: None.

Fragment Identifiers: As for text/markdown (RFC 7763). A fragment addresses a
  heading in the note body; it does not identify an RDF resource.

References:
  Vault-LD Specification, Section 8:
  https://github.com/The-Knowledge-Graph-Guys/vault-ld/blob/<release tag>/SPEC.md#8-media-type
  https://vault-ld.org/                                  [TO CONFIRM stable spec URL]

Contact Information: The Knowledge Graph Guys
  <[TO CONFIRM role address, e.g. standards@knowledge-graph-guys.com]>
  https://github.com/The-Knowledge-Graph-Guys/vault-ld
```

## Reference implementations

- `scripts/vault_to_rdf.py`, `scripts/rdf_to_vault.py` (this repository)
- The Knowledge Graph Guys' schema site generator (your-schema-org), which
  serves single notes under this media type through HTTP content negotiation.
