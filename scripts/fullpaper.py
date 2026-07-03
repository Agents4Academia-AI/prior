"""Render papers to complete Markdown — LaTeX math + embedded figures.

A richer sibling of get_fulltext.py: instead of a stripped plain-text body, it
produces a whole-paper Markdown file with equations as LaTeX ($…$ / $$…$$) and
figures embedded as images. Output goes to $PRIOR_DATA_DIR/fullpaper/ (override
with --out). Every facet is instrumented.

    # one paper, defaults (math + embedded figures), arXiv HTML preferred
    PYTHONPATH=src python3 scripts/fullpaper.py --ids ids.txt

    # text + plots but no equations, PDF capped at 12 pages, figures as files
    PYTHONPATH=src python3 scripts/fullpaper.py --select core \
        --no-math --max-pages 12 --no-embed --out renders/

`--ids FILE` takes DOIs / arXiv ids (one per line); `--select` pulls from the
built corpus (same selectors as get_fulltext.py).
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, fullpaper                  # noqa: E402
from prior.models import Paper                         # noqa: E402


def _log(m):
    print(m, flush=True)


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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--select", choices=["all", "core", "missing", "skip", "preprints"],
                     default="core")
    src.add_argument("--ids", help="file of DOIs / arXiv ids, one per line")
    ap.add_argument("--no-math", action="store_true", help="drop equations")
    ap.add_argument("--no-images", action="store_true", help="drop figures/plots")
    ap.add_argument("--no-embed", action="store_true",
                    help="save figures to <id>_assets/ and link, instead of base64-inline")
    ap.add_argument("--max-pages", type=int, default=None,
                    help="PDF page cap (0 = all; arXiv HTML is always rendered in full)")
    ap.add_argument("--out", help="output dir (default $PRIOR_DATA_DIR/fullpaper)")
    ap.add_argument("--no-cache", action="store_true", help="re-render even if cached")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if args.out:
        config.FULLPAPER = Path(args.out)
    config.ensure_dirs()

    opts = fullpaper.FullPaperOptions(
        include_math=not args.no_math,
        include_images=not args.no_images,
        embed_images=not args.no_embed,
        max_pages=args.max_pages,
    )

    if args.ids:                          # --ids depends on nothing else in the pipeline
        papers = _from_ids(args.ids)
    else:
        from prior import pipeline         # lazy: pulls in the (heavier) corpus stack
        papers = pipeline.select_papers(args.select)
    _log(f"rendering {len(papers)} papers to {config.FULLPAPER}"
         + (f" from {args.ids}" if args.ids else f" (--select {args.select})"))

    if args.no_cache:                 # render serially so the no-cache flag is honoured
        chan: dict = {}
        for i, p in enumerate(papers, 1):
            r = fullpaper.render(p, opts, use_cache=False)
            chan[r.channel] = chan.get(r.channel, 0) + 1
            if i % 10 == 0:
                _log(f"  rendered {i}/{len(papers)} ...")
        got = sum(v for k, v in chan.items() if k != "none")
        _log(f"  fullpaper: {got}/{len(papers)} rendered | "
             + ", ".join(f"{k}:{v}" for k, v in sorted(chan.items(), key=lambda kv: -kv[1])))
    else:
        fullpaper.render_many(papers, opts=opts, workers=args.workers, progress=_log)


if __name__ == "__main__":
    main()
