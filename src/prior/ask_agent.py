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
  Edges may carry: evidence, confidence, source, trust, tier, similarity.

How to work:
- PREFER querying the graph over guessing. Use search_claims for semantic lookup,
  graph_query for precise Cypher, get_paper / neighbours to expand.
- Cite by paper title and id, and by contribution/claim id, whenever you use a
  graph fact.
- Be honest when the graph does not contain the answer: say so, and name the
  closest thing it does contain.
- You MAY use general knowledge, but clearly mark it (e.g. "From general
  knowledge (not in the graph): ..."), and never present it as graph-grounded."""

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

    system = SCHEMA_DOC + "\n\n" + _TOOLS_DOC
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
    SCHEMA_DOC + "\n\n" + _TOOLS_DOC + "\n\n"
    "You work in a step loop. Each step, emit ONE action:\n"
    "  search_claims (use `query`, optional `k`)\n"
    "  search_contributions (use `query`, optional `k`)\n"
    "  graph_query (use `cypher`; READ-ONLY)\n"
    "  get_paper (use `id`)\n"
    "  neighbours (use `id` = a contribution id)\n"
    "  answer (use `answer` = your final, cited reply) — use this when ready.\n"
    "Gather evidence with a few tool steps first, then answer. Keep `thought`\n"
    "brief. Always finish with an `answer` action.")


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
                max_steps: int = ASK_MAX_STEPS) -> dict:
    convo = _flatten(messages)
    if collection:
        convo += f"\n\n(User is focused on the '{collection}' collection.)"

    trace: list[dict] = []
    scratch = ""
    for _ in range(max_steps):
        user = (f"CONVERSATION:\n{convo}\n\n"
                f"OBSERVATIONS SO FAR:\n{scratch or '(none yet)'}\n\n"
                "Emit your next step.")
        step = llm.structured(
            model=ASK_MODEL, system=_REACT_SYSTEM, user=user,
            schema=_STEP_SCHEMA, tool_name="emit_step", timeout=_TIMEOUT)
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
        model=ASK_MODEL,
        system=SCHEMA_DOC + "\n\nAnswer now from the observations; cite ids/titles.",
        user=f"CONVERSATION:\n{convo}\n\nOBSERVATIONS:\n{scratch}\n\n"
             "Give your final cited answer.",
        schema={"type": "object", "properties": {"answer": {"type": "string"}},
                "required": ["answer"]},
        tool_name="emit_answer", timeout=_TIMEOUT)
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
def chat(messages: list[dict], collection: Optional[str] = None) -> dict:
    """Multi-turn, graph-grounded chat. `messages` is OpenAI-style
    [{role, content}]. Returns {"answer", "used", "trace"}.

    Tries the Claude Agent SDK path first (true multi-turn tool use); if the SDK
    is not installed, falls back to a ReAct loop over llm.structured(). Both honour
    PRIOR_LLM_BACKEND (credit-free: claude-cli)."""
    if not messages:
        return {"answer": "", "used": [], "trace": []}
    try:
        return _chat_sdk(messages, collection)
    except ImportError:
        return _chat_react(messages, collection)
