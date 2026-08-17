"""Declarative controller for the exhaustive Scoper experiment.

This file is intentionally boring: it records the DAG, stage type, leakage
boundary, and completion receipts.  Scientific logic stays in stage modules.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adaptive_expansion import (_receipt, citation_queue, prepare_embedding, repair,
                                repair_fulltext)


PIPELINE = [
    {"name": "deep_retrieval", "kind": "source", "depends_on": [], "implemented": True},
    {"name": "broad_screen", "kind": "agentic", "depends_on": ["deep_retrieval"], "implemented": True},
    {"name": "repair_metadata", "kind": "source", "depends_on": ["broad_screen"], "implemented": True},
    {"name": "repair_fulltext", "kind": "source", "depends_on": ["repair_metadata"], "implemented": True},
    {"name": "reassess_uncertain", "kind": "agentic", "depends_on": ["repair_fulltext"], "implemented": False},
    {"name": "prepare_embedding", "kind": "deterministic", "depends_on": ["broad_screen"], "implemented": True},
    {"name": "select_embedding", "kind": "gpu_experiment", "depends_on": ["prepare_embedding"], "implemented": False},
    {"name": "induce_query_map", "kind": "agentic", "depends_on": ["select_embedding", "reassess_uncertain"], "implemented": False},
    {"name": "adaptive_search", "kind": "source", "depends_on": ["induce_query_map"], "implemented": False},
    {"name": "citation_queue", "kind": "deterministic", "depends_on": ["broad_screen"], "implemented": True},
    {"name": "citation_expand", "kind": "source", "depends_on": ["citation_queue"], "implemented": False},
    {"name": "strict_synthesis_screen", "kind": "agentic", "depends_on": ["adaptive_search", "citation_expand"], "implemented": False},
    {"name": "boundary_audit", "kind": "mixed", "depends_on": ["strict_synthesis_screen"], "implemented": False},
    {"name": "recovery_and_stopping", "kind": "offline_evaluation", "depends_on": ["boundary_audit"], "implemented": False},
]


def initialize(run_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    spec = {
        "pipeline": "scoper-exhaustiveness-v2",
        "discovery_gold_policy": "hidden; may be joined only in recovery_and_stopping",
        "stage_contract": {
            "deterministic": "immutable inputs + parameters produce byte-stable outputs",
            "source": "requests/results/retries/terminal state and response evidence are traced",
            "agentic": "prompt+schema+model revision+parameters+raw decision+evidence hash are cached",
            "gpu_experiment": "model chosen before hidden-target join",
        },
        "run_dir": str(run_dir), "out_dir": str(out_dir), "stages": PIPELINE,
    }
    (out_dir / "pipeline.json").write_text(json.dumps(spec, indent=2) + "\n")
    # Adopt the already completed v1 stages into the same receipt contract. This
    # records, rather than pretends away, that they predate this controller.
    retrieval_outputs = [run_dir / "retrieval.jsonl", run_dir / "candidates.jsonl"]
    if all(path.exists() for path in retrieval_outputs):
        _receipt(out_dir, "deep_retrieval", [], retrieval_outputs,
                 deterministic=False, parameters={"adopted_existing_artifacts": True})
    screen_outputs = [run_dir / f"{role}.jsonl" for role in
                      ("eligible", "retrieval_only", "uncertain", "excluded")]
    if all(path.exists() for path in screen_outputs):
        _receipt(out_dir, "broad_screen", [run_dir / "candidates.jsonl"], screen_outputs,
                 deterministic=False,
                 parameters={"adopted_existing_artifacts": True,
                             "agentic_cache": str(run_dir / "scope-cache.jsonl")})
    repair_outputs = [out_dir / "repair-ledger.jsonl",
                      out_dir / "repaired-uncertain.jsonl",
                      out_dir / "repair-status.json"]
    if all(path.exists() for path in repair_outputs):
        _receipt(out_dir, "repair_metadata", [run_dir / "uncertain.jsonl"],
                 repair_outputs, deterministic=False,
                 parameters={"adopted_existing_artifacts": True,
                             "sources": ["arxiv", "openalex"], "s2_circuit": "open"})


def status(out_dir: Path) -> dict:
    rows = []
    for stage in PIPELINE:
        receipt = out_dir / f"stage-{stage['name']}.json"
        rows.append({**stage, "status": "complete" if receipt.exists() else "pending",
                     "receipt": str(receipt) if receipt.exists() else ""})
    result = {"stages": rows, "complete": sum(r["status"] == "complete" for r in rows),
              "total": len(rows)}
    (out_dir / "pipeline-status.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def run_stage(name: str, run_dir: Path, out_dir: Path, *, workers: int = 6) -> None:
    if name == "repair_metadata":
        repair(run_dir, out_dir)
    elif name == "repair_fulltext":
        repair_fulltext(run_dir, out_dir, workers=workers)
    elif name == "prepare_embedding":
        prepare_embedding(run_dir, out_dir)
    elif name == "citation_queue":
        citation_queue(run_dir, out_dir)
    else:
        raise SystemExit(f"stage {name!r} is not executable by this controller yet")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("init", "run", "status"))
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--stage")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if args.command == "init":
        initialize(args.run_dir, args.out_dir)
    elif args.command == "run":
        if not args.stage:
            raise SystemExit("--stage is required for run")
        run_stage(args.stage, args.run_dir, args.out_dir, workers=args.workers)
    print(json.dumps(status(args.out_dir), indent=2))


if __name__ == "__main__":
    main()
