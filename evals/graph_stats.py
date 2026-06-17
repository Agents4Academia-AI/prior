"""Cartographer eval — atlas graph statistics, no API key required."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prior import config  # noqa: E402
from prior.atlas import Atlas  # noqa: E402


def evaluate() -> dict:
    path = config.ATLAS / "atlas.json"
    if not path.exists():
        sys.exit("No atlas. Run `prior build` first.")
    a = Atlas.load(path)
    rel_counts = Counter(e.relation for e in a.edges)
    sem = {k: v for k, v in rel_counts.items()
           if k in {"supports", "contradicts", "refines", "extends"}}
    n_sem = sum(sem.values())
    g = a.graph()
    isolated = sum(1 for c in a.claims if g.degree(c) <= 1)  # only its stated_in edge
    return {
        "papers": len(a.papers),
        "claims": len(a.claims),
        "citation_edges": rel_counts.get("cites", 0),
        "semantic_relations": n_sem,
        "relation_breakdown": sem,
        "contradiction_rate": round(sem.get("contradicts", 0) / max(1, n_sem), 3),
        "claims_with_no_relation": isolated,
        "linked_claim_rate": round(1 - isolated / max(1, len(a.claims)), 3),
    }


if __name__ == "__main__":
    r = evaluate()
    print("── Cartographer eval ──")
    print(f"papers / claims      : {r['papers']} / {r['claims']}")
    print(f"citation edges       : {r['citation_edges']}")
    print(f"semantic relations   : {r['semantic_relations']}  {r['relation_breakdown']}")
    print(f"contradiction rate   : {r['contradiction_rate']:.1%}")
    print(f"linked-claim rate    : {r['linked_claim_rate']:.1%}  "
          f"({r['claims_with_no_relation']} isolated)")
