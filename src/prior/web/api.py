"""Prior web API — serves the live Neo4j two-level graph + grounded Q&A.

Reads straight from Neo4j (via graph.py), so it reflects continuous ingestion in
real time — no atlas.json reload needed. Endpoints feed the React UI and double
as agent-callable web services (the graph tools are exposed directly).

Run:  prior serve     (or: uvicorn prior.web.api:app --reload)
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .. import graph

app = FastAPI(title="Prior API", version="0.2.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ── meta ──────────────────────────────────────────────────────────────────────
@app.get("/api/summary")
def summary() -> dict:
    return {"topic": "", **graph.summary()}


@app.get("/api/papers")
def papers() -> list[dict]:
    out = []
    for p in graph.list_papers():
        authors = p.get("authors") or []
        out.append({
            "id": p["id"], "title": p.get("title"), "year": p.get("year"),
            "authors": authors[:5] if isinstance(authors, list) else [],
            "cite": _cite(p), "url": p.get("url"),
            "n_contributions": p.get("n_contributions", 0),
            "n_claims": p.get("n_claims", 0),
        })
    return out


# ── graph views ────────────────────────────────────────────────────────────────
@app.get("/api/graph/global")
def global_graph() -> dict:
    g = graph.global_graph()
    for n in g["nodes"]:
        m = n.get("method") or ""
        n["label"] = (m[:60] + "…") if len(m) > 60 else m
        n["paper"] = n.get("paper_title") or n.get("paper_id")
        n["year"] = n.get("paper_year")
    return g


@app.get("/api/graph/paper/{paper_id:path}")
def local_graph(paper_id: str) -> dict:
    g = graph.paper_local_graph(paper_id)
    if not g:
        raise HTTPException(404, f"Unknown paper {paper_id}")
    p = g["paper"]
    for n in g["nodes"]:
        n["label"] = n.get("text")
    g["paper"] = {"id": p["id"], "title": p.get("title"),
                  "cite": _cite(p), "url": p.get("url")}
    return g


@app.get("/api/contribution/{contrib_id:path}")
def contribution(contrib_id: str) -> dict:
    d = graph.contribution_detail(contrib_id)
    if not d:
        raise HTTPException(404, f"Unknown contribution {contrib_id}")
    return d


# ── agent-callable graph tools ──────────────────────────────────────────────────
class SearchBody(BaseModel):
    query: str
    label: str = "Contribution"
    k: int = 10


@app.post("/api/search")
def search(body: SearchBody) -> list[dict]:
    """Vector search — the agent's entry point into the graph."""
    from .. import embeddings
    return graph.ann(embeddings.embed_one(body.query), label=body.label, k=body.k)


@app.get("/api/neighbours/{node_id:path}")
def neighbours(node_id: str) -> list[dict]:
    return graph.neighbours(node_id)


@app.get("/api/traverse/{node_id:path}")
def traverse(node_id: str, rel: str = "BUILDS_ON", depth: int = 4) -> list[list[dict]]:
    return graph.traverse(node_id, rel=rel, max_depth=depth)


# ── grounded Q&A (graph-backed agent) ───────────────────────────────────────────
class AskBody(BaseModel):
    question: str


class SolvedBody(BaseModel):
    problem: str


@app.post("/api/ask")
def ask(body: AskBody) -> dict:
    from .. import agent
    return agent.ask(body.question).to_dict()


@app.post("/api/solved")
def solved(body: SolvedBody) -> dict:
    from .. import agent
    return agent.has_been_solved(body.problem).to_dict()


def _cite(p: dict) -> str:
    authors = p.get("authors") or []
    first = authors[0].split()[-1] if authors else "Anon"
    etal = " et al." if len(authors) > 1 else ""
    return f"{first}{etal} ({p.get('year') or 'n.d.'})"
