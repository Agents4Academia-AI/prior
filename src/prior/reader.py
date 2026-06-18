"""Reader agent: one paper -> contributions + claims + a local claim graph.

Two levels come out of a single read (see docs/design.md):
  - contributions: the paper's research contributions, ORKG-style
    (problem / method / result) — these become GLOBAL-graph nodes.
  - claims: atomic, evidence-bearing assertions — LOCAL-graph nodes, each
    optionally linked up to the contribution it supports.
  - local_edges: typed relations BETWEEN claims of this paper (entails /
    contradicts / supports / depends_on) — the paper's internal coherence/story.

Local edges are necessarily text-extracted (no citations exist within a paper).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import config, llm
from .models import CLAIM_TYPES, LOCAL_RELATIONS, Claim, Contribution, Edge, Paper

SYSTEM = """You are Reader, a meticulous scientific analyst. From ONE paper you
extract three things and nothing else:

1. CONTRIBUTIONS — the paper's own research contributions, each as a triple:
     problem  (what gap/question it addresses)
     method   (what it proposes/does)
     result   (what it shows/achieves)
   Most papers have 1–3. Use the paper's own contributions, not background it cites.

2. CLAIMS — atomic, self-contained, verifiable assertions (resolve pronouns; name
   the method/dataset/quantity). Each claim has:
     claim_type: empirical | theoretical | methodological | definitional | background
     evidence:   a short span quoted from the provided text
     confidence: [0,1]
     contribution: the index of the CONTRIBUTION it supports, or -1 if it is
                   background/unrelated.
   Extract 3–8 claims. Do not invent claims unsupported by the text.

3. LOCAL_EDGES — relations BETWEEN claims of THIS paper (by claim index):
     entails | contradicts | supports | depends_on
   Capture the paper's internal logic. `contradicts` between two of the paper's
   own claims is a real coherence signal — surface it if present. It is fine to
   return an empty list if the claims are independent."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "contributions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "problem": {"type": "string"},
                    "method": {"type": "string"},
                    "result": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["problem", "method", "result"],
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "claim_type": {"type": "string", "enum": list(CLAIM_TYPES)},
                    "evidence": {"type": "string"},
                    "confidence": {"type": "number"},
                    "contribution": {"type": "integer"},
                },
                "required": ["text", "claim_type", "evidence", "confidence", "contribution"],
            },
        },
        "local_edges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "src": {"type": "integer"},
                    "dst": {"type": "integer"},
                    "relation": {"type": "string", "enum": list(LOCAL_RELATIONS)},
                    "evidence": {"type": "string"},
                },
                "required": ["src", "dst", "relation"],
            },
        },
    },
    "required": ["contributions", "claims", "local_edges"],
}


@dataclass
class ReadResult:
    """Everything Reader pulls from one paper."""
    contributions: list[Contribution] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    local_edges: list[Edge] = field(default_factory=list)


def read(paper: Paper, *, model: str | None = None) -> ReadResult:
    if not paper.abstract:
        return ReadResult()
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
        tool_name="emit_reading",
    )

    contribs: list[Contribution] = []
    for j, k in enumerate(out.get("contributions", [])):
        contribs.append(Contribution(
            id=f"{paper.id}::contrib{j}",
            paper_id=paper.id,
            problem=str(k.get("problem", "")).strip(),
            method=str(k.get("method", "")).strip(),
            result=str(k.get("result", "")).strip(),
            confidence=float(k.get("confidence", 0.5)),
        ))

    claims: list[Claim] = []
    for i, c in enumerate(out.get("claims", [])):
        ci = c.get("contribution", -1)
        contrib_id = contribs[ci].id if isinstance(ci, int) and 0 <= ci < len(contribs) else None
        claim = Claim(
            id=f"{paper.id}::c{i:02d}",
            paper_id=paper.id,
            text=str(c["text"]).strip(),
            claim_type=c.get("claim_type", "empirical"),
            evidence=str(c.get("evidence", "")).strip(),
            location="abstract",
            confidence=float(c.get("confidence", 0.5)),
            contribution_id=contrib_id,
        )
        claims.append(claim)
        if contrib_id:
            contribs[ci].claim_ids.append(claim.id)

    local_edges: list[Edge] = []
    n = len(claims)
    for e in out.get("local_edges", []):
        s, d = e.get("src"), e.get("dst")
        if isinstance(s, int) and isinstance(d, int) and 0 <= s < n and 0 <= d < n and s != d:
            local_edges.append(Edge(
                src=claims[s].id,
                dst=claims[d].id,
                relation=e.get("relation", "supports"),
                evidence=str(e.get("evidence", "")).strip(),
                source="text",
            ))

    return ReadResult(contributions=contribs, claims=claims, local_edges=local_edges)
