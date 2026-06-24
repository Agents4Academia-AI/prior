"""Backfill the LOCAL claim layer for a contribution-only collection.

Some collections (e.g. the core-v0.2 release) ship contributions + consensus
edges but no claims. This runs the Reader's claims-only pass over each paper —
anchored to that paper's existing contributions — to extract atomic claims, the
local claim graph (entails/contradicts/supports/depends_on), and the claim→
contribution bridge, storing them in Neo4j under the same collection.

Full text is read from a directory of `<paper_id with ':'→'_'>.txt` files.
First-class operation: `prior claims --collection <name> --fulltext-dir <dir>`.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config, embeddings, graph, reader
from .models import Contribution, Paper


def _fulltext(paper_id: str, d: str) -> str:
    path = os.path.join(d, paper_id.replace(":", "_") + ".txt")
    try:
        return open(path, encoding="utf-8", errors="ignore").read() if os.path.exists(path) else ""
    except OSError:
        return ""


def _papers_with_contribs(collection: str) -> list[tuple[dict, list[dict]]]:
    with graph.session() as s:
        rows = s.run(
            """MATCH (p:Paper {collection:$c})-[:HAS_CONTRIBUTION]->(k:Contribution)
               RETURN p{.id,.title,.year,.abstract} AS p,
                      collect(k{.id,.statement,.kind}) AS ks""", c=collection)
        return [(r["p"], r["ks"]) for r in rows if r["ks"]]


def _process(p: dict, ks: list[dict], d: str, collection: str, model: str | None) -> tuple:
    paper = Paper(id=p["id"], source="", title=p.get("title") or "", url="",
                  abstract=p.get("abstract") or "", year=p.get("year"),
                  full_text=_fulltext(p["id"], d))
    contribs = [Contribution(id=k["id"], paper_id=p["id"],
                             statement=k.get("statement") or "", kind=k.get("kind") or "other")
                for k in ks]
    rr = reader.read_claims(paper, contribs, model=model)
    if not rr.claims:
        return (p["id"], 0, 0)
    vecs = embeddings.embed([c.text for c in rr.claims])
    edge_rows = [{"src": e.src, "dst": e.dst, "rel": e.relation, "evidence": e.evidence,
                  "confidence": e.confidence, "source": e.source} for e in rr.local_edges]
    graph.bulk_load([], [], [{**c.to_dict(), "embedding": v} for c, v in zip(rr.claims, vecs)],
                    edge_rows, collection=collection)
    return (p["id"], len(rr.claims), len(rr.local_edges))


def run(collection: str, fulltext_dir: str, *, workers: int | None = None,
        model: str | None = None, progress=print) -> dict:
    graph.setup_schema()
    items = _papers_with_contribs(collection)
    progress(f"{len(items)} papers with contributions in {collection}")
    workers = workers or int(os.environ.get("PRIOR_WORKERS", "6"))
    nc = ne = npap = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_process, p, ks, fulltext_dir, collection, model): p["id"]
                for p, ks in items}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                pid, c, e = f.result()
                nc += c; ne += e; npap += 1 if c else 0
                progress(f"  [{i}/{len(items)}] {pid}: +{c} claims, +{e} local edges")
            except Exception as ex:  # noqa: BLE001
                progress(f"  [{i}/{len(items)}] {futs[f]}: ERROR {ex}")
    progress(f"done: {npap} papers, {nc} claims, {ne} local edges")
    return {"papers": npap, "claims": nc, "local_edges": ne}
