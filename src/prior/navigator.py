"""Navigator agent: a question + the atlas -> a grounded answer.

Two modes, both grounded in claims that carry provenance back to primary sources:

  forward  ("has this been done? what's the state of evidence?")
           -> verdict + supporting / contradicting evidence + open questions,
              or a graceful "no": closest work X, gap Y.

  backward ("where did this idea come from?")
           -> trace the matching claims' papers along citation edges to the
              earliest / most foundational source in the atlas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import networkx as nx
from rank_bm25 import BM25Okapi

from . import config, llm
from .atlas import Atlas
from .models import Claim

_WORD = re.compile(r"[a-z0-9]+")


def _tok(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def _retrieve(atlas: Atlas, query: str, n: int) -> list[tuple[Claim, float]]:
    claims = list(atlas.claims.values())
    if not claims:
        return []
    corpus = [_tok(f"{c.text} {c.evidence}") for c in claims]
    bm25 = BM25Okapi(corpus)
    scores = bm25.get_scores(_tok(query))
    ranked = sorted(zip(claims, scores), key=lambda t: t[1], reverse=True)
    return [(c, s) for c, s in ranked[:n] if s > 0]


def _cite(atlas: Atlas, claim: Claim) -> str:
    p = atlas.papers.get(claim.paper_id)
    return p.short_cite() if p else claim.paper_id


# ── forward ─────────────────────────────────────────────────────────────────────
FORWARD_SYSTEM = """You are Navigator, answering whether something has been done
and what the state of evidence is — strictly from the EVIDENCE CLAIMS provided.

Each claim is grounded in a primary source (its citation is shown). Rules:
- Cite claims by their [id] whenever you use them. Never use outside knowledge.
- Sort evidence into: supporting, contradicting, and open questions / gaps.
- Choose a verdict:
    established  — multiple consistent claims support it
    contested    — claims conflict
    emerging     — thin or early support
    not_found    — the atlas does not actually address the question
- If not_found, be a graceful "no": name the CLOSEST claim/work present and the
  specific GAP between it and what was asked. Do not pretend coverage exists.
