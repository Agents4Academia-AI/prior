"""Render a paper as a *complete* Markdown document — LaTeX math + embedded figures.

Where `fulltext.py` deliberately strips math/SVG and flattens everything to a
plain-text body (it feeds an LLM extractor), `fullpaper` keeps the paper whole:

  * equations  → LaTeX, recovered from the MathML `alttext` arXiv/ar5iv render
                 ($…$ inline, $$…$$ display)
  * figures    → real images, embedded inline as base64 data-URIs (one portable
                 .md file) or saved to a sibling `<id>_assets/` folder
  * structure  → headings, lists, tables, captions, references, appendix

Every facet is instrumented through `FullPaperOptions` (and the CLI in
scripts/fullpaper.py): math on/off, images on/off, embed vs. link, page cap.

Sources, richest first:
  1. arXiv HTML (arxiv.org/html → ar5iv)  — the only source that carries true
     LaTeX (in MathML `alttext`) and tagged figures. The headline path.
  2. PDF (OA / arXiv / Unpaywall) via pymupdf4llm — structure-aware Markdown with
     figures (and vector-drawn plots), honouring `max_pages`; falls back to a plain
     PyMuPDF text+image loop if pymupdf4llm is absent. A PDF holds no LaTeX, so math
     stays as extracted text (documented, not silently mangled). Used when no HTML
     render exists. Install: pip install -e ".[fullpaper]".

Returns a `FullPaperResult` (markdown + provenance + counts). `render_many` is the
parallel batch entry point, mirroring `fulltext.fetch_many`.
"""

from __future__ import annotations

import base64
import html as _html
import mimetypes
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import requests

from . import config, fulltext

_UA = {"User-Agent": config.USER_AGENT}


# ── options ──────────────────────────────────────────────────────────────────────

@dataclass
class FullPaperOptions:
    """Instrumentation for a render. Defaults come from config (env-overridable)."""

    include_math: bool = None          # type: ignore[assignment]  # None → config default
    include_images: bool = None        # type: ignore[assignment]
    embed_images: bool = None          # type: ignore[assignment]  # base64 inline vs assets dir
    max_pages: int = None              # type: ignore[assignment]  # PDF page cap (0 = all)
    min_image_px: int = None           # type: ignore[assignment]  # drop images smaller than this

    def __post_init__(self):
        if self.include_math is None:
            self.include_math = config.FULLPAPER_MATH
        if self.include_images is None:
            self.include_images = config.FULLPAPER_IMAGES
        if self.embed_images is None:
            self.embed_images = config.FULLPAPER_EMBED_IMAGES
        if self.max_pages is None:
            self.max_pages = config.FULLPAPER_MAX_PAGES
        if self.min_image_px is None:
            self.min_image_px = config.FULLPAPER_MIN_IMAGE_PX


@dataclass
class FullPaperResult:
    markdown: str | None
    channel: str                       # arxiv_html | pdf | cache | none
    n_math: int = 0
    n_images: int = 0
    assets: dict[str, bytes] = field(default_factory=dict)  # filename → bytes (link mode)


# ── image emit helper (shared by both paths) ─────────────────────────────────────

def _emit_image(data: bytes, mime: str, alt: str, opts: FullPaperOptions,
                result: FullPaperResult, stem: str) -> str:
    """Return the Markdown for one image, recording it on `result`. Embedded as a
    base64 data-URI, or staged into `result.assets` for the caller to write next to
    the .md as `<stem>_assets/figNNN.<ext>`."""
    result.n_images += 1
    idx = result.n_images
    alt = (alt or f"figure {idx}").strip()
    if opts.embed_images:
        b64 = base64.b64encode(data).decode("ascii")
        return f"![{alt}](data:{mime};base64,{b64})"
    ext = mimetypes.guess_extension(mime) or ".img"
    if ext == ".jpe":
        ext = ".jpg"
    name = f"fig{idx:03d}{ext}"
    result.assets[name] = data
    return f"![{alt}]({stem}_assets/{name})"


def _clean_markdown(md: str) -> str:
    md = re.sub(r"(?<=\S) {2,}", " ", md)       # mid-line double spaces (keep indents)
    md = re.sub(r"[ \t]+\n", "\n", md)          # trailing whitespace
    md = re.sub(r"\n{3,}", "\n\n", md)          # collapse blank-line runs
    return md.strip() + "\n"


# ── 1. arXiv HTML → Markdown ─────────────────────────────────────────────────────

