"""Run the SciFact eval.

    # validate the whole harness with ZERO API calls / ZERO credits:
    python evals/scifact/run.py --data <scifact_dir> --mock

    # cheap real dev slice on the Claude Code (Max subscription) backend:
    python evals/scifact/run.py --data <scifact_dir> --limit 20 \
        --backend claude-code --model claude-sonnet-4-6

    # full run on the API:
    python evals/scifact/run.py --data <scifact_dir> --backend api

`--download` fetches SciFact into <scifact_dir> first (one-off, network).
Predictions are cached, so reruns skip finished claims.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
sys.path.insert(0, str(THIS.parents[1]))        # evals/  -> `import scifact`
sys.path.insert(0, str(THIS.parents[2] / "src"))  # src/   -> `import prior`

from scifact import dataset, harness  # noqa: E402


def _mock_ask(atlas, question, *, model=None, **_):
    """Deterministic stand-in for navigator.ask — no LLM. Exercises retrieval,
    atlas construction, mapping, and scoring so the harness can be validated for
    free. Spreads predictions across labels so the report is non-degenerate."""
    from prior.navigator import ForwardAnswer

    claims = list(atlas.claims.values())
    bucket = abs(hash(question)) % 3
    if not claims or bucket == 2:
        return ForwardAnswer("not_found", "(mock)", [], [], [], "none", "mock", [])
    cid = claims[0].id
    if bucket == 0:
        return ForwardAnswer("established", "(mock)", [cid], [], [], "", "", claims)
    return ForwardAnswer("contested", "(mock)", [], [cid], [], "", "", claims)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="dir containing corpus.jsonl + claims_*.jsonl")
    ap.add_argument("--split", default="dev")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--k", type=int, default=5, help="abstracts retrieved per claim")
    ap.add_argument("--model", default=None)
    ap.add_argument("--backend", choices=["api", "claude-code"], default=None,
                    help="overrides PRIOR_LLM_BACKEND")
    ap.add_argument("--mock", action="store_true", help="no LLM; validate plumbing for free")
    ap.add_argument("--cache", default=None, help="JSONL of predictions (resumable)")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args(argv)

    if args.backend:
        os.environ["PRIOR_LLM_BACKEND"] = args.backend

    data_dir = Path(args.data)
    if args.download:
        data_dir = dataset.download(data_dir)
    corpus, claims = dataset.load(data_dir, split=args.split)
    print(f"loaded {len(corpus)} abstracts, {len(claims)} {args.split} claims"
          + (f"  (mock backend)" if args.mock else f"  (backend={os.environ.get('PRIOR_LLM_BACKEND','api')})"))

    m = harness.run_eval(
        corpus, claims,
        k=args.k, model=args.model, limit=args.limit,
        ask_fn=_mock_ask if args.mock else harness.navigator.ask,
        cache_path=Path(args.cache) if args.cache else None,
    )
    print()
    print(harness.render(m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
