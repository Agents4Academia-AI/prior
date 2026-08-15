#!/usr/bin/env python3
"""Rerun legacy contribution pairs that missed parent-paper citation evidence.

The frozen enriched run attached citations only when a legacy contribution pair
overlapped a citation-alignment candidate.  This correction keeps the 989 legacy
contribution pairs fixed and attaches citation evidence whenever either parent
paper cites the other.  Only pairs whose prior prediction had no citation fact
are emitted, so the existing full-text-only and already-enriched calls are reused.
"""
from __future__ import annotations

import json
from pathlib import Path

from prepare_cartographer_rebuild import pair_key, paper_id

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "prior-core-v0.2"
OUT = Path(__file__).parent / "out"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    legacy_obj = load_json(BUNDLE / "contributions_core_consensus.json")
    legacy = legacy_obj["edges"] if isinstance(legacy_obj, dict) else legacy_obj
    citation_obj = load_json(OUT / "citations_bbl.json")
    citations = citation_obj["edges"] if isinstance(citation_obj, dict) else citation_obj
    contexts = {
        (row["citing_id"], row["cited_id"]): row.get("contexts", [])
        for row in load_json(OUT / "citation_map.json")
    }
    previous = {
        row["candidate_id"]: row
        for line in (OUT / "cartographer_rebuild_predictions.jsonl").read_text().splitlines()
        if line.strip() for row in [json.loads(line)]
    }
    citation_set = {tuple(row) for row in citations}

    candidates = []
    for edge in legacy:
        a, b = edge["src"], edge["dst"]
        pa, pb = paper_id(a), paper_id(b)
        if pa == pb:
            continue
        key = pair_key(a, b)
        directions = [(x, y) for x, y in ((pa, pb), (pb, pa))
                      if (x, y) in citation_set]
        if not directions or previous[key].get("citation_directions"):
            continue
        candidates.append({
            "candidate_id": key,
            "a": min(a, b),
            "b": max(a, b),
            "channels": ["semantic", "citation"],
            "legacy_edges": [{k: edge.get(k) for k in
                              ("src", "dst", "relation", "confidence",
                               "evidence", "similarity", "trust")}],
            "citations": [{
                "citing_id": citing,
                "cited_id": cited,
                "localized": bool(contexts.get((citing, cited))),
                "alignment_rank": None,
                "alignment_score": None,
            } for citing, cited in directions],
        })

    candidates.sort(key=lambda row: row["candidate_id"])
    output = OUT / "legacy_missing_citation_context_candidates.json"
    output.write_text(json.dumps({
        "schema_version": 1,
        "method": {
            "candidate_policy": "frozen legacy contribution pairs only",
            "citation_policy": "attach parent-paper citation evidence without contribution alignment",
            "reuse_policy": "rerun only prior predictions with no attached citation direction",
        },
        "counts": {"candidates": len(candidates)},
        "candidates": candidates,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": len(candidates), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
