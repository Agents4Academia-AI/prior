"""Named collections of papers in the live graph.

Every Paper / Contribution / Claim carries a `collection` tag, so the same Neo4j
store can hold several independent corpora (e.g. the curated `core-v0.2` release
and anything ingested later) and the UI can switch between them. A `:Collection`
node holds each collection's metadata (display topic, provenance, when loaded).

A collection is loaded from a *release bundle* — the canonical, shareable format
shipped on GitHub (`papers_core.jsonl` + `contributions_core_consensus.json`).
Loading is a first-class operation (`prior collection load …`), not a script.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import embeddings, graph

PAPERS_FILE = "papers_core.jsonl"
CONTRIBS_FILE = "contributions_core_consensus.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── collection metadata (a :Collection node per corpus) ─────────────────────────
def upsert_collection(name: str, *, topic: str = "", source: str = "") -> None:
    with graph.session() as s:
        s.run("""MERGE (c:Collection {name:$name})
                 SET c.topic=$topic, c.source=$source,
                     c.created_at=coalesce(c.created_at, $ts)""",
              name=name, topic=topic, source=source, ts=_now())


def list_collections() -> list[dict]:
    """Every collection with live counts. Includes any untagged legacy data under
    the synthetic name 'default' so nothing is hidden."""
    with graph.session() as s:
        rows = s.run("""MATCH (p:Paper)
                        WITH coalesce(p.collection, 'default') AS name, count(p) AS papers
                        OPTIONAL MATCH (c:Collection {name:name})
                        RETURN name, papers, c.topic AS topic, c.source AS source,
                               c.created_at AS created_at
                        ORDER BY papers DESC""")
        out = []
        for r in rows:
            out.append({"name": r["name"], "papers": r["papers"],
                        "topic": r["topic"] or "", "source": r["source"] or "",
                        "created_at": r["created_at"]})
        return out


def tag_untagged(collection: str = "legacy") -> int:
    """Assign a collection to any pre-existing nodes that predate collections."""
    with graph.session() as s:
        n = s.run("""MATCH (n) WHERE (n:Paper OR n:Contribution OR n:Claim)
                     AND n.collection IS NULL
                     SET n.collection=$c RETURN count(n) AS n""",
                  c=collection).single()["n"]
    upsert_collection(collection, topic="(pre-collections data)")
    return n


# ── release-bundle loader ───────────────────────────────────────────────────────
def _read_papers(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _edge_rows(edges: list[dict]) -> list[dict]:
    """Map a release edge to a bulk_load edge row (carrying the consensus signals)."""
    rows = []
    for e in edges:
        rows.append({
            "src": e["src"], "dst": e["dst"], "rel": e["relation"],
            "evidence": e.get("evidence", ""), "confidence": e.get("confidence"),
            "source": e.get("source", ""), "trust": e.get("trust"),
            "tier": (e.get("agreement") or {}).get("tier", ""),
            "similarity": e.get("similarity"),
        })
    return rows


def load_bundle(bundle_dir: str | Path, *, collection: str, topic: str = "",
                source: str = "", progress=print) -> dict:
    """Load a release bundle into the graph under `collection`. Idempotent (MERGE
    by id), so re-loading refreshes. Embeds each contribution for vector search."""
    d = Path(bundle_dir)
    papers = _read_papers(d / PAPERS_FILE)
    cc = json.loads((d / CONTRIBS_FILE).read_text())
    contribs, edges = cc["contributions"], cc.get("edges", [])
    progress(f"  {len(papers)} papers, {len(contribs)} contributions, {len(edges)} edges")

    progress("  embedding contributions …")
    vecs = embeddings.embed([c.get("statement", "") for c in contribs])
    contrib_rows = [{**c, "embedding": v} for c, v in zip(contribs, vecs)]

    progress("  writing to Neo4j …")
    graph.setup_schema()
    graph.bulk_load(papers, contrib_rows, [], _edge_rows(edges), collection=collection)
    upsert_collection(collection, topic=topic, source=source)
    return {"collection": collection, "papers": len(papers),
            "contributions": len(contribs), "edges": len(edges)}
