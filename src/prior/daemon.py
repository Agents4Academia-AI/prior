"""Continuous ingestion + enrichment.

Instead of a one-shot `build`, the daemon keeps a frontier of papers to ingest,
processes them with a worker pool, and MERGEs each into the live Neo4j graph as
it arrives — so the graph grows over time. Each new paper is also *incrementally
related*: its contributions are linked to the existing graph via vector-nearest
neighbours + citations, so we never rebuild the whole global graph.

Frontier sources:
  - topics      — OpenAlex/arXiv search for each watched topic
  - citations   — references of papers already in the graph (expand outward)

Dedup is by canonical id against Neo4j, so re-discovering a paper is a no-op.

CLI:  prior daemon --topic "<t>" [--rounds N] [--workers M] [--expand]
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import cartographer, config, embeddings, graph, reader
from .models import Contribution
from .sources import arxiv, fulltext, openalex


def _have(paper_id: str) -> bool:
    with graph.session() as s:
        return s.run("MATCH (p:Paper {id:$id}) RETURN p LIMIT 1", id=paper_id).single() is not None


def _discover_topic(topic: str, n: int) -> list:
    papers: dict[str, object] = {}
    for p in openalex.search(topic, max_papers=n):
        papers[p.id] = p
    for p in arxiv.search(topic, max_papers=max(2, n // 3)):
        papers.setdefault(p.id, p)
    return list(papers.values())


def process_paper(paper, *, model: str | None = None, neighbours: int = 6) -> dict:
    """Enrich one paper and MERGE it into the graph, relating it incrementally."""
    paper.full_text = fulltext.fetch(paper) or ""
    r = reader.read(paper, model=model)
    if not r.contributions and not r.claims:
        return {"id": paper.id, "contribs": 0, "claims": 0, "edges": 0}

    cvecs = embeddings.embed([f"{k.problem} {k.method} {k.result}" for k in r.contributions])
    clvecs = embeddings.embed([c.text for c in r.claims])
    edge_rows = [{"src": e.src, "dst": e.dst, "rel": e.relation, "evidence": e.evidence,
                  "confidence": e.confidence, "source": e.source} for e in r.local_edges]
    graph.bulk_load(
        [paper.to_dict()],
        [{**k.to_dict(), "embedding": v} for k, v in zip(r.contributions, cvecs)],
        [{**c.to_dict(), "embedding": v} for c, v in zip(r.claims, clvecs)],
        edge_rows)

    # Incremental global relate: each new contribution vs its nearest existing ones.
    g_edges = 0
    for k, v in zip(r.contributions, cvecs):
        hits = graph.ann(v, label="Contribution", k=neighbours + 4)
        cands = [Contribution(id=h["id"], paper_id=h["paper_id"], problem=h.get("problem", ""),
                              method=h.get("method", ""), result=h.get("result", ""))
                 for h in hits if h["paper_id"] != paper.id][:neighbours]
        if not cands:
            continue
        for e in cartographer._label(k, cands, set(), model or config.CARTOGRAPHER_MODEL):
            graph.add_edge(e.src, e.dst, e.relation, evidence=e.evidence,
                           confidence=e.confidence, source=e.source)
            g_edges += 1
    return {"id": paper.id, "contribs": len(r.contributions),
            "claims": len(r.claims), "edges": g_edges}


def run(topics: list[str], *, rounds: int = 1, per_topic: int = 10,
        workers: int | None = None, watch: bool = False, interval: int = 300,
        progress=print) -> None:
    """Discover → enqueue (dedup) → process pool → repeat. With watch=True, loops
    forever, re-polling topics every `interval` seconds."""
    graph.setup_schema()
    workers = workers or int(os.environ.get("PRIOR_WORKERS", "6"))
    rnd = 0
    while True:
        rnd += 1
        seen = set()
        frontier = []
        for t in topics:
            for p in _discover_topic(t, per_topic):
                if p.id in seen or _have(p.id):
                    continue
                seen.add(p.id)
                frontier.append(p)
        progress(f"[round {rnd}] {len(frontier)} new papers to ingest")
        if frontier:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futs = {pool.submit(process_paper, p): p for p in frontier}
                for i, f in enumerate(as_completed(futs), 1):
                    p = futs[f]
                    try:
                        st = f.result()
                        progress(f"  [{i}/{len(frontier)}] {p.short_cite()}: "
                                 f"+{st['contribs']} contribs, +{st['claims']} claims, "
                                 f"+{st['edges']} global edges")
                    except Exception as e:  # noqa: BLE001
                        progress(f"  [{i}/{len(frontier)}] {p.short_cite()}: ERROR {e}")
        progress(f"[round {rnd}] graph now: {graph.summary()}")
        if watch:
            time.sleep(interval)
            continue
        if rnd >= rounds:
            break
