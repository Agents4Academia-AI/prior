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

from . import cartographer, config, embeddings, fulltext, graph, reader
from .models import Contribution
from .sources import arxiv, openalex


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


def process_paper(paper, *, model: str | None = None, neighbours: int = 6,
                  collection: str = "default") -> dict:
    """Enrich one paper and MERGE it into the graph, relating it incrementally.
    New global edges are consensus-scored (trust/tier) to match the v0.2 schema."""
    from . import consensus
    # Keep already-supplied body text (e.g. an uploaded PDF); else fetch it.
    paper.full_text = paper.full_text or fulltext.fetch(paper) or ""
    r = reader.read(paper, model=model)
    if not r.contributions and not r.claims:
        return {"id": paper.id, "contribs": 0, "claims": 0, "edges": 0}

    cvecs = embeddings.embed([k.summary() for k in r.contributions])
    clvecs = embeddings.embed([c.text for c in r.claims])
    edge_rows = [{"src": e.src, "dst": e.dst, "rel": e.relation, "evidence": e.evidence,
                  "confidence": e.confidence, "source": e.source} for e in r.local_edges]
    graph.bulk_load(
        [paper.to_dict()],
        [{**k.to_dict(), "embedding": v} for k, v in zip(r.contributions, cvecs)],
        [{**c.to_dict(), "embedding": v} for c, v in zip(r.claims, clvecs)],
        edge_rows, collection=collection)

    # Incremental global relate: each new contribution vs its nearest existing ones,
    # scored by Sonnet+Opus+similarity consensus (trust/tier).
    g_edges = 0
    for k, v in zip(r.contributions, cvecs):
        hits = [h for h in graph.ann(v, label="Contribution", k=neighbours + 4)
                if h["paper_id"] != paper.id][:neighbours]
        cands = [Contribution(id=h["id"], paper_id=h["paper_id"],
                              statement=h.get("statement") or "", kind=h.get("kind") or "other",
                              problem=h.get("problem") or "", method=h.get("method") or "",
                              result=h.get("result") or "") for h in hits]
        if not cands:
            continue
        sim_by_id = {h["id"]: h.get("_score", 0.0) for h in hits}
        for ed in consensus.relate(k, cands, sim_by_id, set()):
            graph.add_edge(ed["src"], ed["dst"], ed["relation"], evidence=ed["evidence"],
                           confidence=ed["confidence"], source=ed["source"],
                           trust=ed["trust"], tier=ed["tier"], similarity=ed["similarity"])
            g_edges += 1
    return {"id": paper.id, "contribs": len(r.contributions),
            "claims": len(r.claims), "edges": g_edges}


def _discover(topics: list[str], topic_defs: list[str], per_topic: int,
              progress) -> list:
    """Two discovery modes: plain `topics` (raw search) and `topic_defs` (Scoper —
    LLM queries + multi-source gather + strict relevance filter for a clean corpus)."""
    out = []
    for t in topics:
        out.extend(_discover_topic(t, per_topic))
    if topic_defs:
        try:
            from . import scoper          # optional: present once klara/scoper is merged
        except ImportError as e:  # noqa: BLE001
            raise RuntimeError("--topic-def needs the Scoper (merge klara/scoper)") from e
        for td in topic_defs:
            progress(f"  scoping topic-def ({len(td)} chars) ...")
            kept, dropped = scoper.build_scoped_corpus(td, per_query=per_topic, progress=progress)
            progress(f"  scoper kept {len(kept)} / dropped {len(dropped)}")
            out.extend(kept)
    return out


def run(topics: list[str] | None = None, *, topic_defs: list[str] | None = None,
        rounds: int = 1, per_topic: int = 10, workers: int | None = None,
        watch: bool = False, interval: int = 300, progress=print) -> None:
    """Discover → enqueue (dedup) → process pool → repeat. `topics` use raw search;
    `topic_defs` route through the Scoper for a clean, relevance-filtered corpus.
    With watch=True, loops forever, re-polling every `interval` seconds."""
    graph.setup_schema()
    topics = topics or []
    topic_defs = topic_defs or []
    workers = workers or int(os.environ.get("PRIOR_WORKERS", "6"))
    rnd = 0
    while True:
        rnd += 1
        seen = set()
        frontier = []
        for p in _discover(topics, topic_defs, per_topic, progress):
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
