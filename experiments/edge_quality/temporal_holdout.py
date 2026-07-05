#!/usr/bin/env python3
"""Temporal structure mini-eval (no LLM; Artiles et al. 2026-inspired).

Question: does the atlas's structure anticipate where new work attaches?
Split the corpus at a date; for every LATE contribution with a directed
builds_on/refines edge into an EARLY contribution, ask how structurally central
that antecedent already was in the EARLY-only subgraph (degree percentile).
If new work attached to early nodes at random, the median percentile would be
~0.50; preferential attachment to the mapped structure pushes it up.

Honest framing: this measures that the graph's early structure concentrates
where the field subsequently builds — necessary (not sufficient) for
"the map anticipates the frontier".

Usage: python3 experiments/edge_quality/temporal_holdout.py --bundle ../prior-core-v0.2 [--split 2025-01-01]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "out"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--split", default="2025-01-01")
    args = ap.parse_args()
    d = Path(args.bundle)

    obj = json.load(open(d / "contributions_core_grounded.json"))
    contribs = obj["contributions"] if isinstance(obj, dict) else obj
    by_id = {c["id"]: c for c in contribs}
    obj = json.load(open(d / "contributions_core_consensus.json"))
    edges = obj["edges"] if isinstance(obj, dict) else obj

    date = {c["id"]: (c.get("date") or "") for c in contribs}
    early = {i for i, dt in date.items() if dt and dt < args.split}
    late = {i for i, dt in date.items() if dt and dt >= args.split}

    # degree of each early contribution within the early-only subgraph
    deg: Counter = Counter()
    for e in edges:
        if e["src"] in early and e["dst"] in early and e["src"] != e["dst"]:
            deg[e["src"]] += 1
            deg[e["dst"]] += 1
    ranked = sorted(early, key=lambda i: deg[i])
    pct = {cid: (r + 0.5) / len(ranked) for r, cid in enumerate(ranked)}

    # late -> early attachment points (directed lineage edges only)
    hits = []
    for e in edges:
        if e.get("relation") not in ("builds_on", "refines"):
            continue
        s, t = e["src"], e["dst"]
        if s in late and t in early:
            hits.append(pct[t])
        elif t in late and s in early:
            hits.append(pct[s])

    hits.sort()
    med = hits[len(hits) // 2] if hits else None
    top_q = sum(1 for h in hits if h >= 0.75) / len(hits) if hits else None
    result = {
        "split": args.split,
        "early_contribs": len(early), "late_contribs": len(late),
        "late_to_early_lineage_edges": len(hits),
        "median_antecedent_degree_percentile": round(med, 3) if med is not None else None,
        "frac_antecedents_in_top_degree_quartile": round(top_q, 3) if top_q is not None else None,
        "chance_levels": {"median_percentile": 0.5, "top_quartile_frac": 0.25},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "temporal_holdout.json").write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1), flush=True)


if __name__ == "__main__":
    main()
