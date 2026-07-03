#!/usr/bin/env python3
"""Key-free structural edge auditor — flags likely-spurious cross-paper relations
without any LLM call (so it's free and instant, and runnable on an Opus re-run to
measure how much of the junk is *structural* vs *model*).

Heuristic: a relation is suspect when it BRIDGES TWO TOPIC COMMUNITIES and the two
contributions barely share vocabulary. That's the false-equivalence / equivocation
pattern (e.g. a 'contradicts' linking citation-bias to peer-review-gaming on the
word "reliability"). Within-community edges are a-priori plausible; cross-community
+ low-overlap edges are where hallucinated bridges live.

Usage:  python3 scripts/edge_audit.py [ATLAS_DIR] [CONTRIB_FILE]
        (default: data_hackathon/atlas + contributions_core.json)
"""
from __future__ import annotations
import os

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ATLAS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("PRIOR_DATA_DIR", "data") + "/atlas")
CONTRIB = sys.argv[2] if len(sys.argv) > 2 else "contributions_core.json"
LOW_OVERLAP = 0.08          # Jaccard below this = "barely shares vocabulary"

STOP = set("the a an of for to in on and or but with without via using use uses "
           "is are be as that this these those by from at into over under can could "
           "we our their its it they show shows showed demonstrate propose introduce "
           "method approach system model results result paper papers study analysis "
           "across between both than more less significantly toward towards yet "
           "although however whether based new novel generation generates".split())


def toks(s: str) -> set[str]:
    out = set()
    for w in (s or "").lower().replace("/", " ").split():
        w = "".join(c for c in w if c.isalnum())
        if len(w) > 2 and w not in STOP:
            out.add(w)
    return out


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def cite(p: dict) -> str:
    au = p.get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    last = au[0].split()[-1] if au else (p.get("title") or p.get("id") or "?")[:18]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


def main() -> None:
    C = json.loads((ATLAS_DIR / CONTRIB).read_text())
    A = {p["id"]: p for p in json.loads((ATLAS_DIR / "atlas.json").read_text()).get("papers", [])}
    cons, edges = C["contributions"], C["edges"]
    pid = {c["id"]: c["paper_id"] for c in cons}
    stmt = {c["id"]: c.get("statement", "") for c in cons}
    tok = {c["id"]: toks(c.get("statement", "")) for c in cons}

    # paper-level community detection (greedy modularity; fallback: components)
    padj = defaultdict(set)
    for e in edges:
        a, b = pid.get(e["src"]), pid.get(e["dst"])
        if a and b and a != b:
            padj[a].add(b); padj[b].add(a)
    papers = list({c["paper_id"] for c in cons})
    comm = {}
    try:
        import networkx as nx
        G = nx.Graph()
        G.add_nodes_from(papers)
        for a in padj:
            for b in padj[a]:
                G.add_edge(a, b)
        for i, cset in enumerate(nx.community.greedy_modularity_communities(G)):
            for p in cset:
                comm[p] = i
        method = f"greedy-modularity ({len(set(comm.values()))} communities)"
    except Exception as ex:
        # fallback: connected components
        seen = set()
        i = 0
        for p in papers:
            if p in seen:
                continue
            stack = [p]; seen.add(p)
            while stack:
                u = stack.pop(); comm[u] = i
                for v in padj[u]:
                    if v not in seen:
                        seen.add(v); stack.append(v)
            i += 1
        method = f"components fallback (networkx: {type(ex).__name__})"
    for p in papers:
        comm.setdefault(p, -1)

    # score every cross-paper edge
    rows = []
    cross = within = 0
    for e in edges:
        s, d = e["src"], e["dst"]
        if s not in pid or d not in pid or pid[s] == pid[d]:
            continue
        is_cross = comm[pid[s]] != comm[pid[d]]
        cross += is_cross; within += (not is_cross)
        ov = jaccard(tok[s], tok[d])
        rows.append({"rel": e.get("relation"), "cross": is_cross, "overlap": ov,
                     "src": s, "dst": d, "evidence": e.get("evidence", ""),
                     "csrc": comm[pid[s]], "cdst": comm[pid[d]]})

    suspects = [r for r in rows if r["cross"] and r["overlap"] < LOW_OVERLAP]
    suspects.sort(key=lambda r: (r["overlap"], r["rel"] != "contradicts"))

    n = len(rows)
    print(f"=== STRUCTURAL EDGE AUDIT  ({ATLAS_DIR.name}/{CONTRIB}) ===")
    print(f"community method: {method}")
    print(f"cross-paper edges: {n} | cross-community: {cross} ({cross/n:.0%}) | within: {within}")
    relc = Counter(r["rel"] for r in rows)
    crossc = Counter(r["rel"] for r in rows if r["cross"])
    print("relation | total | cross-community | cross&low-overlap(suspect)")
    for rel in sorted(relc):
        sc = sum(1 for r in suspects if r["rel"] == rel)
        print(f"  {rel:11s} {relc[rel]:5d}   {crossc.get(rel,0):5d}            {sc:5d}")
    print(f"\nSUSPECTS (cross-community AND overlap < {LOW_OVERLAP}): {len(suspects)} "
          f"({len(suspects)/n:.0%} of edges)\n")
    for r in suspects[:15]:
        cs, cd = A.get(pid[r["src"]], {}), A.get(pid[r["dst"]], {})
        print(f"[{r['rel']}] overlap={r['overlap']:.02f}  comm {r['csrc']}→{r['cdst']}")
        print(f"   {cite(cs)} → {cite(cd)}")
        print(f"   FROM: {stmt[r['src']][:95]}")
        print(f"   TO:   {stmt[r['dst']][:95]}")
        print(f"   edge says: {r['evidence'][:120]}\n")

    out = ATLAS_DIR / "edge_suspects.json"
    out.write_text(json.dumps({"n_edges": n, "n_cross": cross, "suspects": suspects}, indent=2))
    print(f"(wrote {out} — {len(suspects)} suspects)")


if __name__ == "__main__":
    main()
