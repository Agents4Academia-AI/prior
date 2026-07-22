"""arXiv adapter — http://export.arxiv.org/api

arXiv has no citation graph but gives clean abstracts and full-text PDFs for
preprints. Useful as a complement to OpenAlex, especially for very recent work
that OpenAlex has not yet indexed. Returns Atom XML; parsed with stdlib.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from .. import config, dates
from ..models import Paper
from ._filters import looks_like_review

API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}


def _get(params: dict, *, tries: int = 4) -> requests.Response:
    """arXiv throttles aggressively (429/503 even at modest rates); back off and
    honour Retry-After so unattended refresh runs survive it."""
    import time
    err: Exception | None = None
    for i in range(tries):
        try:
            r = requests.get(API, params=params,
                             headers={"User-Agent": config.USER_AGENT},
                             timeout=config.HTTP_TIMEOUT)
        except requests.RequestException as e:   # timeouts/conn resets during outages
            err, r = e, None
        if r is not None and r.status_code not in (429, 503):
            r.raise_for_status()
            return r
        wait = float(r.headers.get("Retry-After") or 0) if r is not None else 0
        time.sleep(min(wait or 5 * (i + 1), 60))
    if r is None:
        raise err  # type: ignore[misc]
    r.raise_for_status()
    return r


def _to_paper(entry: ET.Element) -> Paper:
    def txt(tag: str) -> str:
        el = entry.find(f"atom:{tag}", NS)
        return (el.text or "").strip() if el is not None else ""

    raw_id = txt("id")                       # http://arxiv.org/abs/2401.00001v1
    arxiv_id = raw_id.rstrip("/").split("/")[-1]
    authors = [
        (a.find("atom:name", NS).text or "").strip()
        for a in entry.findall("atom:author", NS)
        if a.find("atom:name", NS) is not None
    ]
    year = None
    published = txt("published")                 # first-version date — truest for precedence
    if len(published) >= 4 and published[:4].isdigit():
        year = int(published[:4])
    date = published[:10] if len(published) >= 10 and published[4] == "-" else ""
    title = " ".join(txt("title").split())
    return dates.resolve(Paper(
        id=f"arxiv:{arxiv_id}",
        source="arxiv",
        title=title,
        abstract=" ".join(txt("summary").split()),
        url=raw_id,
        year=year,
        authors=authors,
        is_review=looks_like_review(title),
        date=date,
        date_precision="day" if date else "",
        date_source="arxiv" if date else "",
    ))


def fetch_ids(arxiv_ids: list[str], *, batch: int = 50) -> dict[str, Paper]:
    """Fetch specific arXiv papers by id (e.g. '2504.01848'), keyed 'arxiv:<id>'.
    The direct path for very recent preprints OpenAlex hasn't indexed yet — no
    query, no ranking, so recall is exact for anything we can name."""
    import time
    clean = [i.split(":")[-1].split("v")[0] for i in dict.fromkeys(arxiv_ids) if i]
    out: dict[str, Paper] = {}
    for k in range(0, len(clean), batch):
        chunk = clean[k:k + batch]
        params = {"id_list": ",".join(chunk), "max_results": len(chunk)}
        try:
            r = _get(params)
        except requests.RequestException:
            continue
        for e in ET.fromstring(r.text).findall("atom:entry", NS):
            p = _to_paper(e)
            out[p.id] = p
        time.sleep(1.0)                          # be polite to arXiv
    return out


def fetch_abs(arxiv_id: str) -> Paper | None:
    """Fallback metadata fetch from the arxiv.org abs page — the export API
    lags days behind new listings and has outages; the abs page is live the
    moment a paper is announced. Abstract/title come from the page's citation_*
    meta tags, so no fragile HTML parsing."""
    aid = arxiv_id.split(":")[-1]
    try:
        r = requests.get(f"https://arxiv.org/abs/{aid}",
                         headers={"User-Agent": config.USER_AGENT},
                         timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return None
    meta = dict(re.findall(
        r'<meta name="citation_([a-z_]+)" content="([^"]*)"', r.text))
    title = meta.get("title", "")
    if not title:
        return None
    authors = [m for m in re.findall(
        r'<meta name="citation_author" content="([^"]*)"', r.text)]
    date = (meta.get("date") or meta.get("online_date") or "").replace("/", "-")
    return Paper(
        id=f"arxiv:{aid.split('v')[0]}", source="arxiv", title=title,
        abstract=meta.get("abstract", ""), url=f"https://arxiv.org/abs/{aid}",
        year=int(date[:4]) if date[:4].isdigit() else None, authors=authors,
        pdf_url=meta.get("pdf_url", ""),
        is_review=looks_like_review(title, ""),
        date=date, date_precision="day" if date else "",
        date_source="arxiv_abs" if date else "",
    )


def find_id_by_title(title: str) -> str | None:
    """Find a paper's arXiv 'twin' by title — return its arXiv id on a high-
    confidence title match, else None. OpenAlex often canonicalises a paper to a
    closed publisher/repository edition with no arXiv locator; this recovers the
    open edition so the full-text stage can use it."""
    import re
    want = set(re.sub(r"[^a-z0-9]", " ", (title or "").lower()).split())
    if len(want) < 4:
        return None
    try:
        r = requests.get(API, params={"search_query": f'ti:"{title}"', "max_results": 3},
                         headers={"User-Agent": config.USER_AGENT}, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except (requests.RequestException, ET.ParseError):
        return None
    for e in root.findall("atom:entry", NS):
        el, tl = e.find("atom:id", NS), e.find("atom:title", NS)
        if el is None or tl is None:
            continue
        aid = (el.text or "").rstrip("/").split("/")[-1].split("v")[0]
        at = set(re.sub(r"[^a-z0-9]", " ", (tl.text or "").lower()).split())
        if at and len(want & at) / max(len(want), len(at)) > 0.85:   # strict — avoid mismatches
            return aid
    return None


def search(query: str, *, max_papers: int = config.DEFAULT_MAX_PAPERS,
           exclude_reviews: bool = True, from_date: str | None = None) -> list[Paper]:
    query_str = f"all:{query}"
    if from_date:
        # Date window (YYYY-MM-DD) for freshness scans. Relevance sort still
        # applies WITHIN the window — date sort floods weak lexical matches.
        start = from_date.replace("-", "") + "0000"
        query_str = f"({query_str}) AND submittedDate:[{start} TO 209912312359]"
    params = {
        "search_query": query_str,
        "start": 0,
        "max_results": max_papers * 2,   # over-fetch: reviews get filtered
        "sortBy": "relevance",
    }
    r = _get(params)
    root = ET.fromstring(r.text)
    papers = [_to_paper(e) for e in root.findall("atom:entry", NS)]
    if exclude_reviews:
        papers = [p for p in papers if not p.is_review]
    return papers[:max_papers]
