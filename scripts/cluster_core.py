#!/usr/bin/env python3
"""Cluster the Prior core graph and emit a canonical assignment — shareable,
standalone, key-free (stdlib + networkx only; no LLM, no API).

This is the *same* clustering the Prior atlas viewer renders, lifted out of the
viewer generator so any interface can reproduce or just consume it. Run it on the
released bundle (`core-graph-v0.2`) and it writes:

  clusters.json  — {_meta, clusters:[{id,label,color,n}], assignment:{contrib_id: comm}}
                   the canonical contribution->cluster map (comm -1 = isolated).
  graph.json     — a turnkey render payload: nodes already carrying comm/year/cite,
                   edges with rel/trust/tier, legend + relation colours. Draw it
                   directly (D3 / React-Flow / anything); no clustering needed.

Why ship the assignment, not just the code: greedy modularity is tie-order
sensitive, so two interfaces that each re-cluster can disagree at the margins.
Cluster once, here; everyone reads the same `clusters.json`.

Method: build an *unweighted, undirected* graph over contributions from the
consensus edges, run networkx greedy modularity, keep communities >= MIN (top 9),
the rest are `-1` (isolated/small). Labels are assigned by a keyword vote of each
cluster's member statements against LABELKW (greedy one-to-one).

Usage:
  python3 cluster_core.py <bundle_dir> [out_dir]
  # bundle_dir holds the core-graph-v0.2 files; defaults to the cwd.
"""
from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

MIN = 8  # min community size to be a labelled cluster
GREY = "#c9cdd2"
REL = {"supports": "#0a9396", "builds_on": "#5b8fb0", "refines": "#ca6702", "contradicts": "#ae2012"}
# label + muted colour + content keywords; clusters labelled by keyword vote (not size)
LABELKW = [
    ("Autonomous systems", "#5b8a72", ["autonomous", "end-to-end", "fully automated", "pipeline", "ai scientist", "discovery system", "self-evolving"]),
    ("Multi-agent orchestration", "#8d6a9f", ["multi-agent", "orchestrat", "centralized", "decentralized", "asynchronous", "agent team", "coordinat", "tool", "apis"]),
    ("Peer review", "#4a6d8c", ["review", "reviewer", "peer", "rebuttal", "rating", "openreviewer", "manuscript", "acceptance"]),
    ("Benchmarks & eval", "#b07a52", ["benchmark", "evaluat", "reproduc", "metric", "icml", "leaderboard", "assess", "trajectory"]),
    ("Hypothesis generation", "#c2a14a", ["hypothes", "rediscover", "chemistry", "conjecture", "scientific discovery"]),
    ("Idea novelty / eval", "#3f7d7b", ["novelty", "ideation", "feasibility", "originality", "novel idea", "idea generation"]),
    ("RAG / literature-QA", "#b56b78", ["retrieval", "rag", "literature", "citation", "paperqa", "query", "corpus"]),
    ("Safety / risk", "#9c6b6b", ["safety", "risk", "calibrat", "harm", "guardrail", "misuse", "reliab", "hallucinat"]),
    ("Domain-science agents", "#9c7b62", ["biolog", "material", "quantum", "clinical", "genom", "crispr", "cell", "molecul"]),
]


def yr(p):
    try:
        return int(str((p or {}).get("year") or "").strip()[:4])
    except (ValueError, TypeError):
        return None


def cite(p):
    au = p.get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    last = au[0].split()[-1] if au else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


def _load_contribs(d: Path):
    for name in ("contributions_core_grounded.json", "contributions_core.json"):
        f = d / name
        if f.exists():
            obj = json.loads(f.read_text())
            return obj["contributions"] if isinstance(obj, dict) else obj
    raise SystemExit("no contributions_core_grounded.json / contributions_core.json in bundle dir")


def _load_edges(d: Path):
    obj = json.loads((d / "contributions_core_consensus.json").read_text())
    return obj["edges"] if isinstance(obj, dict) and "edges" in obj else obj


def _load_papers(d: Path):
    jl = d / "papers_core.jsonl"
    if jl.exists():
        return {p["id"]: p for p in (json.loads(l) for l in jl.read_text().splitlines() if l.strip())}
    at = d / "atlas.json"
    if at.exists():
        return {p["id"]: p for p in json.loads(at.read_text())["papers"]}
    return {}