_BLOCK = {"p", "div", "section", "article", "header", "footer", "blockquote",
          "figure", "figcaption", "tr", "br"}
_HEADINGS = {f"h{i}": i for i in range(1, 7)}
_INLINE_WRAP = {"em": "*", "i": "*", "strong": "**", "b": "**", "code": "`"}


class _HTMLToMarkdown(HTMLParser):
    """A pragmatic, dependency-free HTML→Markdown converter tuned for arXiv/ar5iv
    renders. Recovers LaTeX from `<math alttext=…>`, downloads `<img>` figures, and
    keeps document structure (headings, lists, tables, captions)."""

    def __init__(self, base_url: str, opts: FullPaperOptions,
                 result: FullPaperResult, stem: str, session: requests.Session):
        super().__init__(convert_charrefs=True)
        self.base_url, self.opts, self.result = base_url, opts, result
        self.stem, self.session = stem, session
        self.out: list[str] = []
        self._skip = 0                  # >0 ⇒ inside a skipped subtree (script/style/svg/math)
        self._list: list[str] = []      # stack of "ul"/"ol"; ol items numbered
        self._ol_n: list[int] = []
        self._cell: list[str] | None = None   # current table cell buffer
        self._row: list[str] | None = None
        self._table: list[list[str]] | None = None
        self._table_has_head = False
        # arXiv wraps display equations in <table class="...ltx_eqn_table">; collect
        # their math (and the ltx_eqn_eqno number) and emit clean $$…$$ blocks rather
        # than table scaffolding.
        self._eqn_rows: list[dict] | None = None   # not None ⇒ inside an equation table
        self._in_eqno = False

    # text sink: route to the open table cell, else the document body
    def _put(self, s: str) -> None:
        sink = self._cell if self._cell is not None else self.out
        if sink and sink[-1].endswith("\n"):     # no stray space at the start of a line
            s = s.lstrip(" ")
            if not s:
                return
        sink.append(s)

    def handle_starttag(self, tag, attrs):
        if self._skip:
            self._skip += 1
            return
        a = dict(attrs)
        if tag in ("script", "style", "svg", "nav"):
            self._skip = 1
            return
        if tag == "math":
            if self.opts.include_math:
                latex = _html.unescape(a.get("alttext", "")).strip()
                if latex:
                    self.result.n_math += 1
                    if self._eqn_rows is not None:           # collect for the eqn block
                        if self._eqn_rows:
                            self._eqn_rows[-1]["math"].append(latex)
                    else:
                        disp = a.get("display") == "block"
                        self._put(f"\n\n$$\n{latex}\n$$\n\n" if disp else f" ${latex}$ ")
            self._skip = 1              # skip the MathML subtree either way
            return
        if tag == "img":
            self._handle_img(a)
            return
        if tag in _HEADINGS:
            self._put("\n\n" + "#" * _HEADINGS[tag] + " ")
            return
        if tag in _INLINE_WRAP:
            self._put(_INLINE_WRAP[tag])
            return
        if tag in ("ul", "ol"):
            self._list.append(tag)
            self._ol_n.append(0)
            return
        if tag == "li":
            depth = max(0, len(self._list) - 1)
            indent = "  " * depth
            if self._list and self._list[-1] == "ol":
                self._ol_n[-1] += 1
                self._put(f"\n{indent}{self._ol_n[-1]}. ")
            else:
                self._put(f"\n{indent}- ")
            return
        if tag == "table":
            if "ltx_eqn_table" in a.get("class", ""):     # equation, not a real table
                self._eqn_rows = []
            else:
                self._table, self._table_has_head = [], False
            return
        if tag == "tr":
            if self._eqn_rows is not None:
                self._eqn_rows.append({"math": [], "eqno": ""})
            elif self._table is not None:
                self._row = []
            return
        if tag in ("td", "th"):
            if self._eqn_rows is not None:
                self._in_eqno = "ltx_eqn_eqno" in a.get("class", "")
            elif self._table is not None:
                self._cell = []
                if tag == "th":
                    self._table_has_head = True
            return
        if tag == "br":
            self._put("  \n")
            return
        if tag in _BLOCK:
            self._put("\n\n")

    def handle_startendtag(self, tag, attrs):
        if tag == "img" and not self._skip:
            self._handle_img(dict(attrs))
        elif tag == "br" and not self._skip:
            self._put("  \n")

    def handle_endtag(self, tag):
        if self._skip:
            self._skip -= 1
            return
        if tag in _INLINE_WRAP:
            self._put(_INLINE_WRAP[tag])
            return
        if tag in ("ul", "ol"):
            if self._list:
                self._list.pop(); self._ol_n.pop()
            self._put("\n")
            return
        if tag in ("td", "th"):
            if self._eqn_rows is not None:
                self._in_eqno = False
            elif self._table is not None and self._cell is not None:
                text = re.sub(r"\s+", " ", "".join(self._cell)).strip()
                (self._row if self._row is not None else []).append(text)
                self._cell = None
            return
        if tag == "tr":
            if self._eqn_rows is None and self._table is not None and self._row is not None:
                self._table.append(self._row)
                self._row = None
            return
        if tag == "table":
            if self._eqn_rows is not None:
                self._flush_equation()
            elif self._table is not None:
                self._flush_table()
            return
        if tag in _HEADINGS or tag in _BLOCK:
            self._put("\n\n")

    def handle_data(self, data):
        if self._skip:
            return
        if self._eqn_rows is not None:                # inside an equation table
            if self._in_eqno and self._eqn_rows:
                self._eqn_rows[-1]["eqno"] += data    # capture the eqn number
            return                                    # ignore padding-cell text
        self._put(re.sub(r"[ \t\r\n]+", " ", data))   # whitespace-only → single sep space

    # — helpers —
    def _handle_img(self, a: dict) -> None:
        if not self.opts.include_images:
            return
        src = a.get("src") or a.get("data-src")
        if not src or src.startswith("data:"):
            return
        url = urljoin(self.base_url, src)
        data, mime = _download_image(url, self.session)
        if data is None:
            return
        md = _emit_image(data, mime, a.get("alt", ""), self.opts, self.result, self.stem)
        self._put(f"\n\n{md}\n\n")

    def _flush_equation(self) -> None:
        """Emit the collected equation rows as clean $$…$$ blocks (number → \\tag),
        dropping the table scaffolding entirely."""
        rows = self._eqn_rows or []
        self._eqn_rows = None
        blocks = []
        for row in rows:
            math = " ".join(m for m in row["math"] if m).strip()
            if not math:
                continue
            eqno = re.sub(r"^\((.*)\)$", r"\1", row["eqno"].strip()).strip()
            tag = f" \\tag{{{eqno}}}" if eqno else ""
            blocks.append(f"$$\n{math}{tag}\n$$")
        if blocks:
            self._put("\n\n" + "\n\n".join(blocks) + "\n\n")

    def _flush_table(self) -> None:
        rows = [r for r in (self._table or []) if r]
        self._table = None
        if not rows:
            return
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        head = rows[0] if self._table_has_head else [""] * ncol
        body = rows[1:] if self._table_has_head else rows
        lines = ["\n", "| " + " | ".join(head) + " |",
                 "| " + " | ".join(["---"] * ncol) + " |"]
        lines += ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in body]
        self._put("\n".join(lines) + "\n\n")

    def markdown(self) -> str:
        return "".join(self.out)


