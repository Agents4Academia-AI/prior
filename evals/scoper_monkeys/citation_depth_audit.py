"""Audit marginal discovery across checkpointed forward-citation page depths."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from freeze_external_targets import aliases  # noqa: E402


def rows(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                yield json.loads(line)
            except ValueError:
                continue


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--useful", type=Path, action="append", default=[])
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)

    useful_aliases = set()
    for path in args.useful:
        for row in rows(path):
            useful_aliases |= aliases(row.get("paper", row))

    cursor_depth: dict[str, dict[str, int]] = defaultdict(dict)
    occurrences = []
    for event_index, event in enumerate(rows(args.ledger)):
        if event.get("event") != "result":
            continue
        task, cursor = event["task_id"], event.get("cursor", "*")
        if cursor not in cursor_depth[task]:
            cursor_depth[task][cursor] = len(cursor_depth[task]) + 1
        paper = event["paper"]
        occurrences.append({"event_index": event_index, "task_id": task,
                            "depth": cursor_depth[task][cursor], "paper": paper,
                            "paper_aliases": aliases(paper)})

    seen = set(); by_depth = defaultdict(Counter); useful_seen = set()
    for row in occurrences:
        depth, paper_aliases = row["depth"], row["paper_aliases"]
        key = sorted(paper_aliases)[0] if paper_aliases else "event:" + str(row["event_index"])
        by_depth[depth]["result_occurrences"] += 1
        if key in seen:
            by_depth[depth]["rediscovery_occurrences"] += 1
        else:
            seen.add(key); by_depth[depth]["new_unique_candidates"] += 1
        if paper_aliases & useful_aliases:
            by_depth[depth]["known_useful_occurrences"] += 1
            if not (paper_aliases & useful_seen):
                useful_seen |= paper_aliases
                by_depth[depth]["new_known_useful_works"] += 1

    table = []
    for depth in sorted(by_depth):
        item = by_depth[depth]
        total = item["result_occurrences"]
        table.append({"page_depth": depth, **item,
                      "rediscovery_rate": item["rediscovery_occurrences"] / max(1, total),
                      "known_useful_rate": item["known_useful_occurrences"] / max(1, total)})
    fields = ["page_depth", "result_occurrences", "new_unique_candidates",
              "rediscovery_occurrences", "rediscovery_rate", "known_useful_occurrences",
              "new_known_useful_works", "known_useful_rate"]
    with (args.out_dir / "citation-depth-audit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(table)
    (args.out_dir / "citation-depth-audit.json").write_text(json.dumps({
        "ledger": str(args.ledger), "useful_inputs": [str(p) for p in args.useful],
        "definition": "Known-useful is membership in the pre-citation eligible, retrieval-only, or uncertain corpus; hidden targets are not loaded.",
        "result_occurrences": len(occurrences), "unique_candidate_keys": len(seen),
        "known_useful_works_rediscovered": len(useful_seen), "by_page_depth": table,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
