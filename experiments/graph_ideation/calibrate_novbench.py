#!/usr/bin/env python3
"""Calibrate novelty/contribution sentence recognition on NovBench labels."""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402

SYSTEM = """Classify whether each sentence explicitly evaluates or describes the
focal paper's novelty/original contribution. Positive includes a new method, model,
task, dataset, theory, perspective, improvement, or combination attributed to this
paper. Do not mark background, methodology criticism without a novelty judgment,
presentation, significance, or generic praise as novelty. Return every key exactly
once. This is sentence classification, not a verdict on whether the novelty claim
is actually true."""

ITEM = {"type": "object", "properties": {
    "key": {"type": "string"}, "is_novelty": {"type": "boolean"},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
    "required": ["key", "is_novelty", "confidence"]}
SCHEMA = {"type": "object", "properties": {
    "results": {"type": "array", "items": ITEM}}, "required": ["results"]}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--novelty", type=Path, required=True)
    parser.add_argument("--non-novelty", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=40)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    positive = json.loads(args.novelty.read_text())
    negative = json.loads(args.non_novelty.read_text())
    rows = ([{"key": f"positive:{i}", "text": x[0], "gold": True}
             for i, x in enumerate(positive)] +
            [{"key": f"negative:{i}", "text": x["text"], "gold": False}
             for i, x in enumerate(negative)])
    batches = [rows[i:i + args.batch_size] for i in range(0, len(rows), args.batch_size)]
    output = args.out / "judgements.jsonl"
    existing = read_jsonl(output) if output.exists() else []
    done = {x["batch"] for x in existing}
    lock = threading.Lock()

    def classify(item: tuple[int, list[dict]]) -> dict:
        batch_id, batch = item
        expected = {x["key"] for x in batch}
        by_key = {x["key"]: x for x in batch}
        collected = {}
        for _ in range(3):
            missing = expected - set(collected)
            if not missing:
                break
            payload = [{"key": key, "sentence": by_key[key]["text"]} for key in sorted(missing)]
            result = llm.structured(model=args.model, system=SYSTEM,
                user=json.dumps(payload), schema=SCHEMA, tool_name="emit_labels",
                max_tokens=3500, retries=3)
            for row in result.get("results", []):
                if row.get("key") in missing and isinstance(row.get("is_novelty"), bool):
                    collected[row["key"]] = row
        if expected != set(collected):
            raise ValueError(f"missing labels: {expected-set(collected)}")
        return {"batch": batch_id, "model": args.model,
                "results": [collected[x["key"]] for x in batch]}

    todo = [(i, batch) for i, batch in enumerate(batches) if i not in done]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(classify, x): x[0] for x in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with lock, output.open("a") as handle:
                handle.write(json.dumps(row) + "\n")
            print(f"novbench {i}/{len(todo)} batch={row['batch']}", flush=True)

    predictions = {x["key"]: x for batch in read_jsonl(output) for x in batch["results"]}
    tp = sum(predictions[x["key"]]["is_novelty"] and x["gold"] for x in rows)
    fp = sum(predictions[x["key"]]["is_novelty"] and not x["gold"] for x in rows)
    fn = sum(not predictions[x["key"]]["is_novelty"] and x["gold"] for x in rows)
    tn = len(rows) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    summary = {"n": len(rows), "positive": len(positive), "negative": len(negative),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 4), "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0,
        "accuracy": round((tp + tn) / len(rows), 4),
        "scope": "NovBench sentence-level novelty/contribution recognition only; not novelty-verdict correctness or Prior retrieval coverage."}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
