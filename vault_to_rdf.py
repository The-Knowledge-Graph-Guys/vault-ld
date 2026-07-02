#!/usr/bin/env python3
"""
vault_to_rdf.py — Project a Vault-LD vault to RDF, split by namespace.

Walks a vault of Markdown notes (per the Vault-LD SPEC), reads each note's
YAML frontmatter as YAML-LD through the shared context.jsonld, and emits two
Turtle files:

    schema.ttl   the schema layer  — classes, properties, ontologies, concepts
                 minted in the schema namespace (default https://example.org/schema/)
    data.ttl     the instance layer — typed notes (recipes, ingredients, ...)
                 minted in the data namespace   (default https://example.org/data/)

A note is schema-layer when its `@type` is a CURIE (owl:Class, skos:Concept, ...)
and instance-layer when its `@type` is a wiki link ("[[Recipe]]"), matching the
distinction drawn in SPEC §4.6.

Usage:
    python vault_to_rdf.py "Vault-LD Example"
    python vault_to_rdf.py VAULT --context VAULT/context.jsonld --out-dir build
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF

# Host-editor keys are affordances of the editing surface, not triples
# (SPEC §4.3): never emitted, never warned about.
HOST_KEYS = {"tags", "aliases", "cssclasses"}


def iri_safe(name: str) -> str:
    """Percent-encode characters not legal in an IRI local part (SPEC §4.5)."""
    return quote(name, safe="")

# ---------------------------------------------------------------------------
# Folder structure decides the layer (SPEC §3, §5.1): the schema layer lives
# under Ontologies/ and Vocabularies/, everything else is the instance layer.
#
# The acceptable-type sets below are NOT used to classify — they are an error
# bound. Given a note's location we know what kind of resource it ought to be,
# so if its @type isn't one of the expected types we emit a warning rather than
# silently mis-modelling it.
# ---------------------------------------------------------------------------
OWL = "http://www.w3.org/2002/07/owl#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SKOS = "http://www.w3.org/2004/02/skos/core#"

EXPECTED_CLASS = {OWL + "Class", RDFS + "Class"}
EXPECTED_PROPERTY = {
    OWL + "ObjectProperty",
    OWL + "DatatypeProperty",
    OWL + "AnnotationProperty",
    RDF_NS + "Property",
}
EXPECTED_ONTOLOGY = {OWL + "Ontology"}
EXPECTED_SCHEME = {SKOS + "ConceptScheme"}
EXPECTED_CONCEPT = {SKOS + "Concept"}


def merge_context(node, base_dir: Path, seen: set[Path], warnings: list[str]) -> dict:
    """Resolve a JSON-LD `@context` value into one flat mapping.

    Follows JSON-LD composition semantics: a context may be an inline object, a
    string reference to another context document, or an array of either, applied
    left-to-right with later entries overriding earlier ones. String references
    are resolved as file paths relative to the document that names them, so each
    ontology can ship its own self-contained context (as published ontologies
    do) and the root context simply lists the ones it composes.
    """
    merged: dict = {}
    if isinstance(node, dict):
        merged.update(node)
    elif isinstance(node, list):
        for entry in node:
            merged.update(merge_context(entry, base_dir, seen, warnings))
    elif isinstance(node, str):
        if node.startswith("http://") or node.startswith("https://"):
            warnings.append(f"remote context not fetched: {node}")
            return merged
        ref = (base_dir / node).resolve()
        if ref in seen:
            return merged  # cycle guard
        if not ref.exists():
            warnings.append(f"referenced context not found: {ref}")
            return merged
        seen.add(ref)
        doc = json.loads(ref.read_text(encoding="utf-8"))
        sub = merge_context(doc.get("@context"), ref.parent, seen, warnings)
        # A referenced context contributes vocabulary, not a new document base:
        # its @base scopes only its own ontology's subjects (read separately by
        # context_base), so it must not override the root's @base here.
        sub.pop("@base", None)
        merged.update(sub)
    return merged


def context_base(path: Path, warnings: list[str]) -> str | None:
    """Return the `@base` an ontology/vocabulary context declares, or None.

    Read in isolation (not merged into the root) so each ontology keeps its own
    scoped base — the namespace its members are minted under.
    """
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    mapping = merge_context(doc.get("@context"), path.parent, {path.resolve()}, warnings)
    return mapping.get("@base")


def load_context(path: Path, warnings: list[str]) -> "Context":
    """Load a context document, composing any contexts it references."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    mapping = merge_context(doc.get("@context"), path.parent, {path.resolve()}, warnings)
    return Context(mapping)


