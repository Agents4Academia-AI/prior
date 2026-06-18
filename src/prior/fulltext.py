"""Fetch a paper's full text. HTML-first (clean), PDF only as a fallback.

  arXiv      → arxiv.org/html/<id>  (→ ar5iv.org fallback)  — clean, no parsing
  other OA   → best_oa_location PDF via pypdf

Returns the extracted text (intro + body), or None if nothing is accessible.
"""

from __future__ import annotations

import io
import re

import requests

from . import config
from .sources import openalex

_UA = {"User-Agent": config.USER_AGENT}
_ARXIV_IN_URL = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})")


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|math|svg).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"&#?\w+;", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def _arxiv_html(arxiv_id: str) -> str | None:
    for url in (f"https://arxiv.org/html/{arxiv_id}", f"https://ar5iv.org/abs/{arxiv_id}"):
        try:
            r = requests.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
        except requests.RequestException:
            continue
        if r.status_code == 200 and "<html" in r.text[:2000].lower():
            text = _html_to_text(r.text)
            if len(text) > 1000:        # guard against stub/error pages
                return text
    return None


def _pdf_text(url: str, max_pages: int = 12) -> str | None:
    try:
        from pypdf import PdfReader  # lazy: only the PDF fallback needs it
        r = requests.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
        reader = PdfReader(io.BytesIO(r.content))
        text = "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
        return text.strip() or None
    except Exception:  # noqa: BLE001 — full text is best-effort
        return None


def _arxiv_id_of(paper) -> str | None:
    if paper.source == "arxiv" or paper.id.startswith("arxiv:"):
        return paper.id.split(":")[-1].split("v")[0]   # base id, drop version
    m = _ARXIV_IN_URL.search(paper.pdf_url or "")
    return m.group(1) if m else None


def fetch(paper) -> str | None:
    # 1. arXiv HTML (cleanest)
    aid = _arxiv_id_of(paper)
    if aid and (text := _arxiv_html(aid)):
        return text

    # 2. open-access PDF (resolve the URL fresh if the cached paper lacks it)
    url = paper.pdf_url
    if not url and paper.source == "openalex":
        fresh = openalex.fetch(paper.id)
        url = fresh.pdf_url if fresh else ""
        if (m := _ARXIV_IN_URL.search(url)) and (text := _arxiv_html(m.group(1))):
            return text
    return _pdf_text(url) if url else None
