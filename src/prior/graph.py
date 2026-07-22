"""Neo4j repository — the live two-level graph store.

This is the single graph-access layer. The pipeline writes through the upsert_*
functions (idempotent MERGE, so continuous ingestion dedups for free); agents
read through the access functions (ann / neighbours / traverse / aggregate). The
agent never writes Cypher — it calls these functions.

Config (env):
  NEO4J_URI       default bolt://localhost:7687
  NEO4J_USER      default neo4j
  NEO4J_PASSWORD  default priorpass123
  PRIOR_EMBED_DIM default 384   (must match the embedder; see embeddings.py)
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterable, Optional

from neo4j import GraphDatabase

# Relationship types by level (node labels disambiguate shared names).
LOCAL_RELS = ("ENTAILS", "CONTRADICTS", "SUPPORTS", "DEPENDS_ON")
GLOBAL_RELS = ("BUILDS_ON", "REFINES", "CONTRADICTS", "CONTRAST", "SUPPORTS", "MENTIONS")

_driver = None


def _cfg() -> tuple[str, str, str]:
    return (os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "priorpass123"))


def driver():
    global _driver
    if _driver is None:
        uri, user, pwd = _cfg()
        _driver = GraphDatabase.driver(uri, auth=(user, pwd))
    return _driver


@contextmanager
def session():
    with driver().session() as s:
        yield s


def embed_dim() -> int:
    return int(os.environ.get("PRIOR_EMBED_DIM", "1024"))  # mxbai-embed-large-v1


# ── schema ──────────────────────────────────────────────────────────────────────
def setup_schema() -> None:
    """Constraints (unique ids → also the lookup index for MERGE) + vector
    indexes on contribution/claim embeddings. Idempotent."""
    dim = embed_dim()
    with session() as s:
        for label in ("Paper", "Contribution", "Claim"):
            s.run(f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                  f"FOR (n:{label}) REQUIRE n.id IS UNIQUE")
        for label in ("Contribution", "Claim"):
            s.run(f"""CREATE VECTOR INDEX {label.lower()}_vec IF NOT EXISTS
                      FOR (n:{label}) ON (n.embedding)
                      OPTIONS {{indexConfig: {{
                        `vector.dimensions`: {dim},
                        `vector.similarity_function`: 'cosine' }}}}""")
        # Source-independent work identity (same paper across arXiv/OpenAlex/versions).
        s.run("CREATE INDEX paper_work IF NOT EXISTS FOR (p:Paper) ON (p.work_id)")
        # Human annotations (graph enrichment) — keyed by target, queried by index.
        s.run("CREATE CONSTRAINT annotation_id IF NOT EXISTS "
              "FOR (n:Annotation) REQUIRE n.id IS UNIQUE")
        s.run("CREATE INDEX annotation_target IF NOT EXISTS "
              "FOR (n:Annotation) ON (n.target_key)")
        s.run("CREATE INDEX annotation_user IF NOT EXISTS "
              "FOR (n:Annotation) ON (n.annotator)")


# ── writes (idempotent; continuous-ingestion safe) ──────────────────────────────
def upsert_paper(p: dict) -> None:
    with session() as s:
        s.run("""MERGE (n:Paper {id:$id})
                 SET n += $props""",
              id=p["id"], props={k: p.get(k) for k in
                  ("title", "year", "venue", "doi", "url", "cited_by_count",
                   "is_review", "abstract", "authors", "work_id")})


def upsert_contribution(k: dict, embedding: Optional[list[float]] = None) -> None:
    props = {x: k.get(x) for x in ("paper_id", "statement", "kind",
                                   "problem", "method", "result", "quote", "confidence")}
    if embedding is not None:
        props["embedding"] = embedding
    with session() as s:
        s.run("""MERGE (n:Contribution {id:$id}) SET n += $props
                 WITH n MATCH (p:Paper {id:$pid}) MERGE (p)-[:HAS_CONTRIBUTION]->(n)""",
              id=k["id"], pid=k["paper_id"], props=props)


def upsert_claim(c: dict, embedding: Optional[list[float]] = None) -> None:
    props = {x: c.get(x) for x in ("paper_id", "text", "claim_type",
                                   "evidence", "confidence")}
    if embedding is not None:
        props["embedding"] = embedding
    with session() as s:
        s.run("""MERGE (n:Claim {id:$id}) SET n += $props
                 WITH n MATCH (p:Paper {id:$pid}) MERGE (n)-[:STATED_IN]->(p)""",
              id=c["id"], pid=c["paper_id"], props=props)
        if c.get("contribution_id"):
            s.run("""MATCH (cl:Claim {id:$cid}), (k:Contribution {id:$kid})
                     MERGE (cl)-[:SUPPORTS_CONTRIB]->(k)""",
                  cid=c["id"], kid=c["contribution_id"])


def add_edge(src: str, dst: str, rel: str, *, evidence: str = "",
             confidence: float = 0.5, source: str = "text",
             trust: float | None = None, tier: str = "",
             similarity: float | None = None) -> None:
    """Typed relationship. rel must be a LOCAL_/GLOBAL_REL or CITES; we whitelist
    to keep the relationship type safe to interpolate. Optional consensus signals
    (trust/tier/similarity) are stored when provided."""
    rel = rel.upper()
    allowed = set(LOCAL_RELS) | set(GLOBAL_RELS) | {"CITES"}
    if rel not in allowed:
        raise ValueError(f"unknown relation {rel}")
    with session() as s:
        s.run(f"""MATCH (a {{id:$src}}), (b {{id:$dst}})
                  MERGE (a)-[r:{rel}]->(b)
                  SET r.evidence=$ev, r.confidence=$conf, r.source=$source,
                      r.trust=$trust, r.tier=$tier, r.similarity=$sim""",
              src=src, dst=dst, ev=evidence, conf=confidence, source=source,
              trust=trust, tier=tier, sim=similarity)


# ── bulk writes (single transactions — fast vector-index inserts) ───────────────
def bulk_load(papers: list[dict], contributions: list[dict], claims: list[dict],
              edges: list[dict], *, collection: str = "default") -> None:
    """Load a whole atlas in a few batched transactions. Per-node transactions
    flush the HNSW vector index on every commit (~5s each); UNWIND batches amortize
    that to one flush per stage. Each `contributions`/`claims` row carries an
    `embedding` key; `edges` rows have src/dst/rel/evidence/confidence/source and
    optionally trust/tier/similarity. All nodes are tagged with `collection`."""
    with session() as s:
        s.run("UNWIND $rows AS r MERGE (p:Paper {id:r.id}) SET p += r.props",
              rows=[{"id": p["id"], "props": {**{k: p.get(k) for k in
                    ("title", "year", "venue", "doi", "url", "cited_by_count",
                     "is_review", "abstract", "authors", "date", "date_precision",
                     "work_id")},
                    "collection": collection}} for p in papers])

        s.run("""UNWIND $rows AS r
                 MERGE (n:Contribution {id:r.id}) SET n += r.props
                 WITH n, r MATCH (p:Paper {id:r.props.paper_id})
                 MERGE (p)-[:HAS_CONTRIBUTION]->(n)""",
              rows=[{"id": k["id"], "props": {**{x: k.get(x) for x in
                    ("paper_id", "statement", "kind", "problem", "method",
                     "result", "quote", "confidence")}, "collection": collection,
                    "embedding": k.get("embedding")}}
                    for k in contributions])

        s.run("""UNWIND $rows AS r
                 MERGE (n:Claim {id:r.id}) SET n += r.props
                 WITH n, r MATCH (p:Paper {id:r.props.paper_id})
                 MERGE (n)-[:STATED_IN]->(p)""",
              rows=[{"id": c["id"], "props": {**{x: c.get(x) for x in
                    ("paper_id", "text", "claim_type", "evidence", "confidence")},
                    "collection": collection, "embedding": c.get("embedding")}}
                    for c in claims])

        bridge = [{"cid": c["id"], "kid": c["contribution_id"]}
                  for c in claims if c.get("contribution_id")]
        if bridge:
            s.run("""UNWIND $rows AS r
                     MATCH (cl:Claim {id:r.cid}), (k:Contribution {id:r.kid})
                     MERGE (cl)-[:SUPPORTS_CONTRIB]->(k)""", rows=bridge)

        by_rel: dict[str, list[dict]] = {}
        for e in edges:
            by_rel.setdefault(e["rel"].upper(), []).append(e)
        allowed = set(LOCAL_RELS) | set(GLOBAL_RELS) | {"CITES"}
        for rel, rows in by_rel.items():
            if rel not in allowed:
                continue
            s.run(f"""UNWIND $rows AS r
                      MATCH (a {{id:r.src}}), (b {{id:r.dst}})
                      MERGE (a)-[e:{rel}]->(b)
                      SET e.evidence=r.evidence, e.confidence=r.confidence,
                          e.source=r.source, e.trust=r.trust, e.tier=r.tier,
                          e.similarity=r.similarity, e.directed=r.directed""", rows=rows)


# ── reads (the agent's graph tools) ─────────────────────────────────────────────
def ann(query_vec: list[float], *, label: str = "Contribution", k: int = 10) -> list[dict]:
    """Vector k-NN over node embeddings — the entry point for exploration."""
    idx = f"{label.lower()}_vec"
    with session() as s:
        res = s.run("""CALL db.index.vector.queryNodes($idx, $k, $vec)
                       YIELD node, score
                       RETURN node{.*, embedding:null} AS node, score
                       ORDER BY score DESC""",
                    idx=idx, k=k, vec=query_vec)
        return [{**r["node"], "_score": r["score"]} for r in res]


def neighbours(node_id: str, *, rels: Iterable[str] | None = None,
               direction: str = "both") -> list[dict]:
    """1-hop neighbours, optionally filtered by relationship type."""
    arrow = {"out": "-[r]->", "in": "<-[r]-", "both": "-[r]-"}[direction]
    rel_filter = "WHERE type(r) IN $rels" if rels else ""
    with session() as s:
        res = s.run(f"""MATCH (n {{id:$id}}){arrow}(m) {rel_filter}
                        RETURN type(r) AS rel, properties(r) AS props,
                               m{{.*, embedding:null}} AS node""",
                    id=node_id, rels=list(rels) if rels else None)
        return [{"rel": r["rel"], "props": r["props"], "node": r["node"]} for r in res]


def traverse(node_id: str, *, rel: str = "BUILDS_ON", max_depth: int = 5,
             direction: str = "out") -> list[list[dict]]:
    """Bounded variable-length traversal along one relation (e.g. lineage)."""
    rel = rel.upper()
    arrow = f"-[:{rel}*1..{int(max_depth)}]->" if direction == "out" else f"<-[:{rel}*1..{int(max_depth)}]-"
    with session() as s:
        res = s.run(f"""MATCH path=(n {{id:$id}}){arrow}(m)
                        RETURN [x IN nodes(path) | x{{.*, embedding:null}}] AS chain
                        ORDER BY length(path) DESC""", id=node_id)
        return [r["chain"] for r in res]


def aggregate_relations(node_ids: list[str], *, among: str = "Contribution") -> dict:
    """Count edge types within a node set — e.g. supports vs contradicts in a
    problem cluster, to read consensus."""
    with session() as s:
        res = s.run(f"""MATCH (a:{among})-[r]->(b:{among})
                        WHERE a.id IN $ids AND b.id IN $ids
                        RETURN type(r) AS rel, count(*) AS n""", ids=node_ids)
        return {r["rel"]: r["n"] for r in res}


def get(node_id: str) -> Optional[dict]:
    with session() as s:
        res = s.run("MATCH (n {id:$id}) RETURN n{.*, embedding:null} AS node, labels(n) AS labels",
                    id=node_id).single()
        return {**res["node"], "_labels": res["labels"]} if res else None


def claims_of(contrib_id: str) -> list[dict]:
    with session() as s:
        res = s.run("""MATCH (c:Claim)-[:SUPPORTS_CONTRIB]->(:Contribution {id:$id})
                       RETURN c{.*, embedding:null} AS c""", id=contrib_id)
        return [r["c"] for r in res]


def paper_index() -> list[dict]:
    """Lightweight (id, title) for every paper — used for ingest dedup."""
    with session() as s:
        return [{"id": r["id"], "title": r["title"]}
                for r in s.run("MATCH (p:Paper) RETURN p.id AS id, p.title AS title")]


def clear_contrib_edges(collection: str) -> int:
    """Delete all contribution↔contribution relations in a collection. Used before
    a re-load so edge re-orientation (changed src/dst direction) can't leave
    reversed duplicates behind. Leaves nodes, claims, and annotations intact."""
    with session() as s:
        return s.run("""MATCH (:Contribution {collection:$c})-[r]->(:Contribution {collection:$c})
                        DELETE r RETURN count(r) AS n""", c=collection).single()["n"]


def have_work(work_id: str) -> bool:
    """Is this WORK already in the graph under any source id/version?"""
    with session() as s:
        return s.run("MATCH (p:Paper {work_id:$w}) RETURN p LIMIT 1",
                     w=work_id).single() is not None


def have_paper(paper_id: str) -> bool:
    with session() as s:
        return s.run("MATCH (p:Paper {id:$id}) RETURN p LIMIT 1",
                     id=paper_id).single() is not None


def list_papers(collection: Optional[str] = None) -> list[dict]:
    where = "WHERE p.collection=$c" if collection else ""
    with session() as s:
        res = s.run(f"""MATCH (p:Paper) {where}
                       OPTIONAL MATCH (p)-[:HAS_CONTRIBUTION]->(k:Contribution)
                       OPTIONAL MATCH (c:Claim)-[:STATED_IN]->(p)
                       RETURN p{{.*}} AS p, count(DISTINCT k) AS nk, count(DISTINCT c) AS nc
                       ORDER BY p.year DESC""", c=collection)
        return [{k: v for k, v in r["p"].items() if k != "embedding"}
                | {"n_contributions": r["nk"], "n_claims": r["nc"]} for r in res]


def papers_meta(ids: list[str]) -> dict:
    """Map paper_id -> {title, url, doi, year, venue} for a set of ids.

    Used to turn the bare paper_ids that come back from vector search into real,
    citable references (clickable links) in chat answers."""
    ids = [i for i in dict.fromkeys(ids) if i]
    if not ids:
        return {}
    with session() as s:
        res = s.run(
            "MATCH (p:Paper) WHERE p.id IN $ids "
            "RETURN p.id AS id, p.title AS title, p.url AS url, p.doi AS doi, "
            "p.year AS year, p.venue AS venue", ids=ids)
        return {r["id"]: {"title": r["title"], "url": r["url"], "doi": r["doi"],
                          "year": r["year"], "venue": r["venue"]} for r in res}


def global_graph() -> dict:
    """Contribution nodes + contribution→contribution edges, for the top level."""
    with session() as s:
        nodes = [r["n"] for r in s.run(
            """MATCH (k:Contribution) OPTIONAL MATCH (p:Paper)-[:HAS_CONTRIBUTION]->(k)
               RETURN k{.id, .paper_id, .problem, .method, .result,
                       paper_year:p.year, paper_title:p.title} AS n""")]
        rels = set(GLOBAL_RELS)
        edges = []
        for i, r in enumerate(s.run(
            """MATCH (a:Contribution)-[e]->(b:Contribution)
               RETURN a.id AS src, b.id AS dst, type(e) AS rel,
                      e.source AS prov, e.confidence AS conf, e.evidence AS ev""")):
            if r["rel"] in rels:
                edges.append({"id": f"g{i}", "source": r["src"], "target": r["dst"],
                              "relation": r["rel"].lower(), "provenance": r["prov"],
                              "confidence": r["conf"], "evidence": r["ev"]})
    return {"nodes": nodes, "edges": edges}


def paper_local_graph(paper_id: str) -> Optional[dict]:
    with session() as s:
        p = s.run("MATCH (p:Paper {id:$id}) RETURN p{.*} AS p", id=paper_id).single()
        if not p:
            return None
        contribs = [r["k"] for r in s.run(
            "MATCH (:Paper {id:$id})-[:HAS_CONTRIBUTION]->(k:Contribution) "
            "RETURN k{.id, .problem, .method, .result} AS k", id=paper_id)]
        nodes = [r["c"] for r in s.run(
            "MATCH (c:Claim)-[:STATED_IN]->(:Paper {id:$id}) "
            "OPTIONAL MATCH (c)-[:SUPPORTS_CONTRIB]->(k:Contribution) "
            "RETURN c{.id, .text, .claim_type, .confidence, .evidence, "
            "contribution_id: k.id} AS c", id=paper_id)]
        loc = set(LOCAL_RELS)
        edges = []
        for i, r in enumerate(s.run(
            """MATCH (a:Claim)-[e]->(b:Claim)
               WHERE (a)-[:STATED_IN]->(:Paper {id:$id})
               RETURN a.id AS src, b.id AS dst, type(e) AS rel, e.evidence AS ev""",
            id=paper_id)):
            if r["rel"] in loc:
                edges.append({"id": f"l{i}", "source": r["src"], "target": r["dst"],
                              "relation": r["rel"].lower(), "evidence": r["ev"]})
        return {"paper": p["p"], "contributions": contribs, "nodes": nodes, "edges": edges}


def contribution_detail(contrib_id: str) -> Optional[dict]:
    k = get(contrib_id)
    if not k or "Contribution" not in k.get("_labels", []):
        return None
    return {**{x: k.get(x) for x in ("id", "paper_id", "problem", "method", "result")},
            "claims": claims_of(contrib_id),
            "neighbours": [{"src": e["node"]["id"] if False else contrib_id,
                            "rel": e["rel"], **e["props"], "other": e["node"]}
                           for e in neighbours(contrib_id, rels=GLOBAL_RELS)]}


def summary(collection: Optional[str] = None) -> dict:
    f = " {collection:$c}" if collection else ""
    with session() as s:
        def one(q): return s.run(q, c=collection).single()[0]
        return {
            "papers": one(f"MATCH (n:Paper{f}) RETURN count(n)"),
            "contributions": one(f"MATCH (n:Contribution{f}) RETURN count(n)"),
            "claims": one(f"MATCH (n:Claim{f}) RETURN count(n)"),
            "global_edges": one(f"MATCH (:Contribution{f})-[r]->(:Contribution{f}) RETURN count(r)"),
            "local_edges": one(f"MATCH (:Claim{f})-[r]->(:Claim{f}) RETURN count(r)"),
            "citations": one(f"MATCH (:Paper{f})-[r:CITES]->(:Paper{f}) RETURN count(r)"),
        }


def wipe() -> None:
    """Clear the literature graph but SPARE human annotations (they're costly to
    recreate and survive re-ingest)."""
    with session() as s:
        s.run("MATCH (n) WHERE NOT n:Annotation DETACH DELETE n")


# ── annotations (human verification — graph enrichment) ─────────────────────────
def upsert_annotation(annotator: str, target_kind: str, target_key: str, *,
                      faithful: str, issues: list[str], soundness: str,
                      note: str, created_at: str, confidence: float | None = None) -> None:
    """One upsertable annotation per (annotator, target). Two axes:
    `faithful` (correct/incorrect/unsure — did the pipeline extract it right) with
    `issues` (which fields are wrong, when incorrect), and `soundness`
    (sound/doubtful/implausible/contested/na — is the science itself sound, optional).
    `confidence` (optional 0-1) is the JUDGE's own confidence in its faithful verdict,
    distinct from the extractor's per-node confidence. Keyed by target_key — a node id,
    or 'srcId|RELATION|dstId' for an edge."""
    with session() as s:
        s.run("""MERGE (a:Annotation {id: $id})
                 SET a.annotator=$ann, a.target_kind=$kind, a.target_key=$key,
                     a.faithful=$faithful, a.issues=$issues, a.soundness=$soundness,
                     a.note=$note, a.created_at=$ts, a.confidence=$conf""",
              id=f"{annotator}|{target_key}", ann=annotator, kind=target_kind,
              key=target_key, faithful=faithful, issues=issues or [],
              soundness=soundness or "", note=note, ts=created_at, conf=confidence)


def annotations_for(target_key: str, *, viewer: str, see_others: bool) -> list[dict]:
    """All annotations on one target visible to `viewer` (own always; others only
    if see_others)."""
    with session() as s:
        res = s.run("""MATCH (a:Annotation {target_key:$key})
                       WHERE a.annotator=$me OR $others
                       RETURN a{.annotator,.faithful,.issues,.soundness,.note,.created_at,.confidence} AS a
                       ORDER BY a.created_at DESC""",
                    key=target_key, me=viewer, others=see_others)
        return [r["a"] for r in res]


def annotation_summaries(target_keys: list[str], *, viewer: str,
                         see_others: bool) -> dict[str, dict]:
    """Batched tally for a whole subgraph — ONE query for all keys. Returns
    {target_key: {n, correct, incorrect, unsure, mine}} (on the faithfulness axis)."""
    if not target_keys:
        return {}
    with session() as s:
        res = s.run("""UNWIND $keys AS k
                       OPTIONAL MATCH (a:Annotation {target_key:k})
                       WHERE a.annotator=$me OR $others
                       WITH k, collect(a) AS anns,
                            head([x IN collect(a) WHERE x.annotator=$me | x.faithful]) AS mine
                       RETURN k AS key, size(anns) AS n, mine AS mine,
                         size([x IN anns WHERE x.faithful='correct'])   AS correct,
                         size([x IN anns WHERE x.faithful='incorrect']) AS incorrect,
                         size([x IN anns WHERE x.faithful='unsure'])    AS unsure""",
                    keys=target_keys, me=viewer, others=see_others)
        return {r["key"]: {"n": r["n"], "correct": r["correct"],
                           "incorrect": r["incorrect"], "unsure": r["unsure"],
                           "mine": r["mine"]} for r in res}


def my_annotation_count(annotator: str) -> int:
    with session() as s:
        return s.run("MATCH (a:Annotation {annotator:$me}) RETURN count(a)",
                     me=annotator).single()[0]


def annotation_label_sets(judge: str = "claude") -> list[dict]:
    """Per target, the LLM judge's verdict vs all human verdicts — the basis for the
    self-eval / human / aggregated scorecard. Returns
    [{kind, key, judge: verdict|None, humans: [verdict, …]}]."""
    with session() as s:
        res = s.run("""MATCH (a:Annotation)
                       WITH a.target_kind AS kind, a.target_key AS key,
                            collect({who:a.annotator, v:a.faithful}) AS anns
                       RETURN kind, key,
                         head([x IN anns WHERE x.who=$j | x.v]) AS judge,
                         [x IN anns WHERE x.who<>$j | x.v] AS humans""", j=judge)
        return [{"kind": r["kind"], "key": r["key"], "judge": r["judge"],
                 "humans": [v for v in r["humans"] if v]} for r in res]


def annotation_agreement() -> dict:
    """Per-target faithfulness votes across ALL annotators (admin/eval). Returns
    the raw votes so callers compute majority / Cohen's kappa."""
    with session() as s:
        res = s.run("""MATCH (a:Annotation)
                       RETURN a.target_kind AS kind, a.target_key AS key,
                              collect(a.faithful) AS verdicts""")
        return {"items": [{"kind": r["kind"], "key": r["key"],
                           "verdicts": r["verdicts"]} for r in res]}