class Context:
    """A composed @context: prefix map plus short-name term definitions."""

    def __init__(self, ctx: dict):
        self.base = ctx.get("@base", "")
        self.prefixes: dict[str, str] = {}
        self.terms: dict[str, dict] = {}
        for key, val in ctx.items():
            if key.startswith("@"):
                continue
            if isinstance(val, str) and (val.startswith("http") or "#" in val or val.endswith("/")):
                # treat single-string namespace-looking values as prefixes,
                # and single-string IRI-mapped terms as terms too.
                if val.startswith("http") and (val.endswith("/") or val.endswith("#")):
                    self.prefixes[key] = val
                else:
                    self.terms[key] = {"@id": val}
            elif isinstance(val, str):
                self.terms[key] = {"@id": val}
            elif isinstance(val, dict):
                self.terms[key] = val

    def expand_curie(self, token: str) -> str:
        """Expand 'prefix:local' to a full IRI; pass full IRIs through."""
        token = token.strip()
        if token.startswith("http://") or token.startswith("https://"):
            return token
        if ":" in token:
            prefix, local = token.split(":", 1)
            if prefix in self.prefixes:
                return self.prefixes[prefix] + local
        return self.base + token


def parse_frontmatter(path: Path) -> dict | None:
    """Return the YAML frontmatter of a Markdown note as a dict, or None."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    data = yaml.safe_load(parts[1])
    return data if isinstance(data, dict) else None


def type_values(fm: dict) -> list[str]:
    val = fm.get("@type")
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def is_wikilink(token) -> bool:
    return isinstance(token, str) and token.strip().startswith("[[") and token.strip().endswith("]]")


def wikilink_name(token: str) -> str:
    """Reduce a wiki link to the note name it resolves by (SPEC §4.4.1).

    [[name|alias]]   -> alias is display-only, ignored
    [[name#Heading]] -> a fragment addresses a location, not a resource
    [[path/to/name]] -> a path only disambiguates; resolution is by note name
    """
    inner = token.strip()[2:-2]
    inner = inner.split("|", 1)[0]
    inner = inner.split("#", 1)[0]
    inner = inner.rsplit("/", 1)[-1]
    return inner.strip()


def locate(path: Path, vault: Path) -> tuple[str, set[str] | None]:
    """Classify a note by its folder location (SPEC §3).

    Returns (layer, expected_types) where layer is 'schema' or 'data' and
    expected_types is the set of acceptable @type IRIs for that location, or
    None when the location implies no constraint (the instance layer).

    The schema layer is recognised by walking up from the note:
      .../Ontologies/<Name>/Classes/*      -> owl:Class
      .../Ontologies/<Name>/Properties/*   -> owl:{Object,Datatype,...}Property
      .../Ontologies/<Name>/<Name>.md      -> owl:Ontology
      .../Vocabularies/<Scheme>/<Scheme>.md-> skos:ConceptScheme
      .../Vocabularies/<Scheme>/*          -> skos:Concept
    Anything not under Ontologies/ or Vocabularies/ is the data layer.
    """
    parts = path.relative_to(vault).parts
    parent = path.parent.name

    if "Ontologies" in parts:
        if parent == "Classes":
            return "schema", EXPECTED_CLASS
        if parent == "Properties":
            return "schema", EXPECTED_PROPERTY
        # the ontology resource itself: file sits directly in its named folder
        return "schema", EXPECTED_ONTOLOGY

    if "Vocabularies" in parts:
        # the scheme file shares its name with the folder; the rest are concepts
        if path.stem == parent:
            return "schema", EXPECTED_SCHEME
        return "schema", EXPECTED_CONCEPT

    return "data", None


def governing(path: Path, vault: Path) -> tuple[Path | None, str | None]:
    """Locate the ontology/scheme resource note that owns a schema note.

    Every schema note lives under Ontologies/<Name>/ or Vocabularies/<Name>/,
    and the resource that declares that namespace is the note <Name>/<Name>.md.
    Returns (governing_note_path, name), or (None, None) for the data layer.
    A note can be its own governor (the ontology/scheme note itself).
    """
    parts = path.relative_to(vault).parts
    for anchor in ("Ontologies", "Vocabularies"):
        if anchor in parts:
            i = parts.index(anchor)
            name = parts[i + 1]
            gov = vault.joinpath(*parts[: i + 1], name, name + ".md")
            return gov, name
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Project a Vault-LD vault to RDF, split by namespace.")
    ap.add_argument("vault", type=Path, help="path to the vault root directory")
    ap.add_argument("--context", type=Path, default=None,
                    help="path to context.jsonld (default: <vault>/context.jsonld)")
    ap.add_argument("--out-dir", type=Path, default=Path("."),
                    help="directory to write schema.ttl and data.ttl (default: .)")
    ap.add_argument("--schema-ns", default="https://example.org/schema/",
                    help="schema namespace IRI")
    ap.add_argument("--data-ns", default="https://example.org/data/",
                    help="data namespace IRI")
    args = ap.parse_args()

    vault: Path = args.vault
    context_path = args.context or (vault / "context.jsonld")
    if not context_path.exists():
        print(f"error: context not found at {context_path}", file=sys.stderr)
        return 1

    warnings: list[str] = []
    ctx = load_context(context_path, warnings)
    DATA = Namespace(args.data_ns)

    # ---- Pass 1a: discover every note and its layer.
    discovered: list[tuple[Path, dict, str, set[str] | None]] = []
    for path in sorted(vault.rglob("*.md")):
        fm = parse_frontmatter(path)
        if fm is None or "@type" not in fm:
            continue
        layer, expected = locate(path, vault)
        discovered.append((path, fm, layer, expected))

    # Each ontology/vocabulary folder mints its members under the @base its own
    # context.jsonld declares (a scoped base per ontology). Cache base by folder.
    onto_base: dict[Path, str] = {}

    def base_for(gov_path: Path, name: str) -> str:
        onto_dir = gov_path.parent
        if onto_dir not in onto_base:
            base = context_base(onto_dir / "context.jsonld", warnings)
            if base is None:                       # fallback: schema namespace
                base = args.schema_ns.rstrip("/") + "/" + name + "#"
            onto_base[onto_dir] = base
        return onto_base[onto_dir]

    def subject_iri(path: Path, fm: dict, layer: str) -> URIRef:
        if "@id" in fm:
            return URIRef(ctx.expand_curie(str(fm["@id"])))
        if layer == "data":
            return URIRef(DATA[iri_safe(path.stem)])
        # schema layer: resolve the file name against the ontology's scoped
        # @base (SPEC §4.2 deviation note, §4.5, §5.4).
        gov_path, name = governing(path, vault)
        base = base_for(gov_path, name)
        return URIRef(base + iri_safe(path.stem))

    # ---- Pass 1b: mint each subject and index it by note name.
    notes: list[tuple[Path, dict, str, URIRef]] = []
    subject_by_name: dict[str, URIRef] = {}
    for path, fm, layer, expected in discovered:
        subj = subject_iri(path, fm, layer)
        notes.append((path, fm, layer, subj))
        if path.stem in subject_by_name and subject_by_name[path.stem] != subj:
            warnings.append(f"ambiguous note name '{path.stem}': multiple participating "
                            f"notes share it; bare wiki links to it may resolve wrongly "
                            f"(disambiguate with a path-qualified link or an explicit @id)")
        subject_by_name[path.stem] = subj

        # Error bound: a schema-folder note must carry an acceptable @type.
        if expected is not None:
            for t in type_values(fm):
                if is_wikilink(t):
                    iri = "[[" + wikilink_name(t) + "]]"  # report as written
                    warnings.append(f"{path.name}: @type {iri} in a schema folder; "
                                    f"expected one of {sorted(expected)}")
                    continue
                iri = ctx.expand_curie(str(t))
                if iri not in expected:
                    warnings.append(f"{path.name}: @type '{t}' is not an expected "
                                    f"type for {path.parent.name}/ "
                                    f"(expected one of {sorted(expected)})")

    def resolve_iri(token: str) -> URIRef:
        """Resolve a wiki link or CURIE/IRI value to a full IRI."""
        if is_wikilink(token):
            name = wikilink_name(token)
            iri = subject_by_name.get(name)
            if iri is None:
                warnings.append(f"dangling wiki link [[{name}]] -> minted in data namespace")
                return URIRef(DATA[iri_safe(name)])
            return iri
        return URIRef(ctx.expand_curie(token))

    # ---- Build two graphs, binding every prefix the context declares
    # (owl, rdfs, skos, xsd, sdo, and each ontology's own — cul, diff, ...).
    g_schema, g_data = Graph(), Graph()
    for g in (g_schema, g_data):
        for prefix, ns in ctx.prefixes.items():
            g.bind(prefix, ns)
        g.bind("data", DATA)

    for path, fm, layer, subj in notes:
        g = g_schema if layer == "schema" else g_data

        for key, raw in fm.items():
            if key == "@id":
                continue
            values = raw if isinstance(raw, list) else [raw]

            if key == "@type":
                for v in values:
                    g.add((subj, RDF.type, resolve_iri(str(v))))
                continue

            if key in HOST_KEYS:
                continue

            term = ctx.terms.get(key)
            if term is None:
                warnings.append(f"{path.name}: field '{key}' not in context -> skipped")
                continue

            pred = URIRef(ctx.expand_curie(term["@id"]))
            coercion = term.get("@type")  # "@id", a datatype CURIE, or None

            for v in values:
                if coercion == "@id":
                    g.add((subj, pred, resolve_iri(str(v))))
                elif coercion:
                    dt = URIRef(ctx.expand_curie(coercion))
                    g.add((subj, pred, Literal(v, datatype=dt)))
                else:
                    g.add((subj, pred, Literal(v)))

    # ---- Serialize.
    args.out_dir.mkdir(parents=True, exist_ok=True)
    schema_out = args.out_dir / "schema.ttl"
    data_out = args.out_dir / "data.ttl"
    g_schema.serialize(destination=schema_out, format="turtle")
    g_data.serialize(destination=data_out, format="turtle")

    print(f"schema layer: {len(g_schema)} triples -> {schema_out}")
    print(f"data layer:   {len(g_data)} triples -> {data_out}")
    if warnings:
        print("\nwarnings:", file=sys.stderr)
        for w in dict.fromkeys(warnings):  # de-dupe, keep order
            print(f"  - {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
