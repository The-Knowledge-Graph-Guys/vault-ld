#!/usr/bin/env python3
"""
test_security.py — Security regression suite for the reference tools.

Every guarantee SECURITY.md makes is pinned here as an executable test, so a
pull request cannot silently weaken one: CI runs this suite (`make test`)
alongside the roundtrip. The tests are the exploits, kept.

Covered guarantees:
  - reads and writes stay inside the vault (vld:path hints, context
    references, symlinked notes, hostile IRI localnames),
  - no network I/O while parsing untrusted RDF or contexts,
  - bounded parsing (frontmatter size cap that binds before the file is in
    memory, YAML alias refusal, context document size cap),
  - no frontmatter injection through coined term names,
  - refusals fail closed with a warning, never a traceback.

Uses only the standard library (unittest): the security suite must not widen
the dependency surface it exists to defend.

Usage:
    make test
    python -m unittest discover -s scripts -p "test_*.py"
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from rdf_to_vault import emit_frontmatter, sanitize_stem  # noqa: E402
from vault_to_rdf import (  # noqa: E402
    MAX_CONTEXT_BYTES,
    MAX_FRONTMATTER_BYTES,
    parse_frontmatter,
    read_json_document,
    safe_relative_ref,
    within_root,
)

VLD_PATH = "https://github.com/The-Knowledge-Graph-Guys/vault-ld#path"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def run_tool(script: str, *args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a reference tool in a fresh process (network disabling and argv
    handling are process-global, so e2e tests never share state)."""
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *map(str, args)],
        cwd=cwd, capture_output=True, text=True, timeout=120,
    )


def files_under(root: Path) -> set[Path]:
    return {p for p in root.rglob("*") if p.is_file()}


class TmpDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)


# ---------------------------------------------------------------------------
# Path containment primitives
# ---------------------------------------------------------------------------

class TestSafeRelativeRef(unittest.TestCase):
    def test_plain_relative_accepted(self):
        self.assertTrue(safe_relative_ref("Ontologies/Culinary/context.jsonld"))
        self.assertTrue(safe_relative_ref("note.md"))

    def test_traversal_and_absolute_refused(self):
        for ref in ("../escape.md", "a/../../b.md", "/etc/passwd",
                    "C:\\Windows\\evil.md", "a\\b.md", "..", "a/\x00b.md",
                    "//server/share/x.md"):
            self.assertFalse(safe_relative_ref(ref), ref)


class TestWithinRoot(TmpDirTest):
    def test_inside_and_outside(self):
        root = self.tmp / "vault"
        root.mkdir()
        self.assertTrue(within_root(root / "a" / "b.md", root))
        self.assertFalse(within_root(root / ".." / "escape.md", root))
        self.assertFalse(within_root(Path("/etc/passwd"), root))

    def test_symlink_resolution(self):
        root = self.tmp / "vault"
        root.mkdir()
        (self.tmp / "outside").mkdir()
        link = root / "link"
        os.symlink(self.tmp / "outside", link, target_is_directory=True)
        self.assertFalse(within_root(link / "x.md", root))


class TestSanitizeStem(unittest.TestCase):
    def test_dot_segments_neutralised(self):
        # '..' is a path step, not a name — it must never survive
        self.assertEqual(sanitize_stem(".."), "unnamed")
        self.assertEqual(sanitize_stem("."), "unnamed")
        self.assertEqual(sanitize_stem(""), "unnamed")

    def test_encoded_traversal_neutralised(self):
        for hostile in ("%2e%2e%2fescape", "..%2F..%2Fetc", "a/../../b"):
            stem = sanitize_stem(hostile)
            self.assertNotIn("/", stem)
            self.assertNotIn("\\", stem)
            self.assertFalse(stem.startswith("."), stem)

    def test_hidden_files_and_control_chars(self):
        self.assertEqual(sanitize_stem(".hidden"), "hidden")
        self.assertNotIn("\n", sanitize_stem("a%0Ab"))
        self.assertNotIn("\x00", sanitize_stem("a%00b"))

    def test_ordinary_names_untouched(self):
        self.assertEqual(sanitize_stem("Red%20Lentil%20Soup"), "Red Lentil Soup")
        self.assertEqual(sanitize_stem("Recipe"), "Recipe")


