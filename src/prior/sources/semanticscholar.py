"""Semantic Scholar adapter — https://api.semanticscholar.org/graph/v1

S2 has the strongest coverage of very recent preprints (often ahead of OpenAlex's
indexing) plus a citation graph and abstracts. Used to widen recall on recent
work. No key needed, but the public pool is rate-limited — set PRIOR_S2_API_KEY
(free from S2) for headroom. Results are paced and failures are non-fatal.

Papers that carry an arXiv id are keyed `arxiv:<id>` so they dedup against the
arXiv source; otherwise `s2:<paperId>`.
"""

from __future__ import annotations

import os
import time

import requests

from .. import config, dates
from ..models import Paper
from ._filters import looks_like_review

GRAPH = "https://api.semanticscholar.org/graph/v1/paper"
SEARCH = GRAPH + "/search"
FIELDS = ("title,abstract,year,authors,externalIds,citationCount,"
          "openAccessPdf,publicationTypes,venue,publicationDate")


_KEY_DISABLED = False     # set once if the key is rejected (expired/invalid)


def _key() -> str:
    return (os.environ.get("PRIOR_S2_API_KEY")
            or os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or "")


def _headers() -> dict:
    h = {"User-Agent": config.USER_AGENT}
    if _key() and not _KEY_DISABLED:
        h["x-api-key"] = _key()
    return h


def _to_paper(it: dict) -> Paper:
    ext = it.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv")
    pid = f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{it.get('paperId')}"
    doi = ext.get("DOI")
    authors = [a.get("name", "") for a in (it.get("authors") or [])]
    types = it.get("publicationTypes") or []
    title = it.get("title") or "(untitled)"
    pub_date = it.get("publicationDate") or ""        # sometimes null -> dates.resolve falls back
    return dates.resolve(Paper(
        id=pid,
        source="semanticscholar",
        title=title,
        abstract=it.get("abstract") or "",
        url=f"https://www.semanticscholar.org/paper/{it.get('paperId')}",
        year=it.get("year"),
        authors=[a for a in authors if a],
        venue=it.get("venue") or None,
        doi=f"https://doi.org/{doi}" if doi else None,
        referenced_works=[],                       # not returned by search
        cited_by_count=it.get("citationCount") or 0,
        pdf_url=(it.get("openAccessPdf") or {}).get("url") or "",
        is_review=("Review" in types) or looks_like_review(title),
        date=pub_date,
        date_precision="day" if pub_date else "",
        date_source="semanticscholar" if pub_date else "",
    ))


def _get(url: str, params: dict, *, tries: int = 6):
    """GET with backoff. A rejected key (401/403, e.g. expired) disables the key
    and retries keyless — a dead key must never silently break S2. The keyless
    pool 429s readily, so a patient retry recovers most requests."""
    global _KEY_DISABLED
    delay = 3.0
    last = None
    for _ in range(tries):
        last = requests.get(url, params=params, headers=_headers(),
                            timeout=config.HTTP_TIMEOUT)
        if last.status_code in (401, 403) and _key() and not _KEY_DISABLED:
            _KEY_DISABLED = True                   # key rejected → fall back keyless
            continue
        if last.status_code == 429:
            time.sleep(delay)
            delay *= 1.7
            continue
        last.raise_for_status()
        return last
    last.raise_for_status()                        # exhausted retries → surface error
    return last


def _neighbors(s2_id: str, kind: str, *, max_results: int) -> list[Paper]:
    """Paginate a citation edge list. kind='citations' (forward, papers citing
    s2_id) or 'references' (backward, papers s2_id cites). These endpoints sit in
    S2's 10 req/s tier, so with a key the snowball is cheap."""
    sub = "citingPaper" if kind == "citations" else "citedPaper"
    out: list[Paper] = []
    offset = 0
    while len(out) < max_results:
        params = {"fields": FIELDS, "limit": min(100, max_results - len(out)),
                  "offset": offset}
        try:
            body = _get(f"{GRAPH}/{s2_id}/{kind}", params).json()
        except requests.RequestException:
            break
        data = body.get("data") or []
        if not data:
            break
        for it in data:
            p = it.get(sub)
            if p and p.get("title"):
                out.append(_to_paper(p))
        nxt = body.get("next")
        if not nxt:
            break
        offset = nxt
    return out


def citations(s2_id: str, *, max_results: int = 60) -> list[Paper]:
    """Forward citations (papers that cite s2_id) — the recent-frontier signal
    OpenAlex lacks for fresh preprints."""
    return _neighbors(s2_id, "citations", max_results=max_results)


def references(s2_id: str, *, max_results: int = 60) -> list[Paper]:
    """Backward references (papers s2_id cites)."""
    return _neighbors(s2_id, "references", max_results=max_results)


def fetch(s2_id: str) -> Paper | None:
    """Fetch one paper's metadata (incl. abstract) by an S2-resolvable id:
    'ARXIV:2006.11239', 'DOI:10.1145/x', or a raw S2 paperId. The repair path uses
    this to recover an abstract when another source's copy is missing/corrupted."""
    try:
        r = _get(f"{GRAPH}/{s2_id}", {"fields": FIELDS})
    except requests.RequestException:
        return None
    it = r.json()
    return _to_paper(it) if it and it.get("title") else None


def search(query: str, *, max_papers: int = config.DEFAULT_MAX_PAPERS,
           require_abstract: bool = True, exclude_reviews: bool = True) -> list[Paper]:
    params = {"query": query, "limit": min(max_papers * 3, 100), "fields": FIELDS}
    r = _get(SEARCH, params)
    out: list[Paper] = []
    for it in r.json().get("data", []) or []:
        p = _to_paper(it)
        if require_abstract and not p.abstract:
            continue
        if exclude_reviews and p.is_review:
            continue
        out.append(p)
        if len(out) >= max_papers:
            break
    return out