def main() -> None:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else d
    out.mkdir(parents=True, exist_ok=True)
    cons, edges, papers = _load_contribs(d), _load_edges(d), _load_papers(d)
    ids = {c["id"] for c in cons}

    # 1. graph over contributions (unweighted, undirected) from consensus edges.
    #    sort nodes + edges so the clustering is deterministic, independent of the
    #    order the input files happen to list contributions/edges in.
    G = nx.Graph(); G.add_nodes_from(sorted(ids))
    for e in sorted(edges, key=lambda e: (e["src"], e["dst"])):
        if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
            G.add_edge(e["src"], e["dst"])

    # 2. greedy modularity; keep communities >= MIN (top 9), rest -> -1.
    #    break size ties by smallest member id → canonical cluster INDICES.
    comms = sorted(nx.community.greedy_modularity_communities(G), key=lambda cs: (-len(cs), min(cs)))
    big = [cs for cs in comms if len(cs) >= MIN][:9]
    comm_of = {}
    for ci, cs in enumerate(big):
        for n in cs:
            comm_of[n] = ci
    for n in ids:
        comm_of.setdefault(n, -1)

    # 3. label each cluster by keyword vote over member statements (greedy 1-1)
    st = {c["id"]: (c.get("statement") or "").lower() for c in cons}
    blob = {ci: " ".join(st[n] for n in cs) for ci, cs in enumerate(big)}
    scored = sorted(((sum(blob[ci].count(k) for k in kw), ci, li)
                     for ci in range(len(big)) for li, (lb, co, kw) in enumerate(LABELKW)), reverse=True)
    clabel, used_c, used_l = {}, set(), set()
    for s, ci, li in scored:
        if ci in used_c or li in used_l:
            continue
        clabel[ci] = LABELKW[li]; used_c.add(ci); used_l.add(li)
    for ci in range(len(big)):
        clabel.setdefault(ci, (f"cluster {ci}", GREY, []))

    legend = [{"id": ci, "label": clabel[ci][0], "color": clabel[ci][1],
               "n": sum(1 for n in ids if comm_of[n] == ci)} for ci in range(len(big))]
    legend.append({"id": -1, "label": "unclustered (isolated)", "color": GREY,
                   "n": sum(1 for n in ids if comm_of[n] == -1)})

    # 4. emit clusters.json (canonical assignment)
    try:
        modularity = round(nx.community.modularity(G, comms), 4)
    except Exception:
        modularity = None
    (out / "clusters.json").write_text(json.dumps({
        "_meta": {"algorithm": "networkx greedy_modularity_communities over consensus edges",
                  "min_cluster_size": MIN, "n_clusters": len(big), "modularity": modularity,
                  "comm_-1": "unclustered / isolated (no edges or below min size)",
                  "note": "canonical contribution->cluster assignment; ship so consumers don't recompute."},
        "clusters": legend,
        "assignment": {c["id"]: comm_of[c["id"]] for c in cons},
    }, indent=2))

    # 5. emit graph.json (turnkey render payload, mirrors the atlas viewer)
    by_paper = defaultdict(list)
    for c in cons:
        by_paper[c["paper_id"]].append(c)
    contribs_n = [{"id": c["id"], "comm": comm_of[c["id"]], "kind": c.get("kind", ""),
                   "stmt": c.get("statement", ""), "quote": c.get("quote", ""),
                   "year": yr(papers.get(c["paper_id"])), "cite": cite(papers.get(c["paper_id"], {})),
                   "date": c.get("date") or papers.get(c["paper_id"], {}).get("date") or ""}
                  for c in cons]
    contrib_links = [{"source": e["src"], "target": e["dst"], "rel": e["relation"],
                      "ev": (e.get("evidence") or "")[:160], "trust": round(e.get("trust", 0.5), 2),
                      "directed": bool(e.get("directed")),
                      "tier": (e.get("agreement") or {}).get("tier", "")}
                     for e in edges if e["src"] in ids and e["dst"] in ids
                     and e["src"].split("::")[0] != e["dst"].split("::")[0]]
    pair = Counter()
    for e in edges:
        a, b = e["src"].split("::")[0], e["dst"].split("::")[0]
        if a in by_paper and b in by_paper and a != b:
            pair[tuple(sorted((a, b)))] += 1
    deg = Counter()
    for (a, b) in pair:
        deg[a] += 1; deg[b] += 1
    paper_dom = {}
    for p, cs in by_paper.items():
        cl = Counter(comm_of[c["id"]] for c in cs if comm_of[c["id"]] >= 0)
        paper_dom[p] = cl.most_common(1)[0][0] if cl else -1
    papers_n = [{"id": p, "cite": cite(papers.get(p, {})), "title": papers.get(p, {}).get("title") or "",
                 "deg": deg[p], "comm": paper_dom[p], "year": yr(papers.get(p)),
                 "date": papers.get(p, {}).get("date") or "",
                 "n": len(by_paper[p]), "url": papers.get(p, {}).get("url") or ""}
                for p in by_paper]
    paper_links = [{"source": a, "target": b, "w": w, "cross": paper_dom[a] != paper_dom[b]}
                   for (a, b), w in pair.items()]
    (out / "graph.json").write_text(json.dumps({
        "papers": papers_n, "paperLinks": paper_links, "contribs": contribs_n,
        "contribLinks": contrib_links, "legend": legend, "rel": REL,
        "topic": "agents for the scientific process"}))

    print(f"wrote {out/'clusters.json'} and {out/'graph.json'}")
    print(f"  {len(cons)} contributions · {len(big)} clusters · modularity {modularity}")
    for cl in legend:
        print(f"  comm {cl['id']:>2}  n={cl['n']:<3}  {cl['label']}")


if __name__ == "__main__":
    main()
