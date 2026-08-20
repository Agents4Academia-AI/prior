"""Run one autonomous, bounded Scoper expansion from an existing snapshot.

This is the committed workshop policy, not an exhaustiveness claim.  It retains
the supplied snapshot, induces lexical communities, opens one query round,
strictly screens novel works, performs one bounded OpenAlex citation hop from
newly eligible works, screens those candidates, and writes a versioned snapshot
plus a complete stage manifest.  No hidden recovery targets are accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count(path: Path) -> int:
    return sum(1 for line in path.open() if line.strip()) if path.exists() else 0


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def run(command: list[str], *, env: dict[str, str], ledger: Path) -> None:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            capture_output=True, check=False)
    with ledger.open("a") as handle:
        handle.write(json.dumps({
            "event": "command", "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "argv": command, "returncode": result.returncode,
            "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:],
        }, ensure_ascii=False) + "\n")
    if result.returncode:
        raise RuntimeError(f"stage failed ({result.returncode}): {' '.join(command)}\n"
                           f"{result.stderr[-1000:]}")


def ensure_file(path: Path) -> None:
    """Materialise an empty checkpoint when a stage has zero records."""
    if not path.exists():
        path.touch()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen-dir", type=Path, required=True,
                    help="Existing eligible/retrieval_only/uncertain JSONL snapshot")
    ap.add_argument("--scope", type=Path, required=True,
                    help="Strict natural-language inclusion/exclusion criteria")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--components", type=int, default=8)
    ap.add_argument("--max-depth", type=int, default=200)
    ap.add_argument("--citation-seeds", type=int, default=200)
    ap.add_argument("--citation-page", type=int, default=200)
    ap.add_argument("--citation-workers", type=int, default=2)
    ap.add_argument("--model")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    required = [args.screen_dir / f"{role}.jsonl"
                for role in ("eligible", "retrieval_only", "uncertain")]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("missing snapshot inputs: " + ", ".join(missing))
    if args.out_dir.exists() and any(args.out_dir.iterdir()) and not args.resume:
        raise SystemExit("output directory is not empty; pass --resume to reuse checkpoints")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.out_dir / "run-ledger.jsonl"
    env = dict(os.environ); env["PYTHONPATH"] = str(ROOT / "src")
    py = sys.executable

    manifest = {
        "policy": "bounded-adaptive-v1", "hidden_targets_loaded": False,
        "scope": str(args.scope), "scope_sha256": sha(args.scope),
        "screen_dir": str(args.screen_dir),
        "screen_sha256": {path.stem: sha(path) for path in required},
        "parameters": {"components": args.components, "queries_per_component": 2,
                       "max_depth_per_query_source": args.max_depth,
                       "citation_seeds": args.citation_seeds,
                       "citation_page": args.citation_page,
                       "adaptive_rounds": 1, "citation_hops": 1,
                       "sources": ["openalex", "arxiv"], "model": args.model},
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    query_dir = args.out_dir / "query-round"
    query_dir.mkdir(exist_ok=True)
    run([py, str(HERE / "cpu_query_map.py"), "--screen-dir", str(args.screen_dir),
         "--out-dir", str(query_dir), "--components", str(args.components)],
        env=env, ledger=ledger)
    run([py, str(HERE / "depth_ablation.py"), "collect", "--queries",
         str(query_dir / "cpu-adaptive-queries.txt"), "--out",
         str(query_dir / "retrieval.jsonl"), "--max-depth", str(args.max_depth)],
        env=env, ledger=ledger)
    candidate_cmd = [py, str(HERE / "adaptive_candidates.py"), "--retrieval",
                     str(query_dir / "retrieval.jsonl"), "--out-dir", str(query_dir),
                     "--cutoff", "none"]
    for path in required:
        candidate_cmd += ["--existing", str(path)]
    run(candidate_cmd, env=env, ledger=ledger)
    ensure_file(query_dir / "adaptive-pre_cutoff-papers.jsonl")

    query_screen = args.out_dir / "query-screen"
    screen_cmd = [py, str(HERE / "product_disagreement.py"), "screen-historical",
                  "--input", str(query_dir / "adaptive-pre_cutoff-papers.jsonl"),
                  "--topic", str(args.scope), "--out-dir", str(query_screen),
                  "--cache", str(args.out_dir / "screen-cache.jsonl")]
    if args.model:
        screen_cmd += ["--model", args.model]
    run(screen_cmd, env=env, ledger=ledger)

    citation_seed_dir = args.out_dir / "citation-seeds"
    citation_seed_dir.mkdir(exist_ok=True)
    eligible = rows(query_screen / "eligible.jsonl")[:args.citation_seeds]
    write_jsonl(citation_seed_dir / "eligible.jsonl", eligible)
    for role in ("retrieval_only", "uncertain"):
        (citation_seed_dir / f"{role}.jsonl").touch()
    citation_dir = args.out_dir / "citation-round"
    citation_dir.mkdir(exist_ok=True)
    run([py, str(HERE / "adaptive_expansion.py"), "citation-queue", "--run-dir",
         str(citation_seed_dir), "--out-dir", str(citation_dir)], env=env, ledger=ledger)
    run([py, str(HERE / "citation_expansion.py"), "backward", "--queue",
         str(citation_dir / "citation-queue.jsonl"), "--out-dir", str(citation_dir)],
        env=env, ledger=ledger)
    run([py, str(HERE / "citation_expansion.py"), "forward-pass", "--queue",
         str(citation_dir / "citation-queue.jsonl"), "--out-dir", str(citation_dir),
         "--per-page", str(args.citation_page), "--max-tasks", str(args.citation_seeds),
         "--workers", str(args.citation_workers)], env=env, ledger=ledger)
    run([py, str(HERE / "consolidate_citations.py"), "--screen-dir",
         str(citation_seed_dir), "--out-dir", str(citation_dir)], env=env, ledger=ledger)

    citation_screen = args.out_dir / "citation-screen"
    citation_papers = citation_dir / "citation-new-candidate-papers.jsonl"
    write_jsonl(citation_papers,
                (row["paper"] for row in rows(citation_dir / "citation-new-candidates.jsonl")))
    citation_cmd = [py, str(HERE / "product_disagreement.py"), "screen-historical",
                    "--input", str(citation_papers),
                    "--topic", str(args.scope), "--out-dir", str(citation_screen),
                    "--cache", str(args.out_dir / "screen-cache.jsonl")]
    if args.model:
        citation_cmd += ["--model", args.model]
    run(citation_cmd, env=env, ledger=ledger)

    final_dir = args.out_dir / "snapshot"
    final_dir.mkdir(exist_ok=True)
    combined = []
    for path in (args.screen_dir / "eligible.jsonl", query_screen / "eligible.jsonl",
                 citation_screen / "eligible.jsonl"):
        combined.extend(rows(path))
    seen = set(); final = []
    for row in combined:
        paper = row.get("paper", row)
        key = paper.get("work_id") or paper.get("id") or paper.get("title", "").lower()
        if key not in seen:
            seen.add(key); final.append(row)
    write_jsonl(final_dir / "eligible.jsonl", final)
    summary = {
        "status": "complete", "policy": "bounded-adaptive-v1",
        "retained_existing": count(args.screen_dir / "eligible.jsonl"),
        "query_candidates_screened": json.loads((query_screen / "status.json").read_text())["records"],
        "query_eligible": count(query_screen / "eligible.jsonl"),
        "citation_candidates_screened": json.loads((citation_screen / "status.json").read_text())["records"],
        "citation_eligible": count(citation_screen / "eligible.jsonl"),
        "snapshot_eligible": len(final), "hidden_targets_loaded": False,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
