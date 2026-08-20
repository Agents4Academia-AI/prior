"""Run one autonomous, bounded Scoper construction or snapshot expansion.

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
import shutil
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
    ap.add_argument("--screen-dir", type=Path,
                    help="Existing snapshot; omit for a zero-shot construction run")
    ap.add_argument("--anchor-papers", type=Path, action="append", default=[],
                    help="Frozen JSONL papers supplied by researchers; repeatable")
    ap.add_argument("--scope", type=Path, required=True,
                    help="Natural-language discovery scope")
    ap.add_argument("--strict-scope", type=Path,
                    help="Optional stricter screening scope; defaults to --scope")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--components", type=int, default=8)
    ap.add_argument("--initial-query-count", type=int, default=10)
    ap.add_argument("--fixed-queries", type=Path,
                    help="Optional fixed query scaffold used before generated queries")
    ap.add_argument("--initial-depth", type=int, default=50)
    ap.add_argument("--max-depth", type=int, default=200)
    ap.add_argument("--citation-seeds", type=int, default=200)
    ap.add_argument("--citation-page", type=int, default=200)
    ap.add_argument("--citation-workers", type=int, default=2)
    ap.add_argument("--model")
    ap.add_argument("--screen-cache", type=Path,
                    help="Shared screening cache across staged policy rounds")
    ap.add_argument("--skip-adaptive", action="store_true")
    ap.add_argument("--skip-citation", action="store_true")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    strict_scope = args.strict_scope or args.scope

    if args.out_dir.exists() and any(args.out_dir.iterdir()) and not args.resume:
        raise SystemExit("output directory is not empty; pass --resume to reuse checkpoints")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.out_dir / "run-ledger.jsonl"
    screen_cache = args.screen_cache or (args.out_dir / "screen-cache.jsonl")
    screen_cache.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ); env["PYTHONPATH"] = str(ROOT / "src")
    py = sys.executable

    if args.screen_dir:
        required = [args.screen_dir / f"{role}.jsonl"
                    for role in ("eligible", "retrieval_only", "uncertain")]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise SystemExit("missing snapshot inputs: " + ", ".join(missing))
        working_screen = args.screen_dir
        mode = "living_update"
    else:
        mode = "anchored_construction" if args.anchor_papers else "zero_shot_construction"
        initial = args.out_dir / "initial"
        initial.mkdir(exist_ok=True)
        query_plan = [py, str(HERE / "initial_query_plan.py"), "--scope", str(args.scope),
                      "--out-dir", str(initial), "--max-queries",
                      str(args.initial_query_count)]
        if args.model:
            query_plan += ["--model", args.model]
        if args.fixed_queries:
            query_plan += ["--fixed-queries", str(args.fixed_queries)]
        run(query_plan, env=env, ledger=ledger)
        run([py, str(HERE / "depth_ablation.py"), "collect", "--queries",
             str(initial / "initial-queries.txt"), "--out",
             str(initial / "retrieval.jsonl"), "--max-depth", str(args.initial_depth)],
            env=env, ledger=ledger)
        run([py, str(HERE / "adaptive_candidates.py"), "--retrieval",
             str(initial / "retrieval.jsonl"), "--out-dir", str(initial),
             "--cutoff", "none"], env=env, ledger=ledger)
        ensure_file(initial / "adaptive-pre_cutoff-papers.jsonl")
        initial_screen = args.out_dir / "initial-screen"
        initial_screen_cmd = [
            py, str(HERE / "product_disagreement.py"), "screen-historical",
            "--input", str(initial / "adaptive-pre_cutoff-papers.jsonl"),
            "--topic", str(strict_scope), "--out-dir", str(initial_screen),
            "--cache", str(screen_cache)]
        if args.model:
            initial_screen_cmd += ["--model", args.model]
        run(initial_screen_cmd, env=env, ledger=ledger)
        working_screen = args.out_dir / "initial-snapshot"
        working_screen.mkdir(exist_ok=True)
        initial_eligible = rows(initial_screen / "eligible.jsonl")
        anchor_eligible = []
        if args.anchor_papers:
            anchor_input = args.out_dir / "anchor-papers.jsonl"
            supplied = []
            supplied_ledger = []
            for path in args.anchor_papers:
                for row in rows(path):
                    paper = row.get("paper", row)
                    supplied.append(paper)
                    supplied_ledger.append({
                        "paper_id": paper.get("id"), "title": paper.get("title"),
                        "work_id": paper.get("work_id"), "input_path": str(path),
                        "input_sha256": sha(path),
                        "anchor_provenance": row.get("anchor_provenance", {}),
                    })
            # Preserve the supplied set before model screening. This is the
            # researcher input, not hidden evaluation data.
            write_jsonl(anchor_input, supplied)
            write_jsonl(args.out_dir / "anchor-input-ledger.jsonl", supplied_ledger)
            anchor_screen = args.out_dir / "anchor-screen"
            anchor_cmd = [
                py, str(HERE / "product_disagreement.py"), "screen-historical",
                "--input", str(anchor_input), "--topic", str(strict_scope),
                "--out-dir", str(anchor_screen), "--cache",
                str(screen_cache)]
            if args.model:
                anchor_cmd += ["--model", args.model]
            run(anchor_cmd, env=env, ledger=ledger)
            anchor_eligible = rows(anchor_screen / "eligible.jsonl")

        # A work can be independently found by search and supplied as an anchor.
        # Keep one paper row here; discovery-ledger.jsonl below preserves every
        # route rather than forcing a mutually exclusive attribution.
        combined = []
        seen_initial = set()
        for row in initial_eligible + anchor_eligible:
            paper = row.get("paper", row)
            key = paper.get("work_id") or paper.get("id") or paper.get("title", "").lower()
            if key not in seen_initial:
                seen_initial.add(key); combined.append(row)
        write_jsonl(working_screen / "eligible.jsonl", combined)
        for role in ("retrieval_only", "uncertain"):
            (working_screen / f"{role}.jsonl").touch()
        required = [working_screen / f"{role}.jsonl"
                    for role in ("eligible", "retrieval_only", "uncertain")]

    manifest = {
        "policy": "bounded-adaptive-v1", "mode": mode,
        "hidden_targets_loaded": False,
        "scope": str(args.scope), "scope_sha256": sha(args.scope),
        "strict_scope": str(strict_scope), "strict_scope_sha256": sha(strict_scope),
        "screen_dir": str(args.screen_dir) if args.screen_dir else None,
        "screen_sha256": {path.stem: sha(path) for path in required},
        "anchor_inputs": [{"path": str(path), "sha256": sha(path),
                           "records": count(path)} for path in args.anchor_papers],
        "fixed_queries": ({"path": str(args.fixed_queries),
                           "sha256": sha(args.fixed_queries)}
                          if args.fixed_queries else None),
        "screen_cache": str(screen_cache),
        "parameters": {"components": args.components, "queries_per_component": 2,
                       "initial_query_count": args.initial_query_count,
                       "initial_depth_per_query_source": args.initial_depth,
                       "max_depth_per_query_source": args.max_depth,
                       "citation_seeds": args.citation_seeds,
                       "citation_page": args.citation_page,
                       "adaptive_rounds": 1, "citation_hops": 1,
                       "sources": ["openalex", "arxiv"], "model": args.model,
                       "skip_adaptive": args.skip_adaptive,
                       "skip_citation": args.skip_citation},
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    query_dir = args.out_dir / "query-round"
    query_dir.mkdir(exist_ok=True)
    eligible_n = count(working_screen / "eligible.jsonl")
    can_induce = eligible_n >= 5 and not args.skip_adaptive
    if can_induce:
        actual_components = min(args.components, max(1, eligible_n // 3))
        run([py, str(HERE / "cpu_query_map.py"), "--screen-dir", str(working_screen),
             "--out-dir", str(query_dir), "--components", str(actual_components)],
            env=env, ledger=ledger)
        run([py, str(HERE / "depth_ablation.py"), "collect", "--queries",
             str(query_dir / "cpu-adaptive-queries.txt"), "--out",
             str(query_dir / "retrieval.jsonl"), "--max-depth", str(args.max_depth)],
            env=env, ledger=ledger)
    else:
        (query_dir / "cpu-adaptive-queries.txt").touch()
        write_jsonl(query_dir / "retrieval.jsonl", [{
            "event": "manifest", "queries": [], "reason":
            ("adaptive_stage_disabled" if args.skip_adaptive else
             "fewer_than_five_initial_eligible_works_for_community_induction")}])
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
                  "--topic", str(strict_scope), "--out-dir", str(query_screen),
                  "--cache", str(screen_cache)]
    if args.model:
        screen_cmd += ["--model", args.model]
    run(screen_cmd, env=env, ledger=ledger)

    citation_seed_dir = args.out_dir / "citation-seeds"
    citation_seed_dir.mkdir(exist_ok=True)
    # Seed citations from every eligible work available at this point. The
    # historical pipeline snowballed the accumulated corpus, including accepted
    # anchors; limiting this to one stage recreates its former bridge-seed bug.
    eligible = []
    seen_seed = set()
    for path in (working_screen / "eligible.jsonl", query_screen / "eligible.jsonl"):
        for row in rows(path):
            paper = row.get("paper", row)
            key = paper.get("work_id") or paper.get("id") or paper.get("title", "").lower()
            if key not in seen_seed:
                seen_seed.add(key); eligible.append(row)
    eligible = eligible[:args.citation_seeds]
    write_jsonl(citation_seed_dir / "eligible.jsonl", eligible)
    for role in ("retrieval_only", "uncertain"):
        (citation_seed_dir / f"{role}.jsonl").touch()
    citation_screen = args.out_dir / "citation-screen"
    if args.skip_citation:
        citation_screen.mkdir(exist_ok=True)
        for name in ("eligible.jsonl", "excluded.jsonl"):
            (citation_screen / name).touch()
        (citation_screen / "status.json").write_text(json.dumps({
            "records": 0, "eligible": 0, "excluded": 0,
            "reason": "citation_stage_disabled"}, indent=2) + "\n")
    else:
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
        citation_papers = citation_dir / "citation-new-candidate-papers.jsonl"
        write_jsonl(citation_papers,
                    (row["paper"] for row in rows(citation_dir / "citation-new-candidates.jsonl")))
        citation_cmd = [py, str(HERE / "product_disagreement.py"), "screen-historical",
                        "--input", str(citation_papers),
                        "--topic", str(strict_scope), "--out-dir", str(citation_screen),
                        "--cache", str(screen_cache)]
        if args.model:
            citation_cmd += ["--model", args.model]
        run(citation_cmd, env=env, ledger=ledger)

    final_dir = args.out_dir / "snapshot"
    final_dir.mkdir(exist_ok=True)
    combined = []
    for path in (working_screen / "eligible.jsonl", query_screen / "eligible.jsonl",
                 citation_screen / "eligible.jsonl"):
        combined.extend(rows(path))
    seen = set(); final = []
    for row in combined:
        paper = row.get("paper", row)
        key = paper.get("work_id") or paper.get("id") or paper.get("title", "").lower()
        if key not in seen:
            seen.add(key); final.append(row)
    write_jsonl(final_dir / "eligible.jsonl", final)
    for role in ("retrieval_only", "uncertain"):
        (final_dir / f"{role}.jsonl").touch()
    routes = {}
    route_sources = [
        ("initial_search", args.out_dir / "initial-screen" / "eligible.jsonl"),
        ("supplied_anchor", args.out_dir / "anchor-screen" / "eligible.jsonl"),
        ("adaptive_query", query_screen / "eligible.jsonl"),
        ("citation", citation_screen / "eligible.jsonl"),
    ]
    for channel, path in route_sources:
        if not path.exists():
            continue
        for row in rows(path):
            paper = row.get("paper", row)
            key = paper.get("work_id") or paper.get("id") or paper.get("title", "").lower()
            record = routes.setdefault(key, {"work_key": key,
                "paper_id": paper.get("id"), "title": paper.get("title"),
                "discovery_channels": []})
            if channel not in record["discovery_channels"]:
                record["discovery_channels"].append(channel)
    write_jsonl(args.out_dir / "discovery-ledger.jsonl", routes.values())
    summary = {
        "status": "complete", "policy": "bounded-adaptive-v1", "mode": mode,
        "retained_existing": count(working_screen / "eligible.jsonl") if args.screen_dir else 0,
        "initial_eligible": count(working_screen / "eligible.jsonl") if not args.screen_dir else None,
        "autonomous_initial_eligible": count(args.out_dir / "initial-screen" / "eligible.jsonl"),
        "supplied_anchor_records": sum(count(path) for path in args.anchor_papers),
        "screened_anchor_eligible": count(args.out_dir / "anchor-screen" / "eligible.jsonl"),
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
