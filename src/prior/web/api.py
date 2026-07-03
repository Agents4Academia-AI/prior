"""Prior web API — serves the live Neo4j two-level graph + grounded Q&A.

Reads straight from Neo4j (via graph.py), so it reflects continuous ingestion in
real time — no atlas.json reload needed. Endpoints feed the React UI and double
as agent-callable web services (the graph tools are exposed directly).

Run:  prior serve     (or: uvicorn prior.web.api:app --reload)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel

from .. import auth, chat_store, config, graph

app = FastAPI(title="Prior API", version="0.3.0")


class _NoGzipForStream:
    """Strip Accept-Encoding for SSE so GZipMiddleware never buffers the stream.

    GZip on a text/event-stream response holds chunks back to compress them, which
    makes the browser sit on a spinner until the whole answer is done (it can't
    surface events incrementally). curl doesn't hit this because it doesn't send
    Accept-Encoding by default — only the browser does. We drop the header for the
    streaming path so the response goes out as plain, unbuffered chunks."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path", "").endswith("/ask_chat_stream"):
            scope = dict(scope)
            scope["headers"] = [(k, v) for (k, v) in scope["headers"]
                                if k.lower() != b"accept-encoding"]
        await self.app(scope, receive, send)


# gzip the (large) render payloads — ~735KB → ~150KB over the wire.
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
# Added last → outermost → runs before GZip, so SSE is never compressed.
app.add_middleware(_NoGzipForStream)


@app.on_event("startup")
def _warm_cache() -> None:
    """Pre-cluster the default collection so the first page load isn't cold."""
    try:
        from .. import render
        render.recluster(config.DEFAULT_COLLECTION)
    except Exception:  # noqa: BLE001 — never block startup
        pass


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
def _coll(collection: Optional[str]) -> str:
    return collection or config.DEFAULT_COLLECTION


@app.get("/api/collections")
def collections_list() -> dict:
    from .. import collections as colmod
    return {"collections": colmod.list_collections(), "default": config.DEFAULT_COLLECTION}


@app.get("/api/summary")
def summary(collection: Optional[str] = None) -> dict:
    from .. import collections as colmod
    c = _coll(collection)
    topic = next((x["topic"] for x in colmod.list_collections() if x["name"] == c), "")
    return {"collection": c, "topic": topic, **graph.summary(c)}


@app.get("/api/render/global")
def render_global(collection: Optional[str] = None, min_trust: float = 0.0,
                  max_nodes: int = 0, year_max: Optional[int] = None) -> dict:
    from .. import render
    return render.payload(_coll(collection), min_trust=min_trust,
                          max_nodes=max_nodes, year_max=year_max)


@app.get("/api/papers")
def papers(collection: Optional[str] = None) -> list[dict]:
    out = []
    for p in graph.list_papers(_coll(collection)):
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
                 force: bool = Form(False), collection: Optional[str] = Form(None),
                 file: Optional[UploadFile] = File(None)) -> dict:
    """Start a background ingestion. kind ∈ arxiv | pdf_url | pdf_upload. The paper
    is added to `collection` (default) and that collection is re-clustered on done.
    `force` overrides the version-duplicate guard (exact dups are always skipped)."""
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
    job_id = ingestion.start(kind, value=value.strip(), content=content,
                             filename=filename, force=force, collection=_coll(collection))
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


class ChatMessage(BaseModel):
    role: str
    content: str


class AskChatBody(BaseModel):
    # Either send `message` (the new user turn) with a `session_id`, or a full
    # `messages` list (back-compat). The server is the source of truth: it stores
    # every turn and rebuilds context from its own store.
    messages: Optional[list[ChatMessage]] = None
    message: Optional[str] = None
    session_id: Optional[str] = None
    collection: Optional[str] = None
    backend: Optional[str] = None    # "ollama" | "claude" (subscription) | "api"


def _chat_user(user: Optional[str], token: Optional[str]) -> str:
    """Owner for a chat. Sign-in is REQUIRED so every conversation maps to a real
    user (no anonymous bucket). In open dev mode (no users.json) any name counts."""
    ident = _identity(user, token)
    if not ident:
        raise HTTPException(401, "Sign in to use chat.")
    return ident.user


@app.post("/api/ask_chat")
def ask_chat(body: AskChatBody,
             x_prior_user: Optional[str] = Header(None),
             x_prior_password: Optional[str] = Header(None)) -> dict:
    """Graph-grounded chat, persisted server-side and owned by the user.

    `backend` picks the model path: "ollama" (local), "claude" (Max subscription via
    the CLI, API key scrubbed), or "api" (Anthropic key). The conversation is stored
    in chat_store, so it survives the browser and is retrievable from any device."""
    from .. import ask_agent
    user = _chat_user(x_prior_user, x_prior_password)

    # The new user turn: explicit `message`, else the last user msg in `messages`.
    new_text = (body.message or "").strip()
    if not new_text and body.messages:
        new_text = next((m.content for m in reversed(body.messages)
                         if m.role == "user"), "").strip()
    if not new_text:
        raise HTTPException(400, "Empty message.")

    sid = body.session_id or chat_store.create_session(user)["id"]
    # Persist the user turn first (also creates the session if new), then build
    # context from the durable store so the server owns the full history.
    chat_store.add_message(user, sid, "user", new_text)
    context = chat_store.history(user, sid)
    if not context:  # extreme fallback (store failed): use whatever the client sent
        context = [{"role": m.role, "content": m.content} for m in (body.messages or [])]

    try:
        res = ask_agent.chat(context, collection=body.collection, backend=body.backend)
    except RuntimeError as e:  # LLM backend / SDK runtime failure
        raise HTTPException(503, f"Ask agent unavailable: {e}")
    except Exception as e:  # noqa: BLE001 — readable error, not a bare 500
        raise HTTPException(500, f"Ask agent error: {e}")

    chat_store.add_message(user, sid, "assistant", res.get("answer", ""),
                           trace=res.get("trace"))
    return {**res, "session_id": sid}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@app.post("/api/ask_chat_stream")
