#!/usr/bin/env python3
"""
rdf_to_vault.py — Ingest RDF into a Vault-LD vault (the reverse of vault_to_rdf.py).

Reads one or more RDF files (Turtle, N-Triples, JSON-LD, ...) and projects every
subject into the vault format per SPEC §5.5: one subject ⇒ one Markdown note whose
YAML frontmatter carries the subject's triples, resolved through the vault's
composed context. Together with vault_to_rdf.py this closes the roundtrip of
SPEC §5.6: RDF ⇄ vault format, with neither side privileged.

Placement follows SPEC §5.1 — schema subjects land under Ontologies/ and
Vocabularies/ (grouped by the namespace their IRI is minted in), instances land
in plain folders. When a note for a subject already exists anywhere in the
vault it is updated *in place*, so the vault's structure survives regeneration.

Fidelity rules honoured (SPEC §5.5, §5.6, §6):
  - existing bodies are never clobbered; a freshly ingested note starts with an
    empty body,
  - frontmatter keys that are not context-mapped (tags, aliases, ...) belong to
    the Markdown face and are preserved,
  - a predicate with no short name in the context gets one coined from its
    localname and *added to the context* (the ontology's own context.jsonld
    when the predicate lives in that namespace, the root context otherwise),
  - anything the vault format cannot express (blank nodes, language tags,
    datatype mismatches) is flagged as a warning, never dropped silently,
  - a note whose frontmatter would not change is not rewritten at all.

Usage:
    python rdf_to_vault.py VAULT schema.ttl data.ttl
    python rdf_to_vault.py NewVault graph.ttl            # no context: one is synthesized
    python rdf_to_vault.py VAULT g.ttl --context other/context.jsonld --data-ns https://example.org/data/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote

import yaml
from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF

from vault_to_rdf import (
    EXPECTED_CLASS,
    EXPECTED_CONCEPT,
    EXPECTED_ONTOLOGY,
    EXPECTED_PROPERTY,
    EXPECTED_SCHEME,
    OWL,
    RDFS,
    SKOS,
    Context,
    canonical_keywords,
    context_base,
    governing,
    iri_safe,
    load_context,
    locate,
    parse_frontmatter,
)

XSD = "http://www.w3.org/2001/XMLSchema#"
SKOS_IN_SCHEME = URIRef(SKOS + "inScheme")

# Literal datatypes YAML can carry natively without a context coercion: the
# forward direction re-infers the same datatype from the parsed YAML value.
NATIVE_SAFE = {
    XSD + "integer",
    XSD + "boolean",
    XSD + "double",
    XSD + "date",
    XSD + "dateTime",
}


class Raw(str):
    """A scalar emitted into YAML verbatim, unquoted (bare dates, dateTimes)."""


def core_context(data_ns: str) -> dict:
    """The cross-cutting core for a synthesized root context (SPEC Appendix A)."""
    return {
        "@base": data_ns,
        "type": "@type",
        "id": "@id",
        "owl": OWL,
        "rdfs": RDFS,
        "skos": SKOS,
        "xsd": XSD,
        "label": "rdfs:label",
        "comment": "rdfs:comment",
        "seeAlso": {"@id": "rdfs:seeAlso", "@type": "@id"},
        "isDefinedBy": {"@id": "rdfs:isDefinedBy", "@type": "@id"},
        "prefLabel": "skos:prefLabel",
        "altLabel": "skos:altLabel",
        "definition": "skos:definition",
        "scopeNote": "skos:scopeNote",
        "subClassOf": {"@id": "rdfs:subClassOf", "@type": "@id", "@container": "@set"},
        "subPropertyOf": {"@id": "rdfs:subPropertyOf", "@type": "@id", "@container": "@set"},
        "broader": {"@id": "skos:broader", "@type": "@id"},
        "narrower": {"@id": "skos:narrower", "@type": "@id"},
        "inScheme": {"@id": "skos:inScheme", "@type": "@id"},
        "topConceptOf": {"@id": "skos:topConceptOf", "@type": "@id"},
        "hasTopConcept": {"@id": "skos:hasTopConcept", "@type": "@id"},
        "domain": {"@id": "rdfs:domain", "@type": "@id"},
        "range": {"@id": "rdfs:range", "@type": "@id"},
        "equivalentClass": {"@id": "owl:equivalentClass", "@type": "@id"},
        "inverseOf": {"@id": "owl:inverseOf", "@type": "@id"},
    }


# ---------------------------------------------------------------------------
# IRI helpers
# ---------------------------------------------------------------------------

def split_iri(iri: str) -> tuple[str, str]:
    """Split an IRI into (namespace, localname) at the last '#' or '/'."""
    i = max(iri.rfind("#"), iri.rfind("/"))
    if i == -1 or i == len(iri) - 1:
        return iri, ""
    return iri[: i + 1], iri[i + 1:]


def sanitize_stem(local: str) -> str:
    """Make a localname safe as a file stem, percent-decoding first (SPEC §4.5,
    §5.5): the forward direction minted `Red Lentil Soup.md` as
    `Red%20Lentil%20Soup`, so decoding restores the file name that mints back
    to the identical IRI — no explicit @id pin needed."""
    return re.sub(r'[\\/:*?"<>|]', "-", unquote(local)) or "unnamed"


def derive_folder_name(ns: str) -> str:
    """Fall back to a folder name for a namespace with no ontology/scheme subject."""
    for seg in reversed(re.split(r"[/#]+", ns.rstrip("/#"))):
        if re.search(r"[A-Za-z]", seg):
            clean = re.sub(r"[^\w\-]", "", seg)
            return clean[:1].upper() + clean[1:]
    return "Imported"


def pluralize(name: str) -> str:
    return name if name.endswith("s") else name + "s"


# ---------------------------------------------------------------------------
# Context files: read/extend/write, preserving what is already there
# ---------------------------------------------------------------------------

class ContextEditor:
    """Edits one context.jsonld document, writing back only if changed."""

    def __init__(self, path: Path, initial: dict | None = None):
        self.path = path
        if path.exists():
            self.doc = json.loads(path.read_text(encoding="utf-8"))
            self.dirty = False
        else:
            self.doc = {"@context": initial if initial is not None else {}}
            self.dirty = True

    def _first_dict(self) -> dict:
        ctx = self.doc.setdefault("@context", {})
        if isinstance(ctx, dict):
            return ctx
        for entry in ctx:
            if isinstance(entry, dict):
                return entry
        entry = {}
        ctx.insert(0, entry)
        return entry

    def has(self, name: str) -> bool:
        ctx = self.doc.get("@context")
        entries = ctx if isinstance(ctx, list) else [ctx]
        return any(isinstance(e, dict) and name in e for e in entries)

    def add_term(self, name: str, tdef: dict) -> None:
        if self.has(name):
            return
        # single-@id terms use the compact string form ("label": "rdfs:label")
        self._first_dict()[name] = tdef["@id"] if list(tdef) == ["@id"] else tdef
        self.dirty = True

    def add_prefix(self, prefix: str, ns: str) -> None:
        if not self.has(prefix):
            self._first_dict()[prefix] = ns
            self.dirty = True

    def add_reference(self, ref: str) -> None:
        ctx = self.doc.setdefault("@context", {})
        if isinstance(ctx, dict):
            ctx = self.doc["@context"] = [ctx]
        if ref not in ctx:
            ctx.append(ref)
            self.dirty = True

    def save(self) -> bool:
        if not self.dirty:
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.dirty = False
        return True


# ---------------------------------------------------------------------------
# YAML frontmatter emission, styled like the notes a human would write
# ---------------------------------------------------------------------------

PLAIN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-'./:]*$")


def plain_safe(s: str) -> bool:
    """True when a string can be written as a bare YAML scalar (also inside
    a flow list) and re-parse to exactly itself."""
    if not PLAIN_RE.fullmatch(s) or ": " in s or " #" in s or s.endswith(" "):
        return False
    try:
        return yaml.safe_load(s) == s
    except yaml.YAMLError:
        return False


def emit_scalar(v) -> str:
    if isinstance(v, Raw):
        return str(v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):  # preserved non-context keys may hold structures
        return yaml.safe_dump(v, default_flow_style=True, sort_keys=False).strip()
    s = str(v)
    return s if plain_safe(s) else json.dumps(s, ensure_ascii=False)


def emit_frontmatter(fm: dict) -> str:
    lines = ["---"]
    for key, val in fm.items():
        k = json.dumps(key) if key.startswith("@") else key
        if isinstance(val, list):
            lines.append(f"{k}: [ " + ", ".join(emit_scalar(v) for v in val) + " ]")
        else:
            lines.append(f"{k}: {emit_scalar(val)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def norm(v):
    """Normalize a frontmatter value for semantic comparison (list-of-one ==
    scalar, dates == their ISO strings, order-insensitive lists)."""
    if isinstance(v, list):
        n = [norm(x) for x in v]
        return n[0] if len(n) == 1 else sorted(n, key=str)
    if isinstance(v, Raw):
        try:
            parsed = yaml.safe_load(str(v))
        except yaml.YAMLError:
            return str(v)
        return norm(parsed) if not isinstance(parsed, (str, type(None))) else str(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


# ---------------------------------------------------------------------------
# The ingest
# ---------------------------------------------------------------------------

def governing_base(path: Path, vault: Path, root_base: str,
                   warnings: list[str]) -> tuple[str, Path]:
    """The (base, folder) of the nearest context.jsonld at or above a note
    (SPEC §4.5). Falls back to the vault base when none is on disk yet."""
    d = path.parent
    while d != vault and not (d / "context.jsonld").exists():
        d = d.parent
    if (d / "context.jsonld").exists():
        base = context_base(d / "context.jsonld", warnings)
        if base:
            return base, d
    return root_base, vault


def minted_iri(path: Path, vault: Path, root_base: str,
               warnings: list[str]) -> tuple[str, str]:
    """(minted IRI, governing base) for a note's location, exactly as the
    forward direction mints identity (SPEC §4.5): schema notes from the file
    name under their ontology's @base, instances from the context-relative
    file path under the governing @base, each segment percent-encoded."""
    layer, _ = locate(path, vault)
    if layer == "data":
        base, folder = governing_base(path, vault, root_base, warnings)
        rel = path.relative_to(folder).with_suffix("")
        return base + "/".join(iri_safe(seg) for seg in rel.parts), base
    gov, _name = governing(path, vault)
    base = context_base(gov.parent / "context.jsonld", warnings) or ""
    return base + iri_safe(path.stem), base


def classify(type_iris: set[str]) -> str:
    if type_iris & EXPECTED_ONTOLOGY:
        return "ontology"
    if type_iris & EXPECTED_SCHEME:
        return "scheme"
    if type_iris & EXPECTED_CLASS:
        return "class"
    if type_iris & EXPECTED_PROPERTY:
        return "property"
    if type_iris & EXPECTED_CONCEPT:
        return "concept"
    return "instance"


def scan_existing_notes(vault: Path, ctx: Context, root_base: str,
                        warnings: list[str]) -> dict[str, Path]:
    """Map every existing note's subject IRI to its path, minting identity
    exactly as the forward direction does (SPEC §4.5).

    Notes are keyed by IRI, not by name: two notes may legitimately share a
    file name (links to them are emitted path-qualified, SPEC §4.4.1), but two
    notes identifying the same subject would race for one update — the first
    wins and the duplicate is flagged."""
    by_iri: dict[str, Path] = {}
    if not vault.exists():
        return by_iri
    for path in sorted(vault.rglob("*.md")):
        fm = canonical_keywords(parse_frontmatter(path) or {}, ctx)
        minted, base = minted_iri(path, vault, root_base, warnings)
        if "@id" in fm:
            token = str(fm["@id"]).strip()
            iri = token if token.startswith(("http://", "https://")) else base + token
        else:
            iri = minted
        if iri in by_iri:
            warnings.append(f"notes {by_iri[iri]} and {path} both identify <{iri}> "
                            f"— updates go to the former")
            continue
        by_iri[iri] = path
    return by_iri


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ingest RDF into a Vault-LD vault (the reverse of vault_to_rdf.py).")
    ap.add_argument("vault", type=Path, help="vault root directory (created if missing)")
    ap.add_argument("rdf", type=Path, nargs="+", help="RDF file(s) to ingest (.ttl, .nt, ...)")
    ap.add_argument("--context", type=Path, default=None,
                    help="root context document (default: <vault>/context.jsonld; "
                         "synthesized when neither exists)")
    ap.add_argument("--data-ns", default=None,
                    help="explicit vault-root base for instance-layer subjects; replaces "
                         "the root context's @base only — a data folder's own "
                         "context.jsonld still governs its subtree (default: the root "
                         "context's @base; also the @base of a synthesized context)")
    args = ap.parse_args()

    vault: Path = args.vault
    data_ns: str = args.data_ns or "https://example.org/data/"
    warnings: list[str] = []

    # ---- Load the graph(s).
    g = Graph()
    for f in args.rdf:
        if not f.exists():
            print(f"error: RDF file not found: {f}", file=sys.stderr)
            return 1
        g.parse(f)

    # ---- Resolve the context: given, found in the vault, or synthesized.
    root_target = vault / "context.jsonld"
    context_path = args.context or root_target
    if context_path.exists():
        ctx = load_context(context_path, warnings)
        if context_path.resolve() != root_target.resolve() and not root_target.exists():
            # Ingesting into a fresh vault with an external context: copy the
            # root and the local context files it references into the vault.
            doc = json.loads(context_path.read_text(encoding="utf-8"))
            entries = doc.get("@context")
            for ref in (entries if isinstance(entries, list) else []):
                if isinstance(ref, str) and not ref.startswith(("http://", "https://")):
                    src = context_path.parent / ref
                    if src.exists():
                        dst = vault / ref
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            root_editor = ContextEditor(root_target, initial={})
            root_editor.doc, root_editor.dirty = doc, True
        else:
            root_editor = ContextEditor(root_target)
    else:
        core = core_context(data_ns)
        ctx = Context(core)
        root_editor = ContextEditor(root_target, initial=dict(core))
        warnings.append(f"no context found — synthesizing {root_target}")

    # Instances mint against the @base of their governing context (§4.5).
    # --data-ns, when given, replaces only the *vault-root* base at the top of
    # that walk; a data folder's own context.jsonld still governs its subtree.
    root_base = args.data_ns or ctx.base or data_ns

    # ---- Reverse maps: predicate IRI -> (short name, term definition).
    pred_to_term: dict[str, tuple[str, dict]] = {}
    for name, tdef in ctx.terms.items():
        pred_to_term.setdefault(ctx.expand_curie(tdef["@id"]), (name, tdef))

    # Prefixes for CURIE rendering: the context's own win over the graph's.
    graph_prefixes = {p: str(n) for p, n in g.namespaces() if p}
    all_prefixes = {**graph_prefixes, **ctx.prefixes}
    used_prefixes: dict[str, str] = {}

    def curie(iri: str) -> str:
        best = None
        for pfx, ns in all_prefixes.items():
            if iri.startswith(ns) and len(iri) > len(ns) and (best is None or len(ns) > len(best[1])):
                best = (pfx, ns)
        if best:
            local = iri[len(best[1]):]
            if re.fullmatch(r"[A-Za-z_][\w.\-]*", local):
                used_prefixes[best[0]] = best[1]
                return f"{best[0]}:{local}"
        return iri

    # ---- Subjects and their kinds.
    bnode_subjects = {s for s in g.subjects() if isinstance(s, BNode)}
    if bnode_subjects:
        warnings.append(f"{len(bnode_subjects)} blank-node subject(s) skipped — "
                        f"the vault format has no representation for anonymous resources")
    subjects = sorted({s for s in g.subjects() if isinstance(s, URIRef)})
    types_of = {s: {str(o) for o in g.objects(s, RDF.type) if isinstance(o, URIRef)}
                for s in subjects}
    kind_of = {s: classify(types_of[s]) for s in subjects}

    # dcterms:source path hints: the true, context-relative path of a pinned
    # note (SPEC §5.4 step 7). Consumed for file placement, never rendered
    # into frontmatter (§5.5.1) — on the vault side the path IS the location.
    path_hint: dict[str, str] = {}
    for s, o in g.subject_objects(DCTERMS.source):
        if isinstance(s, URIRef) and isinstance(o, Literal) and str(o).endswith(".md"):
            path_hint[str(s)] = str(o)

    # ---- Namespace -> folder. Existing folders first, then the graph's
    # ontology/scheme subjects, then derived names for orphan namespaces.
    ns_to_folder: dict[str, tuple[str, str]] = {}
    for kind_dir in ("Ontologies", "Vocabularies"):
        d = vault / kind_dir
        if d.exists():
            for sub in sorted(p for p in d.iterdir() if p.is_dir()):
                base = context_base(sub / "context.jsonld", warnings)
                if base:
                    ns_to_folder.setdefault(base, (kind_dir, sub.name))

    def register(subj: URIRef, kind_dir: str) -> None:
        ns, local = split_iri(str(subj))
        name = sanitize_stem(local) if local else derive_folder_name(ns)
        # a hash- or slash-ontology IRI also governs <iri># and <iri>/ members
        for candidate in (ns, str(subj) + "#", str(subj) + "/"):
            ns_to_folder.setdefault(candidate, (kind_dir, name))

    for s in subjects:
        if kind_of[s] == "ontology":
            register(s, "Ontologies")
    for s in subjects:
        if kind_of[s] == "scheme":
            register(s, "Vocabularies")

    def folder_for(s: URIRef) -> tuple[str, str]:
        ns, _ = split_iri(str(s))
        if ns in ns_to_folder:
            return ns_to_folder[ns]
        if kind_of[s] == "concept":
            scheme = g.value(s, SKOS_IN_SCHEME)
            if isinstance(scheme, URIRef):
                _, sl = split_iri(str(scheme))
                folder = ("Vocabularies", sanitize_stem(sl) if sl else derive_folder_name(ns))
            else:
                folder = ("Vocabularies", derive_folder_name(ns))
        else:
            folder = ("Ontologies", derive_folder_name(ns))
        warnings.append(f"namespace {ns} has no ontology/scheme subject — "
                        f"grouping under {folder[0]}/{folder[1]}/")
        ns_to_folder[ns] = folder
        return folder

    # ---- Existing notes: subject IRI -> path. Structure preservation and
    # wiki-link resolution both key off this.
    existing_by_iri = scan_existing_notes(vault, ctx, root_base, warnings)
    existing_path_iri = {p: i for i, p in existing_by_iri.items()}

    def context_folder_for(iri: str) -> Path:
        """The folder of the context whose @base most specifically prefixes an
        IRI — where a dcterms:source path hint is resolved from (§5.5.1)."""
        best_len, best = (len(root_base), vault) if iri.startswith(root_base) else (-1, vault)
        for b, (kd, name) in ns_to_folder.items():
            if iri.startswith(b) and len(b) > best_len:
                best_len, best = len(b), vault / kd / name
        return best

    # ---- Assign each subject a path (existing note wins) and a stem.
    # Two subjects may share a note *name* (links to them go path-qualified,
    # SPEC §4.4.1) but never one *file*: a canonical path already claimed by a
    # different subject gets a suffixed name, pinned by an explicit @id.
    note_path: dict[str, Path] = {}
    note_stem: dict[str, str] = {}
    folder_members: dict[tuple[str, str], list[str]] = {}
    claimed: dict[Path, str] = {}

    def taken_by_other(path: Path, iri: str) -> bool:
        if path in claimed:
            return claimed[path] != iri
        if path.exists():
            return existing_path_iri.get(path, iri) != iri
        return False

    def free_path(path: Path, iri: str) -> Path:
        base, i = path, 2
        while taken_by_other(path, iri):
            path = base.with_name(f"{base.stem}-{i}{base.suffix}")
            i += 1
        if path != base:
            warnings.append(f"file collision: {base.relative_to(vault)} already "
                            f"belongs to another subject — {iri} stored as "
                            f"'{path.stem}' with an explicit @id")
        return path

    RDFS_SUBCLASS = URIRef(RDFS + "subClassOf")
    SKOS_BROADER = URIRef(SKOS + "broader")
    SKOS_TOPCONCEPT = URIRef(SKOS + "topConceptOf")

    def parent_chain(s: URIRef, rel_pred: URIRef, ns: str) -> list[str]:
        """Stems of the single-local-parent chain above a subject, topmost
        first — the hierarchy-canonical nesting of SPEC §5.2. The chain
        follows exactly one parent per step, and only parents minted in the
        same namespace that this ingest is materialising."""
        segs: list[str] = []
        seen = {s}
        cur = s
        while True:
            parents = [o for o in g.objects(cur, rel_pred)
                       if isinstance(o, URIRef) and o in types_of
                       and split_iri(str(o))[0] == ns]
            if len(parents) != 1 or parents[0] in seen:
                break
            cur = parents[0]
            seen.add(cur)
            segs.append(sanitize_stem(split_iri(str(cur))[1]))
        return list(reversed(segs))

    for s in subjects:
        iri = str(s)
        kind = kind_of[s]
        ns, local = split_iri(iri)
        stem = sanitize_stem(local) if local else derive_folder_name(ns)

        if iri in existing_by_iri:
            path = existing_by_iri[iri]
            folder = None
        elif iri in path_hint:
            # a pinned note's true path, relative to its governing context
            path = free_path(context_folder_for(iri) / path_hint[iri], iri)
            folder = None
        elif kind == "instance" and iri.startswith(root_base):
            # an unpinned instance IRI encodes its vault-relative path (§4.5)
            parts = [sanitize_stem(p) for p in iri[len(root_base):].split("/") if p]
            stem = parts[-1] if parts else stem
            target = vault.joinpath(*parts[:-1], f"{stem}.md") if parts else vault / f"{stem}.md"
            path = free_path(target, iri)
            folder = None
        elif kind == "instance":
            type_stems = sorted(
                split_iri(t)[1] for t in types_of[s] if split_iri(t)[1])
            folder_name = pluralize(sanitize_stem(type_stems[0])) if type_stems else "Resources"
            path = free_path(vault / folder_name / f"{stem}.md", iri)
            folder = None
        else:
            kind_dir, name = folder_for(s)
            if kind in ("ontology", "scheme"):
                path = vault / kind_dir / name / f"{name}.md"
            elif kind == "class":
                # hierarchy-canonical nesting (§5.2): under the single-local-
                # parent chain, flat when there is none or several
                chain = parent_chain(s, RDFS_SUBCLASS, ns)
                path = vault.joinpath(kind_dir, name, "Classes", *chain, f"{stem}.md")
            elif kind == "property":
                path = vault / kind_dir / name / "Properties" / f"{stem}.md"
            elif kind == "concept":
                # a top concept sits at the vocabulary's top level (§5.2)
                chain = ([] if (s, SKOS_TOPCONCEPT, None) in g
                         else parent_chain(s, SKOS_BROADER, ns))
                path = vault.joinpath(kind_dir, name, *chain, f"{stem}.md")
            else:
                path = vault / kind_dir / name / f"{stem}.md"
            path = free_path(path, iri)
            folder = (kind_dir, name)

        claimed[path] = iri
        if kind != "instance" and folder is not None:
            folder_members.setdefault(folder, []).append(ns)
        note_path[iri] = path
        note_stem[iri] = path.stem
        if not types_of[s]:
            warnings.append(f"{path.name}: subject {iri} has no rdf:type — "
                            f"the note will be skipped by a forward export")

    # Wiki-link resolution: every note in the vault after this run.
    note_by_iri = {iri: p.stem for iri, p in existing_by_iri.items()}
    note_by_iri.update(note_stem)
    path_by_iri = dict(existing_by_iri)
    path_by_iri.update(note_path)

    # Generation half of the SPEC §4.4.1 contract: when several notes share a
    # name, a bare [[name]] is ambiguous, so emit the path-qualified form the
    # forward direction resolves by.
    stem_iris: dict[str, set[str]] = {}
    for iri_, stem_ in note_by_iri.items():
        stem_iris.setdefault(stem_, set()).add(iri_)

    def link_for(iri: str) -> str | None:
        stem = note_by_iri.get(iri)
        if stem is None:
            return None
        if len(stem_iris[stem]) > 1 and iri in path_by_iri:
            rel = path_by_iri[iri].relative_to(vault).with_suffix("").as_posix()
            warnings.append(f"note name '{stem}' is ambiguous — linking to it "
                            f"path-qualified as [[{rel}]] (SPEC §4.4.1)")
            return f"[[{rel}]]"
        return f"[[{stem}]]"

    # ---- Ensure each schema folder has a context.jsonld declaring its @base,
    # and that the root context composes it (SPEC §4.2). New folder contexts
    # are flushed immediately: subject minting below reads @base from disk.
    folder_editors: dict[str, ContextEditor] = {}   # namespace -> editor
    written_contexts: list[Path] = []
    for (kind_dir, name), namespaces in sorted(folder_members.items()):
        cpath = vault / kind_dir / name / "context.jsonld"
        base = Counter(namespaces).most_common(1)[0][0]
        if cpath.exists():
            editor = ContextEditor(cpath)
            declared = context_base(cpath, warnings)
        else:
            prefix = next((p for p, n in graph_prefixes.items() if n == base), None)
            editor = ContextEditor(cpath, initial={"@base": base, prefix or name.lower(): base})
            root_editor.add_reference(f"{kind_dir}/{name}/context.jsonld")
            declared = base
            if editor.save():
                written_contexts.append(editor.path)
        folder_editors[declared or base] = editor
        folder_editors.setdefault(base, editor)

    def editor_for_ns(ns: str) -> ContextEditor:
        """The context document a coined term belongs in: the ontology's own
        context when the predicate lives in that namespace, else the root."""
        if ns in folder_editors:
            return folder_editors[ns]
        if ns in ns_to_folder:
            kind_dir, name = ns_to_folder[ns]
            cpath = vault / kind_dir / name / "context.jsonld"
            if cpath.exists():
                folder_editors[ns] = ContextEditor(cpath)
                return folder_editors[ns]
        return root_editor

    # ---- Coin short names for predicates the context does not map (§5.5.3).
    def term_for(pred: URIRef, objs: list) -> tuple[str, dict]:
        iri = str(pred)
        if iri in pred_to_term:
            return pred_to_term[iri]
        ns, local = split_iri(iri)
        name = local or "property"
        base_name, i = name, 2
        while name in ctx.terms:
            name, i = f"{base_name}{i}", i + 1
        tdef: dict = {"@id": curie(iri)}
        if objs and all(isinstance(o, URIRef) for o in objs):
            tdef["@type"] = "@id"
        else:
            dts = {str(o.datatype) for o in objs
                   if isinstance(o, Literal) and o.datatype}
            if len(dts) == 1 and (dt := dts.pop()) not in NATIVE_SAFE and dt != XSD + "string":
                tdef["@type"] = curie(dt)
        target = editor_for_ns(ns)
        target.add_term(name, tdef)
        ctx.terms[name] = tdef
        pred_to_term[iri] = (name, tdef)
        warnings.append(f"predicate {curie(iri)} not in context — "
                        f"coined term '{name}' and added it to {target.path}")
        return name, tdef

    # ---- Value rendering (§5.5.2–3).
    def render_value(obj, coercion) -> object | None:
        if isinstance(obj, BNode):
            warnings.append("blank-node object skipped — not expressible as a wiki link")
            return None
        if isinstance(obj, URIRef):
            iri = str(obj)
            if coercion != "@id":
                warnings.append(f"IRI object {curie(iri)} through a term without @id "
                                f"coercion — will export as a string literal")
            return link_for(iri) or curie(iri)
        lit: Literal = obj
        if lit.language:
            warnings.append(f"language tag @{lit.language} on '{lit}' dropped — "
                            f"not expressible in frontmatter")
            return str(lit)
        dt = str(lit.datatype) if lit.datatype else None
        if coercion == "@id":
            warnings.append(f"literal '{lit}' through @id-coerced term — will export as an IRI")
            return str(lit)
        if coercion is not None:
            cd = ctx.expand_curie(coercion)
            if dt is not None and cd != dt:
                warnings.append(f"literal '{lit}' typed {curie(dt)} but term coerces to "
                                f"{coercion} — retyped on export")
            return native(lit)
        if dt is None or dt == XSD + "string":
            return str(lit)
        if dt in NATIVE_SAFE:
            return native(lit)
        warnings.append(f"typed literal '{lit}' ({curie(dt)}) on an uncoerced term — "
                        f"datatype lost on export")
        return str(lit)

    def native(lit: Literal):
        v = lit.toPython()
        if isinstance(v, bool) or type(v) is int or type(v) is float:
            return v
        if isinstance(v, (date, datetime)):
            return Raw(str(lit))
        return str(lit)

    # ---- Build and write one note per subject.
    canon = {k: i for i, k in enumerate(["@id", "@type", *ctx.terms])}
    created = updated = unchanged = 0

    # Notes are compared and merged in the canonical "@type"/"@id" spelling,
    # but written under the context-declared aliases when there are any
    # (SPEC §4.3) — type:/id: keys need no YAML quoting.
    alias_of = {kw: alias for alias, kw in ctx.aliases.items()}

    def spelled(fm: dict) -> dict:
        return {alias_of.get(k, k): v for k, v in fm.items()}

    for s in subjects:
        iri = str(s)
        path, stem = note_path[iri], note_stem[iri]

        # read the existing note first: its body, extra keys and @id survive
        old_text = path.read_text(encoding="utf-8") if path.exists() else ""
        old_fm = parse_frontmatter(path) if path.exists() else None
        if old_fm is None and old_text:
            body = old_text if old_text.startswith("\n") else "\n" + old_text
        elif old_text:
            body = old_text.split("---", 2)[2]
        else:
            body = "\n"
        old_fm = canonical_keywords(old_fm or {}, ctx)

        # explicit id whenever location minting (SPEC §4.5, as the forward
        # direction performs it — percent-encoded) would not reproduce the
        # subject's IRI. The pin is the base-relative remainder, so export
        # flattens it back to the same IRI.
        minted, base = minted_iri(path, vault, root_base, warnings)

        new_fm: dict = {}
        if minted != iri:
            if base and iri.startswith(base):
                new_fm["@id"] = iri[len(base):]
            else:
                new_fm["@id"] = iri
                warnings.append(f"{path.name}: {iri} lies outside its governing @base "
                                f"{base or '(none)'} — pinned with an absolute id "
                                f"(non-conforming, SPEC §4.5)")
        elif "@id" in old_fm:
            token = str(old_fm["@id"]).strip()
            resolved = token if token.startswith(("http://", "https://")) else base + token
            if resolved == iri:
                new_fm["@id"] = old_fm["@id"]  # a valid explicit pin — keep it

        type_vals = sorted(link_for(t) or curie(t) for t in types_of[s])
        if type_vals:
            new_fm["@type"] = type_vals[0] if len(type_vals) == 1 else type_vals

        preds = sorted(set(g.predicates(s)) - {RDF.type}, key=str)
        rendered: list[tuple[str, dict, object]] = []
        for p in preds:
            objs = sorted(g.objects(s, p), key=str)
            if p == DCTERMS.source and iri in path_hint:
                # the consumed path hint dissolves into the file's location
                objs = [o for o in objs if str(o) != path_hint[iri]]
                if not objs:
                    continue
            name, tdef = term_for(p, objs)
            vals = [v for o in objs if (v := render_value(o, tdef.get("@type"))) is not None]
            if not vals:
                continue
            as_list = len(vals) > 1 or tdef.get("@container") == "@set"
            rendered.append((name, tdef, sorted(vals, key=str) if as_list else vals[0]))
        for name, _, val in sorted(rendered, key=lambda r: canon.get(r[0], len(canon))):
            new_fm[name] = val

        # merge with the existing note: preserve body, non-context keys, order
        final: dict = {}
        for k, v in old_fm.items():
            if k in new_fm:
                final[k] = v if norm(v) == norm(new_fm[k]) else new_fm[k]
            elif not k.startswith("@") and k not in ctx.terms:
                final[k] = v  # a Markdown-face key (tags, aliases, ...) — keep
        for k, v in new_fm.items():
            final.setdefault(k, v)

        if path.exists() and final == old_fm:
            unchanged += 1
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(emit_frontmatter(spelled(final)) + body, encoding="utf-8")
        created, updated = created + (not old_text), updated + bool(old_text)

    # ---- Any prefix used in a note must resolve through the context.
    for pfx, ns in sorted(used_prefixes.items()):
        if pfx not in ctx.prefixes:
            root_editor.add_prefix(pfx, ns)

    for editor in dict.fromkeys([root_editor, *folder_editors.values()]):
        if editor.save() and editor.path not in written_contexts:
            written_contexts.append(editor.path)

    print(f"ingested {len(subjects)} subjects ({len(g)} triples) into {vault}")
    print(f"notes: {created} created, {updated} updated, {unchanged} unchanged")
    for c in dict.fromkeys(written_contexts):
        print(f"context written: {c}")
    if warnings:
        print("\nwarnings:", file=sys.stderr)
        for w in dict.fromkeys(warnings):
            print(f"  - {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
