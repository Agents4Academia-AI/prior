#!/usr/bin/env python3
"""Blinded human annotation queue: stratified edge sample across arms, shuffled,
arm hidden. Labels go in the `human_verdict` column (correct / wrong_type /
no_relation); the key file maps rows back to arms for scoring.

Usage: python3 experiments/edge_quality/make_human_queue.py --bundle ../prior-core-v0.2 [--per-arm 15]
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

OUT = Path(__file__).parent / "out"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--per-arm", type=int, default=15)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    obj = json.load(open(Path(args.bundle) / "contributions_core_grounded.json"))
    contribs = obj["contributions"] if isinstance(obj, dict) else obj
    by_id = {c["id"]: c for c in contribs}
    obj = json.load(open(Path(args.bundle) / "contributions_core_consensus.json"))
    arm_edges = {"A": [{"src": e["src"], "dst": e["dst"], "relation": e["relation"]}
                       for e in (obj["edges"] if isinstance(obj, dict) else obj)]}
    for arm in ("B", "C"):
        f = OUT / f"arm{arm}_edges.json"
        if f.exists():
            arm_edges[arm] = json.load(open(f))["edges"]

    rows, key = [], []
    for arm, edges in arm_edges.items():
        edges = [e for e in edges if e["src"] in by_id and e["dst"] in by_id
                 and by_id[e["src"]]["paper_id"] != by_id[e["dst"]]["paper_id"]]
        for e in rng.sample(edges, min(args.per_arm, len(edges))):
            rows.append(e | {"arm": arm})
    rng.shuffle(rows)
    with open(OUT / "human_queue.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["row", "contribution_A", "quote_A", "asserted_relation",
                    "contribution_B", "quote_B", "human_verdict", "notes"])
        for i, e in enumerate(rows):
            ca, cb = by_id[e["src"]], by_id[e["dst"]]
            w.writerow([i, ca["statement"], (ca.get("quote_verbatim") or ca.get("quote") or "")[:300],
                        e["relation"], cb["statement"],
                        (cb.get("quote_verbatim") or cb.get("quote") or "")[:300], "", ""])
            key.append({"row": i, "arm": e["arm"], "src": e["src"], "dst": e["dst"],
                        "relation": e["relation"]})
    (OUT / "human_queue_key.json").write_text(json.dumps(key, indent=1))
    print(f"human queue: {len(rows)} blinded rows -> {OUT/'human_queue.csv'} (+ key)", flush=True)


if __name__ == "__main__":
    main()
