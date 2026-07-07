#!/usr/bin/env python3
"""Vocabulary-collapse experiment — stage 3: analysis (no LLM).

Arms: "memory" (parametric only) and "search" (model instructed to WebSearch
before answering — the default config of research agents today). Analysis is
per-arm, same metrics, so the two are directly comparable against the atlas.

Ideas = matched atlas contribution ids; unmatched non-generic claims are
greedily clustered by token-Jaccard so repeated out-of-atlas ideas count once.

Reports per arm:
  CONCENTRATION — % of calls containing >=1 top-10 idea (Artiles-style),
    top-10 share of mentions, distinct ideas, mean pairwise call Jaccard.
  COVERAGE — % of the 581 atlas contributions ever produced; recall by
    community and by contribution age; generic + out-of-atlas rates.

Usage: python3 analyze_collapse.py --bundle ../../../prior-core-v0.2
"""
from __future__ import annotations

import argparse
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(__file__).parent / "out"
NOW = (2026, 6)

_tok = lambda s: set(re.findall(r"[a-z0-9]+", s.lower())) - {
    "the", "a", "an", "of", "for", "and", "to", "in", "on", "that", "with", "via"}


def jac(a: set, b: set) -> float:
    return len(a & b) / max(len(a | b), 1)


def analyse(rows: list, byid: dict, contribs: list, clusters_path: str,
            dup_threshold: float) -> dict:
    unmatched = [r for r in rows if r["match"] == "none" and not r.get("generic")]
    reps: list = []                      # (cluster_id, token set)
    cluster_of: dict = {}
    for r in unmatched:
        t = _tok(r["claim"])
        for cid, rt in reps:
            if jac(t, rt) >= dup_threshold:
                cluster_of[r["key"]] = cid
                break
        else:
            cid = f"x{len(reps):03d}"
            reps.append((cid, t))
            cluster_of[r["key"]] = cid

    def idea(r):
        if r["match"] != "none":
            return r["match"]
        if r.get("generic"):
            return None
        return cluster_of[r["key"]]

    calls: dict = defaultdict(set)
    freq: Counter = Counter()
    n_generic = 0
    for r in rows:
        i = idea(r)
        parts = r["key"].split("#")
        call = "#".join(parts[:-1])      # arm-qualified call id
        if i is None:
            n_generic += 1
            continue
        calls[call].add(i)
        freq[i] += 1

    top10 = {i for i, _ in freq.most_common(10)}
    calls_with_top10 = sum(1 for s in calls.values() if s & top10)
    mentions = sum(freq.values())
    top10_share = sum(freq[i] for i in top10) / max(mentions, 1)
    pair_j = [jac(a, b) for a, b in itertools.combinations(calls.values(), 2)]
    matched_ids = {i for i in freq if i in byid}

    comm_recall = {}
    cpath = Path(clusters_path)
    if cpath.exists():
        cl = json.loads(cpath.read_text())
        assign = cl["assignment"]
        label = {c["id"]: c["label"] for c in cl["clusters"]}
        tot: Counter = Counter()
        hit: Counter = Counter()
        for cid, comm in assign.items():
            tot[comm] += 1
            if cid in matched_ids:
                hit[comm] += 1
        comm_recall = {label.get(k, str(k)): f"{hit[k]}/{tot[k]}"
                       for k in sorted(tot, key=lambda x: -tot[x])}

    def age_mo(c):
        d = c.get("date")
        if not d or len(str(d)) < 7:
            return None
        y, m = int(str(d)[:4]), int(str(d)[5:7])
        return (NOW[0] - y) * 12 + (NOW[1] - m)

    age_tot: Counter = Counter()
    age_hit: Counter = Counter()
    for c in contribs:
        a = age_mo(c)
        if a is None:
            continue
        b = "<6mo" if a < 6 else ("6-12mo" if a < 12 else "12mo+")
        age_tot[b] += 1
        if c["id"] in matched_ids:
            age_hit[b] += 1

    return {
        "calls": len(calls), "claims": len(rows), "mentions": mentions,
        "generic_claims": n_generic,
        "distinct_ideas": len(freq),
        "concentration": {
            "calls_with_top10_idea": f"{calls_with_top10}/{len(calls)} ({100*calls_with_top10/max(len(calls),1):.0f}%)",
            "top10_share_of_mentions": round(top10_share, 3),
            "mean_pairwise_call_jaccard": round(sum(pair_j) / max(len(pair_j), 1), 3),
            "top10_ideas": [
                {"idea": i, "n": freq[i],
                 "text": (byid[i]["statement"][:110] if i in byid
                          else next(r["claim"][:110] for r in unmatched
                                    if cluster_of[r["key"]] == i))}
                for i in sorted(top10, key=lambda x: -freq[x])],
        },
        "coverage": {
            "atlas_contributions_recalled": f"{len(matched_ids)}/{len(contribs)} ({100*len(matched_ids)/len(contribs):.0f}%)",
            "out_of_atlas_ideas": len(reps),
            "by_community": comm_recall,
            "by_age": {b: f"{age_hit[b]}/{age_tot[b]} ({100*age_hit[b]/max(age_tot[b],1):.0f}%)"
                       for b in ("<6mo", "6-12mo", "12mo+")},
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--clusters", default=str(OUT / "clusters.json"))
    ap.add_argument("--dup-threshold", type=float, default=0.55)
    args = ap.parse_args()

    contribs = json.load(open(Path(args.bundle) / "contributions_core_grounded.json"))
    if isinstance(contribs, dict):
        contribs = contribs.get("contributions", contribs)
    byid = {c["id"]: c for c in contribs}

    rows = [json.loads(l) for l in open(OUT / "matches.jsonl") if l.strip()]
    arms: dict = defaultdict(list)
    for r in rows:
        arms["search" if r["key"].startswith("search#") else "memory"].append(r)

    res = {arm: analyse(sub, byid, contribs, args.clusters, args.dup_threshold)
           for arm, sub in sorted(arms.items()) if sub}
    (OUT / "collapse_summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    print(f"\n-> {OUT/'collapse_summary.json'}")


if __name__ == "__main__":
    main()
