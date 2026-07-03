"""Publication-date resolution: full dates + a precision tag for month-level
chronology.

Adapters set `date` (YYYY-MM-DD) + `date_source` from their API (day precision).
`resolve` then (a) fills a missing date from the arXiv id (month, zero-cost) or
the year (year), and (b) enforces *preprint precedence* — an arXiv preprint's
month beats a later venue date — so the frontier reflects first appearance.
"""
from __future__ import annotations

import re

# arXiv new-scheme id YYMM.xxxxx (post-2007). Old-scheme ids (math/0309001) don't
# match and fall through to the year fallback — fine for a recent-LLM corpus.
_ARXIV = re.compile(r"(\d{2})(\d{2})\.\d{4,5}")

_REAL_SOURCES = ("openalex", "arxiv", "semanticscholar")


def arxiv_id_of(paper) -> str | None:
    """The paper's arXiv id, from its canonical id or any arXiv locator."""
    if (paper.id or "").startswith("arxiv:"):
        return paper.id.split(":", 1)[1]
    for s in (paper.pdf_url, paper.url, paper.doi):
        if s and "arxiv" in s.lower() and _ARXIV.search(s):
            return _ARXIV.search(s).group(0)
    return None


def _from_arxiv_id(aid: str | None):
    m = _ARXIV.search(aid or "")
    if not m:
        return None
    yy, mm = m.group(1), m.group(2)
    if not 1 <= int(mm) <= 12:
        return None
    return (f"20{yy}-{mm}-01", "month", "arxiv_id")


def resolve(paper):
    """Set paper.date / date_precision / date_source. Safe to re-run after
    arXiv-twin enrichment — it recomputes from the API date + the arXiv id."""
    cands = []                                   # (YYYY-MM-DD, precision, source)
    if paper.date and paper.date_source in _REAL_SOURCES:
        cands.append((paper.date[:10], "day", paper.date_source))
    av = _from_arxiv_id(arxiv_id_of(paper))
    if av:
        cands.append(av)
    if cands:
        # earliest month wins (preprint precedence); within a month prefer day precision
        paper.date, paper.date_precision, paper.date_source = min(
            cands, key=lambda c: (c[0][:7], 0 if c[1] == "day" else 1))
    elif paper.year:
        paper.date, paper.date_precision, paper.date_source = (
            f"{paper.year}-01-01", "year", "year_fallback")
    else:
        paper.date, paper.date_precision, paper.date_source = "", "", ""
    return paper


def earliest(records):
    """Earliest real (day/month) date across same-paper source variants, as
    (date, precision, source) — preprint precedence for cross-source dedup."""
    best = None
    for p in records:
        if p.date and p.date_precision in ("day", "month"):
            cur = (p.date[:10], p.date_precision, p.date_source)
            if best is None or cur[0] < best[0]:
                best = cur
    return best


_PREC = {"day": 10, "month": 7, "year": 4}


def compare(date_a, prec_a, date_b, prec_b) -> int:
    """Order two dates at their COARSEST shared precision. -1 if a is earlier,
    +1 if b is earlier, 0 if equal/ambiguous (same bucket, or either missing).
    Used to set directional-edge precedence (builds_on/refines) by chronology
    instead of the model: the later contribution is the deriver, the earlier the
    antecedent."""
    if not date_a or not date_b:
        return 0
    p = min(_PREC.get(prec_a, 4), _PREC.get(prec_b, 4))
    a, b = date_a[:p], date_b[:p]
    return -1 if a < b else (1 if a > b else 0)
