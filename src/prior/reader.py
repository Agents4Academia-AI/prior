"""Reader agent: one paper -> structured, atomic claims.

A claim must be self-contained (no dangling "this"/"it"), verifiable, and tied
to a short evidence span from the source. We extract from the abstract by
default; richer full-text extraction can slot in behind the same interface.
"""

from __future__ import annotations

from . import config, llm
from .models import CLAIM_TYPES, Claim, Paper

SYSTEM = """You are Reader, a meticulous scientific claims extractor.
You read one paper and extract its ATOMIC, VERIFIABLE claims — the assertions a
careful peer reviewer would check.

Rules:
- Each claim is self-contained: resolve pronouns, name the method/dataset/quantity.
- Prefer the paper's own contributions and findings over background it cites.
- Every claim needs a short evidence span quoted from the provided text.
- Classify each claim:
    empirical      — a measured result / observation ("X improves Y by Z%")
    theoretical    — a proof, bound, or formal statement
    methodological — "we propose/introduce method M that does N"
    definitional   — a definition or framing the paper establishes
- confidence ∈ [0,1]: how sure you are this is a genuine, checkable claim.
- Extract 3–8 claims. Do not invent claims not supported by the text."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["text", "claim_type", "evidence", "confidence"],
            },
        }
    },
    "required": ["claims"],
}


def read(paper: Paper, *, model: str | None = None) -> list[Claim]:
    if not paper.abstract:
        return []
    user = (
        f"PAPER TITLE: {paper.title}\n"
        f"YEAR: {paper.year}\n"
        f"AUTHORS: {', '.join(paper.authors[:8])}\n\n"
        f"TEXT (abstract):\n{paper.abstract}"
    )
    out = llm.structured(
        model=model or config.READER_MODEL,
        system=SYSTEM,
        user=user,
        schema=_SCHEMA,
        tool_name="emit_claims",
    )
    claims: list[Claim] = []
    for i, c in enumerate(out.get("claims", [])):
        claims.append(Claim(
            id=f"{paper.id}::c{i:02d}",
            paper_id=paper.id,
            text=c["text"].strip(),
            claim_type=c.get("claim_type", "empirical"),
            evidence=c.get("evidence", "").strip(),
            location="abstract",
            confidence=float(c.get("confidence", 0.5)),
        ))
    return claims
