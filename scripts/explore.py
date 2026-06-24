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
    ap.add_argument("--recover-rounds", type=int, default=5,
                    help="query-recovery rounds: reformulate from results to fill recall gaps (0 = one-shot; stops early on saturation)")
    ap.add_argument("--no-repair", action="store_true",
                    help="skip abstract repair (arXiv/S2 backfill of corrupted abstracts)")
    ap.add_argument("--hub-cites", type=int, default=1000,
                    help="warn when a dropped paper has at least this many citations")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    config.ensure_dirs()

    corpus, dropped, stats = scoper.explore(
        args.topic, hops=args.hops, per_query=args.per_query,
        repair_abstracts=not args.no_repair, recover_rounds=args.recover_rounds,
        model=args.model, progress=_log)

    pp = config.RAW / "papers.jsonl"
    pp.write_text("\n".join(json.dumps(p.to_dict()) for p in corpus) + "\n")

    # Persist the dropped set + reasons so "why is X missing?" is auditable, not a
    # manual re-investigation.
    dp = config.RAW / "dropped.jsonl"
    dp.write_text("\n".join(json.dumps(
        {"id": p.id, "title": p.title, "cited_by_count": p.cited_by_count,
         "doi": p.doi, "reason": reason}) for p, reason in dropped) + "\n")

    # Hub-paper safety net: surface any high-citation paper that was dropped, so a
    # foundational miss is visible rather than silent.
    hubs = sorted(((p, r) for p, r in dropped if (p.cited_by_count or 0) >= args.hub_cites),
                  key=lambda pr: -(pr[0].cited_by_count or 0))
    if hubs:
        _log(f"WARNING: {len(hubs)} dropped paper(s) have >= {args.hub_cites} citations "
             f"— review {dp}:")
        for p, r in hubs[:10]:
            _log(f"  [{p.cited_by_count}] {p.title[:70]} — {r}")

    _log(f"DONE | {len(corpus)} scoped papers -> {pp} | {len(dropped)} dropped -> {dp} | "
         f"curve {stats['curve']} | completeness {stats['completeness']}")


if __name__ == "__main__":
    main()
