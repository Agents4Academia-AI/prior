#!/usr/bin/env python3
"""Select legacy contribution pairs affected by newly localized v12 citations."""
from __future__ import annotations

import json
from pathlib import Path

from prepare_cartographer_rebuild import pair_key, paper_id

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data/prior-core-v0.2"
OUT = Path(__file__).parent / "out"
SUBSTRATE_OUT = Path("/Users/kk1918_1/projects/Otto/worktrees/prior-citation-substrate/experiments/edge_quality/out")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    legacy_obj = load(BUNDLE / "contributions_core_consensus.json")
    legacy = legacy_obj["edges"] if isinstance(legacy_obj, dict) else legacy_obj
    contexts_obj = load(SUBSTRATE_OUT / "citation_contexts_incoming_v12.json")
    contexts = contexts_obj.get("edges", []) if isinstance(contexts_obj, dict) else contexts_obj
    existing = load(SUBSTRATE_OUT / "citations_intent.json")
    old_edges = {(r["citing_id"], r["cited_id"]) for r in existing["edges"]}
    new_context_edges = {(r["citing_id"], r["cited_id"])
                         for r in contexts if r.get("contexts") and
                         (r["citing_id"], r["cited_id"]) not in old_edges}
    candidates = []
    parent_edges = set()
    for edge in legacy:
        a, b = edge["src"], edge["dst"]
        pa, pb = paper_id(a), paper_id(b)
        directions = [(x, y) for x, y in ((pa, pb), (pb, pa)) if (x, y) in new_context_edges]
        if not directions:
            continue
        parent_edges.update(directions)
        candidates.append({
            "candidate_id": pair_key(a, b), "a": min(a, b), "b": max(a, b),
            "channels": ["semantic", "citation"],
            "legacy_edges": [edge],
            "citations": [{"citing_id": x, "cited_id": y, "localized": True,
                           "alignment_rank": None, "alignment_score": None}
                          for x, y in directions],
        })
    candidates.sort(key=lambda r: r["candidate_id"])
    output = OUT / "legacy_incoming_v12_context_candidates.json"
    output.write_text(json.dumps({
        "schema_version": 1,
        "method": {"candidate_policy": "frozen legacy contribution pairs only",
                   "citation_policy": "newly localized v12 parent-paper citation passages",
                   "intent_policy": "site intent is audit metadata, not an edge-classifier input"},
        "counts": {"new_context_edges": len(new_context_edges),
                   "affected_parent_edges": len(parent_edges),
                   "candidates": len(candidates)},
        "candidates": candidates,
    }, indent=2), encoding="utf-8")
    print(json.dumps({"new_context_edges": len(new_context_edges),
                      "affected_parent_edges": len(parent_edges),
                      "candidates": len(candidates), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
