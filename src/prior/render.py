"""Render payload for the graph viewer — live from Neo4j, per collection.

The D3 viewer draws a *turnkey payload* (the same shape as the shipped
`graph.json`): contribution nodes carrying `comm/kind/stmt/year/cite` and edges
carrying `rel/trust/tier`. This module produces that payload from the live graph
for a given collection, so it always reflects what's actually stored (including
freshly-ingested papers) instead of a baked file.

Clustering is the canonical one (deterministic greedy modularity over the
consensus edges, same as `scripts/cluster_core.py`): we cluster once, store the
assignment back on the nodes (`k.comm`), and cache the payload. `recluster()` is
called on load and after each ingest; the payload is then served straight from
cache. Size is bounded by server-side constraints (min-trust, top-N by degree).
"""

from __future__ import annotations

import math
import threading
from collections import Counter, defaultdict
from typing import Optional

import networkx as nx

from . import graph

MIN = 8                       # min community size to be a labelled cluster
GREY = "#c9cdd2"
REL = {"supports": "#0a9396", "builds_on": "#5b8fb0",
       "refines": "#ca6702", "contradicts": "#ae2012"}
_CONTRIB_RELS = ("SUPPORTS", "BUILDS_ON", "REFINES", "CONTRADICTS", "CONTRAST")

# cluster label + colour + content keywords (labelled by keyword vote, not size)
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

_CACHE: dict[str, dict] = {}
_LOCK = threading.Lock()


# ── reads from Neo4j (collection-scoped) ────────────────────────────────────────
def _read(collection: str) -> tuple[dict, list, list]:
    with graph.session() as s:
        papers = {r["id"]: dict(r) for r in s.run(
            "MATCH (p:Paper {collection:$c}) "
            "RETURN p.id AS id, p.title AS title, p.year AS year, "
            "p.authors AS authors, p.url AS url", c=collection)}
        contribs = [dict(r) for r in s.run(
            "MATCH (k:Contribution {collection:$c}) "
            "RETURN k.id AS id, k.paper_id AS paper_id, k.statement AS statement, "
            "k.kind AS kind, k.quote AS quote", c=collection)]
        rel_list = list(_CONTRIB_RELS)
        edges = [dict(r) for r in s.run(
            "MATCH (a:Contribution {collection:$c})-[r]->(b:Contribution {collection:$c}) "
            "WHERE type(r) IN $rels "
            "RETURN a.id AS src, b.id AS dst, type(r) AS rel, r.trust AS trust, "
            "r.tier AS tier, r.evidence AS evidence", c=collection, rels=rel_list)]
    return papers, contribs, edges


def _cite(p: dict) -> str:
    au = p.get("authors") or []
    if not isinstance(au, list):
        au = []
    last = au[0].split()[-1] if au else (p.get("title") or "?")[:16]
    return f"{last}{' et al.' if len(au) > 1 else ''} ({p.get('year')})"


def _year(p: dict) -> Optional[int]:
    try:
        return int(str((p or {}).get("year") or "").strip()[:4])
    except (ValueError, TypeError):
        return None


# ── clustering (deterministic; canonical) ───────────────────────────────────────
def _cluster(contribs: list, edges: list) -> tuple[dict, list]:
    ids = {c["id"] for c in contribs}
    G = nx.Graph(); G.add_nodes_from(sorted(ids))
    for e in sorted(edges, key=lambda e: (e["src"], e["dst"])):
        if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
            G.add_edge(e["src"], e["dst"])
    comms = sorted(nx.community.greedy_modularity_communities(G),
                   key=lambda cs: (-len(cs), min(cs))) if G.number_of_edges() else []
    big = [cs for cs in comms if len(cs) >= MIN][:9]
    comm_of: dict[str, int] = {}
    for ci, cs in enumerate(big):
        for n in cs:
            comm_of[n] = ci
    for n in ids:
        comm_of.setdefault(n, -1)

    st = {c["id"]: (c.get("statement") or "").lower() for c in contribs}
    blob = {ci: " ".join(st[n] for n in cs) for ci, cs in enumerate(big)}
    scored = sorted(((sum(blob[ci].count(k) for k in kw), ci, li)
                     for ci in range(len(big))
                     for li, (lb, co, kw) in enumerate(LABELKW)), reverse=True)
    clabel: dict[int, tuple] = {}
    used_c, used_l = set(), set()
    for _, ci, li in scored:
        if ci in used_c or li in used_l:
            continue
        clabel[ci] = LABELKW[li]; used_c.add(ci); used_l.add(li)
    for ci in range(len(big)):
        clabel.setdefault(ci, (f"cluster {ci}", GREY, []))
    legend = [{"id": ci, "label": clabel[ci][0], "color": clabel[ci][1],
               "n": sum(1 for n in ids if comm_of[n] == ci)} for ci in range(len(big))]
    legend.append({"id": -1, "label": "unclustered", "color": GREY,
                   "n": sum(1 for n in ids if comm_of[n] == -1)})
    return comm_of, legend


