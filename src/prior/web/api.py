"""Prior web API — serves the live Neo4j two-level graph + grounded Q&A.

Reads straight from Neo4j (via graph.py), so it reflects continuous ingestion in
real time — no atlas.json reload needed. Endpoints feed the React UI and double
as agent-callable web services (the graph tools are exposed directly).

Run:  prior serve     (or: uvicorn prior.web.api:app --reload)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .. import auth, config, graph

app = FastAPI(title="Prior API", version="0.3.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


# ── identity (username + token via headers) ─────────────────────────────────────
def _identity(user: Optional[str], token: Optional[str]) -> Optional[auth.Identity]:
    return auth.authenticate(user, token)


def _require(user: Optional[str], token: Optional[str]) -> auth.Identity:
    ident = auth.authenticate(user, token)
    if not ident:
        raise HTTPException(401, "Sign in: invalid username or token.")
    return ident


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
def _edge_key(e: dict) -> str:
    return f"{e['source']}|{e['relation'].upper()}|{e['target']}"


def _attach_annotations(g: dict, ident: Optional[auth.Identity]) -> None:
    """Merge batched annotation tallies into a graph payload's nodes & edges, in
    ONE query. No-op (empty) when not signed in."""
    if not ident:
        for x in g["nodes"] + g["edges"]:
            x["ann"] = None
        return
    keys = [n["id"] for n in g["nodes"]] + [_edge_key(e) for e in g["edges"]]
    summ = graph.annotation_summaries(
        keys, viewer=ident.user, see_others=auth.can_see_others(ident))
    for n in g["nodes"]:
        n["ann"] = summ.get(n["id"])
    for e in g["edges"]:
        e["ann"] = summ.get(_edge_key(e))


@app.get("/api/graph/global")
def global_graph(x_prior_user: Optional[str] = Header(None),
                 x_prior_password: Optional[str] = Header(None)) -> dict:
    g = graph.global_graph()
    for n in g["nodes"]:
        m = n.get("method") or ""
        n["label"] = (m[:60] + "…") if len(m) > 60 else m
        n["paper"] = n.get("paper_title") or n.get("paper_id")
        n["year"] = n.get("paper_year")
    _attach_annotations(g, _identity(x_prior_user, x_prior_password))
    return g


@app.get("/api/graph/paper/{paper_id:path}")
def local_graph(paper_id: str, x_prior_user: Optional[str] = Header(None),
                x_prior_password: Optional[str] = Header(None)) -> dict:
    g = graph.paper_local_graph(paper_id)
    if not g:
        raise HTTPException(404, f"Unknown paper {paper_id}")
    p = g["paper"]
    for n in g["nodes"]:
        n["label"] = n.get("text")
    g["paper"] = {"id": p["id"], "title": p.get("title"),
                  "cite": _cite(p), "url": p.get("url")}
    _attach_annotations(g, _identity(x_prior_user, x_prior_password))
    return g


@app.get("/api/contribution/{contrib_id:path}")
def contribution(contrib_id: str, x_prior_user: Optional[str] = Header(None),
                 x_prior_password: Optional[str] = Header(None)) -> dict:
    d = graph.contribution_detail(contrib_id)
    if not d:
        raise HTTPException(404, f"Unknown contribution {contrib_id}")
    ident = _identity(x_prior_user, x_prior_password)
    if ident:
        d["annotations"] = graph.annotations_for(
            contrib_id, viewer=ident.user, see_others=auth.can_see_others(ident))
    return d


# ── human annotation (verification → eval gold set) ─────────────────────────────
_FAITHFUL = {"correct", "incorrect", "unsure"}
_SOUNDNESS = {"", "sound", "doubtful", "implausible", "contested", "na"}


@app.get("/api/whoami")
def whoami(x_prior_user: Optional[str] = Header(None),
           x_prior_password: Optional[str] = Header(None)) -> dict:
    ident = _identity(x_prior_user, x_prior_password)
    if not ident:
        return {"signed_in": False, "shared": config.ANNOTATIONS_SHARED}
    return {"signed_in": True, "user": ident.user, "is_admin": ident.is_admin,
            "open_mode": ident.open_mode, "shared": config.ANNOTATIONS_SHARED,
            "annotated": graph.my_annotation_count(ident.user)}


class AnnotateBody(BaseModel):
    target_kind: str            # claim | contribution | edge
    target_key: str             # node id, or "src|REL|dst"
    faithful: str               # axis A: correct | incorrect | unsure
    issues: list[str] = []      # which fields are wrong (when incorrect)
    soundness: str = ""         # axis B: ""|sound|doubtful|implausible|contested|na
    note: str = ""


@app.post("/api/annotate")
def annotate(body: AnnotateBody, x_prior_user: Optional[str] = Header(None),
             x_prior_password: Optional[str] = Header(None)) -> dict:
    ident = _require(x_prior_user, x_prior_password)
    if body.faithful not in _FAITHFUL:
        raise HTTPException(422, f"faithful must be one of {sorted(_FAITHFUL)}")
    if body.soundness not in _SOUNDNESS:
        raise HTTPException(422, f"soundness must be one of {sorted(_SOUNDNESS)}")
    graph.upsert_annotation(ident.user, body.target_kind, body.target_key,
                            faithful=body.faithful, issues=body.issues,
                            soundness=body.soundness, note=body.note, created_at=_now())
    return {"ok": True, "annotated": graph.my_annotation_count(ident.user)}


@app.get("/api/annotations")
def annotations(target_key: str, x_prior_user: Optional[str] = Header(None),
                x_prior_password: Optional[str] = Header(None)) -> list[dict]:
    ident = _require(x_prior_user, x_prior_password)
    return graph.annotations_for(target_key, viewer=ident.user,
                                 see_others=auth.can_see_others(ident))


@app.get("/api/annotations/summary")
def annotations_summary(x_prior_user: Optional[str] = Header(None),
                        x_prior_password: Optional[str] = Header(None)) -> dict:
    """Cross-annotator agreement / coverage — admins only."""
    ident = _require(x_prior_user, x_prior_password)
    if not ident.is_admin:
        raise HTTPException(403, "admin only")
    return graph.annotation_agreement()


# ── on-demand ingestion (add a paper from the UI) ───────────────────────────────
@app.post("/api/ingest")
async def ingest(kind: str = Form(...), value: str = Form(""),
                 file: Optional[UploadFile] = File(None)) -> dict:
    """Start a background ingestion. kind ∈ arxiv | pdf_url | pdf_upload."""
    from .. import ingestion
    if kind not in ("arxiv", "pdf_url", "pdf_upload"):
        raise HTTPException(422, "kind must be arxiv | pdf_url | pdf_upload")
    content, filename = None, ""
    if kind == "pdf_upload":
        if not file:
            raise HTTPException(422, "no file uploaded")
        content, filename = await file.read(), file.filename or "upload.pdf"
    elif not value.strip():
        raise HTTPException(422, "value (arXiv id/URL or PDF URL) is required")
    job_id = ingestion.start(kind, value=value.strip(), content=content, filename=filename)
    return {"job_id": job_id}


@app.get("/api/ingest/{job_id}")
def ingest_status(job_id: str) -> dict:
    from .. import ingestion
    st = ingestion.job_status(job_id)
    if not st:
        raise HTTPException(404, "unknown job")
    return st


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


@app.get("/api/eval")
def eval_results() -> dict:
    """The scorecard for the /eval dashboard: saved LLM-metric run (if any) merged
    with live key-free graph distributions."""
    from .. import config, eval_suite
    live = {"graph": graph.summary(), "distributions": eval_suite.graph_distributions()}
    human = eval_suite.human_metrics()           # always fresh from annotations
    path = config.DATA / "eval" / "results.json"
    if path.exists():
        import json
        saved = json.loads(path.read_text())
        # keep saved LLM/key-free metrics; refresh the human ones live.
        metrics = [m for m in saved.get("metrics", []) if m.get("kind") != "human"] + human
        return {**saved, **live, "metrics": metrics,
                "gates": saved.get("gates", eval_suite.GATES)}
    # no saved run yet — live key-free faithfulness + the live human gold set.
    return {**live, "metrics": [eval_suite.faithfulness(str(config.DATA))] + human,
            "gates": eval_suite.GATES, "note": "no full run yet — `prior eval`"}


def _cite(p: dict) -> str:
    authors = p.get("authors") or []
    first = authors[0].split()[-1] if authors else "Anon"
    etal = " et al." if len(authors) > 1 else ""
    return f"{first}{etal} ({p.get('year') or 'n.d.'})"
