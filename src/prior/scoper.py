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

import json
import re
from pathlib import Path

from . import config, llm
from .models import Paper
from .sources import arxiv, openalex, semanticscholar

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
def _dedup_cross_source(papers: list[Paper]) -> list[Paper]:
    """Collapse the same paper arriving from different sources (OpenAlex / arXiv /
    S2) by normalised title, preferring OpenAlex (it carries the citation graph
    the snowball needs), then arXiv, then S2. Papers with no usable title pass
    through untouched. This avoids double-processing without capping recall."""
    rank = {"openalex": 0, "arxiv": 1, "semanticscholar": 2}
    by_title: dict[str, Paper] = {}
    out: list[Paper] = []
    for p in papers:
        key = " ".join(re.sub(r"[^a-z0-9]", " ", (p.title or "").lower()).split())
        if len(key) < 8:
            out.append(p)
            continue
        cur = by_title.get(key)
        if cur is None or rank.get(p.source, 9) < rank.get(cur.source, 9):
            by_title[key] = p
    return out + list(by_title.values())


def gather_candidates(queries: list[str], *, per_query: int = 25,
                      use_arxiv: bool = True, use_s2: bool = True,
                      progress=print) -> list[Paper]:
    """Resilient multi-source recall: OpenAlex + arXiv + Semantic Scholar. A
    source that errors (rate-limit, timeout) on one query is skipped, not fatal;
    arXiv and S2 are paced to respect their public limits. Cross-source
    duplicates are collapsed by title at the end."""
    import time
    papers: dict[str, Paper] = {}
    for q in queries:
        try:
            for p in openalex.search(q, max_papers=per_query):
                papers.setdefault(p.id, p)
        except Exception as e:  # noqa: BLE001
            progress(f"  openalex error on '{q[:40]}': {e}")
        if use_arxiv:
            try:
                for p in arxiv.search(q, max_papers=max(4, per_query // 5)):
                    papers.setdefault(p.id, p)
                time.sleep(1.0)   # be polite to arXiv
            except Exception as e:  # noqa: BLE001
                progress(f"  arxiv skip '{q[:40]}': {e}")
        if use_s2:
            try:
                for p in semanticscholar.search(q, max_papers=max(6, per_query // 2)):
                    papers.setdefault(p.id, p)
                time.sleep(1.1)   # S2 public pool is throttled
            except Exception as e:  # noqa: BLE001
                progress(f"  s2 skip '{q[:40]}': {e}")
        progress(f"  query '{q[:50]}' → pool now {len(papers)}")
    return _dedup_cross_source(list(papers.values()))


# ── stage 2b: citation snowball (recall, the high-leverage step) ─────────────
def snowball(seeds: list[Paper], *, anchor_k: int = 25, per_paper: int = 40,
             progress=print) -> list[Paper]:
    """One-hop citation expansion of a seed set (OpenAlex): backward references
    of all seeds + forward cited-by of the most-cited anchors. Finds the
    connected cluster that keyword search misses. Returns NEW candidate papers
    (not already among the seeds)."""
    have = {p.id for p in seeds}
    new: dict[str, Paper] = {}

    # backward — union of references (they overlap heavily, so the set is bounded)
    refs = list(dict.fromkeys(
        r for p in seeds for r in p.referenced_works
        if r.startswith("openalex:") and r not in have))
    for pid, p in openalex.fetch_many(refs).items():
        if pid not in have:
            new.setdefault(pid, p)
    progress(f"  backward: {len(refs)} refs → +{len(new)} new")

    # forward — cited-by of the most-cited anchors (catches newer connected work)
    anchors = sorted((p for p in seeds if p.id.startswith("openalex:")),
                     key=lambda p: -p.cited_by_count)[:anchor_k]
    for p in anchors:
        for cp in openalex.cited_by(p.id, max_results=per_paper):
            if cp.id not in have and cp.id not in new:
                new[cp.id] = cp
        progress(f"  forward cited-by {p.short_cite()} → pool {len(new)}")
    return list(new.values())


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
          batch: int = 12, cache_path: str | Path | None = None,
          progress=print) -> tuple[list[tuple[Paper, str]], list[tuple[Paper, str]]]:
    """Return (kept, dropped), each a list of (paper, reason).

    If cache_path is given, each decision is recorded (keyed by paper id) and a
    restart skips already-judged candidates — so re-scoping after a snowball, or
    resuming a crashed run, never re-spends LLM calls on papers already seen."""
    cache: dict[str, dict] = {}
    cp = Path(cache_path) if cache_path else None
    if cp and cp.exists():
        for line in cp.read_text().splitlines():
            if not line:
                continue
            try:                                   # tolerate a torn final line
                d = json.loads(line)
                cache[d["id"]] = d
            except (ValueError, KeyError):
                continue

    kept: list[tuple[Paper, str]] = []
    dropped: list[tuple[Paper, str]] = []
    pending: list[Paper] = []
    for p in candidates:                           # replay cached decisions first
        d = cache.get(p.id)
        if d is None:
            pending.append(p)
        else:
            (kept if d["in_scope"] else dropped).append((p, d.get("reason", "")))
    if cache:
        progress(f"  {len(cache)} cached decisions reused — {len(pending)} to score")

    fh = cp.open("a") if cp else None
    try:
        for i in range(0, len(pending), batch):
            chunk = pending[i:i + batch]
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
                in_scope = bool(d.get("in_scope"))
                reason = d.get("reason", "")
                (kept if in_scope else dropped).append((p, reason))
                if fh:
                    fh.write(json.dumps(
                        {"id": p.id, "in_scope": in_scope, "reason": reason}) + "\n")
                    fh.flush()
            progress(f"  scored {min(i + batch, len(pending))}/{len(pending)} "
                     f"— kept {len(kept)}")
    finally:
        if fh:
            fh.close()
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
