"""OpenAlex adapter — https://docs.openalex.org

OpenAlex is fully open, needs no API key, and crucially exposes citation edges
(`referenced_works`) and `cited_by_count`. That bibliographic structure is what
powers Navigator's backward / origin-tracing mode.
"""

from __future__ import annotations

import requests

from .. import config
from ..models import Paper
from ._filters import looks_like_review

API = "https://api.openalex.org/works"
_SELECT = ("id,title,publication_year,authorships,primary_location,doi,type,"
           "best_oa_location,abstract_inverted_index,referenced_works,cited_by_count")


def _headers() -> dict:
    return {"User-Agent": config.USER_AGENT}


def _params() -> dict:
    p: dict = {}
    if config.CONTACT_EMAIL:
        p["mailto"] = config.CONTACT_EMAIL
    return p


def _norm_id(openalex_url: str | None) -> str:
    """'https://openalex.org/W123' -> 'openalex:W123'."""
    if not openalex_url:
        return ""
    return "openalex:" + openalex_url.rstrip("/").split("/")[-1]


def _abstract_from_index(inv: dict | None) -> str:
    """OpenAlex stores abstracts as an inverted index {word: [positions]}."""
    if not inv:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def _pdf_url(w: dict) -> str:
    for loc in (w.get("best_oa_location"), w.get("primary_location")):
        if loc and loc.get("pdf_url"):
            return loc["pdf_url"]
    return ""


def _to_paper(w: dict) -> Paper:
    authors = [
        a.get("author", {}).get("display_name", "")
        for a in w.get("authorships", [])
    ]
    venue = (w.get("primary_location") or {}).get("source") or {}
    title = w.get("title") or "(untitled)"
    return Paper(
        id=_norm_id(w.get("id")),
        source="openalex",
        title=title,
        abstract=_abstract_from_index(w.get("abstract_inverted_index")),
        url=w.get("id") or "",
        year=w.get("publication_year"),
        authors=[a for a in authors if a],
        venue=venue.get("display_name"),
        doi=w.get("doi"),
        referenced_works=[_norm_id(r) for r in w.get("referenced_works", [])],
        cited_by_count=w.get("cited_by_count", 0),
        pdf_url=_pdf_url(w),
        is_review=looks_like_review(title, w.get("type", "")),
    )


def search(query: str, *, max_papers: int = config.DEFAULT_MAX_PAPERS,
           require_abstract: bool = True, exclude_reviews: bool = True) -> list[Paper]:
    """Search works by relevance; keep primary research with usable abstracts."""
    params = _params() | {
        "search": query,
        "per_page": min(max_papers * 3, 200),   # over-fetch: reviews get filtered
        "sort": "relevance_score:desc",
        "select": _SELECT,
    }
    r = requests.get(API, params=params, headers=_headers(),
                     timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    papers: list[Paper] = []
    for w in r.json().get("results", []):
        p = _to_paper(w)
        if require_abstract and not p.abstract:
            continue
        if exclude_reviews and p.is_review:
            continue
        papers.append(p)
        if len(papers) >= max_papers:
            break
    return papers


def fetch_many(ids: list[str], *, batch: int = 50) -> dict[str, Paper]:
    """Resolve many OpenAlex ids in batched requests (for reference expansion).
    Accepts 'openalex:W..' or bare 'W..'. Returns {id: Paper}."""
    clean = [i.split(":")[-1] for i in dict.fromkeys(ids) if i]
    out: dict[str, Paper] = {}
    for k in range(0, len(clean), batch):
        chunk = clean[k:k + batch]
        params = _params() | {
            "filter": "ids.openalex:" + "|".join(chunk),
            "per_page": batch,
            "select": _SELECT,
        }
        r = requests.get(API, params=params, headers=_headers(),
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        for w in r.json().get("results", []):
            p = _to_paper(w)
            out[p.id] = p
    return out


def cited_by(openalex_id: str, *, max_results: int = 50) -> list[Paper]:
    """Forward citations: works that CITE the given paper, most-recent first —
    the key signal for snowballing toward newer connected work."""
    wid = openalex_id.split(":")[-1]
    params = _params() | {
        "filter": f"cites:{wid}",
        "per_page": min(max_results, 200),
        "sort": "publication_date:desc",
        "select": _SELECT,
    }
    try:
        r = requests.get(API, params=params, headers=_headers(),
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return []
    return [_to_paper(w) for w in r.json().get("results", [])][:max_results]


def fetch(openalex_id: str) -> Paper | None:
    """Fetch a single work by id ('openalex:W123' or bare 'W123')."""
    wid = openalex_id.split(":")[-1]
    r = requests.get(f"{API}/{wid}", params=_params(), headers=_headers(),
                     timeout=config.HTTP_TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return _to_paper(r.json())