# ---------------------------------------------------------------------------
# Bounded, non-injectable parsing
# ---------------------------------------------------------------------------

class TestParseFrontmatter(TmpDirTest):
    def note(self, content, binary=False) -> Path:
        p = self.tmp / "note.md"
        if binary:
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
        return p

    def test_normal_note_parses(self):
        fm = parse_frontmatter(self.note("---\ntype: \"[[Recipe]]\"\nname: x\n---\nbody\n"))
        self.assertEqual(fm, {"type": "[[Recipe]]", "name": "x"})

    def test_yaml_alias_refused(self):
        fm = parse_frontmatter(self.note("---\na: &x [1, 2]\nb: *x\n---\n"))
        self.assertIsNone(fm)

    def test_oversized_frontmatter_skipped(self):
        big = "x: " + "a" * (MAX_FRONTMATTER_BYTES + 1024)
        self.assertIsNone(parse_frontmatter(self.note(f"---\n{big}\n---\n")))

    def test_unterminated_giant_frontmatter_skipped(self):
        # no closing '---' within the cap: the bounded read must give up
        # instead of pulling the whole file into memory
        self.assertIsNone(parse_frontmatter(self.note("---\n" + "a" * (2 * MAX_FRONTMATTER_BYTES))))

    def test_undecodable_note_skipped_not_crashed(self):
        self.assertIsNone(parse_frontmatter(self.note(b"\xff\xfe\x00garbage", binary=True)))


class TestReadJsonDocument(TmpDirTest):
    def doc(self, content: str) -> Path:
        p = self.tmp / "context.jsonld"
        p.write_text(content, encoding="utf-8")
        return p

    def test_valid_object(self):
        warnings: list[str] = []
        self.assertEqual(read_json_document(self.doc('{"@context": {}}'), warnings),
                         {"@context": {}})
        self.assertEqual(warnings, [])

    def test_malformed_warns_not_raises(self):
        warnings: list[str] = []
        self.assertIsNone(read_json_document(self.doc("{ not json"), warnings))
        self.assertTrue(warnings)

    def test_non_object_refused(self):
        warnings: list[str] = []
        self.assertIsNone(read_json_document(self.doc("[1, 2]"), warnings))
        self.assertTrue(warnings)

    def test_oversized_refused_before_reading(self):
        warnings: list[str] = []
        p = self.doc('{"pad": "' + "a" * (MAX_CONTEXT_BYTES + 1024) + '"}')
        self.assertIsNone(read_json_document(p, warnings))
        self.assertIn("exceeds", warnings[0])


class TestFrontmatterInjection(unittest.TestCase):
    def test_hostile_key_cannot_inject_lines(self):
        # a coined term name derived from a hostile IRI localname: without
        # quoting, the newline would inject an `id:` line into the note
        hostile = "inject\nid: https://evil.example/hijacked"
        text = emit_frontmatter({hostile: "payload", "label": "ok"})
        block = text.split("---")[1]
        parsed = yaml.safe_load(block)
        self.assertEqual(set(parsed), {hostile, "label"})
        self.assertNotIn("id", parsed)

    def test_colon_space_key_quoted(self):
        text = emit_frontmatter({"id: https://evil": "v"})
        parsed = yaml.safe_load(text.split("---")[1])
        self.assertEqual(list(parsed), ["id: https://evil"])

    def test_ordinary_keys_stay_bare(self):
        text = emit_frontmatter({"label": "x", "subClassOf": ["[[A]]"]})
        self.assertIn("label: x", text)
        self.assertIn("subClassOf:", text)


# ---------------------------------------------------------------------------
# No network I/O
# ---------------------------------------------------------------------------

