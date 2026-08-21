"""Add the recovered historical S2 snowball to a completed OA-only replay.

Runs sequentially and checkpoints after every seed. It never modifies the OA-only
run. The caller should set PRIOR_S2_MIN_INTERVAL_SECONDS conservatively and clear
invalid API-key environment variables to use the anonymous citation endpoints.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prior import scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import semanticscholar  # noqa: E402
from product_disagreement import screen_historical  # noqa: E402


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, values) -> None:
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oa-run", required=True, type=Path)
    ap.add_argument("--construction-dir", required=True, type=Path)
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--strict-scope", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--model")
    args = ap.parse_args()
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise SystemExit("output directory must be new and empty")
    args.out_dir.mkdir(parents=True)

    construction_path = args.construction_dir / "snapshot/eligible.jsonl"
    construction = rows(construction_path)
    seeds = [Paper.from_dict(row.get("paper", row)) for row in construction]
    anchors = [p for p in seeds if (p.year or 0) >= 2024 or p.id.startswith(("arxiv:", "s2:"))]
    anchors = sorted(anchors, key=lambda p: -(p.year or 0))[:40]

    checkpoint = args.out_dir / "s2-seed-checkpoints.jsonl"
    complete = {row["seed_id"] for row in rows(checkpoint) if row.get("status") == "complete"}
    mode = "a" if checkpoint.exists() else "w"
    with checkpoint.open(mode) as handle:
        for index, seed in enumerate(anchors, 1):
            if seed.id in complete:
                continue
            sid = scoper._s2_id(seed)
            if not sid:
                handle.write(json.dumps({"seed_id": seed.id, "status": "unresolvable"}) + "\n")
                handle.flush()
                continue
            backward = semanticscholar.references(sid, max_results=40)
            forward = semanticscholar.citations(sid, max_results=40)
            record = {
                "seed_id": seed.id, "seed_title": seed.title, "s2_lookup_id": sid,
                "status": "complete", "backward": [p.to_dict() for p in backward],
                "forward": [p.to_dict() for p in forward],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"S2 seed {index}/{len(anchors)}: {seed.short_cite()} -> "
                  f"{len(backward)} back, {len(forward)} forward", flush=True)

    all_checkpoints = rows(checkpoint)
    candidates = []
    for record in all_checkpoints:
        candidates.extend(Paper.from_dict(value) for value in record.get("backward", []))
        candidates.extend(Paper.from_dict(value) for value in record.get("forward", []))
    candidates = scoper._dedup_cross_source(candidates)
    known = {p.key() for p in seeds}
    candidates = [p for p in candidates if p.key() not in known]
    candidate_path = args.out_dir / "s2-new-candidates.jsonl"
    write_jsonl(candidate_path, (p.to_dict() for p in candidates))

    broad_cache = args.out_dir / "broad-screen-cache.jsonl"
    shutil.copy2(args.oa_run / "broad-screen-cache.jsonl", broad_cache)
    s2_screen = args.out_dir / "s2-broad-screen"
    screen_historical(candidate_path, args.scope, s2_screen, args.model, cache=broad_cache)

    oa_broad = rows(args.oa_run / "broad-corpus.jsonl")
    s2_kept = rows(s2_screen / "eligible.jsonl")
    combined = {}
    for row in oa_broad + s2_kept:
        p = Paper.from_dict(row.get("paper", row))
        combined.setdefault(p.key(), row.get("paper", row))
    combined_path = args.out_dir / "broad-corpus-oa-s2.jsonl"
    write_jsonl(combined_path, combined.values())

    strict_dir = args.out_dir / "strict-screen-raw"
    screen_historical(combined_path, args.strict_scope, strict_dir, args.model,
                      cache=args.out_dir / "strict-screen-cache.jsonl")
    status = json.loads((strict_dir / "status.json").read_text())
    summary = {
        "policy": "historical-scoper-replay-no-adaptive-queries-oa-s2-v1",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {"oa_run": str(args.oa_run), "oa_summary_sha256": sha(args.oa_run / "summary.json"),
                   "construction_sha256": sha(construction_path)},
        "s2_policy": {"anchors": 40, "recent_year": 2024,
                      "directions": ["backward", "forward"], "per_direction": 40,
                      "execution": "anonymous, sequential, per-seed checkpointed"},
        "counts": {"s2_candidates": len(candidates), "s2_broad_eligible": len(s2_kept),
                   "combined_broad_corpus": len(combined),
                   "strict_raw_eligible": status["eligible"],
                   "strict_raw_excluded": status["excluded"]},
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
