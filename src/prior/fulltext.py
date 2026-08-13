"""Fetch a paper's full text, cheapest/cleanest source first.

Cascade (all free/open or publisher-sanctioned):
  1. arXiv HTML        arxiv.org/html/<id> (→ ar5iv)          — clean, no parsing
  2. open-access PDF   OpenAlex best_oa_location              — free
  3. preprint / Unpaywall  a *legal* OA copy resolved by DOI  — free, recovers most
  4. publisher TDM APIs    Elsevier / Springer / Wiley        — sanctioned text-mining
  5. arXiv title-search    a paywalled paper's open arXiv twin

We use only free/open channels and the publishers' own sanctioned text-mining APIs
(where entitled). Papers behind a paywall with no open copy are cited, not fetched —
some can't be retrieved at scale and may need to be added manually.

Returns the extracted text (intro + body), or None if nothing is accessible.
"""

from __future__ import annotations

import io
import html as html_lib
import json
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests

from . import config
from .sources import openalex

_UA = {"User-Agent": config.USER_AGENT}
_ARXIV_IN_URL = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})")
_throttle_lock = threading.Lock()   # paces rate-sensitive hits across fetch threads
_last_fetch = 0.0


@dataclass(frozen=True)
class FullTextCandidate:
    """One independently retrieved representation and its fitness for reuse."""

    text: str
    source: str
    bibliography_status: str
    reference_count: int

    @property
    def score(self) -> tuple[int, int, int]:
        status_rank = {
            "parsed": 5,
            "reference_block_unsegmented": 4,
            "heading_without_reference_block": 3,
            "heading_absent": 2,
            "short_or_stub": 1,
            "text_unavailable": 0,
        }
        return status_rank.get(self.bibliography_status, 0), self.reference_count, len(self.text)


# ── parsing helpers ─────────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|math|svg).*?</\1>", " ", html)
    # Preserve document structure. Bibliography headings and entry boundaries
    # are essential for citation recovery and were previously flattened away.
    html = re.sub(r"(?is)</?(?:article|section|div|p|h[1-6]|li|tr|br|hr)\b[^>]*>", "\n", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = html_lib.unescape(html)
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in html.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line)).strip()


def _pdf_text(content: bytes, max_pages: int | None = None) -> str | None:
    if not content[:5].startswith(b"%PDF"):          # landing/paywall page, not a PDF
        return None
    text = None
    try:
        import fitz  # PyMuPDF — infers word spacing far better than pypdf
        doc = fitz.open(stream=content, filetype="pdf")
        limit = len(doc) if max_pages is None else min(max_pages, len(doc))
        text = "\n".join(doc[i].get_text() for i in range(limit))
    except Exception:  # noqa: BLE001 — fall back to pypdf if fitz unavailable/fails
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            pages = reader.pages if max_pages is None else reader.pages[:max_pages]
            text = "\n".join((p.extract_text() or "") for p in pages)
        except Exception:  # noqa: BLE001 — full text is best-effort
            return None
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
    return text.strip() or None


def _throttle() -> None:
    global _last_fetch
    with _throttle_lock:                     # serialize rate-sensitive hits across threads
        wait = config.FULLTEXT_DELAY - (time.time() - _last_fetch)
        if wait > 0:
            time.sleep(wait)
        _last_fetch = time.time()


# ── raw full-text cache ──────────────────────────────────────────────────────────
# Persist every retrieved full text so we never re-fetch (expensive/rate-limited
# entitled pulls), keep provenance, and can re-extract with any model. Local copy
# only — within TDM/API terms; gitignored, never redistributed.
def _cache_path(paper):
    config.FULLTEXT.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", paper.id)
    return config.FULLTEXT / f"{safe}.txt"


def _quality_path(paper):
    return _cache_path(paper).with_suffix(".quality.json")


def fulltext_quality(text: str | None) -> dict:
    """Assess whether retrieved text is fit for citation-aware processing."""
    from .sources.refextract import bibliography_status, reference_entries
    value = text or ""
    status = bibliography_status(value)
    references = len(reference_entries(value)) if value else 0
    flags = []
    if status == "text_unavailable":
        flags.append("full_text_unavailable")
    elif status == "short_or_stub":
        flags.append("likely_stub_or_truncated")
    elif status == "heading_absent":
        flags.append("bibliography_not_present_in_retrieved_text")
    elif status == "heading_without_reference_block":
        flags.append("bibliography_heading_without_entries")
    elif status == "reference_block_unsegmented":
        flags.append("bibliography_layout_unsupported")
    return {"text_chars": len(value), "bibliography_status": status,
            "reference_count": references,
            "complete_for_citation_analysis": status == "parsed", "flags": flags}