def _download_image(url: str, session: requests.Session) -> tuple[bytes | None, str]:
    try:
        r = session.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200 or not r.content:
            return None, ""
    except requests.RequestException:
        return None, ""
    mime = (r.headers.get("Content-Type") or "").split(";")[0].strip()
    if not mime.startswith("image/"):
        mime = mimetypes.guess_type(url)[0] or "image/png"
    return r.content, mime


def _arxiv_html_markdown(arxiv_id: str, opts: FullPaperOptions,
                         result: FullPaperResult, stem: str) -> str | None:
    session = requests.Session()
    for url in (f"https://arxiv.org/html/{arxiv_id}", f"https://ar5iv.org/abs/{arxiv_id}"):
        try:
            r = requests.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
        except requests.RequestException:
            continue
        if r.status_code != 200 or "<html" not in r.text[:2000].lower():
            continue
        # confine to the article body when present (drops site chrome/nav)
        body = re.search(r"(?is)<article\b.*?</article>", r.text)
        chunk = body.group(0) if body else r.text
        # Resolve relative <img src> exactly as a browser would: honour <base href>
        # when the render declares one (newer arXiv HTML, e.g. "/html/2302.10130v3/"),
        # else fall back to the final response URL (older renders whose src already
        # carries the versioned dir, e.g. "1706.03762v7/Figures/x.png").
        bh = re.search(r"(?is)<base[^>]+href=[\"']([^\"']+)", r.text)
        base = urljoin(r.url, bh.group(1)) if bh else r.url
        parser = _HTMLToMarkdown(base, opts, result, stem, session)
        parser.feed(chunk)
        md = _clean_markdown(parser.markdown())
        if len(md) > 1000:             # guard against stub/error pages
            return md
        result.n_math = result.n_images = 0   # reset partial counts before next try
        result.assets.clear()
    return None


