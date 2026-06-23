#!/usr/bin/env python3
"""Characterize the paper-level communities (key-free, stdlib + networkx).

For each greedy-modularity community: size, top papers by degree, and the most
*distinctive* unigrams/bigrams (over-represented vs the whole corpus) from the
contribution statements + titles. No LLM, no numpy.

Usage: python3 scripts/cluster_summary.py [ATLAS_DIR] [CONTRIB_FILE]
"""
from __future__ import annotations
import ast, json, re, sys
from collections import Counter, defaultdict
from math import log
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    "/Users/kk1918_1/Desktop/hackathon/prior/data_hackathon/atlas")
CONTRIB = sys.argv[2] if len(sys.argv) > 2 else "contributions_core.json"

STOP = set("the a an of for to in on and or but with without via using use uses is are be "
           "as that this these those by from at into over under can could we our their its it "
           "they show shows showed demonstrate demonstrates propose proposes introduce introduces "
           "method methods approach approaches system systems model models result results paper "
           "papers study studies analysis across between both than more less significantly toward "
           "towards yet although however whether based new novel generation generates generate "
           "ai llm llms large language scientific science research agent agents automated automatic "
           "tasks task data set sets human used while which when where what how also such may "
           "not no only one two three first second key work works enable enables".split())


def toks(s):
    return [w for w in (re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).split()
            if len(w) > 2 and w not in STOP]


def grams(ws):
    return ws + [f"{ws[i]} {ws[i+1]}" for i in range(len(ws) - 1)]


def cite(p):
    au = p.get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    last = au[0].split()[-1] if au else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


C = json.loads((DIR / CONTRIB).read_text())
A = {p["id"]: p for p in json.loads((DIR / "atlas.json").read_text())["papers"]}
cons, edges = C["contributions"], C["edges"]
by_paper = defaultdict(list)
for c in cons:
    by_paper[c["paper_id"]].append(c)

padj = defaultdict(set)
for e in edges:
    a, b = e["src"].split("::")[0], e["dst"].split("::")[0]
    if a in by_paper and b in by_paper and a != b:
        padj[a].add(b); padj[b].add(a)
papers = list(by_paper)

import networkx as nx
G = nx.Graph(); G.add_nodes_from(papers)
for a in padj:
    for b in padj[a]:
        G.add_edge(a, b)
comms = sorted(nx.community.greedy_modularity_communities(G), key=len, reverse=True)
deg = {p: len(padj[p]) for p in papers}

# corpus-wide term doc-frequency for distinctiveness baseline
def paper_terms(p):
    txt = (A.get(p, {}).get("title") or "") + " . " + " . ".join(c.get("statement", "") for c in by_paper[p])
    return set(grams(toks(txt)))


gdf = Counter()
for p in papers:
    gdf.update(paper_terms(p))
NP = len(papers)

print(f"=== {len(comms)} COMMUNITIES — agents for the scientific process (CORE) ===\n")
for i, cset in enumerate(comms):
    cset = list(cset)
    ncon = sum(len(by_paper[p]) for p in cset)
    cdf = Counter()
    for p in cset:
        cdf.update(paper_terms(p))
    # distinctiveness: (df in comm / comm size) / (df overall / corpus size), min support
    scored = []
    for t, c_in in cdf.items():
        if c_in < 3:
            continue
        lift = (c_in / len(cset)) / (gdf[t] / NP)
        if lift > 1.2:
            scored.append((lift, c_in, t))
    scored.sort(reverse=True)
    uni = [t for _, _, t in scored if " " not in t][:12]
    bi = [t for _, _, t in scored if " " in t][:10]
    kinds = Counter(c.get("kind") for p in cset for c in by_paper[p])
    top = sorted(cset, key=lambda p: deg.get(p, 0), reverse=True)[:6]
    print(f"── Community {i}: {len(cset)} papers, {ncon} contributions ──")
    print("  top papers:")
    for p in top:
        print(f"    deg {deg.get(p,0):3d}  {cite(A.get(p,{})):24s} {(A.get(p,{}).get('title') or '')[:64]}")
    print("  distinctive terms:", ", ".join(uni))
    print("  distinctive phrases:", ", ".join(bi))
    print("  kinds:", dict(kinds.most_common(5)))
    print()
