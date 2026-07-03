#!/usr/bin/env python3
"""Edge-based clustering of contributions (done properly this time).

Greedy-modularity on the contribution relation graph (any relation = topical
proximity). Report the REAL size distribution (not singleton-inflated), then
characterize the substantive communities: distinctive terms, nearest paper-topic,
example statements, top papers. Plus paper-straddle and the Lu-2024 test case.

Usage: python3 scripts/contrib_edge_clusters.py [ATLAS_DIR] [CONTRIB_FILE]
"""
from __future__ import annotations
import os
import ast, json, sys
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("PRIOR_DATA_DIR", "data") + "/atlas")
CONTRIB = sys.argv[2] if len(sys.argv) > 2 else "contributions_core.json"

STOP = set("the a an of for to in on and or but with without via using use uses is are be as that this "
           "these those by from at into over under can could we our their its it they show shows showed "
           "demonstrate demonstrates propose proposes introduce introduces while which when where what how "
           "also such may not no only one two three first second key new based across between both than "
           "more less significantly toward towards yet although however whether each per".split())
TOPICS = {
    "Systems": ["system", "end-to-end", "autonomous", "pipeline", "agentic", "automation", "execute", "laborator"],
    "Benchmarks/critiques": ["benchmark", "evaluat", "metric", "fail", "reproducib", "assess", "limitation"],
    "Peer review": ["review", "reviewer", "peer", "feedback", "rebuttal", "manuscript"],
    "Hypothesis/ideas": ["hypothes", "idea", "novelty", "discover", "exploration", "knowledge graph"],
}


def toks(s):
    return [w for w in "".join(c if c.isalnum() or c == " " else " " for c in (s or "").lower()).split()
            if len(w) > 2 and w not in STOP]


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
ids = {c["id"] for c in cons}
stmt = {c["id"]: c.get("statement", "") for c in cons}
cpaper = {c["id"]: c["paper_id"] for c in cons}
tf = {cid: Counter(toks(stmt[cid])) for cid in ids}

import networkx as nx
G = nx.Graph(); G.add_nodes_from(ids)
for e in edges:
    if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
        G.add_edge(e["src"], e["dst"])
comps = sorted((len(c) for c in nx.connected_components(G)), reverse=True)
comms = sorted(nx.community.greedy_modularity_communities(G), key=len, reverse=True)
mod = nx.community.modularity(G, comms)
node_comm = {n: ci for ci, cs in enumerate(comms) for n in cs}

sizes = [len(c) for c in comms]
buckets = Counter("1" if s == 1 else "2-4" if s <= 4 else "5-7" if s <= 7 else "8+" for s in sizes)
print(f"contributions {len(ids)} | edges {G.number_of_edges()} | isolated {sizes.count(1)}")
print(f"connected components: {len(comps)} | giant {comps[0]} ({comps[0]/len(ids):.0%})")
print(f"communities {len(comms)} (modularity {mod:.3f}) | size buckets {dict(buckets)} | "
      f"big-community sizes {[s for s in sizes if s >= 8]}\n")

gdf = Counter()
for cid in ids:
    gdf.update(set(tf[cid]))
N = len(ids)


def distinctive(members):
    cdf = Counter()
    for cid in members:
        cdf.update(set(tf[cid]))
    out = [((c_in / len(members)) / (gdf[t] / N), t) for t, c_in in cdf.items() if c_in >= 3]
    return [t for lift, t in sorted(out, reverse=True) if lift > 1.3][:9]


def topic_match(members):
    blob = " ".join(stmt[c].lower() for c in members)
    return max(TOPICS, key=lambda k: sum(blob.count(w) for w in TOPICS[k]))


for ci, cs in enumerate(comms):
    if len(cs) < 8:
        continue
    cs = list(cs)
    papers = Counter(cpaper[c] for c in cs)
    print(f"── cluster {ci}: {len(cs)} contributions, {len(papers)} papers | nearest paper-topic: {topic_match(cs)}")
    print("   terms:", ", ".join(distinctive(cs)))
    print("   top papers:", "; ".join(f"{cite(A.get(p,{}))}×{n}" for p, n in papers.most_common(3)))
    for e in sorted(cs, key=lambda c: -sum(tf[c].values()))[:2]:
        print(f"     • {stmt[e][:96]}")
    print()

by_paper = defaultdict(list)
for c in cons:
    by_paper[c["paper_id"]].append(c["id"])
big = {ci for ci, cs in enumerate(comms) if len(cs) >= 8}
straddle = {p: {node_comm[c] for c in cs if node_comm[c] in big} for p, cs in by_paper.items()}
bridges = {p: t for p, t in straddle.items() if len(t) >= 2}
print(f"papers {len(by_paper)} | bridge papers (span >=2 big edge-clusters): {len(bridges)} ({len(bridges)/len(by_paper):.0%})")

print("\n=== test case: The AI Scientist (Lu 2024) ===")
for p, recs in by_paper.items():
    t = A.get(p, {}).get("title") or ""
    if "AI Scientist" in t and str(A.get(p, {}).get("year")) == "2024" and "v2" not in t:
        for cid in recs:
            cl = node_comm[cid]
            tag = f"cluster {cl}" + ("" if cl in big else " (small/isolated)")
            print(f"  {tag}: {stmt[cid][:80]}")
        break
