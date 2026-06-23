"""Fetch a paper's full text, cheapest/cleanest source first.

Cascade:
  1. arXiv HTML        arxiv.org/html/<id> (→ ar5iv)          — clean, no parsing
  2. open-access PDF   OpenAlex best_oa_location              — free
  3. Unpaywall         a *legal* OA copy resolved by DOI      — free, recovers most
  4. institutional     Oxford/Bodleian via EZproxy + cookies  — entitled, opt-in

Steps 1–3 are free and always on. Step 4 is OFF unless `config.EZPROXY_HOST` and a
cookie file (`config.INSTITUTIONAL_COOKIES`) are set — it fetches only papers the
user is *entitled* to, prefers Crossref TDM links (sanctioned for text-mining),
and is rate-limited. It is the user's own library access, used politely; it is not
a paywall bypass. Bulk runs should respect publisher TDM terms.

Returns the extracted text (intro + body), or None if nothing is accessible.
"""

from __future__ import annotations

import http.cookiejar
import io
import re
import threading
import time
from urllib.parse import quote, urljoin

import requests

from . import config
from .sources import openalex

_UA = {"User-Agent": config.USER_AGENT}
_ARXIV_IN_URL = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5})")
_throttle_lock = threading.Lock()   # paces rate-sensitive hits across fetch threads
_last_fetch = 0.0


# ── parsing helpers ─────────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|math|svg).*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    html = re.sub(r"&#?\w+;", " ", html)
    return re.sub(r"\s+", " ", html).strip()


def _pdf_text(content: bytes, max_pages: int = 14) -> str | None:
    if not content[:5].startswith(b"%PDF"):          # landing/paywall page, not a PDF
        return None
    text = None
    try:
        import fitz  # PyMuPDF — infers word spacing far better than pypdf
        doc = fitz.open(stream=content, filetype="pdf")
        text = "\n".join(doc[i].get_text() for i in range(min(max_pages, len(doc))))
    except Exception:  # noqa: BLE001 — fall back to pypdf if fitz unavailable/fails
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
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


def _arxiv_search(title: str) -> str | None:
    """Last-ditch: a paper behind a paywall/repository DOI often has an open arXiv
    twin. Find it by title (arxiv.find_id_by_title) and use its clean HTML/PDF."""
    from .sources import arxiv
    _throttle()                                        # arXiv API asks for slow polling
    aid = arxiv.find_id_by_title(title)
    return (_arxiv_html(aid) or _arxiv_pdf(aid)) if aid else None


# ── preprint servers (bioRxiv / medRxiv / openRxiv) — open access ────────────────
_PREPRINT_PREFIXES = ("10.1101", "10.64898")   # 10.64898 = openRxiv (bio/medRxiv)


def _preprint(doi: str) -> str | None:
    if not any(doi.startswith(p) for p in _PREPRINT_PREFIXES):
        return None
    _throttle()                                # bio/medRxiv rate-limit automated bursts
    try:                                       # resolve to the bio/medRxiv landing URL
        r = requests.head(f"https://doi.org/{doi}", headers=_UA,
                          timeout=config.HTTP_TIMEOUT, allow_redirects=True)
        base = r.url.rstrip("/")
    except requests.RequestException:
        return None
    if "/content/" not in base:
        return None
    if text := _oa_pdf(base + ".full.pdf"):    # the rendered PDF
        return text
    try:                                       # fall back to the full-text HTML page
        r = requests.get(base + ".full", headers=_UA, timeout=config.HTTP_TIMEOUT)
        if r.status_code == 200 and "<html" in r.text[:2000].lower():
            text = _html_to_text(r.text)
            if len(text) > 1000:
                return text
    except requests.RequestException:
        pass
    return None


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


# ── 4. institutional access (Oxford / Bodleian via EZproxy) ──────────────────────

def _institutional_session() -> requests.Session | None:
    """A requests Session carrying the user's authenticated library cookies.
    Cookies are sufficient on their own (OpenAthens/Shibboleth, as at Oxford);
    EZPROXY_HOST is only needed for EZproxy-style URL-rewriting institutions."""
    if not config.INSTITUTIONAL_COOKIES:
        return None
    try:
        jar = http.cookiejar.MozillaCookieJar(config.INSTITUTIONAL_COOKIES)
        jar.load(ignore_discard=True, ignore_expires=True)
    except (OSError, http.cookiejar.LoadError):
        return None
    s = requests.Session()
    s.cookies = jar
    s.headers.update(_UA)
    return s


def _ezproxy(url: str) -> str:
    """Wrap a publisher URL in the EZproxy login form so it resolves through the
    institution's entitlement (the session cookie carries the authentication)."""
    return f"https://{config.EZPROXY_HOST}/login?url={quote(url, safe='')}"


