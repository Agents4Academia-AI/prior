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
from .models import (CLAIM_TYPES, CONTRIB_KINDS, LOCAL_RELATIONS, Claim,
                     Contribution, Edge, Paper)

SYSTEM = """You are Reader, a meticulous scientific analyst. From ONE paper you
extract three things and nothing else:

1. CONTRIBUTIONS — the paper's own research contributions, each as:
     statement: ONE self-contained sentence naming the contribution (resolve
                pronouns; name the system/method/finding concretely).
     kind:      empirical_finding | framework | method | benchmark | dataset |
                model | analysis | resource | system | other
     quote:     a short verbatim span from the text that grounds it.
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
                    "statement": {"type": "string"},
                    "kind": {"type": "string", "enum": list(CONTRIB_KINDS)},
                    "quote": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["statement", "kind"],
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


def _windowed(text: str, cap: int) -> str:
    """Fit long body text into `cap` chars by keeping the head and tail — intro
    and conclusion carry most of the contributions/claims."""
    if len(text) <= cap:
        return text
    head = int(cap * 0.7)
    tail = cap - head
    return text[:head] + "\n\n[... middle elided ...]\n\n" + text[-tail:]


# ── claims-only pass (anchored to existing contributions) ───────────────────────
CLAIMS_SYSTEM = """You extract the LOCAL claim layer of ONE paper, given the
paper's already-identified CONTRIBUTIONS. Output two things:

1. CLAIMS — atomic, self-contained, verifiable assertions the paper makes (resolve
   pronouns; name the method/dataset/quantity). Each:
     claim_type: empirical | theoretical | methodological | definitional | background
     evidence:   a short span quoted from the text
     confidence: [0,1]
     contribution: the index of the CONTRIBUTION (from the numbered list) this claim
                   supports, or -1 if background/unrelated.
   Extract 3–10 claims grounded in the text. Do not invent claims.

2. LOCAL_EDGES — relations BETWEEN claims of THIS paper (by claim index):
     entails | contradicts | supports | depends_on
   Capture the paper's internal logic; `contradicts` between two of its own claims
   is a real signal. Empty list is fine."""

_CLAIMS_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": _SCHEMA["properties"]["claims"],
        "local_edges": _SCHEMA["properties"]["local_edges"],
    },
    "required": ["claims", "local_edges"],
}


def read_claims(paper: Paper, contributions: list[Contribution], *,
                model: str | None = None) -> ReadResult:
    """Extract the local claim graph for a paper whose contributions already exist,
    bridging each claim to one of those contributions. Used to backfill the claim
    layer for collections loaded contribution-only (e.g. core-v0.2)."""
    body = paper.full_text or paper.abstract
    if not body or not contributions:
        return ReadResult(contributions=contributions)
    if paper.full_text:
        loc, content = "full text", _windowed(paper.full_text, config.FULLTEXT_CHARS)
    else:
        loc, content = "abstract", paper.abstract
    listing = "\n".join(f"[{i}] {k.summary()}" for i, k in enumerate(contributions))
    out = llm.structured(
        model=model or config.READER_MODEL, system=CLAIMS_SYSTEM,
        user=(f"PAPER TITLE: {paper.title}\nYEAR: {paper.year}\n\n"
              f"CONTRIBUTIONS:\n{listing}\n\nTEXT ({loc}):\n{content}"),
        schema=_CLAIMS_SCHEMA, tool_name="emit_claims")

    claims: list[Claim] = []
    for i, c in enumerate(out.get("claims", [])):
        ci = c.get("contribution", -1)
        contrib_id = contributions[ci].id if isinstance(ci, int) and 0 <= ci < len(contributions) else None
        claim = Claim(
            id=f"{paper.id}::c{i:02d}", paper_id=paper.id, text=str(c["text"]).strip(),
            claim_type=c.get("claim_type", "empirical"),
            evidence=str(c.get("evidence", "")).strip(), location=loc,
            confidence=float(c.get("confidence", 0.5)), contribution_id=contrib_id)
        claims.append(claim)
        if contrib_id:
            contributions[ci].claim_ids.append(claim.id)

    local_edges: list[Edge] = []
    n = len(claims)
    for e in out.get("local_edges", []):
        s, d = e.get("src"), e.get("dst")
        if isinstance(s, int) and isinstance(d, int) and 0 <= s < n and 0 <= d < n and s != d:
            local_edges.append(Edge(src=claims[s].id, dst=claims[d].id,
                                    relation=e.get("relation", "supports"),
                                    evidence=str(e.get("evidence", "")).strip(),
                                    source="text", level="local"))
    return ReadResult(contributions=contributions, claims=claims, local_edges=local_edges)


def read(paper: Paper, *, model: str | None = None) -> ReadResult:
    body = paper.full_text or paper.abstract
    if not body:
        return ReadResult()
    if paper.full_text:
        kind = "full text"
        content = _windowed(paper.full_text, config.FULLTEXT_CHARS)
    else:
        kind = "abstract"
        content = paper.abstract
    user = (
        f"PAPER TITLE: {paper.title}\n"
        f"YEAR: {paper.year}\n"
        f"AUTHORS: {', '.join(paper.authors[:8])}\n\n"
        f"TEXT ({kind}):\n{content}"
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
        kind = str(k.get("kind", "other")).strip()
        contribs.append(Contribution(
            id=f"{paper.id}::contrib{j}",
            paper_id=paper.id,
            statement=str(k.get("statement", "")).strip(),
            kind=kind if kind in CONTRIB_KINDS else "other",
            quote=str(k.get("quote", "")).strip(),
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
            location=kind,
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
                level="local",
            ))

    return ReadResult(contributions=contribs, claims=claims, local_edges=local_edges)
