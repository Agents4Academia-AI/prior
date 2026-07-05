#!/usr/bin/env python3
"""Union all citation sources into out/citations_core.json (what Arm C reads).

Sources, in provenance order:
  ingest/API  — out/citations_core.json as written by backfill_citations.py
  fulltext    — out/citations_fulltext.json from scan_fulltext_citations.py

Run after backfill completes (and re-run any time a source improves).
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent / "out"


def main() -> None:
    edges: dict[tuple[str, str], str] = {}
    cov = {}
    for name, tag in (("citations_core.json", "api"), ("citations_fulltext.json", "fulltext")):
        f = OUT / name
        if not f.exists():
            print(f"({name} missing — skipped)")
            continue
        d = json.load(open(f))
        for e in d["edges"]:
            edges.setdefault(tuple(e), tag)
        cov[tag] = d.get("coverage", {})
    merged = {
        "edges": sorted(edges),
        "edge_source": {f"{a}->{b}": t for (a, b), t in edges.items()},
        "coverage": cov | {"merged_edges": len(edges)},
    }
    (OUT / "citations_core.json").write_text(json.dumps(merged, indent=1))
    from collections import Counter
    print(f"merged: {len(edges)} edges {dict(Counter(edges.values()))} -> citations_core.json")


if __name__ == "__main__":
    main()