class TestNetworkDisabled(unittest.TestCase):
    def test_urlopen_refused_after_disable(self):
        # in a subprocess: disable_network patches the process globally
        code = (
            "from vault_to_rdf import disable_network\n"
            "import urllib.request\n"
            "disable_network()\n"
            "try:\n"
            "    urllib.request.urlopen('http://127.0.0.1:9/')\n"
            "except RuntimeError as e:\n"
            "    assert 'network access is disabled' in str(e)\n"
            "else:\n"
            "    raise SystemExit('urlopen was not blocked')\n"
        )
        r = subprocess.run([sys.executable, "-c", code], cwd=SCRIPTS,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unsafe_flag_banners_and_delays(self):
        # the opt-out must announce itself and leave a cancellation window
        # before anything is fetched or written
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rdf = tmp_path / "ok.nt"
            rdf.write_text(
                f'<https://example.org/data/a> <{RDF_TYPE}> <https://example.org/schema/Thing> .\n',
                encoding="utf-8")
            start = time.monotonic()
            r = run_tool("rdf_to_vault.py", tmp_path / "vault", rdf,
                         "--unsafe-allow-network", cwd=tmp_path)
            elapsed = time.monotonic() - start
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("WARNING: --unsafe-allow-network", r.stderr)
            self.assertIn("Ctrl-C to cancel", r.stderr)
            self.assertGreaterEqual(elapsed, 4.5, "cancellation window was skipped")

    @unittest.skipIf(os.name == "nt", "POSIX signal semantics")
    def test_unsafe_flag_ctrl_c_cancels_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            rdf = tmp_path / "ok.nt"
            rdf.write_text(
                f'<https://example.org/data/a> <{RDF_TYPE}> <https://example.org/schema/Thing> .\n',
                encoding="utf-8")
            proc = subprocess.Popen(
                [sys.executable, str(SCRIPTS / "rdf_to_vault.py"),
                 str(tmp_path / "vault"), str(rdf), "--unsafe-allow-network"],
                cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(1.5)  # inside the countdown
            proc.send_signal(signal.SIGINT)
            _, stderr = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 130, stderr)
            self.assertIn("cancelled", stderr)
            # fail closed: nothing may have been ingested before the window closed
            self.assertFalse(list((tmp_path / "vault").rglob("*.md"))
                             if (tmp_path / "vault").exists() else [])

    def test_ingest_refuses_remote_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            evil = tmp_path / "evil.jsonld"
            evil.write_text(json.dumps({
                "@context": "http://127.0.0.1:9/context.jsonld",
                "@id": "https://example.org/data/x",
                "@type": "https://example.org/schema/Thing",
            }), encoding="utf-8")
            r = run_tool("rdf_to_vault.py", tmp_path / "vault", evil, cwd=tmp_path)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)


# ---------------------------------------------------------------------------
# End-to-end containment: hostile inputs against the real tools
# ---------------------------------------------------------------------------

