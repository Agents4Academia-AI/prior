#!/usr/bin/env python3
"""Cluster at the CONTRIBUTION level (not paper level) and measure how many papers
straddle communities — i.e. whether labelling contributions individually is worth it.

Communities via greedy modularity on the contribution graph; each community labelled
by keyword-vote over its member statements; isolated contributions fall into their own
(singleton) community, labelled by their own statement. A 'bridge paper' has
contributions in >= 2 distinct topic labels.

Usage: python3 scripts/contrib_communities.py [ATLAS_DIR] [CONTRIB_FILE]
"""
from __future__ import annotations
import os
import ast, json, sys
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    os.environ.get("PRIOR_DATA_DIR", "data") + "/atlas")
CONTRIB = sys.argv[2] if len(sys.argv) > 2 else "contributions_core.json"

LABELS = [
    ("Systems", ["ai scientist", "end-to-end", "end to end", "researchagent", "evoscientist",
                 "kosmos", "autonomous", "fully automated", "laborator", "automation", "pipeline",
                 "agentic system", "multi-agent", "tree search", "execute"]),
    ("Benchmarks/critiques", ["bench", "benchmark", "evaluat", "failure", "reproducib", "metric",
                              "assess", "reasoning", "rigorous", "limitation", "cannot", "fail"]),
    ("Peer review", ["review", "reviewer", "peer", "feedback", "rebuttal", "openreview", "critic",
                     "rating", "manuscript", "submission"]),
    ("Hypothesis/ideas", ["hypothes", "hypo", "idea", "novelty", "novel idea", "rediscover",
                          "exploration", "generation of", "discover", "knowledge graph"]),
]


def cite(p):
    au = p.get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    last = au[0].split()[-1] if au else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


def topic_of(text):
    text = text.lower()
    best = max((sum(text.count(k) for k in kws), li) for li, (lab, kws) in enumerate(LABELS))
    return best[1] if best[0] > 0 else None


C = json.loads((DIR / CONTRIB).read_text())
A = {p["id"]: p for p in json.loads((DIR / "atlas.json").read_text())["papers"]}
cons = C["contributions"]; edges = C["edges"]
stmt = {c["id"]: c.get("statement", "") for c in cons}
cpaper = {c["id"]: c["paper_id"] for c in cons}
ids = set(cpaper)

import networkx as nx
G = nx.Graph(); G.add_nodes_from(ids)
for e in edges:
    if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
        G.add_edge(e["src"], e["dst"])
iso = [n for n in G if G.degree(n) == 0]
comms = list(nx.community.greedy_modularity_communities(G))

# label each community by keyword-vote over members' statements
comm_topic = {}
for ci, cs in enumerate(comms):
    t = topic_of(" . ".join(stmt[c] for c in cs))
    comm_topic[ci] = t
# topic per contribution: its community's label, else its own statement's keywords
ctopic = {}
for ci, cs in enumerate(comms):
    for c in cs:
        ctopic[c] = comm_topic[ci] if comm_topic[ci] is not None else topic_of(stmt[c])

named = lambda t: LABELS[t][0] if t is not None else "unassigned"

print(f"contributions {len(cons)} | isolated {len(iso)} | modularity-communities {len(comms)}")
print("contribution topic distribution:",
      {named(t): n for t, n in Counter(ctopic.values()).most_common()})

# straddle: distinct topics per paper
by_paper = defaultdict(list)
for c in cons:
    by_paper[c["paper_id"]].append(c["id"])
straddle = {}
for p, cs in by_paper.items():
    topics = {ctopic.get(c) for c in cs if ctopic.get(c) is not None}
    straddle[p] = topics
bridges = {p: t for p, t in straddle.items() if len(t) >= 2}
print(f"\npapers {len(by_paper)} | BRIDGE papers (contributions span >=2 topics): "
      f"{len(bridges)} ({len(bridges)/len(by_paper):.0%})")

print("\ntop bridge papers (most topics spanned):")
for p in sorted(bridges, key=lambda p: -len(bridges[p]))[:10]:
    ts = ", ".join(sorted(named(t) for t in bridges[p]))
    print(f"  {cite(A.get(p,{})):26s} [{ts}]  {(A.get(p,{}).get('title') or '')[:46]}")

# the test case: The AI Scientist (Lu 2024)
print("\n=== test case: The AI Scientist (Lu 2024) ===")
for p, recs in by_paper.items():
    t = (A.get(p, {}).get("title") or "")
    if "AI Scientist" in t and str(A.get(p, {}).get("year")) == "2024" and "v2" not in t:
        for cid in recs:
            print(f"  [{named(ctopic.get(cid))}] {stmt[cid][:88]}")
        break
