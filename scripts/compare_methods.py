"""Render each paper through every extraction method into SEPARATE files, so the
outputs can be opened side by side and compared.

For each paper it writes four files into --out (one per method):

  <id>__1_fulltext.txt                 fulltext.py — plain text (the original path)
  <id>__2_fullpaper_html.md            fullpaper — arXiv HTML → Markdown (LaTeX math)
  <id>__3_fullpaper_pdf_pymupdf4llm.md fullpaper — PDF → Markdown via pymupdf4llm
  <id>__4_fullpaper_pdf_fitz.md        fullpaper — PDF → Markdown via the fitz fallback

A method that doesn't apply to a paper (e.g. no arXiv HTML render) still gets a
file, marked unavailable, so every paper has the full side-by-side set. Figures are
base64-embedded by default (self-contained, render in any Markdown preview); with
--no-embed they are written to per-method `<id>__<method>_assets/` folders instead.

Defaults to the curated prior.sample_papers set; override with --ids FILE.

    PYTHONPATH=src python3 scripts/compare_methods.py --out compare/
    PYTHONPATH=src python3 scripts/compare_methods.py --ids ids.txt --out compare/ --no-embed
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import fullpaper, fulltext                 # noqa: E402
from prior.models import Paper                          # noqa: E402
from prior.sample_papers import SAMPLE_PAPERS           # noqa: E402


def _log(m):
    print(m, flush=True)


def _stem(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", pid)


def _from_ids(path):
    papers = []
    for s in (l.strip() for l in Path(path).read_text().splitlines()):
        if not s or s.startswith("#"):
            continue
        if re.fullmatch(r"(arxiv:)?\d{4}\.\d{4,5}(v\d+)?", s):
            aid = s.split(":")[-1].split("v")[0]
            papers.append(Paper(id=f"arxiv:{aid}", source="arxiv", title="", abstract="", url=""))
        else:
            doi = s.replace("https://doi.org/", "").replace("doi:", "")
            papers.append(Paper(id=f"doi:{doi}", source="", title="", abstract="", url="", doi=doi))
    return papers


def _default_papers():
    return [Paper(id=s.id, source="arxiv" if s.id.startswith("arxiv") else "",
                  title=s.title, abstract="", url="") for s in SAMPLE_PAPERS]


def _write(path: Path, header: str, body: str | None) -> None:
    path.write_text(f"<!-- {header} -->\n\n" + (body or "_(method unavailable for this paper)_\n"))


def _write_assets(out: Path, stem: str, result) -> None:
    if result.assets:
        adir = out / f"{stem}_assets"
        adir.mkdir(exist_ok=True)
        for name, data in result.assets.items():
            (adir / name).write_bytes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", help="file of DOIs / arXiv ids (default: curated sample papers)")
    ap.add_argument("--out", default="compare", help="output dir (default: ./compare)")
    ap.add_argument("--no-embed", action="store_true",
                    help="write figures to per-method _assets/ dirs instead of base64-inline")
    ap.add_argument("--no-math", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--max-pages", type=int, default=None, help="PDF page cap (0 = all)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    opts = fullpaper.FullPaperOptions(include_math=not args.no_math,
                                      include_images=not args.no_images,
                                      embed_images=not args.no_embed,
                                      max_pages=args.max_pages)

    papers = _from_ids(args.ids) if args.ids else _default_papers()
    _log(f"comparing {len(papers)} papers across 4 methods -> {out.resolve()}/")

    for p in papers:
        stem = _stem(p.id)
        _log(f"== {p.id} ==")

        # 1. fulltext.py — plain text (runs the full retrieval cascade)
        try:
            txt, ch = fulltext.fetch_with_source(p, use_cache=False)
        except Exception as e:  # noqa: BLE001
            txt, ch = None, f"error: {e}"
        _write(out / f"{stem}__1_fulltext.txt",
               f"fulltext.py (plain text) | channel={ch} | chars={len(txt) if txt else 0}", txt)
        _log(f"  1 fulltext            channel={ch} chars={len(txt) if txt else 0}")

        # 2. fullpaper — arXiv HTML → Markdown (LaTeX math + figures)
        aid = fulltext._arxiv_id_of(p)
        r2 = fullpaper.FullPaperResult(None, "none")
        md2 = fullpaper._arxiv_html_markdown(aid, opts, r2, f"{stem}__2_html") if aid else None
        _write(out / f"{stem}__2_fullpaper_html.md",
               f"fullpaper arXiv-HTML | math={r2.n_math} images={r2.n_images}", md2)
        _write_assets(out, f"{stem}__2_html", r2)
        _log(f"  2 fullpaper html      math={r2.n_math} images={r2.n_images} "
             f"{'ok' if md2 else 'unavailable'}")

        # 3 & 4 share one PDF fetch + one fitz document
        content = fullpaper._pdf_bytes(p)
        r3 = fullpaper.FullPaperResult(None, "none")
        r4 = fullpaper.FullPaperResult(None, "none")
        md3 = md4 = None
        if content:
            try:
                import fitz
                doc = fitz.open(stream=content, filetype="pdf")
                n = len(doc) if opts.max_pages in (0, None) else min(opts.max_pages, len(doc))
                md3 = fullpaper._pdf_markdown_llm(doc, n, opts, r3, f"{stem}__3_pdfllm")
                md4 = fullpaper._pdf_markdown_fitz(fitz, doc, n, opts, r4, f"{stem}__4_pdffitz")
            except ImportError:
                _log("  (pymupdf/fitz not installed — PDF methods skipped; pip install -e '.[fullpaper]')")
            except Exception as e:  # noqa: BLE001
                _log(f"  PDF parse error: {e}")
        _write(out / f"{stem}__3_fullpaper_pdf_pymupdf4llm.md",
               f"fullpaper PDF via pymupdf4llm | images={r3.n_images}", md3)
        _write_assets(out, f"{stem}__3_pdfllm", r3)
        _write(out / f"{stem}__4_fullpaper_pdf_fitz.md",
               f"fullpaper PDF via fitz fallback | images={r4.n_images}", md4)
        _write_assets(out, f"{stem}__4_pdffitz", r4)
        _log(f"  3 fullpaper pdf(llm)  images={r3.n_images} {'ok' if md3 else 'unavailable'}")
        _log(f"  4 fullpaper pdf(fitz) images={r4.n_images} {'ok' if md4 else 'unavailable'}")

    _log(f"done -> {out.resolve()}/")


if __name__ == "__main__":
    main()
