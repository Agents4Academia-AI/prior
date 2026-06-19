"""Cartographer agent: assemble the atlas and build the GLOBAL graph.

Assembly is mechanical: papers + contributions + claims + the local edges Reader
already produced + citation edges (free, from OpenAlex).

The GLOBAL graph (contribution → contribution) uses the hybrid from
docs/design.md — "citations propose, text disposes":

  1. candidates = contributions of {papers this one cites, that we hold}
                  ∪ BM25 text-neighbour contributions from other papers
  2. an LLM labels each candidate pair with a typed global relation
  3. each edge is stamped with provenance: `source = both` when a citation links
     the two papers (citation backbone + text confirmation), else `source = text`
     (uncited parallel work — the part pure-citation tools can't find).

BM25 proposes a handful of candidates per contribution so we avoid O(n^2) LLM calls.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from . import config, llm
from .atlas import Atlas
from .models import GLOBAL_RELATIONS, Contribution, Edge, Paper
from .reader import ReadResult

_WORD = re.compile(r"[a-z0-9]+")


def _tok(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def _contrib_text(k: Contribution) -> str:
    return f"{k.problem} {k.method} {k.result}"


def _candidates(contribs: list[Contribution], k: int) -> dict[str, list[Contribution]]:
    """For each contribution, BM25-nearest contributions from *other* papers."""
    if len(contribs) < 2:
        return {c.id: [] for c in contribs}
    corpus = [_tok(_contrib_text(c)) for c in contribs]
    bm25 = BM25Okapi(corpus)
    out: dict[str, list[Contribution]] = {}
    for i, c in enumerate(contribs):
        scores = bm25.get_scores(corpus[i])
        ranked = sorted(range(len(contribs)), key=lambda j: scores[j], reverse=True)
        picks: list[Contribution] = []
        for j in ranked:
            if j == i or contribs[j].paper_id == c.paper_id:
                continue
            picks.append(contribs[j])
            if len(picks) >= k:
                break
        out[c.id] = picks
    return out


SYSTEM = """You are Cartographer. Given a SOURCE research contribution and a
numbered list of CANDIDATE contributions from other papers, label the relation
FROM the source TO each candidate, choosing only relations that genuinely hold:
  builds_on    — the source is based on / extends / applies the candidate
  refines      — the source qualifies or improves the candidate
  contradicts  — the source's result is incompatible with the candidate's
  contrast     — the source presents an alternative approach to the candidate
  supports     — the source's result corroborates the candidate's
  mentions     — related but none of the above
Most pairs are unrelated — omit those. Be conservative: only assert a relation
you could defend from the contribution texts. Give a one-line reason."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "candidate": {"type": "integer"},
                    "relation": {"type": "string", "enum": list(GLOBAL_RELATIONS)},
                    "reason": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["candidate", "relation", "reason", "confidence"],
            },
        }
    },
    "required": ["relations"],
}


def _label(source: Contribution, cands: list[Contribution], cited: set[str],
           model: str) -> list[Edge]:
    listing = "\n".join(
        f"[{i}] problem: {c.problem}\n    method: {c.method}\n    result: {c.result}"
        for i, c in enumerate(cands))
    out = llm.structured(
        model=model,
        system=SYSTEM,
        user=(f"SOURCE CONTRIBUTION:\n  problem: {source.problem}\n"
              f"  method: {source.method}\n  result: {source.result}\n\n"
              f"CANDIDATE CONTRIBUTIONS:\n{listing}"),
        schema=_SCHEMA,
        tool_name="emit_relations",
        max_tokens=1024,
    )
    edges: list[Edge] = []
    for r in out.get("relations", []):
        j = r.get("candidate")
        if not isinstance(j, int) or not 0 <= j < len(cands):
            continue
        cand = cands[j]
        # Provenance: a citation between the two papers => text-confirmed citation.
        src = "both" if cand.paper_id in cited else "text"
        edges.append(Edge(
            src=source.id,
            dst=cand.id,
            relation=r["relation"],
            evidence=r.get("reason", "").strip(),
            confidence=float(r.get("confidence", 0.5)),
            source=src,
            level="global",
        ))
    return edges


def build(papers: list[Paper], reading: ReadResult, *, topic: str = "",
          model: str | None = None, neighbors: int | None = None,
          relate: bool = True) -> Atlas:
    """Assemble the atlas from Reader output and (optionally) build the global
    contribution graph. relate=False = local graph + citations only (fast)."""
    model = model or config.CARTOGRAPHER_MODEL
    k = neighbors or config.RELATION_NEIGHBORS

    atlas = Atlas()
    atlas.topic = topic
    for p in papers:
        atlas.add_paper(p)
    for kc in reading.contributions:
        atlas.add_contribution(kc)
    for c in reading.claims:
        atlas.add_claim(c)
    for e in reading.local_edges:
        atlas.add_edge(e)
    atlas.link_citations()

    if relate and len(reading.contributions) > 1:
        _relate_global(atlas, reading.contributions, k, model)
    return atlas


def _relate_global(atlas: Atlas, contribs: list[Contribution], k: int,
                   model: str) -> None:
    """Add typed contribution→contribution edges via the citations-propose,
    text-disposes hybrid."""
    by_paper: dict[str, list[Contribution]] = {}
    for c in contribs:
        by_paper.setdefault(c.paper_id, []).append(c)

    text_cands = _candidates(contribs, k)
    held = set(atlas.papers)
    seen: set[frozenset[str]] = set()

    for c in contribs:
        paper = atlas.papers.get(c.paper_id)
        cited_papers = {r for r in (paper.referenced_works if paper else []) if r in held}
        # citation-derived candidates ∪ text neighbours
        cite_cands = [k2 for pid in cited_papers for k2 in by_paper.get(pid, [])]
        cands: list[Contribution] = []
        ids: set[str] = set()
        for cand in cite_cands + text_cands.get(c.id, []):
            if cand.id == c.id or cand.paper_id == c.paper_id or cand.id in ids:
                continue
            if frozenset({c.id, cand.id}) in seen:
                continue
            cands.append(cand)
            ids.add(cand.id)
        if not cands:
            continue
        for e in _label(c, cands, cited_papers, model):
            pair = frozenset({e.src, e.dst})
            if pair in seen:
                continue
            seen.add(pair)
            atlas.add_edge(e)
