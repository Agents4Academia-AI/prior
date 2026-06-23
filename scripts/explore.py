"""Stage 1 — EXPLORATION (the agentic stage): topic -> scoped corpus, one call.

Wraps `scoper.explore`, the full 4-point pipeline:
  1. recall-then-precision (LLM query variations over OpenAlex+arXiv+S2 -> LLM filter)
  2. citation snowball (backward refs + forward cited-by, OpenAlex + Semantic Scholar)
  3. BM25 pre-filter before the expensive LLM filter
  4. saturation stopping + a capture-recapture completeness estimate

Writes the scoped corpus to $PRIOR_DATA_DIR/raw/papers.jsonl. Use --hops 0 for a
search-only run (no snowball) if top-k recall is enough.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=mydata PYTHONPATH=src \
        python3 scripts/explore.py --topic "$(cat topic.txt)" --hops 3
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, scoper                  # noqa: E402


def _log(m):
    print(m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, help="in-/out-of-scope topic definition")
    ap.add_argument("--hops", type=int, default=3, help="snowball hops (0 = search only)")
    ap.add_argument("--per-query", type=int, default=25)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    config.ensure_dirs()

    corpus, dropped, stats = scoper.explore(
        args.topic, hops=args.hops, per_query=args.per_query, model=args.model, progress=_log)
    pp = config.RAW / "papers.jsonl"
    pp.write_text("\n".join(json.dumps(p.to_dict()) for p in corpus) + "\n")
    _log(f"DONE | {len(corpus)} scoped papers -> {pp} | "
         f"curve {stats['curve']} | completeness {stats['completeness']}")


if __name__ == "__main__":
    main()
