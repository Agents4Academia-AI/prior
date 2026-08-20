"""Best-evidence executable reconstruction of the hand-held June Scoper policy.

This deliberately separates broad discovery from the final strict core screen.
It uses the recovered fixed query scaffold plus newly generated queries, screened
researcher anchors, repeated adaptive recovery, and repeated citation traversal
until a historical 3% marginal-yield rule fires or the recovered round limits are
reached. Semantic Scholar remains unavailable and is recorded as a limitation.
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


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, values) -> None:
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n"
                            for value in values))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(argv: list[str], *, env: dict[str, str], ledger: Path) -> None:
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=ROOT, env=env, text=True,
                            capture_output=True, check=False)
    with ledger.open("a") as handle:
        handle.write(json.dumps({
            "event": "stage_command", "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "argv": argv, "returncode": result.returncode,
            "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:],
        }, ensure_ascii=False) + "\n")
    if result.returncode:
        raise RuntimeError(f"stage failed: {' '.join(argv)}\n{result.stderr[-2000:]}")


def yield_below(summary: dict, prefix: str, epsilon: float) -> bool:
    candidates = int(summary.get(f"{prefix}_candidates_screened") or 0)
    eligible = int(summary.get(f"{prefix}_eligible") or 0)
    return candidates == 0 or eligible / candidates < epsilon


def complete_screen(status_path: Path) -> bool:
    if not status_path.exists():
        return False
    status = json.loads(status_path.read_text())
    return int(status.get("records") or 0) == (
        int(status.get("eligible") or 0) + int(status.get("excluded") or 0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", type=Path, required=True,
                    help="Broad historical discovery scope")
    ap.add_argument("--strict-scope", type=Path, required=True,
                    help="Final core synthesis scope")
    ap.add_argument("--anchor-papers", type=Path, action="append", required=True)
    ap.add_argument("--fixed-queries", type=Path,
                    default=HERE / "workshop_inputs" / "historical-fixed-queries-v1.txt")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--query-rounds", type=int, default=5)
    ap.add_argument("--citation-hops", type=int, default=3)
    ap.add_argument("--epsilon", type=float, default=0.03)
    ap.add_argument("--initial-depth", type=int, default=20)
    ap.add_argument("--initial-query-count", type=int, default=40,
                    help="23 fixed queries plus up to 10 generated queries by default")
    ap.add_argument("--adaptive-depth", type=int, default=200)
    ap.add_argument("--citation-seeds", type=int, default=200)
    ap.add_argument("--citation-page", type=int, default=200)
    ap.add_argument("--citation-workers", type=int, default=2)
    ap.add_argument("--model")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    if args.out_dir.exists() and any(args.out_dir.iterdir()) and not args.resume:
        raise SystemExit("output directory is not empty; pass --resume")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.out_dir / "policy-ledger.jsonl"
    shared_cache = args.out_dir / "screen-cache.jsonl"
    env = dict(os.environ); env["PYTHONPATH"] = str(ROOT / "src")
    py = sys.executable
    bounded = str(HERE / "bounded_expansion.py")
    common = ["--scope", str(args.scope), "--strict-scope", str(args.scope),
              "--screen-cache", str(shared_cache), "--max-depth", str(args.adaptive_depth),
              "--citation-seeds", str(args.citation_seeds),
              "--citation-page", str(args.citation_page),
              "--citation-workers", str(args.citation_workers)]
    if args.model:
        common += ["--model", args.model]

    construction = args.out_dir / "00-construction"
    command = [py, bounded, *common, "--out-dir", str(construction),
               "--fixed-queries", str(args.fixed_queries),
               "--initial-query-count", str(args.initial_query_count),
               "--initial-depth", str(args.initial_depth),
               "--skip-adaptive", "--skip-citation"]
    for path in args.anchor_papers:
        command += ["--anchor-papers", str(path)]
    if args.resume:
        command += ["--resume"]
    if not (construction / "summary.json").exists():
        invoke(command, env=env, ledger=ledger)
    previous = construction / "snapshot"
    stages = [{"stage": "construction", **json.loads((construction / "summary.json").read_text())}]

    for round_number in range(1, args.query_rounds + 1):
        out = args.out_dir / f"query-{round_number:02d}"
        command = [py, bounded, *common, "--screen-dir", str(previous),
                   "--out-dir", str(out), "--skip-citation"]
        if args.resume:
            command += ["--resume"]
        if not (out / "summary.json").exists():
            invoke(command, env=env, ledger=ledger)
        summary = json.loads((out / "summary.json").read_text())
        stages.append({"stage": f"query_{round_number}", **summary})
        previous = out / "snapshot"
        if round_number > 1 and yield_below(summary, "query", args.epsilon):
            break

    for hop in range(1, args.citation_hops + 1):
        out = args.out_dir / f"citation-{hop:02d}"
        command = [py, bounded, *common, "--screen-dir", str(previous),
                   "--out-dir", str(out), "--skip-adaptive"]
        if args.resume:
            command += ["--resume"]
        if not (out / "summary.json").exists():
            invoke(command, env=env, ledger=ledger)
        summary = json.loads((out / "summary.json").read_text())
        stages.append({"stage": f"citation_{hop}", **summary})
        previous = out / "snapshot"
        if yield_below(summary, "citation", args.epsilon):
            break

    # Strict re-screen mirrors the historical broad-corpus -> strict-255 step.
    candidates = args.out_dir / "strict-candidates.jsonl"
    write_jsonl(candidates, (row.get("paper", row) for row in rows(previous / "eligible.jsonl")))
    strict_dir = args.out_dir / "strict-screen"
    strict_cmd = [py, str(HERE / "product_disagreement.py"), "screen-historical",
                  "--input", str(candidates), "--topic", str(args.strict_scope),
                  "--out-dir", str(strict_dir), "--cache", str(args.out_dir / "strict-cache.jsonl")]
    if args.model:
        strict_cmd += ["--model", args.model]
    if not complete_screen(strict_dir / "status.json"):
        invoke(strict_cmd, env=env, ledger=ledger)
    if not complete_screen(strict_dir / "status.json"):
        raise RuntimeError("strict screen remains incomplete after resume")
    snapshot = args.out_dir / "snapshot"; snapshot.mkdir(exist_ok=True)
    write_jsonl(snapshot / "eligible.jsonl", rows(strict_dir / "eligible.jsonl"))
    for role in ("retrieval_only", "uncertain"):
        (snapshot / f"{role}.jsonl").touch()
    strict_status = json.loads((strict_dir / "status.json").read_text())
    manifest = {
        "policy": "historical-anchored-reconstruction-v1",
        "scope": str(args.scope), "scope_sha256": sha(args.scope),
        "strict_scope": str(args.strict_scope), "strict_scope_sha256": sha(args.strict_scope),
        "fixed_queries": str(args.fixed_queries), "fixed_queries_sha256": sha(args.fixed_queries),
        "anchors": [{"path": str(p), "sha256": sha(p)} for p in args.anchor_papers],
        "parameters": {"query_rounds_max": args.query_rounds,
            "citation_hops_max": args.citation_hops, "epsilon": args.epsilon,
            "initial_depth": args.initial_depth, "adaptive_depth": args.adaptive_depth},
        "historical_query_model": args.model or "configured READER_MODEL (historically claude-sonnet-4-6)",
        "source_limitation": "OpenAlex and arXiv active; Semantic Scholar unavailable (429 anonymous, 403 key)",
        "stages": stages, "strict_screen": strict_status,
        "snapshot_eligible": len(rows(snapshot / "eligible.jsonl")),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.out_dir / "summary.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"policy": manifest["policy"], "stages": len(stages),
                      "snapshot_eligible": manifest["snapshot_eligible"]}, indent=2))


if __name__ == "__main__":
    main()