# ── 2. PDF → Markdown (PyMuPDF) ──────────────────────────────────────────────────

def _pdf_bytes(paper) -> bytes | None:
    """Resolve a paper to raw PDF bytes via the free OA routes (arXiv PDF, the
    paper's own pdf_url, then Unpaywall's best OA location)."""
    aid = fulltext._arxiv_id_of(paper)
    urls: list[str] = []
    if aid:
        urls.append(f"https://arxiv.org/pdf/{aid}")
    if paper.pdf_url:
        urls.append(paper.pdf_url)
    doi = fulltext._doi_of(paper)
    if doi and config.UNPAYWALL_EMAIL:
        urls += _unpaywall_pdf_urls(doi)
    for url in urls:
        try:
            r = requests.get(url, headers=_UA, timeout=config.HTTP_TIMEOUT)
        except requests.RequestException:
            continue
        if r.content[:5].startswith(b"%PDF"):
            return r.content
    return None


def _unpaywall_pdf_urls(doi: str) -> list[str]:
    try:
        r = requests.get(f"https://api.unpaywall.org/v2/{doi}",
                         params={"email": config.UNPAYWALL_EMAIL},
                         headers=_UA, timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return []
        data = r.json()
    except (requests.RequestException, ValueError):
        return []
    out: list[str] = []
    for loc in [data.get("best_oa_location")] + (data.get("oa_locations") or []):
        if loc:
            out += [u for u in (loc.get("url_for_pdf"), loc.get("url")) if u]
    return out


def _pdf_markdown(content: bytes, opts: FullPaperOptions,
                  result: FullPaperResult, stem: str) -> str | None:
    """PDF → Markdown. Prefers pymupdf4llm's structure-aware converter (headings,
    lists, tables, and figures incl. vector plots), falling back to a plain
    PyMuPDF text+image loop. A PDF carries no LaTeX, so math stays as extracted
    text on either path."""
    try:
        import fitz  # PyMuPDF — the engine behind both converters
    except ImportError:
        return None
    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception:  # noqa: BLE001
        return None
    n = len(doc) if opts.max_pages in (0, None) else min(opts.max_pages, len(doc))
    return (_pdf_markdown_llm(doc, n, opts, result, stem)
            or _pdf_markdown_fitz(fitz, doc, n, opts, result, stem))


_DATA_URI_IMG = re.compile(r"!\[([^\]]*)\]\(data:(image/[^;]+);base64,([A-Za-z0-9+/=]+)\)")


def _pdf_markdown_llm(doc, n: int, opts: FullPaperOptions,
                      result: FullPaperResult, stem: str) -> str | None:
    """pymupdf4llm.to_markdown — the package's own Markdown writer. Renders figures
    (and vector-drawn plots) inline as base64; we re-home them to honour embed-vs-link."""
    try:
        import pymupdf4llm
    except ImportError:
        return None
    pages = list(range(n))
    try:
        if opts.include_images:
            md = pymupdf4llm.to_markdown(doc, pages=pages, embed_images=True,
                                         show_progress=False)
        else:
            md = pymupdf4llm.to_markdown(doc, pages=pages, ignore_images=True,
                                         ignore_graphics=True, show_progress=False)
    except Exception:  # noqa: BLE001 — fall back to the plain loop
        return None
    md = _rehome_data_uris(md, opts, result, stem)
    md = _clean_markdown(md)
    return md if len(md) > 200 else None


def _rehome_data_uris(md: str, opts: FullPaperOptions,
                      result: FullPaperResult, stem: str) -> str:
    """Count base64 figures pymupdf4llm inlined; in link mode decode them into
    `result.assets` and rewrite the references to the sibling assets dir."""
    if not opts.include_images:
        return md
    if opts.embed_images:
        result.n_images = len(_DATA_URI_IMG.findall(md))
        return md

    def repl(m):
        data = base64.b64decode(m.group(3))
        return _emit_image(data, m.group(2), m.group(1), opts, result, stem)

    return _DATA_URI_IMG.sub(repl, md)


def _pdf_markdown_fitz(fitz, doc, n: int, opts: FullPaperOptions,
                       result: FullPaperResult, stem: str) -> str | None:
    """Fallback: plain per-page text + embedded raster images (no pymupdf4llm)."""
    seen: set[int] = set()
    parts: list[str] = []
    for i in range(n):
        page = doc[i]
        text = page.get_text().replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
        if text.strip():
            parts.append(text.strip())
        if opts.include_images:
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                md = _pdf_image_md(fitz, doc, xref, opts, result, stem)
                if md:
                    parts.append(md)
    md = _clean_markdown("\n\n".join(parts))
    return md if len(md) > 200 else None


def _pdf_image_md(fitz, doc, xref: int, opts: FullPaperOptions,
                  result: FullPaperResult, stem: str) -> str | None:
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.width < opts.min_image_px or pix.height < opts.min_image_px:
            return None
        if pix.n - pix.alpha >= 4:                 # CMYK / other → RGB
            pix = fitz.Pixmap(fitz.csRGB, pix)
        data = pix.tobytes("png")
    except Exception:  # noqa: BLE001 — image extraction is best-effort
        return None
    return "\n\n" + _emit_image(data, "image/png", "", opts, result, stem) + "\n\n"


# ── orchestrator ─────────────────────────────────────────────────────────────────

def _cache_path(paper) -> Path:
    config.FULLPAPER.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", paper.id)
    return config.FULLPAPER / f"{safe}.md"


def render(paper, opts: FullPaperOptions | None = None, *,
           use_cache: bool = True, write: bool = True) -> FullPaperResult:
    """Render `paper` to a full Markdown document. arXiv HTML first (true LaTeX +
    figures), PDF fallback otherwise. Caches the .md (and any assets dir) next to
    other renders in config.FULLPAPER unless `write=False`."""
    opts = opts or FullPaperOptions()
    cp = _cache_path(paper)
    if use_cache and cp.exists() and cp.stat().st_size:
        return FullPaperResult(cp.read_text(), "cache")

    stem = cp.stem
    result = FullPaperResult(None, "none")

    aid = fulltext._arxiv_id_of(paper)
    md = _arxiv_html_markdown(aid, opts, result, stem) if aid else None
    if md:
        result.channel = "arxiv_html"
    else:
        result = FullPaperResult(None, "none")     # discard partial HTML counts
        if (content := _pdf_bytes(paper)) and (md := _pdf_markdown(content, opts, result, stem)):
            result.channel = "pdf"

    if not md:
        return FullPaperResult(None, "none")

    md = _front_matter(paper, result) + md
    result.markdown = md
    if write:
        _write(cp, stem, md, result, opts)
    return result


def _front_matter(paper, result: FullPaperResult) -> str:
    bits = [f"# {paper.title}" if paper.title else f"# {paper.id}"]
    if paper.authors:
        bits.append("*" + ", ".join(paper.authors) + "*")
    meta = " · ".join(x for x in (str(paper.year) if paper.year else "", paper.venue or "",
                                  f"doi:{paper.doi}" if paper.doi else "") if x)
    if meta:
        bits.append(meta)
    bits.append(f"<!-- prior/fullpaper: {result.channel}, "
                f"{result.n_math} equations, {result.n_images} figures -->")
    return "\n\n".join(bits) + "\n\n"


def _write(cp: Path, stem: str, md: str, result: FullPaperResult,
           opts: FullPaperOptions) -> None:
    try:
        cp.write_text(md)
        if result.assets:                          # link mode: stage figures in a sibling dir
            adir = cp.parent / f"{stem}_assets"
            adir.mkdir(exist_ok=True)
            for name, data in result.assets.items():
                (adir / name).write_bytes(data)
    except OSError:
        pass


def render_many(papers, *, opts: FullPaperOptions | None = None,
                workers: int = 8, progress=print) -> dict:
    """Batch render in parallel (I/O-bound), mirroring fulltext.fetch_many. Returns
    {channel: count}. Idempotent: cache hits skip re-rendering."""
    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor
    opts = opts or FullPaperOptions()
    papers = list(papers)
    channels: Counter = Counter()

    def _one(p):
        return render(p, opts).channel

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, ch in enumerate(ex.map(_one, papers), 1):
            channels[ch] += 1
            if i % 10 == 0:
                progress(f"  rendered {i}/{len(papers)} ...")
    got = sum(v for k, v in channels.items() if k != "none")
    progress(f"  fullpaper: {got}/{len(papers)} rendered | "
             + ", ".join(f"{k}:{v}" for k, v in channels.most_common()))
    return dict(channels)
