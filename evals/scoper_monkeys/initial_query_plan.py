"""Generate and freeze the initial zero-shot Scoper query plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import scoper  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--max-queries", type=int, default=10)
    ap.add_argument("--fixed-queries", type=Path,
                    help="Optional historical/domain query scaffold, one per line")
    ap.add_argument("--model")
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)
    generated = scoper.propose_queries(args.scope.read_text(), model=args.model)
    fixed = (args.fixed_queries.read_text().splitlines()
             if args.fixed_queries else [])
    queries = list(dict.fromkeys(
        q.strip() for q in fixed + generated if q.strip()
    ))[:args.max_queries]
    if not queries:
        raise RuntimeError("Scoper generated no initial queries")
    query_file = args.out_dir / "initial-queries.txt"
    query_file.write_text("\n".join(queries) + "\n")
    (args.out_dir / "initial-query-manifest.json").write_text(json.dumps({
        "stage": "zero_shot_query_generation", "scope": str(args.scope),
        "scope_sha256": hashlib.sha256(args.scope.read_bytes()).hexdigest(),
        "model": args.model, "queries": queries,
        "fixed_queries": fixed,
        "fixed_queries_path": str(args.fixed_queries) if args.fixed_queries else None,
        "fixed_queries_sha256": (hashlib.sha256(args.fixed_queries.read_bytes()).hexdigest()
                                  if args.fixed_queries else None),
        "generated_queries": generated, "hidden_targets_loaded": False,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