def _cache_text(paper, text: str, source: str, *, attempts: list[dict] | None = None) -> None:
    _cache_path(paper).write_text(text)
    manifest = {"paper_id": paper.id, "selected_source": source,
                **fulltext_quality(text), "attempts": attempts or []}
    _quality_path(paper).write_text(json.dumps(manifest, indent=2))


def cached_quality(paper) -> dict | None:
    path = _quality_path(paper)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            pass
    text = cached_text(paper)
    return fulltext_quality(text) if text else None


def cached_text(paper) -> str | None:
    cp = _cache_path(paper)
    return cp.read_text() if cp.exists() and cp.stat().st_size else None


# ── 1. arXiv HTML ───────────────────────────────────────────────────────────────

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


def _arxiv_pdf(arxiv_id: str) -> str | None:
    """Fallback when arxiv.org/html has no rendering (older / LaTeX-source papers)."""
    try:
        r = requests.get(f"https://arxiv.org/pdf/{arxiv_id}", headers=_UA,
                         timeout=config.HTTP_TIMEOUT)
    except requests.RequestException:
        return None
    return _pdf_text(r.content)


def _arxiv_id_of(paper) -> str | None:
    if paper.source == "arxiv" or paper.id.startswith("arxiv:"):
        return paper.id.split(":")[-1].split("v")[0]   # base id, drop version
    m = _ARXIV_IN_URL.search(paper.pdf_url or "")
    return m.group(1) if m else None


def _manifestation_locators(paper) -> tuple[list[str], list[str], list[str]]:
    """All arXiv ids, PDF URLs and DOIs retained for one canonical work."""
    arxiv_ids, pdfs, dois = [], [], []
    for item in paper.all_manifestations():
        hay = " ".join(str(item.get(k) or "") for k in ("id", "url", "pdf_url", "doi"))
        match = re.search(r"(?:arxiv[:./]|abs/|pdf/)(\d{4}\.\d{4,5})(?:v\d+)?", hay, re.I)
        if match: arxiv_ids.append(match.group(1))
        if item.get("pdf_url"): pdfs.append(item["pdf_url"])
        value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(item.get("doi") or "").lower())
        if value: dois.append(value)
    return list(dict.fromkeys(arxiv_ids)), list(dict.fromkeys(pdfs)), list(dict.fromkeys(dois))


def _arxiv_search(title: str) -> str | None:
    """Last-ditch: a paper behind a paywall/repository DOI often has an open arXiv
    twin. Find it by title (arxiv.find_id_by_title) and use its clean HTML/PDF."""
    from .sources import arxiv
    _throttle()                                        # arXiv API asks for slow polling
    aid = arxiv.find_id_by_title(title)
    return (_arxiv_html(aid) or _arxiv_pdf(aid)) if aid else None


# ── preprint servers (bioRxiv / medRxiv / openRxiv) — open access ────────────────
_PREPRINT_PREFIXES = ("10.1101", "10.64898")   # 10.64898 = openRxiv (bio/medRxiv)


def _preprint_base(doi: str) -> str | None:
    if not any(doi.startswith(p) for p in _PREPRINT_PREFIXES):
        return None
    _throttle()                                # bio/medRxiv rate-limit automated bursts
    try:                                       # resolve to the bio/medRxiv landing URL
        r = requests.head(f"https://doi.org/{doi}", headers=_UA,
                          timeout=config.HTTP_TIMEOUT, allow_redirects=True)
        base = r.url.rstrip("/")
    except requests.RequestException:
        return None
    return base if "/content/" in base else None


def _url_text(url: str) -> str | None:
    try:                                       # fall back to the full-text HTML page
        r = requests.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
        head = r.text[:3000].lower()
        if r.status_code == 200 and ("<html" in head or "<article" in head):
            text = _html_to_text(r.text)
            if len(text) > 1000:
                return text
    except requests.RequestException:
        pass
    return None


def _preprint(doi: str) -> str | None:
    base = _preprint_base(doi)
    if not base:
        return None
    return _oa_pdf(base + ".full.pdf") or _url_text(base + ".full")


def _doi_html(doi: str) -> str | None:
    """Try the DOI landing page as full text; quality scoring rejects metadata."""
    try:
        r = requests.get(f"https://doi.org/{doi}", headers=_UA,
                         timeout=config.HTTP_TIMEOUT, allow_redirects=True)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    text = _html_to_text(r.text)
    return text if len(text) > 1000 else None


