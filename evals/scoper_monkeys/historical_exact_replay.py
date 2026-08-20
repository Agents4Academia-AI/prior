"""Replay the recovered June Scoper policy from a frozen construction stage.

Policy: initial 33-query depth-20 construction (supplied as an immutable input),
then one OpenAlex snowball: backward references from every broad-eligible work and
forward cited-by from the 25 most-cited OpenAlex works, 40 results each.  The
historical S2 snowball is recorded unavailable rather than silently replaced.
No adaptive query recovery is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prior import scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from product_disagreement import screen_historical  # noqa: E402


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, values) -> None:
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contradiction(in_scope: bool, reason: str) -> list[str]:
    text = reason.lower()
    flags = []
    if in_scope and any(term in text for term in (
        "out of scope", "reads as a survey", "review article", "position paper",
        "perspective paper", "not an agentic", "does not meet",
    )):
        flags.append("accept_rationale_indicates_exclusion")
    if not in_scope and any(term in text for term in (
        "directly in scope", "directly matches", "core contribution is the agent",
    )):
        flags.append("exclude_rationale_indicates_inclusion")
    return flags


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--construction-dir", required=True, type=Path)
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--strict-scope", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--reuse-broad-cache", type=Path)
    ap.add_argument("--model")
    args = ap.parse_args()
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise SystemExit("output directory must be new and empty")
    args.out_dir.mkdir(parents=True)

    source_snapshot = args.construction_dir / "snapshot/eligible.jsonl"
    source_manifest = args.construction_dir / "manifest.json"
    construction_rows = rows(source_snapshot)
    papers = [Paper.from_dict(row.get("paper", row)) for row in construction_rows]

    copied = args.out_dir / "construction-snapshot.jsonl"
    shutil.copy2(source_snapshot, copied)
    broad_cache = args.out_dir / "broad-screen-cache.jsonl"
    if args.reuse_broad_cache:
        shutil.copy2(args.reuse_broad_cache, broad_cache)

    events = []
    def observe(event: dict) -> None:
        converted = {}
        for key, value in event.items():
            converted[key] = value.to_dict() if isinstance(value, Paper) else value
        events.append(converted)

    new_oa, reached = scoper.snowball(
        papers, corpus=papers, anchor_k=25, per_paper=40,
        progress=lambda message: print(message, flush=True), observe=observe, hop=1,
    )
    write_jsonl(args.out_dir / "openalex-snowball-ledger.jsonl", events)
    write_jsonl(args.out_dir / "openalex-new-candidates.jsonl", (p.to_dict() for p in new_oa))

    broad_dir = args.out_dir / "broad-citation-screen"
    screen_historical(
        args.out_dir / "openalex-new-candidates.jsonl", args.scope, broad_dir,
        args.model, cache=broad_cache,
    )
    accepted_new = rows(broad_dir / "eligible.jsonl")
    merged = construction_rows + accepted_new
    by_key = {}
    for row in merged:
        p = Paper.from_dict(row.get("paper", row))
        by_key.setdefault(p.key(), row)
    broad_corpus = args.out_dir / "broad-corpus.jsonl"
    write_jsonl(broad_corpus, (row.get("paper", row) for row in by_key.values()))

    strict_dir = args.out_dir / "strict-screen-raw"
    screen_historical(
        broad_corpus, args.strict_scope, strict_dir, args.model,
        cache=args.out_dir / "strict-screen-cache.jsonl",
    )
    audit = []
    for eligible, name in ((True, "eligible.jsonl"), (False, "excluded.jsonl")):
        for row in rows(strict_dir / name):
            reason = row.get("decision", {}).get("reason", "")
            flags = contradiction(eligible, reason)
            audit.append({
                "paper": row.get("paper", row), "in_scope": eligible,
                "reason": reason, "consistency_flags": flags,
            })
    write_jsonl(args.out_dir / "strict-decision-consistency-audit.jsonl", audit)
    flagged = [row for row in audit if row["consistency_flags"]]
    write_jsonl(args.out_dir / "strict-decisions-flagged-for-review.jsonl", flagged)

    summary = {
        "policy": "historical-scoper-replay-no-adaptive-queries-v1",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "construction_snapshot": str(source_snapshot),
            "construction_snapshot_sha256": sha(source_snapshot),
            "construction_manifest_sha256": sha(source_manifest),
            "scope_sha256": sha(args.scope), "strict_scope_sha256": sha(args.strict_scope),
        },
        "historical_policy": {
            "initial_queries": 33, "per_query_depth": 20,
            "adaptive_query_rounds": 0, "citation_hops": 1,
            "openalex_backward_seed_policy": "every broad-eligible work",
            "openalex_forward_seed_policy": "25 most-cited OpenAlex works",
            "openalex_forward_results_per_seed": 40,
            "semantic_scholar": "unavailable; historical channel not replayed",
        },
        "counts": {
            "construction_broad_eligible": len(construction_rows),
            "openalex_new_candidates": len(new_oa),
            "citation_broad_eligible": len(accepted_new),
            "broad_corpus": len(by_key),
            "strict_raw_eligible": sum(row["in_scope"] for row in audit),
            "strict_raw_excluded": sum(not row["in_scope"] for row in audit),
            "strict_consistency_flags": len(flagged),
            "citation_reached_existing": len(reached),
        },
        "screening_note": "Raw historical decisions are preserved; consistency flags do not mutate labels.",
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
