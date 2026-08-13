#!/usr/bin/env python3
"""Evaluate Prior's fixed citation window against CORWA's human citation spans."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def overlap(pred_start: int, pred_end: int, gold_start: int, gold_end: int):
    shared = max(0, min(pred_end, gold_end) - max(pred_start, gold_start))
    precision = shared / max(1, pred_end - pred_start)
    recall = shared / max(1, gold_end - gold_start)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def marker_offsets(paragraph: str, span: dict) -> tuple[int, int] | None:
    mappings = span["span_citation_mapping"].get(span["span_type"], {})
    candidates = []
    for marker in mappings:
        start = 0
        while True:
            found = paragraph.find(marker, start)
            if found < 0:
                break
            candidates.append((abs(found - span["char_start"]), found,
                               found + len(marker)))
            start = found + 1
    if not candidates:
        return None
    _, start, end = min(candidates)
    return start, end


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--window", type=int, default=320,
                        help="characters on either side, matching Prior's extractor")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.data.read_text().splitlines()
            if line.strip()]
    scores = defaultdict(list)
    missing, total = Counter(), Counter()
    examples = []
    for row in rows:
        paragraph = row["paragraph"]
        for span in row["span_citation_mapping"]:
            kind = span["span_type"]
            total[kind] += 1
            marker = marker_offsets(paragraph, span)
            if marker is None:
                missing[kind] += 1
                continue
            start = max(0, marker[0] - args.window)
            end = min(len(paragraph), marker[1] + args.window)
            values = overlap(start, end, span["char_start"], span["char_end"])
            scores[kind].append(values)
            if len(examples) < 20:
                examples.append({"paragraph_id": row["id"], "span_type": kind,
                                 "gold": [span["char_start"], span["char_end"]],
                                 "predicted": [start, end],
                                 "precision": values[0], "recall": values[1],
                                 "f1": values[2]})
    result = {"dataset": str(args.data), "window_each_side": args.window,
              "paragraphs": len(rows), "by_span_type": {}}
    for kind in sorted(total):
        values = scores[kind]
        result["by_span_type"][kind] = {
            "gold_spans": total[kind], "markers_located": len(values),
            "marker_coverage": round(len(values) / total[kind], 4),
            "mean_precision": round(sum(x[0] for x in values) / len(values), 4),
            "mean_recall": round(sum(x[1] for x in values) / len(values), 4),
            "mean_f1": round(sum(x[2] for x in values) / len(values), 4),
        }
    result["examples"] = examples
    output = args.output or Path(__file__).parent / "out" / "corwa_fixed_window.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "examples"}, indent=2))
    print("->", output)


if __name__ == "__main__":
    main()
