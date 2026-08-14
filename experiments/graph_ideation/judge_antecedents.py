#!/usr/bin/env python3
"""Blindly judge generated ideas against retrieved frozen-corpus antecedents."""
from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402

SYSTEM = """You conservatively audit candidate research ideas against a frozen
literature corpus. For each idea, inspect only its retrieved antecedent contributions.
- fully_covered: one antecedent or an obvious combination directly contains the
  proposed question, mechanism, and evaluation.
- partially_covered: important elements are anticipated, but a material combination,
  mechanism, setting, or test remains different.
- not_found: none of the supplied nearest antecedents substantially anticipates it.
- unclear: evidence is insufficient to decide.
This is corpus-relative coverage, not global novelty. Do not reward grand language.
Return every input key exactly once and cite contribution IDs from its candidates."""

SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {
    "type": "object", "properties": {
        "key": {"type": "string"},
        "coverage": {"type": "string", "enum": ["fully_covered", "partially_covered",
                                                   "not_found", "unclear"]},
        "closest_contribution_ids": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"}, "reason": {"type": "string"}},
    "required": ["key", "coverage", "closest_contribution_ids", "confidence", "reason"]
}}}, "required": ["results"]}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    candidates = read_jsonl(args.out / "antecedent_candidates.jsonl")
    by_seed = defaultdict(list)
    arm_by_key = {}
    for row in candidates:
        by_seed[row["seed_id"]].append({
            "key": row["key"], "idea": row["idea"],
            "antecedents": row["antecedents"]})
        arm_by_key[row["key"]] = row["arm"]
    output = args.out / __import__("os").environ.get(
        "PRIOR_ANTECEDENT_JUDGEMENTS", "antecedent_judgements.jsonl")
    existing = read_jsonl(output) if output.exists() else []
    done = {x["seed_id"] for x in existing}
    todo = [(seed, rows) for seed, rows in sorted(by_seed.items()) if seed not in done]
    lock = threading.Lock()

    def one(item: tuple[str, list[dict]]) -> dict:
        seed, rows = item
        result = llm.structured(model=args.model, system=SYSTEM,
            user=json.dumps(rows), schema=SCHEMA, tool_name="emit_coverage",
            max_tokens=6500, retries=3, timeout=300)
        expected = {x["key"] for x in rows}
        received = {x["key"] for x in result["results"]}
        if expected != received or any(
                row.get("coverage") not in {"fully_covered", "partially_covered", "not_found"}
                or not isinstance(row.get("confidence"), (int, float))
                or not 0 <= row["confidence"] <= 1 for row in result["results"]):
            raise ValueError(f"key mismatch missing={expected-received} extra={received-expected}")
        for row in result["results"]:
            row["arm"] = arm_by_key[row["key"]]
        return {"seed_id": seed, "model": args.model, "results": result["results"]}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, x): x[0] for x in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with lock, output.open("a") as f:
                f.write(json.dumps(row) + "\n")
            print(f"coverage {i}/{len(todo)} {row['seed_id']}", flush=True)

    all_rows = read_jsonl(output)
    counts = defaultdict(Counter)
    confidences = defaultdict(list)
    for batch in all_rows:
        for row in batch["results"]:
            counts[row["arm"]][row["coverage"]] += 1
            confidences[row["arm"]].append(float(row["confidence"]))
    summary = {arm: {"n": sum(c.values()), "coverage": dict(c),
                     "mean_confidence": round(sum(confidences[arm]) / len(confidences[arm]), 4)}
               for arm, c in counts.items()}
    summary_name = __import__("os").environ.get(
        "PRIOR_ANTECEDENT_SUMMARY", "antecedent_summary.json")
    (args.out / summary_name).write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
