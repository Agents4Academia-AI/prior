"""Contribution agent: extract a paper's *self-declared* contributions.

A distinct task from Reader. Reader extracts every claim (incl. background,
definitions, surveys of open problems, others' work). The Contribution agent
isolates what the paper claims for ITSELF — anchored on the explicit
self-declaration in the abstract/intro ("we propose…", "our contributions are…").

This is step 1 of the contribution pipeline. Assessing *true* novelty against the
atlas (merge + chronology) is deferred — see WEEK_2.md.
"""

from __future__ import annotations

from . import config, llm
from .models import Paper

KINDS = ("method", "model", "dataset", "benchmark", "framework",
         "empirical_finding", "analysis", "resource", "other")

SYSTEM = """You are the Contribution agent. You read a paper's title, abstract,
and the start of its full text (where the introduction and any explicit
contribution list live) and extract ONLY the contributions the paper claims for
ITSELF — what it proposes, introduces, builds, or demonstrates as new.

Anchor on the paper's own self-declaration: "we propose / introduce / present /
develop", "our contributions are", "in this work/paper we …", "(1) … (2) …".

EXCLUDE, even if stated as findings:
- background, definitions, motivation;
- surveys/lists of open problems, challenges, or future directions;
- descriptions of prior work or others' methods.
A review/survey paper usually has NO contributions of its own — return [].

Return 1–5 contributions for a primary paper (fewer is fine), each with a
one-sentence statement, a kind, and the quoted self-declaration span it came from."""

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


def extract(paper: Paper, fulltext: str | None = None, *,
            model: str | None = None) -> list[dict]:
    """Return the paper's self-declared contributions as dicts
    {id, paper_id, statement, kind, quote}. Requires full text — we do NOT fall
    back to the abstract (the contribution list lives in the intro)."""
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
        result.append({
            "id": f"{paper.id}::k{i:02d}",
            "paper_id": paper.id,
            "statement": c.get("statement", "").strip(),
            "kind": c.get("kind", "other"),
            "quote": c.get("quote", "").strip(),
        })
    return result
