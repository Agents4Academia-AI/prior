#!/usr/bin/env python3
"""Blind audit of cumulative, field-strengthening value for generated ideas."""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402

GAP_TYPES = ["benchmark_reconciliation", "replication_validation",
             "boundary_generalization", "contradiction_resolution",
             "system_integration", "missing_feedback_loop",
             "infrastructure_tooling", "new_capability", "other"]

SYSTEM = """You evaluate proposed studies for cumulative scientific value, not
prestige or rhetorical novelty. Each case includes a generated idea, five nearest
antecedent contributions from a frozen corpus, and a corpus-relative coverage audit.
Condition labels are hidden.

Score integers 1-5:
- uncertainty_reduction: would the result resolve a consequential unknown?
- validation_value: would it test robustness, reproducibility, generalization, or boundaries?
- connective_value: would it reconcile or connect fragmented benchmarks, domains, or evidence?
- downstream_enablement: would it improve later research, tools, standards, or decisions?
- actionability: is there a concrete feasible study?
- flashiness: is the idea likely to appear surprising/high-profile, independent of usefulness?

Classify one gap_type. incentive_mismatch is true when the main contribution is
unglamorous but useful cumulative work (validation, reconciliation, integration,
boundary mapping, infrastructure) rather than primarily a new system or capability.
field_strengthening_value is a 1-5 closing holistic judgment grounded in the axes;
do not simply average them. Fully covered ideas normally cannot score above 2 unless
the proposed replication itself has clear value. Cite exact antecedent contribution
IDs and state the missing evidence. Do not claim global novelty.

Return every key exactly once. Then select one preferred_key: the study in this batch
that, if completed, would most improve the field's reliability, connectedness, or
cumulative understanding."""

ITEM_SCHEMA = {"type": "object", "properties": {
    "key": {"type": "string"},
    "gap_type": {"type": "string", "enum": GAP_TYPES},
    "uncertainty_reduction": {"type": "integer", "minimum": 1, "maximum": 5},
    "validation_value": {"type": "integer", "minimum": 1, "maximum": 5},
    "connective_value": {"type": "integer", "minimum": 1, "maximum": 5},
    "downstream_enablement": {"type": "integer", "minimum": 1, "maximum": 5},
    "actionability": {"type": "integer", "minimum": 1, "maximum": 5},
    "flashiness": {"type": "integer", "minimum": 1, "maximum": 5},
    "incentive_mismatch": {"type": "boolean"},
    "field_strengthening_value": {"type": "integer", "minimum": 1, "maximum": 5},
    "antecedent_ids": {"type": "array", "items": {"type": "string"}},
    "missing_evidence": {"type": "string"}, "reason": {"type": "string"},
}, "required": ["key", "gap_type", "uncertainty_reduction", "validation_value",
                 "connective_value", "downstream_enablement", "actionability",
                 "flashiness", "incentive_mismatch", "field_strengthening_value",
                 "antecedent_ids", "missing_evidence", "reason"]}

SCHEMA = {"type": "object", "properties": {
    "results": {"type": "array", "items": ITEM_SCHEMA},
    "preferred_key": {"type": "string"}, "preference_reason": {"type": "string"},
}, "required": ["results", "preferred_key", "preference_reason"]}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=83)
    args = parser.parse_args()

    candidates = read_jsonl(args.out / "antecedent_candidates.jsonl")
    coverage = {}
    antecedent_name = os.environ.get(
        "PRIOR_ANTECEDENT_JUDGEMENTS", "antecedent_judgements.jsonl")
    for batch in read_jsonl(args.out / antecedent_name):
        for row in batch["results"]:
            coverage[row["key"]] = {k: row[k] for k in
                ("coverage", "closest_contribution_ids", "confidence", "reason")}
    arm_by_key = {x["key"]: x["arm"] for x in candidates}
    by_seed = defaultdict(list)
    for row in candidates:
        by_seed[row["seed_id"]].append({
            "key": row["key"], "idea": row["idea"],
            "retrieved_antecedents": row["antecedents"],
            "coverage_audit": coverage[row["key"]],
        })

    output = args.out / os.environ.get(
        "PRIOR_FIELD_VALUE_JUDGEMENTS", "field_value_judgements.jsonl")
    existing = read_jsonl(output) if output.exists() else []
    done = {x["seed_id"] for x in existing}
    todo = [(seed, rows) for seed, rows in sorted(by_seed.items()) if seed not in done]
    lock = threading.Lock()

    def one(item: tuple[str, list[dict]]) -> dict:
        seed, rows = item
        random.Random(f"{args.seed}:{seed}").shuffle(rows)
        result = llm.structured(model=args.model, system=SYSTEM, user=json.dumps(rows),
            schema=SCHEMA, tool_name="emit_field_value", max_tokens=8000,
            retries=3, timeout=360)
        expected = {x["key"] for x in rows}
        received = {x["key"] for x in result["results"]}
        metrics = ("uncertainty_reduction", "validation_value", "connective_value",
                   "downstream_enablement", "actionability", "flashiness",
                   "field_strengthening_value")
        invalid = any(
            row.get("gap_type") not in GAP_TYPES
            or any(not isinstance(row.get(metric), int) or not 1 <= row[metric] <= 5
                   for metric in metrics)
            for row in result["results"])
        if expected != received or result["preferred_key"] not in expected or invalid:
            raise ValueError(f"key mismatch missing={expected-received} extra={received-expected}")
        for row in result["results"]:
            row["arm"] = arm_by_key[row["key"]]
        return {"seed_id": seed, "model": args.model, **result,
                "preferred_arm": arm_by_key[result["preferred_key"]]}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, x): x[0] for x in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with lock, output.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"field-value {i}/{len(todo)} {row['seed_id']}", flush=True)

    batches = read_jsonl(output)
    metrics = ("uncertainty_reduction", "validation_value", "connective_value",
               "downstream_enablement", "actionability", "flashiness",
               "field_strengthening_value")
    values = defaultdict(lambda: defaultdict(list))
    types, incentive, high_value = defaultdict(Counter), Counter(), Counter()
    preferences = Counter()
    for batch in batches:
        preferences[batch["preferred_arm"]] += 1
        for row in batch["results"]:
            arm = row["arm"]
            for metric in metrics:
                values[arm][metric].append(row[metric])
            types[arm][row["gap_type"]] += 1
            incentive[arm] += bool(row["incentive_mismatch"])
            cov = coverage[row["key"]]["coverage"]
            high_value[arm] += (row["field_strengthening_value"] >= 4
                                and row["actionability"] >= 3
                                and cov != "fully_covered")
    summary = {"arms": {arm: {
        "n": len(next(iter(metric_values.values()))),
        "means": {m: round(sum(v) / len(v), 4) for m, v in metric_values.items()},
        "gap_types": dict(types[arm]),
        "incentive_mismatch_n": incentive[arm],
        "high_field_value_actionable_not_fully_covered_n": high_value[arm],
    } for arm, metric_values in values.items()},
        "seed_level_preferences": dict(preferences),
        "caveat": "Single LLM judge; field-value construct requires blinded human validation."}
    summary_name = os.environ.get("PRIOR_FIELD_VALUE_SUMMARY", "field_value_summary.json")
    (args.out / summary_name).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