def ask_chat_stream(body: AskChatBody,
                    x_prior_user: Optional[str] = Header(None),
                    x_prior_password: Optional[str] = Header(None),
                    x_anthropic_key: Optional[str] = Header(None)):
    """Streaming chat (Server-Sent Events). Emits `session` first, then `trace`
    (if it queried the graph), then `delta` chunks as the answer generates, then a
    final `done`. The full turn is persisted server-side once streaming completes."""
    from fastapi.responses import StreamingResponse

    from .. import ask_agent
    user = _chat_user(x_prior_user, x_prior_password)
    new_text = (body.message or "").strip()
    if not new_text and body.messages:
        new_text = next((m.content for m in reversed(body.messages)
                         if m.role == "user"), "").strip()
    if not new_text:
        raise HTTPException(400, "Empty message.")

    sid = body.session_id or chat_store.create_session(user)["id"]
    chat_store.add_message(user, sid, "user", new_text)
    context = chat_store.history(user, sid)

    def gen():
        yield _sse({"type": "session", "session_id": sid})
        answer, trace = "", []
        try:
            for ev in ask_agent.chat_stream(context, collection=body.collection,
                                            backend=body.backend, api_key=x_anthropic_key):
                if ev["type"] == "delta":
                    yield _sse(ev)
                elif ev["type"] == "trace":
                    trace = ev.get("trace") or trace
                    yield _sse(ev)
                elif ev["type"] == "done":
                    answer = ev.get("answer", "")
                    trace = ev.get("trace") or trace
            chat_store.add_message(user, sid, "assistant", answer, trace=trace)
            yield _sse({"type": "done", "session_id": sid, "trace": trace})
        except Exception as e:  # noqa: BLE001 — surface to the client as an event
            yield _sse({"type": "error", "error": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# ── chat history (durable, per-user) ─────────────────────────────────────────────
@app.get("/api/chats")
def chats_list(x_prior_user: Optional[str] = Header(None),
               x_prior_password: Optional[str] = Header(None)) -> dict:
    user = _chat_user(x_prior_user, x_prior_password)
    return {"user": user, "sessions": chat_store.list_sessions(user)}


@app.get("/api/chats/{sid}")
def chats_get(sid: str,
              x_prior_user: Optional[str] = Header(None),
              x_prior_password: Optional[str] = Header(None)) -> dict:
    user = _chat_user(x_prior_user, x_prior_password)
    sess = chat_store.get_session(user, sid)
    if not sess:
        raise HTTPException(404, "No such chat.")
    return sess


class RenameBody(BaseModel):
    title: str


@app.post("/api/chats/{sid}/rename")
def chats_rename(sid: str, body: RenameBody,
                 x_prior_user: Optional[str] = Header(None),
                 x_prior_password: Optional[str] = Header(None)) -> dict:
    user = _chat_user(x_prior_user, x_prior_password)
    if not chat_store.rename_session(user, sid, body.title):
        raise HTTPException(404, "No such chat.")
    return {"ok": True}


@app.delete("/api/chats/{sid}")
def chats_delete(sid: str,
                 x_prior_user: Optional[str] = Header(None),
                 x_prior_password: Optional[str] = Header(None)) -> dict:
    user = _chat_user(x_prior_user, x_prior_password)
    if not chat_store.delete_session(user, sid):
        raise HTTPException(404, "No such chat.")
    return {"ok": True}


@app.get("/api/eval")
def eval_results(collection: Optional[str] = None) -> dict:
    """Three-view scorecard (self-eval / human / aggregated) per dimension, live
    from the annotation store, plus graph distributions. Run the judge with
    `prior selfeval`; human numbers update as people annotate."""
    from .. import eval_suite, evaluation
    return {"summary": graph.summary(_coll(collection)),
            "scorecard": evaluation.scorecard(),
            "judges": evaluation.judges(),
            "calibration": evaluation.calibration(_coll(collection)),
            "distributions": eval_suite.graph_distributions()}


def _cite(p: dict) -> str:
    authors = p.get("authors") or []
    first = authors[0].split()[-1] if authors else "Anon"
    etal = " et al." if len(authors) > 1 else ""
    return f"{first}{etal} ({p.get('year') or 'n.d.'})"
