"""Orchestration: topic -> ingest -> read -> map -> saved atlas.

Each stage caches to disk so they can be run and re-run independently (ingest is
network-bound; read/map are LLM-bound and the expensive part).
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import cartographer, config, fulltext, reader
from .atlas import Atlas
from .models import Claim, Contribution, Edge, Paper
from .reader import ReadResult
from .sources import arxiv, openalex


def sink_to_neo4j(atlas, *, progress=print) -> dict:
    """Push a built atlas into Neo4j with embeddings via batched (UNWIND) writes.
    Idempotent (MERGE), so it also serves as the incremental-merge primitive for
    continuous ingestion."""
    from . import embeddings, graph
    graph.setup_schema()

    contribs = list(atlas.contributions.values())
    cvecs = embeddings.embed([f"{k.problem} {k.method} {k.result}" for k in contribs])
    contrib_rows = [{**k.to_dict(), "embedding": v} for k, v in zip(contribs, cvecs)]

    claims = list(atlas.claims.values())
    clvecs = embeddings.embed([c.text for c in claims])
    claim_rows = [{**c.to_dict(), "embedding": v} for c, v in zip(claims, clvecs)]

    edge_rows = []
    for e in atlas.edges:
        if e.level in ("global", "local"):
            edge_rows.append({"src": e.src, "dst": e.dst, "rel": e.relation,
                              "evidence": e.evidence, "confidence": e.confidence,
                              "source": e.source})
        elif e.relation == "cites":
            edge_rows.append({"src": e.src, "dst": e.dst, "rel": "CITES",
                              "evidence": "", "confidence": e.confidence, "source": "citation"})

    graph.bulk_load([p.to_dict() for p in atlas.papers.values()],
                    contrib_rows, claim_rows, edge_rows)
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


def expand_references(papers: list[Paper], *, hops: int = 1, cap: int = 200,
                      progress=print) -> list[Paper]:
    """Walk citation edges backward: fetch the OpenAlex works the given papers
    reference, reaching an idea's true origins that keyword search (bound by
    current terminology) never surfaces. (From main.)"""
    have: dict[str, Paper] = {p.id: p for p in papers}
    frontier = list(papers)
    for hop in range(hops):
        wanted = [ref for p in frontier for ref in p.referenced_works
                  if ref.startswith("openalex:") and ref not in have]
        wanted = list(dict.fromkeys(wanted))
        room = cap - len(have)
        if not wanted or room <= 0:
            break
        fetched = openalex.fetch_many(wanted[:room])
        new = [p for pid, p in fetched.items() if pid not in have]
        for p in new:
            have[p.id] = p
        progress(f"  hop {hop + 1}: +{len(new)} cited works (corpus now {len(have)})")
        frontier = new
    return list(have.values())


def ingest(topic: str, *, max_papers: int | None = None, use_arxiv: bool = True,
           full_text: bool = True, cite_hops: int = 0, cap: int = 200,
           progress=print) -> list[Paper]:
    """Fetch papers for a topic from primary sources and cache them. `cite_hops>0`
    expands backward along citations; `full_text` fetches body text where available."""
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
    if cite_hops > 0:
        out = expand_references(out, hops=cite_hops, cap=cap, progress=progress)

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
    """Run Reader over every paper (in parallel — PRIOR_READ_WORKERS at a time),
    caching contributions/claims/local edges. Returns one aggregate ReadResult."""
    config.ensure_dirs()
    workers = int(os.environ.get("PRIOR_READ_WORKERS", "6"))
    results: dict[int, ReadResult] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(reader.read, p, model=model): (i, p)
                for i, p in enumerate(papers)}
        for f in as_completed(futs):
            i, p = futs[f]
            done += 1
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001 — one bad paper shouldn't sink the run
                progress(f"  read [{done}/{len(papers)}] {p.short_cite()}: ERROR {e}")
                continue
            results[i] = r
            progress(f"  read [{done}/{len(papers)}] {p.short_cite()}: "
                     f"{len(r.contributions)} contribs, {len(r.claims)} claims, "
                     f"{len(r.local_edges)} edges")

    # Write caches + aggregate in stable paper order.
    agg = ReadResult()
    with _contributions_path().open("w") as kf, \
            _claims_path().open("w") as cf, \
            _local_edges_path().open("w") as ef:
        for i in range(len(papers)):
            r = results.get(i)
            if not r:
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
          cite_hops: int = 0, progress=print) -> Atlas:
    """Full pipeline: ingest -> read -> map -> save."""
    progress(f"[1/3] ingesting '{topic}' ...")
    papers = ingest(topic, max_papers=max_papers, cite_hops=cite_hops, progress=progress)
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


# ── full-text + exploration stages (integrated onto the read_all / graph model) ──
_PREPRINT_PREFIXES = {"10.1101", "10.64898", "10.26434", "10.21203", "10.20944",
                      "10.31234", "10.31235", "10.31219", "10.36227", "10.22541",
                      "10.48550", "10.3929", "10.5281", "10.2139"}


def fetch_fulltext(papers: list[Paper], *, workers: int = 12, progress=print) -> dict:
    """Pre-stage: cache raw full text for `papers` in PARALLEL (no LLM), so the
    parallel reader (read_all -> reader.read -> fulltext.fetch) reads locally
    instead of re-fetching. Delegates to the standalone fulltext.fetch_many."""
    config.ensure_dirs()
    return fulltext.fetch_many(papers, workers=workers, progress=progress)


def enrich_arxiv_twins(papers: list[Paper], *, throttle: float = 1.0, progress=print) -> int:
    """Exploration enrichment: attach the open arXiv twin to records that came in
    closed (OpenAlex canonicalised to a publisher/repository deposit). Sets pdf_url
    so the full-text stage uses the open edition. Mutates in place; returns count."""
    import time
    cand = [p for p in papers
            if p.source != "arxiv" and "arxiv.org" not in (p.pdf_url or "")]
    progress(f"  enriching {len(cand)} records lacking an arXiv locator ...")
    n = 0
    for p in cand:
        aid = arxiv.find_id_by_title(p.title)
        time.sleep(throttle)                           # polite to the arXiv API
        if aid:
            p.pdf_url = f"https://arxiv.org/pdf/{aid}"
            n += 1
            progress(f"  twin: {p.short_cite()} -> arXiv:{aid}")
    progress(f"  attached arXiv twins to {n} records")
    return n


def select_papers(which: str = "core") -> list[Paper]:
    """Shared corpus selector by full-text status, over the reading store.
    which ∈ {all, core, missing, preprints}."""
    corpus = load_papers()
    has_contrib = {c.paper_id for c in load_reading().contributions}

    def has_ft(p):
        return p.id in has_contrib or fulltext.cached_text(p) is not None

    if which == "core":
        core = set(json.loads((config.ATLAS / "core_scope.json").read_text())["core_ids"])
        return [p for p in corpus if p.id in core]
    if which == "missing":
        return [p for p in corpus if not has_ft(p)]
    if which == "preprints":
        def is_pre(p):
            d = (p.doi or "").replace("https://doi.org/", "")
            return p.source == "arxiv" or (d and ".".join(d.split("/")[0].split(".")[:2]) in _PREPRINT_PREFIXES)
        return [p for p in corpus if is_pre(p) and not has_ft(p)]
    return corpus


def expand(papers: list[Paper], *, model: str | None = None, workers: int = 12,
           progress=print) -> ReadResult:
    """Stage chain over `papers`: cache full text (parallel) -> read (extract into
    the Contribution + local-graph model). Extraction is read_all; build() /
    sink_to_neo4j then take it to the global graph DB."""
    progress(f"expand: {len(papers)} papers")
    progress("[1/2] full text")
    fetch_fulltext(papers, workers=workers, progress=progress)
    progress("[2/2] read (extract into contributions + local graph)")
    return read_all(papers, model=model, progress=progress)
