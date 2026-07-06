#!/usr/bin/env python3
"""The B-vs-C diff: what does citation+context awareness CHANGE?

On citation-informed pairs (the only ones where C's prompt differs), cross-tab
B's verdict against C's: relatedness flips, type flips (e.g. contrast ->
contradicts), and — joined with judgements.jsonl where available — who was
right when they disagreed. Also lists C-only edges (citation-proposed pairs B
never saw). Writes out/arm_diff.json and prints a readable summary.

Usage: python3 experiments/edge_quality/diff_arms.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

OUT = Path(__file__).parent / "out"


def load(f):
    d = {}
    for line in open(OUT / f):
        if line.strip():
            r = json.loads(line)
            d[r["pair"]] = r
    return d


def verdict(r):
    return r.get("relation") if r.get("related") else "none"


def main() -> None:
    B, C = load("armB_verdicts.jsonl"), load("armC_verdicts.jsonl")
    cited = {k: r for k, r in C.items() if r.get("cited") and not r.get("reused_from_B")}
    both = [k for k in cited if k in B]
    xtab = Counter((verdict(B[k]), verdict(C[k])) for k in both)
    flips = [k for k in both if verdict(B[k]) != verdict(C[k])]

    # judge outcomes on flipped pairs, where judged
    jud = {}
    jf = OUT / "judgements.jsonl"
    if jf.exists():
        for line in open(jf):
            if line.strip():
                r = json.loads(line)
                _, s, d, _ = r["key"].split("|")
                jud.setdefault(f"{min(s,d)}|{max(s,d)}", {})[r["arm"]] = r["verdict"]

    examples = []
    for k in flips[:40]:
        e = {"pair": k, "B": verdict(B[k]), "C": verdict(C[k]),
             "C_reason": cited[k].get("reason") or cited[k].get("s1_reason", "")}
        if k in jud:
            e["judge"] = jud[k]
        examples.append(e)

    c_only = [k for k, r in C.items() if k not in B and verdict(r) != "none"]
    res = {
        "citation_informed_pairs_relabelled": len(cited),
        "compared_with_B": len(both),
        "agree": sum(v for (b, c), v in xtab.items() if b == c),
        "flips": len(flips),
        "crosstab_B_to_C": {f"{b}->{c}": v for (b, c), v in sorted(xtab.items(), key=lambda x: -x[1])},
        "citation_proposed_new_edges": len(c_only),
        "flip_examples": examples,
    }
    (OUT / "arm_diff.json").write_text(json.dumps(res, indent=1))
    print(f"citation-informed pairs re-labelled: {len(cited)} · flips vs B: {len(flips)} "
          f"({100*len(flips)/max(len(both),1):.0f}%) · new citation-proposed edges: {len(c_only)}")
    for t, v in list(res["crosstab_B_to_C"].items())[:8]:
        print(f"  {t}: {v}")
    print(f"-> {OUT/'arm_diff.json'}")


if __name__ == "__main__":
    main()
