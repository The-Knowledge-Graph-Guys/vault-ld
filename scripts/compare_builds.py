#!/usr/bin/env python3
"""
compare_builds.py — Compare two export directories (schema.ttl + data.ttl).

Used by `make compare` to close the roundtrip test loop (SPEC §5.6): the
original export and the export of the rehydrated vault must be
graph-isomorphic. Prints any triples present in only one side.

Usage:
    python compare_builds.py build rehydratedVaultBuild
"""

from __future__ import annotations

import sys
from pathlib import Path

from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic

from vault_to_rdf import disable_network


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    left, right = Path(sys.argv[1]), Path(sys.argv[2])

    # The .ttl files compared are usually this repo's own build outputs, but
    # nothing stops a user pointing the tool at foreign RDF — same trust
    # boundary as ingest, so the same rule: parsing must never reach the network.
    disable_network()

    ok = True
    for name in ("schema.ttl", "data.ttl"):
        g1, g2 = Graph(), Graph()
        g1.parse(left / name)
        g2.parse(right / name)
        if isomorphic(g1, g2):
            print(f"{name}: isomorphic ({len(g1)} triples)")
            continue
        ok = False
        _, in_left, in_right = graph_diff(g1, g2)
        print(f"{name}: NOT isomorphic ({len(g1)} vs {len(g2)} triples)")
        for label, only in ((f"only in {left}", in_left), (f"only in {right}", in_right)):
            for s, p, o in sorted(only):
                print(f"  {label}: {s.n3()} {p.n3()} {o.n3()}")

    print("roundtrip OK" if ok else "roundtrip BROKEN")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