def _crossref_tdm_pdfs(doi: str) -> list[str]:
    """Crossref `link` entries flagged for text-mining — the sanctioned full-text
    URLs for an entitled reader. Ordered text-mining-first."""
    try:
        r = requests.get(f"https://api.crossref.org/works/{doi}",
                         headers=_UA, timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return []
        links = r.json().get("message", {}).get("link", [])
    except (requests.RequestException, ValueError):
        return []
    pdfs = [l["URL"] for l in links
            if l.get("content-type") in ("application/pdf", "unspecified") and l.get("URL")]
    tdm = [l["URL"] for l in links
           if l.get("intended-application") == "text-mining" and l.get("URL")]
    seen, ordered = set(), []
    for u in tdm + pdfs:                    # TDM links first, dedup preserving order
        if u not in seen:
            seen.add(u); ordered.append(u)
    return ordered


def _institutional(paper) -> str | None:
    session = _institutional_session()
    doi = _doi_of(paper)
    if not session or not doi:
        return None
    # candidate full-text URLs: Crossref TDM links, then the DOI landing page
    candidates = _crossref_tdm_pdfs(doi) or [f"https://doi.org/{doi}"]
    for url in candidates:
        _throttle()
        target = _ezproxy(url) if config.EZPROXY_HOST else url   # OpenAthens: cookie-only
        try:
            r = session.get(target, timeout=config.HTTP_TIMEOUT, allow_redirects=True)
        except requests.RequestException:
            continue
        if text := _pdf_text(r.content):
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


# ── Playwright (real browser) — website-only / bot-protected publishers ──────────
def _playwright(paper) -> str | None:
    """Last resort: drive a real (persistent, logged-in) browser to clear JS /
    Cloudflare walls. Reads the publisher's citation_pdf_url, else the article
    body. Opt-in; reuses config.PLAYWRIGHT_PROFILE (seed it once via SSO)."""
    if not config.PLAYWRIGHT:
        return None
    doi = _doi_of(paper)
    url = f"https://doi.org/{doi}" if doi else (paper.url or paper.pdf_url or "")
    if not url:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    _throttle()
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                config.PLAYWRIGHT_PROFILE, headless=True,
                user_agent=config.USER_AGENT)
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded",
                          timeout=config.HTTP_TIMEOUT * 1000)
                page.wait_for_timeout(2500)                # let JS / redirects settle
                pdf_url = page.evaluate(
                    "() => { const m = document.querySelector("
                    "'meta[name=citation_pdf_url]'); return m && m.content; }")
                if pdf_url:                                # fetch PDF in-session (auth applies)
                    resp = ctx.request.get(pdf_url, timeout=config.HTTP_TIMEOUT * 1000)
                    if (text := _pdf_text(resp.body())):
                        return text
                for sel in ("article", "main", "div[id*=fulltext]", "body"):
                    try:
                        body = page.inner_text(sel)
                    except Exception:  # noqa: BLE001
                        continue
                    if body and len(body) > 3000:
                        return re.sub(r"\s+", " ", body).strip()
                return None
            finally:
                ctx.close()
    except Exception:  # noqa: BLE001 — browser path is best-effort
        return None


# ── orchestrator ─────────────────────────────────────────────────────────────────

def fetch_with_source(paper, *, use_cache: bool = True) -> tuple[str | None, str]:
    """Full text plus the channel that produced it. Reads the raw-text cache first
    (channel 'cache'); on a fresh hit, writes the raw text to the cache so it's
    never re-fetched. Channel ∈ {cache, arxiv, arxiv_pdf, oa_pdf, preprint,
    unpaywall, elsevier, springer, wiley, institutional, playwright, none}."""
    if use_cache and (t := cached_text(paper)):
        return t, "cache"
    text, src = _fetch_cascade(paper)
    if text:
        try:
            _cache_path(paper).write_text(text)      # persist raw full text
        except OSError:
            pass
    return text, src


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
    # 6. institutional (Oxford/Bodleian cookies) — opt-in, entitled, rate-limited
    if text := _institutional(paper):
        return text, "institutional"
    # 7. Playwright real browser — website-only / bot-protected publishers
    if text := _playwright(paper):
        return text, "playwright"
    return None, "none"


def fetch(paper) -> str | None:
    return fetch_with_source(paper)[0]


def fetch_many(papers, *, workers: int = 12, progress=print) -> dict:
    """Standalone batch full-text retrieval — the reusable 'obtain full text' stage.
    Runs the cascade over `papers` in PARALLEL (I/O-bound, no LLM), caching each
    success to data/fulltext/. Idempotent (cache hits skip re-fetch). Returns
    {channel: count}. Depends on nothing in the rest of the pipeline — give it any
    objects with .id/.title/.doi/.source/.pdf_url and you get cached full text."""
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor
    channels: Counter = Counter()
    papers = list(papers)

    def _one(p):
        return fetch_with_source(p)[1]                  # caches on success; returns channel

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, src in enumerate(ex.map(_one, papers), 1):
            channels[src] += 1
            if i % 25 == 0:
                progress(f"  fetched {i}/{len(papers)} ...")
    got = sum(v for k, v in channels.items() if k not in ("none", "missing_paper"))
    progress(f"  full text: {got}/{len(papers)} cached | "
             + ", ".join(f"{k}:{v}" for k, v in channels.most_common()))
    return dict(channels)
