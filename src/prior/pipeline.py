"""Orchestration: topic -> ingest -> read -> map -> saved atlas.

Each stage caches to disk so they can be run and re-run independently (ingest is
network-bound; read/map are LLM-bound and the expensive part).
"""

from __future__ import annotations

import json
from pathlib import Path

from . import cartographer, config, reader
from .atlas import Atlas
from .models import Claim, Contribution, Edge, Paper
from .reader import ReadResult
from .sources import arxiv, fulltext, openalex


def sink_to_neo4j(atlas, *, progress=print) -> dict:
    """Push a built atlas into Neo4j with embeddings. Idempotent (MERGE), so it
    doubles as the incremental-merge primitive for continuous ingestion."""
    from . import embeddings, graph
    graph.setup_schema()

    for p in atlas.papers.values():
        graph.upsert_paper(p.to_dict())

    contribs = list(atlas.contributions.values())
    cvecs = embeddings.embed([f"{k.problem} {k.method} {k.result}" for k in contribs])
    for k, v in zip(contribs, cvecs):
        graph.upsert_contribution(k.to_dict(), embedding=v)

    claims = list(atlas.claims.values())
    clvecs = embeddings.embed([c.text for c in claims])
    for c, v in zip(claims, clvecs):
        graph.upsert_claim(c.to_dict(), embedding=v)

    for e in atlas.edges:
        if e.level == "global" or e.level == "local":
            graph.add_edge(e.src, e.dst, e.relation, evidence=e.evidence,
                           confidence=e.confidence, source=e.source)
        elif e.relation == "cites":
            graph.add_edge(e.src, e.dst, "CITES", confidence=e.confidence)

    s = graph.summary()
    progress(f"      neo4j: {s}")
    return s


def _papers_path() -> Path:
    return config.RAW / "papers.jsonl"


def _claims_path() -> Path:
    return config.ATLAS / "claims.jsonl"


def _contributions_path() -> Path:
    return config.ATLAS / "contributions.jsonl"


def _local_edges_path() -> Path:
    return config.ATLAS / "local_edges.jsonl"


def ingest(topic: str, *, max_papers: int | None = None,
           use_arxiv: bool = True, full_text: bool = True, progress=print) -> list[Paper]:
    """Fetch papers for a topic from primary sources and cache them. When
    `full_text` is set, also fetch body text where available (else abstract)."""
    config.ensure_dirs()
    n = max_papers or config.DEFAULT_MAX_PAPERS
    papers: dict[str, Paper] = {}
    for p in openalex.search(topic, max_papers=n):
        papers[p.id] = p
    if use_arxiv and len(papers) < n:
        # Fill the remainder from arXiv so `max_papers` is a true total cap.
        for p in arxiv.search(topic, max_papers=n - len(papers)):
            if len(papers) >= n:
                break
            papers.setdefault(p.id, p)
    out = list(papers.values())[:n]

    if full_text:
        got = 0
        for p in out:
            try:
                body = fulltext.fetch(p)
            except Exception:  # noqa: BLE001 — full text is best-effort
                body = ""
            if body:
                p.full_text = body
                got += 1
        progress(f"      full text for {got}/{len(out)} papers")

    with _papers_path().open("w") as f:
        for p in out:
            f.write(json.dumps(p.to_dict()) + "\n")
    return out


def load_papers() -> list[Paper]:
    path = _papers_path()
    if not path.exists():
        return []
    return [Paper.from_dict(json.loads(line)) for line in path.read_text().splitlines() if line]


def read_all(papers: list[Paper], *, model: str | None = None,
             progress=print) -> ReadResult:
    """Run Reader over every paper, caching contributions/claims/local edges as
    we go. Returns one aggregate ReadResult across all papers."""
    config.ensure_dirs()
    agg = ReadResult()
    with _contributions_path().open("w") as kf, \
            _claims_path().open("w") as cf, \
            _local_edges_path().open("w") as ef:
        for i, p in enumerate(papers, 1):
            try:
                r = reader.read(p, model=model)
            except Exception as e:  # noqa: BLE001 — one bad paper shouldn't sink the run
                progress(f"  [{i}/{len(papers)}] {p.short_cite()}: ERROR {e}")
                continue
            for k in r.contributions:
                kf.write(json.dumps(k.to_dict()) + "\n")
            for c in r.claims:
                cf.write(json.dumps(c.to_dict()) + "\n")
            for e in r.local_edges:
                ef.write(json.dumps(e.to_dict()) + "\n")
            agg.contributions.extend(r.contributions)
            agg.claims.extend(r.claims)
            agg.local_edges.extend(r.local_edges)
            progress(f"  [{i}/{len(papers)}] {p.short_cite()}: "
                     f"{len(r.contributions)} contribs, {len(r.claims)} claims, "
                     f"{len(r.local_edges)} edges")
    return agg


def load_reading() -> ReadResult:
    def _lines(path: Path):
        return path.read_text().splitlines() if path.exists() else []
    return ReadResult(
        contributions=[Contribution.from_dict(json.loads(x))
                       for x in _lines(_contributions_path()) if x],
        claims=[Claim.from_dict(json.loads(x)) for x in _lines(_claims_path()) if x],
        local_edges=[Edge.from_dict(json.loads(x))
                     for x in _lines(_local_edges_path()) if x],
    )


def build(topic: str, *, max_papers: int | None = None, relate: bool = True,
          progress=print) -> Atlas:
    """Full pipeline: ingest -> read -> map -> save."""
    progress(f"[1/3] ingesting '{topic}' ...")
    papers = ingest(topic, max_papers=max_papers)
    progress(f"      {len(papers)} papers")

    progress("[2/3] reading (paper -> contributions + claims + local graph) ...")
    r = read_all(papers, progress=progress)
    progress(f"      {len(r.contributions)} contributions, {len(r.claims)} claims, "
             f"{len(r.local_edges)} local edges")

    progress("[3/3] mapping (contributions -> global graph) ...")
    atlas = cartographer.build(papers, r, topic=topic, relate=relate, model=None)
    path = atlas.save()
    progress(f"      {atlas.summary()}")
    progress(f"saved -> {path}")
    return atlas