def _layout(contribs: list, comm_of: dict, cluster_ids: list) -> dict:
    """Deterministic, O(n) initial positions: each cluster anchored on a ring, its
    members spiralled around the anchor (golden angle). Normalised to ~[-0.5, 0.5].
    Shipped so the client renders from a good starting layout and barely needs to
    run the force sim — the main page-load cost."""
    k = len(cluster_ids) or 1
    anchor = {}
    for i, cid in enumerate(sorted(cluster_ids)):
        a = 2 * math.pi * i / k - math.pi / 2
        anchor[cid] = (0.36 * math.cos(a), 0.36 * math.sin(a))
    anchor[-1] = (0.0, 0.0)
    members: dict[int, list] = defaultdict(list)
    for c in contribs:
        members[comm_of.get(c["id"], -1)].append(c["id"])
    pos = {}
    for cid, ids in members.items():
        ax, ay = anchor.get(cid, (0.0, 0.0))
        n = len(ids)
        spread = 0.45 if cid < 0 else 0.13   # isolated nodes fan out around centre
        for j, nid in enumerate(sorted(ids)):
            r = spread * math.sqrt((j + 1) / n)
            t = j * 2.399963229728653          # golden angle
            pos[nid] = (round(ax + r * math.cos(t), 4), round(ay + r * math.sin(t), 4))
    return pos


def _build_payload(collection: str, papers: dict, contribs: list, edges: list,
                   comm_of: dict, legend: list) -> dict:
    topic = ""
    with graph.session() as s:
        rec = s.run("MATCH (c:Collection {name:$n}) RETURN c.topic AS t",
                    n=collection).single()
        if rec:
            topic = rec["t"] or ""
    ids = {c["id"] for c in contribs}
    deg = Counter()
    for e in edges:
        deg[e["src"]] += 1; deg[e["dst"]] += 1
    pos = _layout(contribs, comm_of, [l["id"] for l in legend if l["id"] >= 0])
    contribs_n = [{"id": c["id"], "comm": comm_of.get(c["id"], -1),
                   "kind": c.get("kind") or "", "stmt": c.get("statement") or "",
                   "quote": c.get("quote") or "", "deg": deg[c["id"]],
                   "x": pos[c["id"]][0], "y": pos[c["id"]][1],
                   "year": _year(papers.get(c["paper_id"])),
                   "cite": _cite(papers.get(c["paper_id"], {}))}
                  for c in contribs]
    contrib_links = [{"source": e["src"], "target": e["dst"],
                      "rel": (e["rel"] or "").lower(),
                      "ev": (e.get("evidence") or "")[:160],
                      "trust": round(e["trust"], 2) if e.get("trust") is not None else 0.5,
                      "tier": e.get("tier") or ""}
                     for e in edges if e["src"] in ids and e["dst"] in ids
                     and e["src"].split("::")[0] != e["dst"].split("::")[0]]

    # ── paper level: roll contributions up to their papers ──────────────────────
    by_paper: dict[str, list] = defaultdict(list)
    for c in contribs:
        by_paper[c["paper_id"]].append(c)
    paper_dom, paper_bridge, paper_spread = {}, {}, {}
    for p, cs in by_paper.items():
        cnt = Counter(comm_of.get(c["id"], -1) for c in cs if comm_of.get(c["id"], -1) >= 0)
        paper_dom[p] = cnt.most_common(1)[0][0] if cnt else -1
        paper_spread[p] = sorted(cnt)
        paper_bridge[p] = len(cnt) >= 2
    pair = Counter()
    for e in edges:
        a, b = e["src"].split("::")[0], e["dst"].split("::")[0]
        if a in by_paper and b in by_paper and a != b:
            pair[tuple(sorted((a, b)))] += 1
    pdeg = Counter()
    for (a, b) in pair:
        pdeg[a] += 1; pdeg[b] += 1
    papers_n = [{"id": p, "cite": _cite(papers.get(p, {})),
                 "title": (papers.get(p, {}) or {}).get("title") or "",
                 "deg": pdeg[p], "comm": paper_dom[p], "bridge": paper_bridge[p],
                 "year": _year(papers.get(p)), "spread": paper_spread[p],
                 "n": len(by_paper[p]), "url": (papers.get(p, {}) or {}).get("url") or ""}
                for p in by_paper]
    paper_links = [{"source": a, "target": b, "w": w,
                    "cross": paper_dom.get(a) != paper_dom.get(b)}
                   for (a, b), w in pair.items()]

    return {"collection": collection, "topic": topic, "legend": legend, "rel": REL,
            "contribs": contribs_n, "contribLinks": contrib_links,
            "papers": papers_n, "paperLinks": paper_links,
            "n_contribs": len(contribs_n), "n_links": len(contrib_links),
            "n_papers": len(papers_n)}


