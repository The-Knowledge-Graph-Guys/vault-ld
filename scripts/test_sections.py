#!/usr/bin/env python3
"""
test_sections.py — Behaviour of section references (SPEC §4.4.2).

A literal-valued term whose frontmatter value is a same-note fragment link
([[#Heading]], [[#A#B]], [[#^block-id]]) takes its value from that location
in the note's body. These tests pin how a location is addressed, what value
it yields, and how the ingester writes a value back without disturbing the
rest of the body. The security side (size cap, fence escape, hostile term
names) lives in test_security.py with the other guarantees.

Usage:
    make test
    python -m unittest discover -s scripts -p "test_*.py"
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from rdf_to_vault import place_section  # noqa: E402
from vault_to_rdf import section_fragment, section_value  # noqa: E402

BODY = """
# Report
Intro paragraph, not part of any referenced section.

## Query
```sql
SELECT region, SUM(amount)
FROM invoices

GROUP BY region;
```

## Notes
Intro to the notes.

### Caveats
Figures are *unaudited*.

- one
- two

## Setup ##
```bash
# a shell comment, not a heading
make all
```
^setup

Watch out for **this**. ^warn

## Notes
A second heading with the same text.
"""


class TestSectionFragment(unittest.TestCase):
    def test_same_note_links(self):
        self.assertEqual(section_fragment("[[#Query]]"), "Query")
        self.assertEqual(section_fragment(" [[#Notes#Caveats]] "), "Notes#Caveats")
        self.assertEqual(section_fragment("[[#^setup]]"), "^setup")
        self.assertEqual(section_fragment("[[#Query|the query]]"), "Query")

    def test_not_section_links(self):
        for v in ("[[Report#Query]]", "[[Query]]", "#Query", "see [[#Query]]", 25, None):
            self.assertIsNone(section_fragment(v), v)


class TestSectionValue(unittest.TestCase):
    def test_single_code_block_yields_the_code(self):
        self.assertEqual(section_value(BODY, "Query"),
                         "SELECT region, SUM(amount)\nFROM invoices\n\nGROUP BY region;")

    def test_prose_yields_markdown_verbatim(self):
        self.assertEqual(section_value(BODY, "Notes#Caveats"),
                         "Figures are *unaudited*.\n\n- one\n- two")

    def test_section_runs_to_next_heading_of_same_or_higher_level(self):
        v = section_value(BODY, "Notes")
        self.assertTrue(v.startswith("Intro to the notes."))
        self.assertIn("### Caveats", v)        # deeper headings stay inside
        self.assertNotIn("Setup", v)            # a sibling heading ends it

    def test_first_matching_heading_wins(self):
        self.assertNotIn("second heading", section_value(BODY, "Notes"))

    def test_closing_hashes_are_not_heading_text(self):
        self.assertIsNotNone(section_value(BODY, "Setup"))

    def test_hash_lines_inside_fences_are_not_headings(self):
        self.assertIsNone(section_value(BODY, "a shell comment, not a heading"))

    def test_block_id_after_a_code_block(self):
        self.assertEqual(section_value(BODY, "^setup"),
                         "# a shell comment, not a heading\nmake all")

    def test_inline_block_id_is_stripped(self):
        self.assertEqual(section_value(BODY, "^warn"), "Watch out for **this**.")

    def test_unresolvable_fragments(self):
        for frag in ("Nope", "Notes#Nope", "^nope", "^bad id"):
            self.assertIsNone(section_value(BODY, frag), frag)

    def test_tilde_fence_and_longer_fence(self):
        body = "## A\n~~~~\n```\nnested\n```\n~~~~\n"
        self.assertEqual(section_value(body, "A"), "```\nnested\n```")

    def test_two_code_blocks_are_markdown_not_code(self):
        body = "## A\n```\none\n```\n\n```\ntwo\n```\n"
        self.assertEqual(section_value(body, "A"), "```\none\n```\n\n```\ntwo\n```")


class TestPlaceSection(unittest.TestCase):
    def test_new_section_is_appended_fenced(self):
        body, frag = place_section("\nSome prose.\n", "query", "SELECT 1\nFROM t", None)
        self.assertEqual(frag, "query")
        self.assertEqual(body, "\nSome prose.\n\n## query\n\n```\nSELECT 1\nFROM t\n```\n")
        self.assertEqual(section_value(body, frag), "SELECT 1\nFROM t")

    def test_fence_outgrows_backticks_in_the_value(self):
        value = "a\n```\nb\n````"
        body, frag = place_section("\n", "code", value, None)
        self.assertIn("\n`````\n", body)
        self.assertEqual(section_value(body, frag), value)

    def test_heading_name_collision_gets_a_new_name(self):
        body, frag = place_section("\n## query\nhand-written\n", "query", "x\ny", None)
        self.assertEqual(frag, "query 2")
        self.assertEqual(section_value(body, "query"), "hand-written")

    def test_unchanged_value_leaves_body_byte_identical(self):
        value = section_value(BODY, "Query")
        self.assertEqual(place_section(BODY, "query", value, "Query"), (BODY, "Query"))

    def test_changed_value_rewrites_only_its_section(self):
        new = "SELECT region, SUM(net)\nFROM invoices"
        body, frag = place_section(BODY, "query", new, "Query")
        self.assertEqual(frag, "Query")
        self.assertEqual(section_value(body, "Query"), new)
        self.assertIn("```sql\nSELECT region, SUM(net)", body)   # info string kept
        before, after = BODY.split("## Query"), body.split("## Query")
        self.assertEqual(before[0], after[0])                     # above: untouched
        self.assertEqual(before[1][before[1].index("## Notes"):],
                         after[1][after[1].index("## Notes"):])   # below: untouched

    def test_prose_section_stays_prose(self):
        body, _ = place_section(BODY, "caveats", "Now *audited*.\n\n- one", "Notes#Caveats")
        self.assertIn("### Caveats\nNow *audited*.\n\n- one\n", body)
        self.assertEqual(section_value(body, "Notes#Caveats"), "Now *audited*.\n\n- one")


if __name__ == "__main__":
    unittest.main()
