"""Orchestrator — chains the deterministic stages over a paper selection:
    obtain full text (parallel, cached) -> extract contributions -> [view].

Exploration (the agentic stage — search / snowball / scope) is separate, in
`scoper` / `scripts/enrich_arxiv.py`. For the individual stages use
`scripts/get_fulltext.py` and `scripts/extract.py`.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src \
        python3 scripts/expand.py --select core --view core --model claude-haiku-4-5-20251001
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, pipeline                 # noqa: E402


def _log(m):
    print(m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", choices=["all", "core", "missing", "skip", "preprints"],
                    default="core")
    ap.add_argument("--view", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()
    config.ensure_dirs()

    papers = pipeline.select_papers(args.select)
    _log(f"-- expand over {len(papers)} papers (--select {args.select}) --")
    _log(str(pipeline.expand(papers, model=args.model, view=args.view,
                             workers=args.workers, progress=_log)))


if __name__ == "__main__":
    main()
