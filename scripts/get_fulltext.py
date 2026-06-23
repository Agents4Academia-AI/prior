"""Stage 2 — OBTAIN FULL TEXT (standalone, reusable, deterministic).

Give it corpus papers (--select) or a plain list of DOIs / arXiv ids (--ids FILE,
one per line), and it runs the retrieval cascade in parallel, caching clean text to
$PRIOR_DATA_DIR/fulltext/. No dependency on the exploration or extraction stages —
other hackathon projects can use it with just a list of identifiers.

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/get_fulltext.py --select missing
    PRIOR_DATA_DIR=mydata        PYTHONPATH=src python3 scripts/get_fulltext.py --ids dois.txt
"""

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, fulltext, pipeline       # noqa: E402
from prior.models import Paper                       # noqa: E402


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", choices=["all", "core", "missing", "skip", "preprints"],
                    default="missing")
    ap.add_argument("--ids", help="file of DOIs / arXiv ids, one per line (any project)")
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    config.ensure_dirs()

    papers = _from_ids(args.ids) if args.ids else pipeline.select_papers(args.select)
    _log(f"obtaining full text for {len(papers)} papers"
         + (f" from {args.ids}" if args.ids else f" (--select {args.select})"))
    fulltext.fetch_many(papers, workers=args.workers, progress=_log)


if __name__ == "__main__":
    main()
