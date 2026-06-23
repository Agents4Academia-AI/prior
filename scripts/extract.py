"""Stage 3 — EXTRACTION (contributions + relations + view) from cached full text.

Reads $PRIOR_DATA_DIR/fulltext/ (run get_fulltext.py first). Sequential LLM
(concurrent claude-code is unsafe), additive + incremental. With --view it also
rebuilds a re-related filtered view.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src \
        python3 scripts/extract.py --select core --view core --model claude-haiku-4-5-20251001
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
    ap.add_argument("--view", default=None, help="also rebuild this filtered view")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    config.ensure_dirs()

    papers = pipeline.select_papers(args.select)
    _log(f"extracting {len(papers)} papers (--select {args.select})")
    r = pipeline.read_all(papers, model=args.model, progress=_log)
    _log(f"done | {len(r.contributions)} contributions, {len(r.claims)} claims, "
         f"{len(r.local_edges)} local edges (run `build`/`sink_to_neo4j` for the global graph)")


if __name__ == "__main__":
    main()
