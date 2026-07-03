"""Agentic Ask: a multi-turn chat grounded in the live Neo4j knowledge graph.

Unlike the one-shot Navigator (agent.ask), this lets the model DRIVE retrieval:
it can run read-only Cypher, do vector/semantic claim search, fetch a paper, and
expand a contribution's neighbourhood, across several turns, then answer. It MAY
also use general knowledge, but is told to keep that visibly separate from
graph-grounded facts.

Backends (selected by PRIOR_LLM_BACKEND, same as llm.py):
  - Preferred path: the Claude Agent SDK (claude_agent_sdk) with in-process,
    read-only MCP tools. This supports real multi-turn tool use. The SDK is
    imported lazily inside chat() because it may not be installed here.
  - Fallback path (when the SDK is unavailable): a minimal ReAct loop built on
    llm.structured(), which is backend-agnostic. The project's credit-free path
    is PRIOR_LLM_BACKEND=claude-cli (drives the interactive TUI, no API credits);
    "api" uses metered Anthropic API credits.

Public entry point:
    chat(messages, collection=None) -> {"answer", "used", "trace"}
where `messages` is OpenAI-style [{"role": "...", "content": "..."}].
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import os

from . import config, embeddings, graph, llm

_TIMEOUT = 180
# The agentic loop spawns one model call per reasoning step. Over the credit-free
# claude-cli backend each call is a fresh interactive session, so Opus here is very
# slow; default the loop to the faster Sonnet (override with PRIOR_ASK_MODEL) and
# keep the step budget small so a query returns in a sensible time.
ASK_MODEL = os.environ.get("PRIOR_ASK_MODEL", config.READER_MODEL)
ASK_MAX_STEPS = int(os.environ.get("PRIOR_ASK_MAX_STEPS", "4"))

# ── schema knowledge handed to the model (the "skill") ───────────────────────────
SCHEMA_DOC = """You are Prior's research assistant, grounded in a literature
knowledge graph about "agents for the scientific process" (LLM/AI agents applied
to research: ideation, experiment design, literature work, etc.).

The graph is Neo4j. Schema:
  Nodes:
    (:Paper {id, title, year, url, venue, authors, abstract, cited_by_count})
    (:Contribution {id, statement, kind, problem, method, result, quote,
                    confidence, collection, paper_id})
    (:Claim {id, text, claim_type, evidence, confidence, paper_id})
  Relationships:
    (:Paper)-[:HAS_CONTRIBUTION]->(:Contribution)
    (:Claim)-[:STATED_IN]->(:Paper)
    (:Claim)-[:SUPPORTS_CONTRIB]->(:Contribution)
    Between Contributions (global): BUILDS_ON, REFINES, CONTRADICTS, CONTRAST,
                                    SUPPORTS, MENTIONS
    Between Claims (local): ENTAILS, CONTRADICTS, SUPPORTS, DEPENDS_ON
    (:Paper)-[:CITES]->(:Paper)
  Edges may carry: evidence, confidence, source, trust, tier, similarity."""


# ── shared behaviour policy (used by EVERY backend / path) ────────────────────────
# This is the single place that tells the assistant *how to behave*. The fast path,
# the ReAct loop, and the Agent-SDK path all prepend SCHEMA_DOC + this policy, so the
# chatbot acts the same regardless of which model/backend is answering.
CHAT_POLICY = """How to answer:
- FIRST decide whether you can already answer well from the conversation so far plus
  your own knowledge and reasoning. Greetings, clarifications, definitions, general
  background, math, and follow-ups about something already discussed usually need NO
  graph lookup, just answer directly.
- Query the knowledge graph ONLY when the question needs specific facts from THIS
  corpus: which papers say X, who introduced Y, what contradicts Z, the details of a
  named paper/contribution/claim, counts, or comparisons across papers. Retrieve first,
  then answer.
- When you state a fact from the graph, cite it by paper title + id and by
  contribution/claim id. When you rely on general knowledge, label it plainly
  ("From general knowledge (not in the graph): ...") and never pass it off as grounded
  in the corpus.
- Be honest when the graph does not contain the answer: say so, and name the closest
  thing it does contain.
