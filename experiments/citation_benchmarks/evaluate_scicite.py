#!/usr/bin/env python3
"""Evaluate citation-intent classification on SciCite's human-labelled test set."""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402

LABELS = ["background", "method", "result"]
SYSTEM = """Classify the intent of the explicitly marked target citation using
only the supplied citation context and section name. Choose exactly one SciCite label:
- background: provides background, motivation, prior concepts, or general related work
- method: the citing work uses, adopts, or builds on a method, tool, data, or procedure
- result: discusses, compares, supports, or contrasts empirical/theoretical results
Classify the TARGET citation, not other citations that may occur in the context."""
SCHEMA = {"type": "object", "properties": {
    "label": {"type": "string", "enum": LABELS},
    "confidence": {"type": "number"},
    "reason": {"type": "string"},
}, "required": ["label", "confidence", "reason"]}


def marked_context(row: dict) -> str:
    text = row.get("string") or row.get("context") or ""
    try:
        start, end = int(row["citeStart"]), int(row["citeEnd"])
    except (KeyError, TypeError, ValueError):
        return text
    if 0 <= start < end <= len(text):
        return text[:start] + "[TARGET_CITATION]" + text[end:]
    return text


def read_jsonl(path: Path, key: str) -> dict[str, dict]:
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row[key]] = row
    return rows


def prf(confusion: dict[str, Counter[str]], label: str) -> dict:
    tp = confusion[label][label]
    fp = sum(confusion[gold][label] for gold in LABELS if gold != label)
    fn = sum(confusion[label][pred] for pred in LABELS if pred != label)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(f1, 4), "support": sum(confusion[label].values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0,
                        help="deterministic stratified subset; 0 evaluates the full split")
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "out" / "scicite_predictions.jsonl")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.data.read_text().splitlines()
            if line.strip()]
    if args.limit and args.limit < len(rows):
        rng = random.Random(args.seed)
        groups = {label: [row for row in rows if row["label"] == label]
                  for label in LABELS}
        for group in groups.values():
            rng.shuffle(group)
        sample = []
        while len(sample) < args.limit and any(groups.values()):
            for label in LABELS:
                if groups[label] and len(sample) < args.limit:
                    sample.append(groups[label].pop())
        rows = sample

    done = read_jsonl(args.output, "unique_id")
    todo = [row for row in rows if row["unique_id"] not in done]
    lock = threading.Lock()

    def classify(row: dict) -> dict:
        result = llm.structured(
            model=args.model, system=SYSTEM,
            user=f"SECTION: {row.get('sectionName') or '(unknown)'}\nCONTEXT:\n{marked_context(row)}",
            schema=SCHEMA, tool_name="emit_scicite_intent", max_tokens=220,
            timeout=args.timeout, retries=3,
        )
        return {"unique_id": row["unique_id"], "gold": row["label"],
                "section": row.get("sectionName", ""), "model": args.model,
                "prompt_version": "scicite-native-v1", **result}

    print(f"SciCite: {len(todo)} remaining / {len(rows)}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(classify, row): row for row in todo}
        for i, future in enumerate(as_completed(futures), 1):
            source = futures[future]
            try:
                result = future.result()
                with lock, args.output.open("a") as handle:
                    handle.write(json.dumps(result) + "\n")
                done[result["unique_id"]] = result
                print(f"[{i}/{len(todo)}] {result['gold']} -> {result['label']}",
                      flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{i}/{len(todo)}] ERROR {source['unique_id']}: {exc}",
                      flush=True)

    evaluated = [done[row["unique_id"]] for row in rows if row["unique_id"] in done]
    confusion = {gold: Counter(result["label"] for result in evaluated
                               if result["gold"] == gold) for gold in LABELS}
    metrics = {label: prf(confusion, label) for label in LABELS}
    summary = {
        "dataset": str(args.data), "n": len(evaluated), "model": args.model,
        "accuracy": round(sum(row["gold"] == row["label"] for row in evaluated)
                          / len(evaluated), 4) if evaluated else None,
        "macro_f1": round(sum(value["f1"] for value in metrics.values()) / 3, 4),
        "per_label": metrics,
        "confusion_gold_rows": {gold: dict(confusion[gold]) for gold in LABELS},
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("->", args.output, summary_path)


if __name__ == "__main__":
    main()
