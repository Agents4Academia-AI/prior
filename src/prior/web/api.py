"""Prior web API — serves the two-level atlas + grounded Q&A to the UI.

These endpoints are the agent-callable web services from the design: a frontend
(or another agent) gets the global contribution graph, drills into a paper's
local claim graph, and asks the Navigator questions.

Run:  uvicorn prior.web.api:app --reload
The atlas is loaded from PRIOR_DATA_DIR/atlas/atlas.json (built by `prior build`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .. import config, navigator
from ..atlas import Atlas
from ..models import GLOBAL_RELATIONS, LOCAL_RELATIONS

app = FastAPI(title="Prior API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_atlas: Optional[Atlas] = None


def atlas() -> Atlas:
    global _atlas
    if _atlas is None:
        path = config.ATLAS / "atlas.json"
        if not path.exists():
            raise HTTPException(503, f"No atlas built yet (expected {path}).")
        _atlas = Atlas.load(path)
    return _atlas


# ── meta ──────────────────────────────────────────────────────────────────────
@app.get("/api/summary")
def summary() -> dict:
    a = atlas()
    return {
        "topic": a.topic,
        "papers": len(a.papers),
        "contributions": len(a.contributions),
        "claims": len(a.claims),
        "global_edges": sum(1 for e in a.edges if e.level == "global"),
        "local_edges": sum(1 for e in a.edges if e.level == "local"),
        "citations": sum(1 for e in a.edges if e.relation == "cites"),
    }


@app.post("/api/reload")
def reload() -> dict:
    """Reload atlas.json from disk (after a rebuild)."""
    global _atlas
    _atlas = None
    return summary()


@app.get("/api/papers")
def papers() -> list[dict]:
    a = atlas()
    return [{
        "id": p.id, "title": p.title, "year": p.year, "authors": p.authors[:5],
        "cite": p.short_cite(), "url": p.url,
        "n_contributions": len(a.contributions_for(p.id)),
        "n_claims": len(a.claims_for(p.id)),
    } for p in a.papers.values()]


# ── global graph (contributions) ───────────────────────────────────────────────
@app.get("/api/graph/global")
def global_graph() -> dict:
    """Contribution nodes + contribution→contribution edges, for the top level."""
    a = atlas()
    nodes = [{
        "id": k.id, "paper_id": k.paper_id,
        "label": (k.method[:60] + "…") if len(k.method) > 60 else k.method,
        "problem": k.problem, "method": k.method, "result": k.result,
        "paper": a.papers[k.paper_id].short_cite() if k.paper_id in a.papers else k.paper_id,
        "year": a.papers[k.paper_id].year if k.paper_id in a.papers else None,
    } for k in a.contributions.values()]
    edges = [{
        "id": f"g{i}", "source": e.src, "target": e.dst,
        "relation": e.relation, "provenance": e.source, "confidence": e.confidence,
        "evidence": e.evidence,
    } for i, e in enumerate(a.edges) if e.level == "global"]
    return {"nodes": nodes, "edges": edges}


# ── local graph (one paper's claims) ───────────────────────────────────────────
@app.get("/api/graph/paper/{paper_id:path}")
def local_graph(paper_id: str) -> dict:
    """Claim nodes + within-paper claim edges, plus the paper's contributions."""
    a = atlas()
    if paper_id not in a.papers:
        raise HTTPException(404, f"Unknown paper {paper_id}")
    claims = a.claims_for(paper_id)
    claim_ids = {c.id for c in claims}
    nodes = [{
        "id": c.id, "label": c.text, "claim_type": c.claim_type,
        "confidence": c.confidence, "evidence": c.evidence,
        "contribution_id": c.contribution_id,
    } for c in claims]
    edges = [{
        "id": f"l{i}", "source": e.src, "target": e.dst, "relation": e.relation,
        "evidence": e.evidence,
    } for i, e in enumerate(a.edges)
        if e.level == "local" and e.src in claim_ids and e.dst in claim_ids]
    contribs = [{
        "id": k.id, "problem": k.problem, "method": k.method, "result": k.result,
        "claim_ids": k.claim_ids,
    } for k in a.contributions_for(paper_id)]
    p = a.papers[paper_id]
    return {
        "paper": {"id": p.id, "title": p.title, "cite": p.short_cite(), "url": p.url},
        "contributions": contribs, "nodes": nodes, "edges": edges,
    }


@app.get("/api/contribution/{contrib_id:path}")
def contribution(contrib_id: str) -> dict:
    a = atlas()
    k = a.contributions.get(contrib_id)
    if not k:
        raise HTTPException(404, f"Unknown contribution {contrib_id}")
    neighbours = [{
        "src": e.src, "dst": e.dst, "relation": e.relation,
        "provenance": e.source, "confidence": e.confidence, "evidence": e.evidence,
    } for e in a.global_relations_of(contrib_id)]
    return {
        "id": k.id, "paper_id": k.paper_id, "problem": k.problem,
        "method": k.method, "result": k.result,
        "claims": [a.claims[cid].to_dict() for cid in k.claim_ids if cid in a.claims],
        "neighbours": neighbours,
    }


# ── grounded Q&A (Navigator) ───────────────────────────────────────────────────
class AskBody(BaseModel):
    question: str


class OriginBody(BaseModel):
    concept: str


@app.post("/api/ask")
def ask(body: AskBody) -> dict:
    ans = navigator.ask(atlas(), body.question)
    return {
        "verdict": ans.verdict, "answer": ans.answer,
        "supporting": ans.supporting, "contradicting": ans.contradicting,
        "open_questions": ans.open_questions, "closest": ans.closest, "gap": ans.gap,
        "used": [{"id": c.id, "text": c.text, "cite": _cite(c)} for c in ans.used],
    }


@app.post("/api/origin")
def origin(body: OriginBody) -> dict:
    ans = navigator.origin(atlas(), body.concept)
    return {
        "origin_paper": ans.origin_paper, "account": ans.account,
        "lineage": ans.lineage, "caveat": ans.caveat,
    }


def _cite(claim) -> str:
    a = atlas()
    p = a.papers.get(claim.paper_id)
    return p.short_cite() if p else claim.paper_id