- Format answers in Markdown: short paragraphs, bullet points, **bold** key terms, and
  links where useful. Be concise and match the depth of the question, do not pad."""

_TOOLS_DOC = """Tools available (all READ-ONLY):
  search_claims(query, k=12) : semantic vector search over Claim nodes; returns
      top claims with ids, text, claim_type, paper_id.
  search_contributions(query, k=12) : same, over Contribution nodes (problem /
      method / result).
  graph_query(cypher) : run a single READ-ONLY Cypher query and get rows back.
      Writes are rejected (no CREATE/MERGE/DELETE/SET/REMOVE/DROP/etc).
  get_paper(id) : a paper's properties plus its contributions and claims.
  neighbours(contribution_id) : a contribution's 1-hop graph neighbours
      (BUILDS_ON / SUPPORTS / CONTRADICTS / ...)."""

# ── read-only Cypher guard ───────────────────────────────────────────────────────
_WRITE_KEYWORDS = (
    "CREATE", "MERGE", "DELETE", "SET", "REMOVE", "DROP", "DETACH",
    "LOAD", "CALL", "FOREACH", "USING", "GRANT", "REVOKE", "DENY",
    "START", "ALTER", "RENAME",
)
_WRITE_RE = re.compile(
    r"\b(" + "|".join(_WRITE_KEYWORDS) + r")\b", re.IGNORECASE)


def _is_read_only(cypher: str) -> bool:
    """Reject anything that could mutate the store or escape into procedures.
    Case-insensitive keyword guard; conservative (CALL is blocked too)."""
    if not cypher or not cypher.strip():
        return False
    # strip string literals so a keyword inside text isn't matched
    stripped = re.sub(r"'[^']*'|\"[^\"]*\"", "", cypher)
    return _WRITE_RE.search(stripped) is None


# ── tool implementations (backed by graph.py) ────────────────────────────────────
def _t_search_claims(query: str, k: int = 12) -> list[dict]:
    qv = embeddings.embed_one(query)
    hits = graph.ann(qv, label="Claim", k=int(k))
    return [{"id": h["id"], "text": h.get("text", ""),
             "claim_type": h.get("claim_type", ""), "paper_id": h.get("paper_id", ""),
             "score": round(float(h.get("_score", 0)), 3)} for h in hits]


def _t_search_contributions(query: str, k: int = 12) -> list[dict]:
    qv = embeddings.embed_one(query)
    hits = graph.ann(qv, label="Contribution", k=int(k))
    return [{"id": h["id"], "problem": h.get("problem", ""),
             "method": h.get("method", ""), "result": h.get("result", ""),
             "kind": h.get("kind", ""), "paper_id": h.get("paper_id", ""),
             "score": round(float(h.get("_score", 0)), 3)} for h in hits]


def _paper_url(pid: str, meta: Optional[dict] = None) -> str:
    """Best clickable URL for a paper: stored url, then DOI, else derived from the id
    prefix (arxiv:/openalex:). Empty string if nothing usable (e.g. uploaded PDFs)."""
    meta = meta or {}
    if meta.get("url"):
        return str(meta["url"])
    if meta.get("doi"):
        doi = str(meta["doi"])
        return doi if doi.startswith("http") else f"https://doi.org/{doi}"
    if pid.startswith("arxiv:"):
        return f"https://arxiv.org/abs/{pid.split(':', 1)[1]}"
    if pid.startswith("openalex:"):
        return f"https://openalex.org/{pid.split(':', 1)[1]}"
    return ""


def _sources_block(paper_ids: list[str]) -> tuple[str, list[dict]]:
    """Resolve paper_ids to title + clickable URL so the model can cite real links.
    Returns (text block for the prompt, [{id,title,url}] for the API response)."""
    meta = graph.papers_meta(paper_ids)
    lines, sources = [], []
    for pid in dict.fromkeys(paper_ids):
        if not pid:
            continue
        m = meta.get(pid, {})
        url = _paper_url(pid, m)
        title = (m.get("title") or pid).strip()
        year = m.get("year")
        label = title + (f" ({year})" if year else "")
        sources.append({"id": pid, "title": title, "url": url})
        lines.append(f"- {pid} | {label} | " + (url or "(no url available)"))
    return "\n".join(lines), sources


def _t_graph_query(cypher: str, limit: int = 50) -> dict:
    if not _is_read_only(cypher):
        return {"error": "rejected: query is not read-only (write keyword found)"}
    try:
        with graph.session() as s:
            res = s.run(cypher)
            rows = []
            for i, rec in enumerate(res):
                if i >= int(limit):
                    break
                # drop embeddings from any returned node maps to keep rows small
                rows.append({k: _scrub(v) for k, v in rec.data().items()})
        return {"rows": rows, "n": len(rows)}
    except Exception as e:  # noqa: BLE001 — surface as a tool error, not a crash
        return {"error": f"cypher failed: {e}"}


def _scrub(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _scrub(x) for k, x in v.items() if k != "embedding"}
    if isinstance(v, list):
        return [_scrub(x) for x in v]
    return v


def _t_get_paper(paper_id: str) -> dict:
    node = graph.get(paper_id)
    if not node or "Paper" not in node.get("_labels", []):
        return {"error": f"no Paper with id {paper_id}"}
    with graph.session() as s:
        contribs = [r["k"] for r in s.run(
            "MATCH (:Paper {id:$id})-[:HAS_CONTRIBUTION]->(k:Contribution) "
            "RETURN k{.id, .problem, .method, .result, .kind} AS k", id=paper_id)]
        claims = [r["c"] for r in s.run(
            "MATCH (c:Claim)-[:STATED_IN]->(:Paper {id:$id}) "
            "RETURN c{.id, .text, .claim_type} AS c", id=paper_id)]
    return {"paper": {k: v for k, v in node.items()
                      if k not in ("embedding", "_labels", "abstract")},
            "contributions": contribs, "claims": claims}


def _t_neighbours(contribution_id: str) -> list[dict]:
    out = []
    for n in graph.neighbours(contribution_id, rels=graph.GLOBAL_RELS):
        node = n["node"]
        out.append({"rel": n["rel"], "id": node.get("id"),
                    "method": node.get("method", ""), "problem": node.get("problem", ""),
                    "paper_id": node.get("paper_id", ""),
                    "confidence": (n.get("props") or {}).get("confidence")})
    return out


# ── Claude Agent SDK path (preferred; multi-turn in-process tools) ────────────────
def _chat_sdk(messages: list[dict], collection: Optional[str]) -> dict:
    """Multi-turn tool use via claude_agent_sdk in-process MCP tools. Imported
    lazily; raises ImportError if the SDK is not installed (caller falls back)."""
    import asyncio

    from claude_agent_sdk import (  # noqa: F401 — lazy import
        AssistantMessage, ClaudeAgentOptions, TextBlock, create_sdk_mcp_server,
        query, tool,
    )

    trace: list[dict] = []

    @tool("search_claims", "Semantic vector search over Claim nodes.",
          {"query": str, "k": int})
    async def search_claims(args):
        rows = _t_search_claims(args["query"], args.get("k", 12) or 12)
        trace.append({"tool": "search_claims", "args": args, "n": len(rows)})
        return {"content": [{"type": "text", "text": json.dumps(rows)}]}

    @tool("search_contributions", "Semantic vector search over Contribution nodes.",
          {"query": str, "k": int})
    async def search_contributions(args):
        rows = _t_search_contributions(args["query"], args.get("k", 12) or 12)
        trace.append({"tool": "search_contributions", "args": args, "n": len(rows)})
        return {"content": [{"type": "text", "text": json.dumps(rows)}]}

    @tool("graph_query", "Run a single READ-ONLY Cypher query (writes rejected).",
          {"cypher": str})
    async def graph_query(args):
        res = _t_graph_query(args["cypher"])
        trace.append({"tool": "graph_query", "args": args,
                      "n": res.get("n"), "error": res.get("error")})
        return {"content": [{"type": "text", "text": json.dumps(res)}]}

    @tool("get_paper", "Fetch a Paper with its contributions and claims.",
          {"id": str})
    async def get_paper(args):
        res = _t_get_paper(args["id"])
        trace.append({"tool": "get_paper", "args": args})
        return {"content": [{"type": "text", "text": json.dumps(res)}]}

    @tool("neighbours", "1-hop graph neighbours of a Contribution.",
          {"contribution_id": str})
    async def neighbours(args):
        rows = _t_neighbours(args["contribution_id"])
        trace.append({"tool": "neighbours", "args": args, "n": len(rows)})
        return {"content": [{"type": "text", "text": json.dumps(rows)}]}

    server = create_sdk_mcp_server(
        name="prior_graph", version="0.1.0",
        tools=[search_claims, search_contributions, graph_query, get_paper, neighbours])

    system = SCHEMA_DOC + "\n\n" + CHAT_POLICY + "\n\n" + _TOOLS_DOC
    if collection:
        system += f"\n\nThe user is focused on the '{collection}' collection."

    prompt = _flatten(messages)

    async def _go() -> str:
        opts = ClaudeAgentOptions(
            system_prompt=system,
            mcp_servers={"prior_graph": server},
            allowed_tools=[
                "mcp__prior_graph__search_claims",
                "mcp__prior_graph__search_contributions",
                "mcp__prior_graph__graph_query",
                "mcp__prior_graph__get_paper",
                "mcp__prior_graph__neighbours",
            ],
            max_turns=12,
            model=ASK_MODEL,
        )
        chunks: list[str] = []
        async for msg in query(prompt=prompt, options=opts):
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        chunks.append(block.text)
        return "".join(chunks).strip()

    answer = asyncio.run(_go())
    return {"answer": answer, "used": [], "trace": trace}


# ── fallback ReAct loop (backend-agnostic, via llm.structured) ────────────────────
_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "thought": {"type": "string"},
        "action": {"type": "string",
                   "enum": ["search_claims", "search_contributions",
                            "graph_query", "get_paper", "neighbours", "answer"]},
        "query": {"type": "string"},
        "cypher": {"type": "string"},
        "id": {"type": "string"},
        "k": {"type": "integer"},
        "answer": {"type": "string"},
    },
    "required": ["thought", "action"],
}

_REACT_SYSTEM = (
    SCHEMA_DOC + "\n\n" + CHAT_POLICY + "\n\n" + _TOOLS_DOC + "\n\n"
    "You work in a step loop. Each step, emit ONE action:\n"
    "  search_claims (use `query`, optional `k`)\n"
    "  search_contributions (use `query`, optional `k`)\n"
    "  graph_query (use `cypher`; READ-ONLY)\n"
    "  get_paper (use `id`)\n"
    "  neighbours (use `id` = a contribution id)\n"
    "  answer (use `answer` = your final, cited reply) — use this when ready.\n"
    "Per the policy above, if you can already answer without the graph, emit `answer`\n"
    "immediately. Otherwise gather just the evidence you need, then answer. Keep\n"
    "`thought` brief. Always finish with an `answer` action.")


def _run_action(step: dict) -> Any:
    act = step.get("action")
    if act == "search_claims":
        return _t_search_claims(step.get("query", ""), step.get("k", 12) or 12)
    if act == "search_contributions":
        return _t_search_contributions(step.get("query", ""), step.get("k", 12) or 12)
    if act == "graph_query":
        return _t_graph_query(step.get("cypher", ""))
    if act == "get_paper":
        return _t_get_paper(step.get("id", ""))
    if act == "neighbours":
        return _t_neighbours(step.get("id", ""))
    return None


def _chat_react(messages: list[dict], collection: Optional[str],
                max_steps: int = ASK_MAX_STEPS, backend: Optional[str] = None) -> dict:
    convo = _flatten(messages)
    if collection:
        convo += f"\n\n(User is focused on the '{collection}' collection.)"
    model = _model_for(backend)

    trace: list[dict] = []
    scratch = ""
    for _ in range(max_steps):
        user = (f"CONVERSATION:\n{convo}\n\n"
                f"OBSERVATIONS SO FAR:\n{scratch or '(none yet)'}\n\n"
                "Emit your next step.")
        step = llm.structured(
            model=model, system=_REACT_SYSTEM, user=user,
            schema=_STEP_SCHEMA, tool_name="emit_step", timeout=_TIMEOUT, backend=backend)
        act = step.get("action")
        if act == "answer":
            trace.append({"tool": "answer", "thought": step.get("thought", "")})
            return {"answer": step.get("answer", ""), "used": [], "trace": trace}
        obs = _run_action(step)
        n = len(obs) if isinstance(obs, list) else (obs.get("n") if isinstance(obs, dict) else None)
        trace.append({"tool": act, "args": {k: step.get(k) for k in
                      ("query", "cypher", "id", "k") if step.get(k)}, "n": n})
        obs_json = json.dumps(obs)[:4000]
        scratch += f"\n[{act}] {obs_json}"

    # ran out of steps: force a final answer from what we gathered
    final = llm.structured(
        model=model,
        system=SCHEMA_DOC + "\n\nAnswer now from the observations; cite ids/titles.",
        user=f"CONVERSATION:\n{convo}\n\nOBSERVATIONS:\n{scratch}\n\n"
             "Give your final cited answer.",
        schema={"type": "object", "properties": {"answer": {"type": "string"}},
                "required": ["answer"]},
        tool_name="emit_answer", timeout=_TIMEOUT, backend=backend)
    return {"answer": final.get("answer", ""), "used": [], "trace": trace}


# ── helpers ──────────────────────────────────────────────────────────────────────
def _flatten(messages: list[dict]) -> str:
    """OpenAI-style messages -> a single readable transcript for the model."""
    lines = []
    for m in messages:
        role = (m.get("role") or "user").upper()
        lines.append(f"{role}: {m.get('content', '')}")
    return "\n\n".join(lines)


# ── public entry point ───────────────────────────────────────────────────────────
_FAST_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "verdict": {"type": "string", "enum": ["established", "contested", "emerging", "not_found"]},
    },
    "required": ["answer"],
}


# Map the chat UI's backend choice to an llm.py backend (and pick an appropriate model).
# "claude" -> claude-p (headless `claude -p`): ~4s/call and, with the API key scrubbed
# from its subprocess, runs on the OAuth/Max subscription. The interactive-TUI path
# (claude-cli) is ~45s/call because it cold-starts the TUI and shuffles files; keep it
# only as an explicit opt-in fallback.
_BACKEND_MAP = {
    "ollama": "openai", "vllm": "openai", "local": "openai", "openai": "openai",
    "claude": "claude-p", "claude-p": "claude-p", "subscription": "claude-p",
    "claude-cli": "claude-cli",
    "api": "api", "agent-sdk": "api", "sdk": "api", "anthropic": "api",
}


def _resolve_backend(choice: Optional[str]) -> Optional[str]:
    return _BACKEND_MAP.get((choice or "").lower()) if choice else None


def _model_for(bk: Optional[str]) -> str:
    if bk in ("openai", "vllm", "ollama"):
        return os.environ.get("PRIOR_LOCAL_MODEL", "qwen3:14b")
    return ASK_MODEL


_ROUTER_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_graph": {"type": "boolean",
                        "description": "true only if answering needs specific facts from the corpus"},
        "search_queries": {"type": "array", "items": {"type": "string"},
                           "description": "1-3 short search phrases; only when needs_graph is true"},
        "answer": {"type": "string",
                   "description": "your full Markdown answer; fill this when needs_graph is false"},
    },
    "required": ["needs_graph"],
}


def _chat_fast(messages: list[dict], collection: Optional[str] = None,
               backend: Optional[str] = None) -> dict:
    """Decide-then-retrieve, honouring the shared CHAT_POLICY.

    One model call decides: if the question can be answered from context + the model's
    own knowledge, it answers there (1 round-trip, snappy). Only if it needs corpus
    facts does it ask for searches, which we run, then answer with that evidence
    (2 round-trips). `backend` overrides PRIOR_LLM_BACKEND for the call."""
    model = _model_for(backend)
    convo = _flatten(messages)
    if collection:
        convo += f"\n\n(User is focused on the '{collection}' collection.)"

    route = llm.structured(
        model=model,
        system=SCHEMA_DOC + "\n\n" + CHAT_POLICY + "\n\n"
        "Apply the policy and decide now. Set needs_graph=true ONLY if a good answer "
        "needs specific facts from the corpus; then give 1-3 `search_queries` and do "
        "NOT answer yet. Otherwise set needs_graph=false and put your full Markdown "
        "reply in `answer`.",
        user=f"CONVERSATION:\n{convo}\n\nDecide and respond.",
        schema=_ROUTER_SCHEMA, tool_name="route", timeout=_TIMEOUT, backend=backend)

    if not route.get("needs_graph") and (route.get("answer") or "").strip():
        return {"answer": route["answer"], "used": [],
                "trace": [{"tool": "direct", "args": {}, "n": 0}]}

    # Needs the graph (or the router skipped the direct answer): retrieve, then answer.
    q = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    queries = [s for s in (route.get("search_queries") or []) if s.strip()] or [q]
    claims, contribs, seen_c, seen_k = [], [], set(), set()
    for sq in queries[:3]:
        for c in _t_search_claims(sq, k=8):
            if c["id"] not in seen_c:
                seen_c.add(c["id"]); claims.append(c)
        for k in _t_search_contributions(sq, k=5):
            if k["id"] not in seen_k:
                seen_k.add(k["id"]); contribs.append(k)
    evidence = ("CLAIMS:\n" + json.dumps(claims)[:3500]
                + "\n\nCONTRIBUTIONS:\n" + json.dumps(contribs)[:2500])
    out = llm.structured(
        model=model,
        system=SCHEMA_DOC + "\n\n" + CHAT_POLICY + "\n\n"
        "Answer the user's question using the EVIDENCE below (retrieved from the corpus "
        "for this turn). Cite the ids/titles you use.",
        user=f"CONVERSATION:\n{convo}\n\nEVIDENCE:\n{evidence}\n\nGive your cited, well-formatted answer.",
        schema=_FAST_SCHEMA, tool_name="emit_answer", timeout=_TIMEOUT, backend=backend)
    used = [{"id": c.get("id"), "text": (c.get("text", "") or "")[:160]} for c in claims[:6]]
    qlabel = "; ".join(queries[:3])
    trace = [{"tool": "search_claims", "args": {"query": qlabel}, "n": len(claims)},
             {"tool": "search_contributions", "args": {"query": qlabel}, "n": len(contribs)}]
    return {"answer": out.get("answer", ""), "used": used, "trace": trace}


def chat(messages: list[dict], collection: Optional[str] = None,
         backend: Optional[str] = None) -> dict:
    """Graph-grounded chat. `messages` is OpenAI-style [{role, content}]. Returns
    {"answer", "used", "trace"}.

    `backend` is the chat UI's pick: "ollama" (local model via OpenAI endpoint),
    "claude" (Max subscription via the interactive CLI, API key scrubbed), or "api"
    (Anthropic SDK / API key, pay-per-token). It overrides PRIOR_LLM_BACKEND for the call.

    Default is the FAST path: retrieve in Python, answer in one LLM call (snappy). Set
    PRIOR_ASK_AGENTIC=1 for the multi-step agent that drives its own retrieval."""
    if not messages:
        return {"answer": "", "used": [], "trace": []}
    import time as _time
    bk = _resolve_backend(backend)
    agentic = os.environ.get("PRIOR_ASK_AGENTIC", "").lower() in ("1", "true", "yes")
    q = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    t0 = _time.time()
    print(f"[ask_chat] start backend={bk or 'env-default'} model={_model_for(bk)} "
          f"mode={'agentic' if agentic else 'fast'} q={q[:90]!r}", flush=True)
    try:
        if agentic:
            try:
                res = _chat_sdk(messages, collection)
            except ImportError:
                res = _chat_react(messages, collection, backend=bk)
        else:
            res = _chat_fast(messages, collection, backend=bk)
    except Exception as e:  # noqa: BLE001
        print(f"[ask_chat] ERROR after {_time.time()-t0:.1f}s: {e}", flush=True)
        raise
    tools = ", ".join(f"{t.get('tool')}({t.get('n')})" for t in res.get("trace", []))
    print(f"[ask_chat] done in {_time.time()-t0:.1f}s | tools=[{tools}] "
          f"| answer={len(res.get('answer',''))} chars", flush=True)
    return res


_ROUTER_SYSTEM = (
    SCHEMA_DOC + "\n\n" + CHAT_POLICY + "\n\n"
    "Apply the policy and decide now. Set needs_graph=true ONLY if a good answer needs "
    "specific facts from the corpus; then give 1-3 `search_queries` and do NOT answer "
    "yet. Otherwise set needs_graph=false and put your full Markdown reply in `answer`.")


def chat_stream(messages: list[dict], collection: Optional[str] = None,
                backend: Optional[str] = None, api_key: Optional[str] = None):
    """Streaming variant of the fast chat. Same decide-then-retrieve policy, but the
    final answer is streamed token-by-token. Yields event dicts:
        {"type": "trace", "trace": [...]}   graph queries that ran (graph path only)
        {"type": "delta", "text": "..."}    a chunk of the answer
        {"type": "done",  "answer": "...", "trace": [...]}
    The router (decision) is a single fast structured call; only the answer streams."""
    import time as _time
    bk = _resolve_backend(backend)
    model = _model_for(bk)
    convo = _flatten(messages)
    if collection:
        convo += f"\n\n(User is focused on the '{collection}' collection.)"
    q = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    t0 = _time.time()
    print(f"[ask_stream] start backend={bk or 'env-default'} model={model} q={q[:90]!r}", flush=True)

    # 1) Decide (fast, structured). May also carry a direct answer for non-graph Qs.
    route = llm.structured(
        model=model, system=_ROUTER_SYSTEM,
        user=f"CONVERSATION:\n{convo}\n\nDecide and respond.",
        schema=_ROUTER_SCHEMA, tool_name="route", timeout=_TIMEOUT, backend=bk, api_key=api_key)

    if not route.get("needs_graph") and (route.get("answer") or "").strip():
        ans = route["answer"]
        yield {"type": "delta", "text": ans}
        yield {"type": "done", "answer": ans, "trace": [{"tool": "direct", "args": {}, "n": 0}]}
        print(f"[ask_stream] direct in {_time.time()-t0:.1f}s | {len(ans)} chars", flush=True)
        return

    # 2) Retrieve the evidence the model asked for, announce it, then stream the answer.
    queries = [s for s in (route.get("search_queries") or []) if s.strip()] or [q]
    claims, contribs, seen_c, seen_k = [], [], set(), set()
    for sq in queries[:3]:
        for c in _t_search_claims(sq, k=8):
            if c["id"] not in seen_c:
                seen_c.add(c["id"]); claims.append(c)
        for k in _t_search_contributions(sq, k=5):
            if k["id"] not in seen_k:
                seen_k.add(k["id"]); contribs.append(k)
    qlabel = "; ".join(queries[:3])
    trace = [{"tool": "search_claims", "args": {"query": qlabel}, "n": len(claims)},
             {"tool": "search_contributions", "args": {"query": qlabel}, "n": len(contribs)}]
    yield {"type": "trace", "trace": trace}

    paper_ids = [c.get("paper_id", "") for c in claims] + [k.get("paper_id", "") for k in contribs]
    papers_block, _sources = _sources_block(paper_ids)
    evidence = ("PAPERS (cite these as Markdown links — format: [Title](url)):\n" + papers_block
                + "\n\nCLAIMS:\n" + json.dumps(claims)[:3500]
                + "\n\nCONTRIBUTIONS:\n" + json.dumps(contribs)[:2500])
    sys = (SCHEMA_DOC + "\n\n" + CHAT_POLICY + "\n\n"
           "Answer the user's question using the EVIDENCE below (retrieved from the "
           "corpus for this turn). When you name a paper, link it as [Title](url) using "
           "the url from the PAPERS list. If a paper has '(no url available)', cite it by "
           "title + id without a link. Never invent a url.")
    usr = (f"CONVERSATION:\n{convo}\n\nEVIDENCE:\n{evidence}\n\n"
           "Give your cited, well-formatted Markdown answer.")
    acc: list[str] = []
    for chunk in llm.stream_text(model=model, system=sys, user=usr, backend=bk,
                                 timeout=_TIMEOUT, api_key=api_key):
        acc.append(chunk)
        yield {"type": "delta", "text": chunk}
    answer = "".join(acc)
    yield {"type": "done", "answer": answer, "trace": trace}
    print(f"[ask_stream] graph in {_time.time()-t0:.1f}s | tools={[t['tool'] for t in trace]} "
          f"| {len(answer)} chars", flush=True)
