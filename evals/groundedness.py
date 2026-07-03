"""Reader eval — groundedness, no API key required.

A claim is "grounded" if its evidence span genuinely appears in the source text.
We compare on a normalised, word-token basis with a fuzzy overlap threshold, so
minor whitespace/casing differences pass but invented evidence fails.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prior import pipeline  # noqa: E402
from prior.models import CLAIM_TYPES  # noqa: E402

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def overlap(evidence: str, source: str) -> float:
    """Fraction of evidence tokens (as a multiset) covered by the source."""
    ev = _tokens(evidence)
    if not ev:
        return 0.0
    src = set(_tokens(source))
    return sum(1 for t in ev if t in src) / len(ev)


def evaluate(threshold: float = 0.8) -> dict:
    papers = {p.id: p for p in pipeline.load_papers()}
    claims = pipeline.load_claims()
    if not claims:
        sys.exit("No claims cached. Run `prior build`/`prior read` first.")

    grounded = 0
    scores: list[float] = []
    type_counts = {t: 0 for t in CLAIM_TYPES}
    for c in claims:
        p = papers.get(c.paper_id)
        src = (p.abstract + " " + p.title) if p else ""
        o = overlap(c.evidence, src)
        scores.append(o)
        if o >= threshold:
            grounded += 1
        type_counts[c.claim_type] = type_counts.get(c.claim_type, 0) + 1

    n_papers = len({c.paper_id for c in claims})
    return {
        "claims": len(claims),
        "papers_with_claims": n_papers,
        "claims_per_paper": round(len(claims) / max(1, n_papers), 2),
        "groundedness_rate": round(grounded / len(claims), 3),
        "mean_evidence_overlap": round(sum(scores) / len(scores), 3),
        "type_distribution": type_counts,
        "mean_confidence": round(
            sum(c.confidence for c in claims) / len(claims), 3),
    }


if __name__ == "__main__":
    r = evaluate()
    print("── Reader eval ──")
    print(f"claims               : {r['claims']} over {r['papers_with_claims']} papers "
          f"({r['claims_per_paper']}/paper)")
    print(f"groundedness rate    : {r['groundedness_rate']:.1%}  (evidence span found in source)")
    print(f"mean evidence overlap: {r['mean_evidence_overlap']:.1%}")
    print(f"mean confidence      : {r['mean_confidence']}")
    print(f"type distribution    : {r['type_distribution']}")
