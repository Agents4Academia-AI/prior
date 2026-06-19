"""Full-text fetcher — best-effort body text for a Paper.

Coverage strategy (no paywalled scraping):
  - arXiv papers       -> fetch the HTML rendering (arxiv.org/html, then ar5iv).
  - OpenAlex papers    -> if the title matches an arXiv preprint, use that;
                          otherwise fall back to abstract-only (return "").

HTML is stripped to plain text (good enough for LLM extraction). Returns "" when
no full text is available, and the caller falls back to the abstract.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET

import requests

from .. import config
from ..models import Paper

_ARXIV_API = "http://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}
_HTML_HOSTS = ("https://arxiv.org/html/{id}", "https://ar5iv.labs.arxiv.org/html/{id}")

_TAG = re.compile(r"<[^>]+>")
_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_WS = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")
_NONWORD = re.compile(r"[^a-z0-9]+")


def _norm_title(s: str) -> str:
    return _NONWORD.sub(" ", s.lower()).strip()


def _bare_arxiv_id(paper: Paper) -> str | None:
    """An arXiv id for this paper, if one can be determined."""
    if paper.id.startswith("arxiv:"):
        return paper.id.split(":", 1)[1]
    for hay in (paper.url or "", paper.doi or ""):
        m = re.search(r"arxiv\.org/abs/([0-9]+\.[0-9]+(?:v[0-9]+)?)", hay)
        if m:
            return m.group(1)
    return _arxiv_id_by_title(paper.title)


def _arxiv_id_by_title(title: str) -> str | None:
    """Look up an arXiv preprint by (near-)exact title match."""
    if not title:
        return None
    try:
        r = requests.get(
            _ARXIV_API,
            params={"search_query": f'ti:"{title}"', "max_results": 3},
            headers={"User-Agent": config.USER_AGENT}, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except Exception:  # noqa: BLE001 — best-effort
        return None
    want = _norm_title(title)
    for e in root.findall("atom:entry", _NS):
        t = e.find("atom:title", _NS)
        idn = e.find("atom:id", _NS)
        if t is None or idn is None:
            continue
        if _norm_title(" ".join((t.text or "").split())) == want:
            return (idn.text or "").rstrip("/").split("/")[-1]
    return None


def _html_to_text(raw: str) -> str:
    raw = _SCRIPT_STYLE.sub(" ", raw)
    raw = re.sub(r"</(p|div|section|h[1-6]|li|br)\s*>", "\n", raw, flags=re.I)
    text = html.unescape(_TAG.sub(" ", raw))
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANKS.sub("\n\n", text).strip()


def _fetch_html_text(arxiv_id: str) -> str:
    for tmpl in _HTML_HOSTS:
        url = tmpl.format(id=arxiv_id)
        try:
            r = requests.get(url, headers={"User-Agent": config.USER_AGENT},
                             timeout=config.HTTP_TIMEOUT)
            if r.status_code == 200 and "<html" in r.text.lower():
                text = _html_to_text(r.text)
                if len(text) > 2000:        # got a real body, not a stub/404 page
                    return text
        except Exception:  # noqa: BLE001 — try the next host
            continue
    return ""


def fetch(paper: Paper) -> str:
    """Best-effort full body text for a paper; "" if unavailable."""
    arxiv_id = _bare_arxiv_id(paper)
    if not arxiv_id:
        return ""
    return _fetch_html_text(arxiv_id)
