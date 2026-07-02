# Contributing to Vault-LD

Vault-LD is an open standard, published so the community can evolve it. Contributions of every size are welcome, from typo fixes to new normative sections.

## The two kinds of contribution

**1. Changes to the specification (normative text in `SPEC.md`)**

Please **open an issue first** using the *Spec change proposal* template. Normative changes affect every conforming implementation, so they need discussion before wording. A good proposal states:

- the problem: what the spec currently gets wrong, leaves ambiguous, or cannot express;
- the proposed behaviour, ideally with a frontmatter/RDF example of both the current and the proposed outcome;
- who is affected: exporters, ingesters, or both.

Once there's rough consensus on the issue, submit a pull request.

**2. Everything else.** The reference tools (`vault_to_rdf.py`, `rdf_to_vault.py`), the example vault, the guides (`EXPORT.md`, `INGEST.md`), the README, typos, broken links: a direct pull request is fine, no issue needed.

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
   python vault_to_rdf.py "Vault-LD Example" --out-dir build
   python rdf_to_vault.py RoundtripVault build/schema.ttl
   python rdf_to_vault.py RoundtripVault build/data.ttl
   ```

   Vault to RDF back to vault must be a no-op, and RDF to vault back to RDF must be graph-isomorphic (SPEC §5).
5. Open the pull request against `main`. The template will ask you to confirm the sync and roundtrip checks.

## Conformance language

The spec uses RFC 2119/8174 key words (**MUST**, **SHOULD**, **MAY**). Use them deliberately in normative text, and not at all in explanatory prose.

## Licensing

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE), the same license as the project. There is no CLA.

## Questions

Not sure whether something is a bug in a tool or an ambiguity in the spec? Open an issue and say so. Clarifying ambiguity is one of the most valuable contributions to a young standard.