# ── Elsevier ScienceDirect full-text API (sanctioned TDM route) ──────────────────
def _elsevier(doi: str) -> str | None:
    if not config.ELSEVIER_API_KEY or not doi.startswith("10.1016"):
        return None
    headers = dict(_UA)
    if config.ELSEVIER_INSTTOKEN:           # entitlement: insttoken (off-campus) or IP
        headers["X-ELS-Insttoken"] = config.ELSEVIER_INSTTOKEN
    try:
        r = requests.get(f"https://api.elsevier.com/content/article/doi/{doi}",
                         params={"APIKey": config.ELSEVIER_API_KEY}, headers=headers,
                         timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
    except requests.RequestException:
        return None
    # <originalText> holds the full body when entitled; only the abstract otherwise.
    m = re.search(r"<[^>]*originalText[^>]*>(.*?)</[^>]*originalText>", r.text, re.S)
    body = _html_to_text(m.group(1)) if m else ""
    return body if len(body) > 2500 else None   # reject metadata/abstract-only


# ── Springer Nature open-access JATS API ─────────────────────────────────────────
def _springer(doi: str) -> str | None:
    if not config.SPRINGER_API_KEY or not doi.startswith(("10.1007", "10.1038", "10.1186")):
        return None
    try:
        r = requests.get(f"https://api.springernature.com/openaccess/jats/doi/{doi}",
                         params={"api_key": config.SPRINGER_API_KEY}, headers=_UA,
                         timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200 or "<article" not in r.text:
            return None
    except requests.RequestException:
        return None
    text = _html_to_text(r.text)          # JATS XML → plain text
    return text if len(text) > 1000 else None


# ── Wiley TDM API (returns the article PDF) ──────────────────────────────────────
def _wiley(doi: str) -> str | None:
    if not config.WILEY_API_KEY or not doi.startswith(("10.1002", "10.1111")):
        return None
    _throttle()                           # Wiley TDM asks for a slow cadence
    try:
        r = requests.get(f"https://api.wiley.com/onlinelibrary/tdm/v1/articles/{doi}",
                         headers=dict(_UA) | {"Wiley-TDM-Client-Token": config.WILEY_API_KEY},
                         timeout=config.HTTP_TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None
    except requests.RequestException:
        return None
    return _pdf_text(r.content)


# ── 2. open-access PDF ──────────────────────────────────────────────────────────

def _oa_pdf(url: str) -> str | None:
    try:
        r = requests.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
    except requests.RequestException:
        return None
    return _pdf_text(r.content)


# ── 3. Unpaywall (legal OA by DOI) ───────────────────────────────────────────────

def _doi_of(paper) -> str | None:
    doi = (paper.doi or "").strip()
    if not doi:
        return None
    return doi.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "")


def _unpaywall(doi: str) -> str | None:
    if not config.UNPAYWALL_EMAIL:
        return None
    try:
        r = requests.get(f"https://api.unpaywall.org/v2/{doi}",
                         params={"email": config.UNPAYWALL_EMAIL},
                         headers=_UA, timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    # try the designated best location first, then every OA location
    locs = [data.get("best_oa_location")] + (data.get("oa_locations") or [])
    for loc in locs:
        if not loc:
            continue
        for url in (loc.get("url_for_pdf"), loc.get("url")):
            if url and (text := _oa_pdf(url)):
                return text
    return None


# ── generic OA resolver: landing-page citation_pdf_url (covers preprint servers) ──
def _meta_pdf(doi: str) -> str | None:
    """Resolve doi.org -> landing page -> <meta name=citation_pdf_url> -> PDF.
    Catches preprint servers (ChemRxiv, Research Square, OSF/PsyArXiv, TechRxiv,
    Authorea, ETH, Zenodo, ...) and OA journals that Unpaywall and the publisher
    APIs miss. None for paywalled (the linked 'PDF' is a login page, rejected by
    the %PDF check)."""
    try:
        r = requests.get(f"https://doi.org/{doi}", headers=_UA,
                         timeout=config.HTTP_TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return None
        html = r.text
    except requests.RequestException:
        return None
    # resolve a (possibly relative / scheme-relative) citation_pdf_url as a browser
    # would: against <base href> if declared, else the final landing-page URL.
    bh = re.search(r"(?is)<base[^>]+href=[\"']([^\"']+)", html)
    base = urljoin(r.url, bh.group(1)) if bh else r.url
    for pat in (r'name=["\']citation_pdf_url["\'][^>]*?content=["\']([^"\']+)',
                r'content=["\']([^"\']+)["\'][^>]*?name=["\']citation_pdf_url["\']'):
        m = re.search(pat, html, re.I | re.S)
        if m and (text := _oa_pdf(urljoin(base, m.group(1).replace("&amp;", "&")))):
            return text
    return None


# ── orchestrator ─────────────────────────────────────────────────────────────────

def fetch_with_source(paper, *, use_cache: bool = True,
                      require_bibliography: bool = False) -> tuple[str | None, str]:
    """Full text plus the channel that produced it. Reads the raw-text cache first
    (channel 'cache'); on a fresh hit, writes the raw text to the cache so it's
    never re-fetched. Channel ∈ {cache, arxiv, arxiv_pdf, oa_pdf, preprint,
    unpaywall, elsevier, springer, wiley, meta_pdf, arxiv_search, none}."""
    cached = cached_text(paper) if use_cache else None
    if cached and not require_bibliography:
        # Backfill a manifest for caches created before quality tracking existed.
        if not _quality_path(paper).exists():
            try:
                _cache_text(paper, cached, "cache")
            except OSError:
                pass
        return cached, "cache"
    if require_bibliography:
        text, src, attempts = fetch_for_bibliography(paper, existing_text=cached)
        if text:
            try:
                _cache_text(paper, text, src, attempts=attempts)
            except OSError:
                pass
        return text, src
    text, src = _fetch_cascade(paper)
    if text:
        try:
            _cache_text(paper, text, src)
        except OSError:
            pass
    return text, src


def _candidate(text: str | None, source: str) -> FullTextCandidate | None:
    if not text:
        return None
    # Local import prevents the ordinary full-text path from paying citation
    # parsing cost or coupling module import order to the optional resolver.
    from .sources.refextract import bibliography_status, reference_entries
    return FullTextCandidate(text, source, bibliography_status(text),
                             len(reference_entries(text)))


def fetch_for_bibliography(paper, *, existing_text: str | None = None,
                           progress=None) -> tuple[str | None, str, list[dict]]:
    """Try alternate legal representations until a bibliography is recoverable.

    Unlike the normal latency-first cascade, this quality-first path does not
    stop at the first non-empty response. It retains an audit trail and returns
    the best representation by parse status, entry count, then text length.
    The caller decides where to cache it, so a failed retry cannot overwrite a
    previously useful text.
    """
    attempts: list[FullTextCandidate] = []
    audit: list[dict] = []

    def consider(text: str | None, source: str) -> bool:
        candidate = _candidate(text, source)
        if candidate:
            attempts.append(candidate)
            audit.append({"source": source, "bibliography_status": candidate.bibliography_status,
                          "reference_count": candidate.reference_count,
                          "text_chars": len(candidate.text)})
            if progress:
                progress(source, candidate.bibliography_status, candidate.reference_count)
            return candidate.bibliography_status == "parsed"
        if progress:
            progress(source, "text_unavailable", 0)
        audit.append({"source": source, "bibliography_status": "text_unavailable",
                      "reference_count": 0, "text_chars": 0})
        return False

    if existing_text:
        consider(existing_text, "existing")

    arxiv_ids, pdf_urls, dois = _manifestation_locators(paper)
    for aid in arxiv_ids:
        if consider(_arxiv_html(aid), "arxiv_html"):
            return _best_candidate(attempts, audit)
        if consider(_arxiv_pdf(aid), "arxiv_pdf"):
            return _best_candidate(attempts, audit)

    url = paper.pdf_url
    fresh_url = ""
    if paper.source == "openalex":
        fresh = openalex.fetch(paper.id)
        fresh_url = fresh.pdf_url if fresh else ""
        if fresh_url and (match := _ARXIV_IN_URL.search(fresh_url)):
            if consider(_arxiv_html(match.group(1)), "openalex_arxiv_html"):
                return _best_candidate(attempts, audit)
    for version_url in pdf_urls:
        if consider(_oa_pdf(version_url), "manifestation_pdf"):
            return _best_candidate(attempts, audit)
    if fresh_url and fresh_url != url and consider(_oa_pdf(fresh_url), "openalex_fresh_oa_pdf"):
        return _best_candidate(attempts, audit)

    channels = []
    for doi in dois:
        preprint_base = _preprint_base(doi)
        if preprint_base:
            channels.extend([
                ("preprint_html", lambda b=preprint_base: _url_text(b + ".full")),
                ("preprint_xml", lambda b=preprint_base: _url_text(b + ".full.xml")),
                ("preprint_pdf", lambda b=preprint_base: _oa_pdf(b + ".full.pdf")),
            ])
        channels.extend([("doi_html", lambda d=doi: _doi_html(d)),
                    ("unpaywall", lambda d=doi: _unpaywall(d)),
                    ("elsevier", lambda d=doi: _elsevier(d)),
                    ("springer", lambda d=doi: _springer(d)),
                    ("wiley", lambda d=doi: _wiley(d)),
                    ("meta_pdf", lambda d=doi: _meta_pdf(d))])
    for source, retrieve in channels:
        if consider(retrieve(), source):
            return _best_candidate(attempts, audit)
    consider(_arxiv_search(paper.title), "arxiv_search")
    return _best_candidate(attempts, audit)


def _best_candidate(attempts: list[FullTextCandidate], audit: list[dict] | None = None
                    ) -> tuple[str | None, str, list[dict]]:
    audit = audit or []
    if not attempts:
        return None, "none", audit
    best = max(attempts, key=lambda candidate: candidate.score)
    return best.text, best.source, audit


def _fetch_cascade(paper) -> tuple[str | None, str]:
    # 1. arXiv HTML (cleanest), then arXiv PDF (older/source-only papers)
    aid = _arxiv_id_of(paper)
    if aid:
        if text := _arxiv_html(aid):
            return text, "arxiv"
        if text := _arxiv_pdf(aid):
            return text, "arxiv_pdf"

    # 2. open-access PDF (resolve the URL fresh if the cached paper lacks it)
    url = paper.pdf_url
    if not url and paper.source == "openalex":
        fresh = openalex.fetch(paper.id)
        url = fresh.pdf_url if fresh else ""
        if (m := _ARXIV_IN_URL.search(url)) and (text := _arxiv_html(m.group(1))):
            return text, "arxiv"
    if url and (text := _oa_pdf(url)):
        return text, "oa_pdf"

    doi = _doi_of(paper)
    # 3. preprint servers (bioRxiv/medRxiv/openRxiv) — open access, free
    if doi and (text := _preprint(doi)):
        return text, "preprint"
    # 4. Unpaywall — a legal OA copy by DOI (recovers most "paywalled" records)
    if doi and (text := _unpaywall(doi)):
        return text, "unpaywall"
    # 5. publisher TDM APIs (entitled full text) — Elsevier, Springer, Wiley
    if doi and (text := _elsevier(doi)):
        return text, "elsevier"
    if doi and (text := _springer(doi)):
        return text, "springer"
    if doi and (text := _wiley(doi)):
        return text, "wiley"
    # 5b. generic OA landing-page resolver (preprint servers + OA journals)
    if doi and (text := _meta_pdf(doi)):
        return text, "meta_pdf"
    # 5c. arXiv title-search — a paywalled/repository paper may have an arXiv twin
    if text := _arxiv_search(paper.title):
        return text, "arxiv_search"
    return None, "none"


def fetch(paper) -> str | None:
    return fetch_with_source(paper)[0]


def fetch_many(papers, *, workers: int = 12, progress=print,
               require_bibliography: bool = False) -> dict:
    """Standalone batch full-text retrieval — the reusable 'obtain full text' stage.
    Runs the cascade over `papers` in PARALLEL (I/O-bound, no LLM), caching each
    success to data/fulltext/. Idempotent (cache hits skip re-fetch). Returns
    {channel: count}. Depends on nothing in the rest of the pipeline — give it any
    objects with .id/.title/.doi/.source/.pdf_url and you get cached full text."""
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor
    channels: Counter = Counter()
    quality: Counter = Counter()
    papers = list(papers)

    def _one(p):
        _text, source = fetch_with_source(p, require_bibliography=require_bibliography)
        manifest = cached_quality(p) or {"bibliography_status": "text_unavailable"}
        return source, manifest["bibliography_status"]

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (src, status) in enumerate(ex.map(_one, papers), 1):
            channels[src] += 1
            quality[status] += 1
            if i % 25 == 0:
                progress(f"  fetched {i}/{len(papers)} ...")
    got = sum(v for k, v in channels.items() if k not in ("none", "missing_paper"))
    progress(f"  full text: {got}/{len(papers)} cached | "
             + ", ".join(f"{k}:{v}" for k, v in channels.most_common()))
    progress("  retrieval quality: " + ", ".join(f"{k}:{v}" for k, v in quality.most_common()))
    return dict(channels)