# ── public API ──────────────────────────────────────────────────────────────────
def recluster(collection: str) -> dict:
    """(Re)cluster a collection, persist `comm` on its nodes, and cache the payload.
    Call on load and after each ingest."""
    papers, contribs, edges = _read(collection)
    comm_of, legend = _cluster(contribs, edges)
    with graph.session() as s:
        s.run("""UNWIND $rows AS r MATCH (k:Contribution {id:r.id}) SET k.comm=r.comm""",
              rows=[{"id": cid, "comm": cm} for cid, cm in comm_of.items()])
    payload = _build_payload(collection, papers, contribs, edges, comm_of, legend)
    with _LOCK:
        _CACHE[collection] = payload
    return {"contribs": payload["n_contribs"], "links": payload["n_links"],
            "clusters": len([l for l in legend if l["id"] >= 0])}


def invalidate(collection: str) -> None:
    with _LOCK:
        _CACHE.pop(collection, None)


def _filtered(payload: dict, *, min_trust: float, max_nodes: int,
              year_max: Optional[int]) -> dict:
    """Apply size constraints: drop low-trust edges, optional year ceiling, then
    cap to the top-N contributions by degree (keep the densest core)."""
    links = [l for l in payload["contribLinks"] if l["trust"] >= min_trust]
    nodes = payload["contribs"]
    if year_max is not None:
        nodes = [n for n in nodes if (n["year"] or 0) <= year_max]
    keep = {n["id"] for n in nodes}
    links = [l for l in links if l["source"] in keep and l["target"] in keep]
    capped = False
    if max_nodes and len(nodes) > max_nodes:
        top = sorted(nodes, key=lambda n: n["deg"], reverse=True)[:max_nodes]
        keep = {n["id"] for n in top}
        nodes, links = top, [l for l in links if l["source"] in keep and l["target"] in keep]
        capped = True
    return {**payload, "contribs": nodes, "contribLinks": links,
            "n_contribs": len(nodes), "n_links": len(links),
            "capped": capped, "total_contribs": payload["n_contribs"]}


def payload(collection: str, *, min_trust: float = 0.0, max_nodes: int = 0,
            year_max: Optional[int] = None) -> dict:
    """Cached render payload for a collection (clusters lazily if cold), with
    optional size constraints applied."""
    with _LOCK:
        cached = _CACHE.get(collection)
    if cached is None:
        recluster(collection)
        with _LOCK:
            cached = _CACHE[collection]
    return _filtered(cached, min_trust=min_trust, max_nodes=max_nodes, year_max=year_max)
