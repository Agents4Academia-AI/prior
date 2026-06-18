"""Cartographer agent: a bag of claims -> a structured atlas.

Two kinds of structure:
  1. Citation edges between papers (free, from OpenAlex) — added by the Atlas.
  2. Semantic relations between claims (supports/contradicts/refines/extends).

Naively asking the LLM about every claim pair is O(n^2). Instead we use BM25 to
propose a handful of candidate neighbours per claim (cheap), then spend one LLM
call per claim to label only those candidates. Pairs are de-duplicated so each
relation is judged once.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from . import config, llm
from .atlas import Atlas
from .models import RELATIONS, Claim, Edge, Paper

_WORD = re.compile(r"[a-z0-9]+")


def _tok(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def _candidates(claims: list[Claim], k: int) -> dict[str, list[Claim]]:
    """For each claim, BM25-nearest claims from *other* papers."""
    corpus = [_tok(c.text) for c in claims]
    bm25 = BM25Okapi(corpus)
    out: dict[str, list[Claim]] = {}
    for i, c in enumerate(claims):
        scores = bm25.get_scores(corpus[i])
        ranked = sorted(range(len(claims)), key=lambda j: scores[j], reverse=True)
        picks: list[Claim] = []
        for j in ranked:
            if j == i or claims[j].paper_id == c.paper_id:
                continue
            picks.append(claims[j])
            if len(picks) >= k:
                break
        out[c.id] = picks
    return out


SYSTEM = """You are Cartographer. Given a SOURCE claim and a numbered list of
CANDIDATE claims from other papers, label the relation from the source to each
candidate, choosing only relations that genuinely hold:
  supports     — candidate provides evidence for / agrees with the source
  contradicts  — candidate asserts something incompatible with the source
  refines      — candidate qualifies / adds conditions to the source claim
  extends      — candidate builds on the source, applying it further
Most pairs are simply unrelated — omit those. Be conservative: only assert a
relation you could defend with the claim texts. Give a one-line reason."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer"},
                    "relation": {"type": "string", "enum": list(RELATIONS)},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["candidate", "relation", "reason", "confidence"],
            },
        }
    },
    "required": ["relations"],
}


def _label(source: Claim, cands: list[Claim], model: str) -> list[Edge]:
    listing = "\n".join(f"[{i}] {c.text}" for i, c in enumerate(cands))
    out = llm.structured(
        model=model,
        system=SYSTEM,
        user=f"SOURCE CLAIM:\n{source.text}\n\nCANDIDATE CLAIMS:\n{listing}",
        schema=_SCHEMA,
        tool_name="emit_relations",
        max_tokens=1024,
    )
    edges: list[Edge] = []
    for r in out.get("relations", []):
        j = r.get("candidate")
        if not isinstance(j, int) or not 0 <= j < len(cands):
            continue
        edges.append(Edge(
            src=source.id,
            dst=cands[j].id,
            relation=r["relation"],
            evidence=r.get("reason", "").strip(),
            confidence=float(r.get("confidence", 0.5)),
        ))
    return edges


def build(papers: list[Paper], claims: list[Claim], *, topic: str = "",
          model: str | None = None, neighbors: int | None = None,
          relate: bool = True) -> Atlas:
    """Assemble the atlas. Set relate=False to skip LLM relation-finding
    (citations + provenance only — useful for a fast first pass)."""
    model = model or config.CARTOGRAPHER_MODEL
    k = neighbors or config.RELATION_NEIGHBORS

    atlas = Atlas()
    atlas.topic = topic
    for p in papers:
        atlas.add_paper(p)
    for c in claims:
        atlas.add_claim(c)
    atlas.link_citations()

    if relate:
        for e in relate_claims(claims, model=model, neighbors=k):
            atlas.add_edge(e)
    return atlas


def relate_claims(claims: list[Claim], *, model: str | None = None,
                  neighbors: int | None = None) -> list[Edge]:
    """Find typed relations (supports/contradicts/refines/extends) among a set of
    claims across different papers. Reusable for any claim-like nodes — including
    contributions — so a graph of them connects across papers."""
    model = model or config.CARTOGRAPHER_MODEL
    k = neighbors or config.RELATION_NEIGHBORS
    if len(claims) <= 1:
        return []
    cand_map = _candidates(claims, k)
    seen: set[frozenset[str]] = set()
    edges: list[Edge] = []
    for c in claims:
        fresh = [d for d in cand_map.get(c.id, [])
                 if frozenset({c.id, d.id}) not in seen]
        if not fresh:
            continue
        for e in _label(c, fresh, model):
            pair = frozenset({e.src, e.dst})
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(e)
    return edges
