"""Graph-backed Navigator — answers over the live Neo4j two-level graph.

Unlike the old atlas-in-memory navigator, this explores the graph through the
repository tools (graph.ann / neighbours / aggregate): vector-seed → expand the
neighbourhood → let the model judge, grounded in node ids. Two entry points:

  ask(question)          — forward: state of evidence, cited, with honest not_found.
  has_been_solved(problem) — the headline novelty/gap question, over contributions.

Every model call goes through llm.structured (credit-free claude-cli by default).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import config, embeddings, graph, llm

_TIMEOUT = 120


# ── forward: state of evidence ──────────────────────────────────────────────────
ASK_SYSTEM = """You are Navigator. Answer the QUESTION strictly from the EVIDENCE
CLAIMS provided (each is grounded in a paper). Rules:
- Use only the evidence; cite claims by their [id]. No outside knowledge.
- Sort evidence into supporting, contradicting, and open questions / gaps.
- verdict ∈ established | contested | emerging | not_found.
- If not_found, be a graceful no: name the CLOSEST claim present and the GAP.
- Keep `answer` to a short, honest paragraph."""

_ASK_SCHEMA = {
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
    "required": ["verdict", "answer", "supporting", "contradicting", "open_questions"],
}


@dataclass
class Answer:
    verdict: str = "not_found"
    answer: str = ""
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    closest: str = ""
    gap: str = ""
    used: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def ask(question: str, *, k: int = 12, model: str | None = None) -> Answer:
    qv = embeddings.embed_one(question)
    hits = graph.ann(qv, label="Claim", k=k)
    if not hits:
        return Answer(answer="The graph contains no claims relevant to this question.",
                      closest="(empty graph)", gap="topic not ingested yet")
    block = "\n".join(f"[{h['id']}] ({h.get('claim_type','?')}) {h.get('text','')}"
                      for h in hits)
    out = llm.structured(
        model=model or config.NAVIGATOR_MODEL, system=ASK_SYSTEM,
        user=f"QUESTION: {question}\n\nEVIDENCE CLAIMS:\n{block}",
        schema=_ASK_SCHEMA, tool_name="emit_answer", timeout=_TIMEOUT)
    return Answer(
        verdict=out.get("verdict", "not_found"), answer=out.get("answer", ""),
        supporting=out.get("supporting", []), contradicting=out.get("contradicting", []),
        open_questions=out.get("open_questions", []), closest=out.get("closest", ""),
        gap=out.get("gap", ""),
        used=[{"id": h["id"], "text": h.get("text", "")} for h in hits])


# ── headline: has this problem/contribution been solved? ────────────────────────
SOLVED_SYSTEM = """You assess whether a PROBLEM/HYPOTHESIS has already been
addressed in the literature, using only the CANDIDATE CONTRIBUTIONS retrieved
from the graph (each is one paper's contribution, with its support/contradict
neighbours summarised). Rules:
- Ground every statement in contribution [id]s. No outside knowledge.
- verdict ∈ solved | partially_solved | contested | open | not_addressed.
    solved          — one or more contributions clearly address it, corroborated
    partially_solved— addressed under limits / for special cases only
    contested       — contributions disagree on whether/how it is solved
    open            — related work exists but the problem itself is unaddressed
    not_addressed   — nothing in the graph addresses it
- List the contributions that address it (`addressed_by`, ids), the strongest
  `supporting` and any `contradicting` ids, then `closest` + `gap` for a novel
  framing. Keep `summary` short and honest."""

_SOLVED_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string",
                    "enum": ["solved", "partially_solved", "contested",
                             "open", "not_addressed"]},
        "summary": {"type": "string"},
        "addressed_by": {"type": "array", "items": {"type": "string"}},
        "supporting": {"type": "array", "items": {"type": "string"}},
        "contradicting": {"type": "array", "items": {"type": "string"}},
        "closest": {"type": "string"},
        "gap": {"type": "string"},
    },
    "required": ["verdict", "summary", "addressed_by", "closest", "gap"],
}


@dataclass
class SolvedAnswer:
    verdict: str = "not_addressed"
    summary: str = ""
    addressed_by: list[str] = field(default_factory=list)
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    closest: str = ""
    gap: str = ""
    candidates: list[dict] = field(default_factory=list)
    consensus: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def has_been_solved(problem: str, *, k: int = 8, model: str | None = None) -> SolvedAnswer:
    """Vector-seed contributions about the problem, expand each with its global
    neighbours, aggregate consensus, then let the model judge."""
    qv = embeddings.embed_one(problem)
    hits = graph.ann(qv, label="Contribution", k=k)
    if not hits:
        return SolvedAnswer(summary="No contributions in the graph relate to this.",
                            closest="(empty graph)", gap="topic not ingested yet")

    lines, cand = [], []
    for h in hits:
        nbrs = graph.neighbours(h["id"], rels=graph.GLOBAL_RELS)
        rel_summ = ", ".join(
            f"{n['rel'].lower()}→{n['node'].get('method','')[:40]}" for n in nbrs[:6])
        lines.append(
            f"[{h['id']}] (sim={h.get('_score',0):.2f})\n"
            f"  problem: {h.get('problem','')}\n  method: {h.get('method','')}\n"
            f"  result: {h.get('result','')}\n  relations: {rel_summ or 'none'}")
        cand.append({"id": h["id"], "method": h.get("method", ""),
                     "score": h.get("_score", 0)})

    consensus = graph.aggregate_relations([h["id"] for h in hits])
    out = llm.structured(
        model=model or config.NAVIGATOR_MODEL, system=SOLVED_SYSTEM,
        user=(f"PROBLEM/HYPOTHESIS: {problem}\n\n"
              f"CANDIDATE CONTRIBUTIONS:\n" + "\n\n".join(lines) +
              f"\n\nRELATION COUNTS across candidates: {consensus}"),
        schema=_SOLVED_SCHEMA, tool_name="emit_assessment", timeout=_TIMEOUT)
    return SolvedAnswer(
        verdict=out.get("verdict", "not_addressed"), summary=out.get("summary", ""),
        addressed_by=out.get("addressed_by", []), supporting=out.get("supporting", []),
        contradicting=out.get("contradicting", []), closest=out.get("closest", ""),
        gap=out.get("gap", ""), candidates=cand, consensus=consensus)
