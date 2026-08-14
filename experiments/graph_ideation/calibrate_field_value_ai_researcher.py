#!/usr/bin/env python3
"""Calibrate intrinsic field-value rubric components on AI-Researcher labels."""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402

SYSTEM = """Blindly evaluate one NLP research proposal for cumulative scientific
value. Do not infer whether it was written by a human or AI. Score integers 1-5:
uncertainty_reduction, validation_value, connective_value (connects fragmented
benchmarks/domains/evidence), downstream_enablement, actionability, flashiness
(surprising/high-profile independent of usefulness), and field_strengthening_value.
Classify the dominant gap type and flag incentive_mismatch when the work is useful
validation/reconciliation/infrastructure that may be less glamorous than a new
capability. Judge only what the proposal supports; do not assume successful results
or global novelty. Briefly justify the scores."""

GAPS = ["benchmark_reconciliation", "replication_validation",
        "boundary_generalization", "contradiction_resolution", "system_integration",
        "missing_feedback_loop", "infrastructure_tooling", "new_capability", "other"]
PROPS = {
    "gap_type": {"type": "string", "enum": GAPS},
    "uncertainty_reduction": {"type": "integer", "minimum": 1, "maximum": 5},
    "validation_value": {"type": "integer", "minimum": 1, "maximum": 5},
    "connective_value": {"type": "integer", "minimum": 1, "maximum": 5},
    "downstream_enablement": {"type": "integer", "minimum": 1, "maximum": 5},
    "actionability": {"type": "integer", "minimum": 1, "maximum": 5},
    "flashiness": {"type": "integer", "minimum": 1, "maximum": 5},
    "incentive_mismatch": {"type": "boolean"},
    "field_strengthening_value": {"type": "integer", "minimum": 1, "maximum": 5},
    "reason": {"type": "string"},
}
SCHEMA = {"type": "object", "properties": PROPS, "required": list(PROPS)}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        rank = (i + j - 1) / 2 + 1
        for k in order[i:j]:
            out[k] = rank
        i = j
    return out


def pearson(x: list[float], y: list[float]) -> float | None:
    mx, my = sum(x) / len(x), sum(y) / len(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external", type=Path, required=True)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    ideas = read_jsonl(args.external / "normalized_idea_ratings.jsonl")
    output = args.external / "field_value_calibration_judgements.jsonl"
    existing = read_jsonl(output) if output.exists() else []
    done = {x["idea_id"] for x in existing}
    todo = [x for x in ideas if x["idea_id"] not in done]
    lock = threading.Lock()

    def one(item: dict) -> dict:
        prompt = json.dumps({"title": item["title"], "topic": item["topic"],
                             "proposal": item["proposal_text"][:16000]})
        result = llm.structured(model=args.model, system=SYSTEM, user=prompt,
            schema=SCHEMA, tool_name="emit_field_value", max_tokens=1400, retries=3)
        return {"idea_id": item["idea_id"], "model": args.model, **result}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, x): x["idea_id"] for x in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with lock, output.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"calibrate {i}/{len(todo)} {row['idea_id']}", flush=True)

    judged = {x["idea_id"]: x for x in read_jsonl(output)}
    joined = [(x, judged[x["idea_id"]]) for x in ideas if x["idea_id"] in judged]
    comparisons = {
        "actionability_vs_human_feasibility": ("actionability", "feasibility_score"),
        "field_value_vs_human_effectiveness": ("field_strengthening_value", "effectiveness_score"),
        "field_value_vs_human_overall": ("field_strengthening_value", "overall_score"),
        "flashiness_vs_human_excitement": ("flashiness", "excitement_score"),
        "flashiness_vs_human_novelty": ("flashiness", "novelty_score"),
    }
    correlations = {}
    for name, (ours, human) in comparisons.items():
        x = [float(j[ours]) for _, j in joined]
        y = [float(i[human]) for i, _ in joined]
        value = pearson(ranks(x), ranks(y))
        correlations[name] = round(value, 4) if value is not None else None
    by_condition = defaultdict(list)
    for idea, judged_row in joined:
        by_condition[idea["condition"]].append(judged_row["field_strengthening_value"])
    summary = {"n": len(joined), "spearman": correlations,
               "mean_field_value_by_condition": {
                   k: round(sum(v) / len(v), 4) for k, v in by_condition.items()},
               "scope": "Construct calibration of an intrinsic LLM rubric on Human/AI NLP proposals; not validation of Prior retrieval or graph-grounded novelty."}
    execution_path = args.external / "human_reviews_execution.json"
    if execution_path.exists():
        raw = json.loads(execution_path.read_text())
        execution_rows = [dict(zip(raw, (raw[k][i] for k in raw)))
                          for i in range(len(raw["idea_id"]))]
        grouped = defaultdict(list)
        for row in execution_rows:
            grouped[row["idea_id"].replace(" ", "")].append(row)
        executed = []
        idea_by_id = {x["idea_id"]: x for x in ideas}
        for idea_id, rows in grouped.items():
            if idea_id not in judged or idea_id not in idea_by_id:
                continue
            post = {metric: sum(float(x[metric]) for x in rows) / len(rows)
                    for metric in ("soundness_score", "effectiveness_score", "overall_score")}
            executed.append((idea_by_id[idea_id], judged[idea_id], post))
        post_pairs = {
            "field_value_vs_post_soundness": ("field_strengthening_value", "soundness_score"),
            "field_value_vs_post_effectiveness": ("field_strengthening_value", "effectiveness_score"),
            "field_value_vs_post_overall": ("field_strengthening_value", "overall_score"),
            "actionability_vs_post_soundness": ("actionability", "soundness_score"),
            "actionability_vs_post_effectiveness": ("actionability", "effectiveness_score"),
        }
        post_corr = {}
        for name, (ours, post_metric) in post_pairs.items():
            value = pearson(ranks([float(j[ours]) for _, j, _ in executed]),
                            ranks([float(p[post_metric]) for _, _, p in executed]))
            post_corr[name] = round(value, 4) if value is not None else None
        value = pearson(ranks([float(i["overall_score"]) for i, _, _ in executed]),
                        ranks([float(p["overall_score"]) for _, _, p in executed]))
        post_corr["human_pre_overall_vs_post_overall"] = round(value, 4) if value is not None else None
        summary["post_execution"] = {"n": len(executed), "spearman": post_corr}
    (args.external / "field_value_calibration_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
