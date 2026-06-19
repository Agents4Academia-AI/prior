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

from .. import config
from ..models import Paper
from ._filters import looks_like_review

SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = ("title,abstract,year,authors,externalIds,citationCount,"
          "openAccessPdf,publicationTypes,venue")


def _headers() -> dict:
    h = {"User-Agent": config.USER_AGENT}
    key = os.environ.get("PRIOR_S2_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
    if key:
        h["x-api-key"] = key
    return h


def _to_paper(it: dict) -> Paper:
    ext = it.get("externalIds") or {}
    arxiv_id = ext.get("ArXiv")
    pid = f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{it.get('paperId')}"
    doi = ext.get("DOI")
    authors = [a.get("name", "") for a in (it.get("authors") or [])]
    types = it.get("publicationTypes") or []
    title = it.get("title") or "(untitled)"
    return Paper(
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
    )


def _get(params: dict, *, tries: int = 5):
    """GET with backoff — the keyless S2 pool 429s readily; a patient retry
    (fine for an unattended run) recovers most requests without a key."""
    delay = 3.0
    last = None
    for _ in range(tries):
        last = requests.get(SEARCH, params=params, headers=_headers(),
                            timeout=config.HTTP_TIMEOUT)
        if last.status_code == 429:
            time.sleep(delay)
            delay *= 1.7
            continue
        last.raise_for_status()
        return last
    last.raise_for_status()                        # exhausted retries → surface 429
    return last


def search(query: str, *, max_papers: int = config.DEFAULT_MAX_PAPERS,
           require_abstract: bool = True, exclude_reviews: bool = True) -> list[Paper]:
    params = {"query": query, "limit": min(max_papers * 3, 100), "fields": FIELDS}
    r = _get(params)
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
