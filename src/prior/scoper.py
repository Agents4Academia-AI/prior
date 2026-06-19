"""Scoper agent: turn a topic into a CLEAN, relevant corpus.

Relevance search over a topic pulls in highly-cited but off-topic papers (tools
that merely contain "automated", adjacent subfields, etc.). The Scoper works in
two stages — recall then precision:

  1. propose_queries  — LLM turns a one-line topic definition into search queries
  2. gather_candidates — multi-seed OpenAlex/arXiv → candidate pool
  3. scope            — LLM judges each candidate against the topic's include /
                        exclude criteria, keeping only in-scope primary papers

A precise topic definition (what's IN and what's OUT) is the key input — that's
what lets the filter reject "ChatGPT in the classroom" when the topic is "agents
that do research tasks".
"""

from __future__ import annotations

from . import config, llm
from .models import Paper
from .sources import arxiv, openalex

# ── stage 1: propose search queries ──────────────────────────────────────────
_Q_SYSTEM = """You design literature-search queries. Given a research topic with
its scope, output 6–10 diverse OpenAlex/arXiv keyword queries that together give
broad recall over the topic — vary the phrasing, name key methods/subareas, and
avoid queries so generic they'd pull in unrelated highly-cited tools."""

_Q_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
}


def propose_queries(topic_def: str, *, model: str | None = None) -> list[str]:
    out = llm.structured(
        model=model or config.READER_MODEL, system=_Q_SYSTEM,
        user=f"TOPIC:\n{topic_def}", schema=_Q_SCHEMA, tool_name="emit_queries")
    return [q.strip() for q in out.get("queries", []) if q.strip()]


# ── stage 2: gather candidates (recall) ──────────────────────────────────────
def gather_candidates(queries: list[str], *, per_query: int = 25,
                      use_arxiv: bool = True, progress=print) -> list[Paper]:
    papers: dict[str, Paper] = {}
    for q in queries:
        for p in openalex.search(q, max_papers=per_query):
            papers.setdefault(p.id, p)
        if use_arxiv:
            for p in arxiv.search(q, max_papers=max(4, per_query // 5)):
                papers.setdefault(p.id, p)
        progress(f"  query '{q[:50]}' → pool now {len(papers)}")
    return list(papers.values())


# ── stage 3: relevance filter (precision) ────────────────────────────────────
_S_SYSTEM = """You are the Scoper. Decide whether each candidate paper is IN SCOPE
for the given topic, judging only from its title + abstract. Honour the topic's
inclusion and exclusion criteria exactly. Be strict: a paper that is merely
adjacent — same buzzwords, neighbouring subfield, a tool that just mentions the
terms — is OUT of scope. For each candidate return in_scope (true/false) and a
one-line reason."""

_S_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "in_scope": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "in_scope", "reason"],
            },
        }
    },
    "required": ["decisions"],
}


def scope(topic_def: str, candidates: list[Paper], *, model: str | None = None,
          batch: int = 12, progress=print) -> tuple[list[tuple[Paper, str]],
                                                     list[tuple[Paper, str]]]:
    """Return (kept, dropped), each a list of (paper, reason)."""
    kept: list[tuple[Paper, str]] = []
    dropped: list[tuple[Paper, str]] = []
    for i in range(0, len(candidates), batch):
        chunk = candidates[i:i + batch]
        listing = "\n".join(
            f"[{j}] {p.title}\n    {p.abstract[:320]}" for j, p in enumerate(chunk))
        out = llm.structured(
            model=model or config.READER_MODEL, system=_S_SYSTEM,
            user=f"TOPIC:\n{topic_def}\n\nCANDIDATES:\n{listing}",
            schema=_S_SCHEMA, tool_name="emit_scope", max_tokens=2000)
        dec = {d["index"]: d for d in out.get("decisions", [])
               if isinstance(d.get("index"), int)}
        for j, p in enumerate(chunk):
            d = dec.get(j, {"in_scope": False, "reason": "no decision returned"})
            (kept if d.get("in_scope") else dropped).append((p, d.get("reason", "")))
        progress(f"  scored {min(i + batch, len(candidates))}/{len(candidates)} "
                 f"— kept {len(kept)}")
    return kept, dropped


def build_scoped_corpus(topic_def: str, *, per_query: int = 25,
                        model: str | None = None, progress=print
                        ) -> tuple[list[Paper], list[tuple[Paper, str]]]:
    """Full Scoper run: topic → queries → candidates → scoped corpus.
    Returns (kept_papers, dropped_with_reasons)."""
    progress("[1/3] proposing queries ...")
    queries = propose_queries(topic_def, model=model)
    progress(f"      {len(queries)} queries")
    progress("[2/3] gathering candidates ...")
    candidates = gather_candidates(queries, per_query=per_query, progress=progress)
    progress(f"      {len(candidates)} candidates")
    progress("[3/3] scoping (relevance filter) ...")
    kept, dropped = scope(topic_def, candidates, model=model, progress=progress)
    progress(f"      kept {len(kept)} / dropped {len(dropped)}")
    return [p for p, _ in kept], dropped
