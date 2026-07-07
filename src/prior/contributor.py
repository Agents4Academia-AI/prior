"""Contribution agent: extract a paper's *self-declared* contributions.

A distinct task from Reader. Reader extracts every claim (incl. background,
definitions, surveys of open problems, others' work). The Contribution agent
isolates what the paper claims for ITSELF — anchored on the explicit
self-declaration in the abstract/intro ("we propose…", "our contributions are…").

This is step 1 of the contribution pipeline. Assessing *true* novelty against the
atlas (merge + chronology) is deferred — see docs/project/WEEK_2.md.
"""

from __future__ import annotations

from . import config, llm
from .models import Paper

KINDS = ("method", "model", "dataset", "benchmark", "framework",
         "empirical_finding", "analysis", "resource", "other")

SYSTEM = """You are the Contribution agent. You read a paper's title, abstract,
and the start of its full text and extract the contributions it claims as new.

Phrase each contribution as a STANDALONE, source-agnostic statement of the
contribution ITSELF — the method, system, capability, dataset, or finding —
written so it could stand on its own and be supported by multiple papers. Do NOT
write "the paper / the authors / we propose / this work introduces …"; the
supporting paper is recorded separately. Name the method/system if the paper
names it.
  GOOD: "A small, standalone retriever enables low-latency retrieval-augmented
         generation for structured outputs."
  GOOD: "Chain-of-Verification — draft, independently verify, then revise —
         reduces hallucination in long-form generation."
  BAD:  "The authors propose a small retriever that enables …"
  BAD:  "The paper introduces Chain-of-Verification …"

Anchor your extraction on the paper's self-declaration ("we propose / our
contributions are / in this work we …") but REWRITE it into the standalone form.

EXCLUDE: background, definitions, motivation, surveys of open problems or future
directions, and descriptions of others' prior work. A review/survey paper has NO
contributions of its own — return [].

Return 1–5 contributions, each with: the standalone `statement`, a `kind`, and
the `quote` (the paper's own self-declaration span it was drawn from)."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "contributions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "kind": {"type": "string", "enum": list(KINDS)},
                    "quote": {"type": "string"},
                },
                "required": ["statement", "kind", "quote"],
            },
        }
    },
    "required": ["contributions"],
}


def align_quote(quote: str, source: str) -> dict | None:
    """Snap an extracted quote to its best-matching verbatim span in the source.

    The LLM's `quote` is usually a paraphrase/synthesis even though we ask for a
    span (models don't reliably copy). This recovers the real span deterministically
    so provenance is lexically auditable, returning the verbatim text, its char
    offsets in `source`, and a grounding score in [0,1] (how well the quote is
    actually supported verbatim — a triage signal for the auditor)."""
    q = (quote or "").strip()
    if not q or not source:
        return None
    from rapidfuzz import fuzz
    # match case-insensitively; .lower() preserves length so offsets stay valid in
    # the original (true for ASCII/Latin; negligible drift otherwise).
    a = fuzz.partial_ratio_alignment(q.lower(), source.lower(), score_cutoff=0)
    if a is None:
        return None
    return {
        "quote_verbatim": source[a.dest_start:a.dest_end].strip(),
        "quote_offsets": [a.dest_start, a.dest_end],
        "grounding": round(a.score / 100, 3),
    }


def extract(paper: Paper, fulltext: str | None = None, *,
            model: str | None = None) -> list[dict]:
    """Return the paper's self-declared contributions as dicts
    {id, paper_id, statement, kind, quote, quote_verbatim, quote_offsets, grounding}.
    Requires full text — we do NOT fall back to the abstract (the contribution list
    lives in the intro)."""
    if not fulltext:
        return []
    body = fulltext[:12000]   # intro + contribution list live near the top
    out = llm.structured(
        model=model or config.READER_MODEL,
        system=SYSTEM,
        user=(f"TITLE: {paper.title}\n"
              f"ABSTRACT: {paper.abstract}\n\n"
              f"FULL TEXT (beginning):\n{body}"),
        schema=_SCHEMA,
        tool_name="emit_contributions",
        max_tokens=1500,
    )
    result = []
    for i, c in enumerate(out.get("contributions", [])):
        rec = {
            "id": f"{paper.id}::k{i:02d}",
            "paper_id": paper.id,
            "statement": c.get("statement", "").strip(),
            "kind": c.get("kind", "other"),
            "quote": c.get("quote", "").strip(),
        }
        span = align_quote(rec["quote"], fulltext)   # verbatim provenance + grounding
        if span:
            rec.update(span)
        result.append(rec)
    return result
