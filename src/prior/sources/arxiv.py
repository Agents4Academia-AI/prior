"""arXiv adapter — http://export.arxiv.org/api

arXiv has no citation graph but gives clean abstracts and full-text PDFs for
preprints. Useful as a complement to OpenAlex, especially for very recent work
that OpenAlex has not yet indexed. Returns Atom XML; parsed with stdlib.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import requests

from .. import config
from ..models import Paper

API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}


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
    published = txt("published")
    if len(published) >= 4 and published[:4].isdigit():
        year = int(published[:4])
    return Paper(
        id=f"arxiv:{arxiv_id}",
        source="arxiv",
        title=" ".join(txt("title").split()),
        abstract=" ".join(txt("summary").split()),
        url=raw_id,
        year=year,
        authors=authors,
    )


def search(query: str, *, max_papers: int = config.DEFAULT_MAX_PAPERS) -> list[Paper]:
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_papers,
        "sortBy": "relevance",
    }
    r = requests.get(API, params=params, headers={"User-Agent": config.USER_AGENT},
                     timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    return [_to_paper(e) for e in root.findall("atom:entry", NS)]