- Keep the prose answer to a short, honest paragraph."""

_FORWARD_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string",
                    "enum": ["established", "contested", "emerging", "not_found"]},
        "answer": {"type": "string"},
        "supporting": {"type": "array", "items": {"type": "string"}},
        "contradicting": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "closest": {"type": "string"},
        "gap": {"type": "string"},
    },
    "required": ["verdict", "answer", "supporting", "contradicting",
                 "open_questions"],
}


@dataclass
class ForwardAnswer:
    verdict: str
    answer: str
    supporting: list[str]
    contradicting: list[str]
    open_questions: list[str]
    closest: str
    gap: str
    used: list[Claim]

    def render(self) -> str:
        lines = [f"VERDICT: {self.verdict.upper()}", "", self.answer, ""]
        if self.supporting:
            lines.append("Supporting:")
            lines += [f"  + {s}" for s in self.supporting]
        if self.contradicting:
            lines.append("Contradicting:")
            lines += [f"  - {s}" for s in self.contradicting]
        if self.open_questions:
            lines.append("Open questions / gaps:")
            lines += [f"  ? {s}" for s in self.open_questions]
        if self.verdict == "not_found":
            lines += ["", f"Closest: {self.closest}", f"Gap: {self.gap}"]
        return "\n".join(lines)


def ask(atlas: Atlas, question: str, *, n: int = 12,
        model: str | None = None) -> ForwardAnswer:
    hits = _retrieve(atlas, question, n)
    if not hits:
        return ForwardAnswer(
            "not_found", "The atlas contains no claims relevant to this question.",
            [], [], [], "(nothing in the current atlas)",
            "the topic is not covered by the ingested papers", [])

    block = "\n".join(
        f"[{c.id}] ({c.claim_type}, {_cite(atlas, c)}) {c.text}"
        for c, _ in hits
    )
    out = llm.structured(
        model=model or config.NAVIGATOR_MODEL,
        system=FORWARD_SYSTEM,
        user=f"QUESTION: {question}\n\nEVIDENCE CLAIMS:\n{block}",
        schema=_FORWARD_SCHEMA,
        tool_name="emit_answer",
    )
    return ForwardAnswer(
        verdict=out.get("verdict", "not_found"),
        answer=out.get("answer", ""),
        supporting=out.get("supporting", []),
        contradicting=out.get("contradicting", []),
        open_questions=out.get("open_questions", []),
        closest=out.get("closest", ""),
        gap=out.get("gap", ""),
        used=[c for c, _ in hits],
    )


# ── backward / origin tracing ───────────────────────────────────────────────────
ORIGIN_SYSTEM = """You are Navigator in origin-tracing mode. Given a concept and
a citation-ordered list of papers from the atlas (earliest and most-cited first),
explain where the idea appears to originate and how it propagated — using ONLY
the listed papers. Cite papers by [id]. If the atlas likely misses the true
origin (e.g. the earliest listed paper already treats the idea as known), say so
explicitly rather than overclaiming."""

_ORIGIN_SCHEMA = {
    "type": "object",
    "properties": {
        "origin_paper": {"type": "string"},
        "account": {"type": "string"},
        "lineage": {"type": "array", "items": {"type": "string"}},
        "caveat": {"type": "string"},
    },
    "required": ["origin_paper", "account", "lineage"],
}


@dataclass
class OriginAnswer:
    origin_paper: str
    account: str
    lineage: list[str]
    caveat: str

    def render(self) -> str:
        lines = [f"LIKELY ORIGIN: {self.origin_paper}", "", self.account]
        if self.lineage:
            lines += ["", "Lineage:"] + [f"  -> {s}" for s in self.lineage]
        if self.caveat:
            lines += ["", f"Caveat: {self.caveat}"]
        return "\n".join(lines)


def _cites_descendants(atlas: Atlas, paper_ids: set[str]) -> set[str]:
    """Citation ancestors of the given papers — the older works they (transitively)
    build on, reachable by following `cites` edges. These are where origins live,
    so they must be candidates even though their claims may not match the concept."""
    g = nx.DiGraph()
    for e in atlas.edges:
        if e.relation == "cites":
            g.add_edge(e.src, e.dst)
    anc: set[str] = set()
    for pid in paper_ids:
        if pid in g:
            anc |= nx.descendants(g, pid)
    return {a for a in anc if a in atlas.papers}


def origin_candidates(atlas: Atlas, concept: str, *, n: int = 15,
                      limit: int = 25) -> list[str]:
    """Papers to consider as the origin: those whose claims match the concept,
    PLUS their citation ancestors, ordered foundational-first (most cited within
    the atlas, then oldest, then most globally cited)."""
    hits = _retrieve(atlas, concept, n)
    matched = list(dict.fromkeys(c.paper_id for c, _ in hits))
    if not matched:
        return []
    candidates = set(matched) | _cites_descendants(atlas, set(matched))

    g = atlas.graph()
    def in_atlas_citations(pid: str) -> int:
        return sum(1 for _, _, d in g.in_edges(pid, data=True)
                   if d.get("relation") == "cites")

    def sort_key(pid: str):
        p = atlas.papers[pid]
        return (-in_atlas_citations(pid), p.year or 9999, -p.cited_by_count)

    return sorted(candidates, key=sort_key)[:limit]


def origin(atlas: Atlas, concept: str, *, n: int = 15,
           model: str | None = None) -> OriginAnswer:
    """Find papers whose claims match the concept (and their citation ancestors),
    then order them by foundational-ness and let the model name the origin."""
    ordered = origin_candidates(atlas, concept, n=n)
    if not ordered:
        return OriginAnswer("(none)", "No papers in the atlas match this concept.",
                            [], "Ingest more literature on this topic.")

    g = atlas.graph()
    def in_atlas_citations(pid: str) -> int:
        return sum(1 for _, _, d in g.in_edges(pid, data=True)
                   if d.get("relation") == "cites")

    listing = "\n".join(
        f"[{pid}] {atlas.papers[pid].short_cite()} "
        f"(year={atlas.papers[pid].year}, cited_by={atlas.papers[pid].cited_by_count}, "
        f"cited_within_atlas={in_atlas_citations(pid)}) "
        f"{atlas.papers[pid].title}"
        for pid in ordered
    )
    out = llm.structured(
        model=model or config.NAVIGATOR_MODEL,
        system=ORIGIN_SYSTEM,
        user=f"CONCEPT: {concept}\n\nPAPERS (foundational first):\n{listing}",
        schema=_ORIGIN_SCHEMA,
        tool_name="emit_origin",
    )
    return OriginAnswer(
        origin_paper=out.get("origin_paper", ""),
        account=out.get("account", ""),
        lineage=out.get("lineage", []),
        caveat=out.get("caveat", ""),
    )