class TestIngestContainment(TmpDirTest):
    def ingest(self, ntriples: str) -> subprocess.CompletedProcess:
        rdf = self.tmp / "hostile.nt"
        rdf.write_text(ntriples, encoding="utf-8")
        before = files_under(self.tmp)
        r = run_tool("rdf_to_vault.py", self.tmp / "vault", rdf, cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        vault = (self.tmp / "vault").resolve()
        for new in files_under(self.tmp) - before:
            self.assertTrue(within_root(new, vault),
                            f"{new} was written outside the vault")
        return r

    def test_vld_path_traversal_refused(self):
        r = self.ingest(
            f'<https://example.org/data/a> <{RDF_TYPE}> <https://example.org/schema/Thing> .\n'
            f'<https://example.org/data/a> <{VLD_PATH}> "../escape.md" .\n'
            f'<https://example.org/data/b> <{RDF_TYPE}> <https://example.org/schema/Thing> .\n'
            f'<https://example.org/data/b> <{VLD_PATH}> "/tmp/abs.md" .\n'
        )
        self.assertIn("hint refused", r.stderr)
        self.assertFalse((self.tmp / "escape.md").exists())
        self.assertFalse(Path("/tmp/abs.md").exists())

    def test_dotdot_localname_contained(self):
        # subject and predicate IRIs whose localnames decode to path steps
        self.ingest(
            f'<https://evil.example/ns/..> <{RDF_TYPE}> <http://www.w3.org/2002/07/owl#Class> .\n'
            f'<https://evil.example/ns/%2e%2e%2fClasses> <{RDF_TYPE}> <http://www.w3.org/2002/07/owl#Class> .\n'
        )

    def test_hostile_predicate_localname_roundtrips_inert(self):
        # the coined key must survive as data, not as injected frontmatter
        self.ingest(
            f'<https://example.org/data/v> <{RDF_TYPE}> <https://example.org/schema/Thing> .\n'
            f'<https://example.org/data/v> <https://evil.example/ns/inject%0Aid> "payload" .\n'
        )
        note = next((self.tmp / "vault").rglob("v.md"))
        fm = parse_frontmatter(note)
        self.assertIsNotNone(fm, "hostile key broke the note's own frontmatter")
        self.assertNotIn("id", fm)
        self.assertNotIn("@id", fm)

    def test_malformed_root_context_fails_closed(self):
        vault = self.tmp / "vault"
        vault.mkdir()
        ctx = vault / "context.jsonld"
        ctx.write_text("{ not json", encoding="utf-8")
        rdf = self.tmp / "ok.nt"
        rdf.write_text(
            f'<https://example.org/data/a> <{RDF_TYPE}> <https://example.org/schema/Thing> .\n',
            encoding="utf-8")
        r = run_tool("rdf_to_vault.py", vault, rdf, cwd=self.tmp)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(ctx.read_text(encoding="utf-8"), "{ not json",
                         "a malformed context must never be overwritten")


class TestExportContainment(TmpDirTest):
    def make_vault(self) -> Path:
        vault = self.tmp / "vault"
        vault.mkdir()
        (vault / "context.jsonld").write_text(json.dumps({
            "@context": {"@base": "https://example.org/data/",
                         "type": "@type", "id": "@id",
                         "label": "http://www.w3.org/2000/01/rdf-schema#label"}
        }), encoding="utf-8")
        (vault / "Note.md").write_text(
            "---\ntype: https://example.org/schema/Thing\nlabel: fine\n---\n",
            encoding="utf-8")
        return vault

    def export(self, vault: Path) -> subprocess.CompletedProcess:
        r = run_tool("vault_to_rdf.py", vault, "--out-dir", self.tmp / "out", cwd=self.tmp)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_symlinked_note_not_exported(self):
        secret = self.tmp / "secret.md"
        secret.write_text(
            "---\ntype: https://example.org/schema/Thing\nlabel: SECRET-CANARY\n---\n",
            encoding="utf-8")
        vault = self.make_vault()
        os.symlink(secret, vault / "leak.md")
        r = self.export(vault)
        self.assertIn("symlink", r.stderr)
        exported = (self.tmp / "out" / "data.ttl").read_text(encoding="utf-8")
        self.assertNotIn("SECRET-CANARY", exported)

    def test_context_reference_escape_refused(self):
        secret = self.tmp / "secret.jsonld"
        secret.write_text(json.dumps({"@context": {"@base": "https://leaked.example/"}}),
                          encoding="utf-8")
        vault = self.make_vault()
        (vault / "context.jsonld").write_text(json.dumps({
            "@context": ["../secret.jsonld",
                         {"@base": "https://example.org/data/", "type": "@type",
                          "label": "http://www.w3.org/2000/01/rdf-schema#label"}]
        }), encoding="utf-8")
        r = self.export(vault)
        self.assertIn("refused", r.stderr)
        exported = (self.tmp / "out" / "data.ttl").read_text(encoding="utf-8")
        self.assertNotIn("leaked.example", exported)

    def test_remote_context_reference_not_fetched(self):
        vault = self.make_vault()
        (vault / "context.jsonld").write_text(json.dumps({
            "@context": ["http://127.0.0.1:9/context.jsonld",
                         {"@base": "https://example.org/data/", "type": "@type",
                          "label": "http://www.w3.org/2000/01/rdf-schema#label"}]
        }), encoding="utf-8")
        r = self.export(vault)
        self.assertIn("remote context not fetched", r.stderr)


if __name__ == "__main__":
    unittest.main()
