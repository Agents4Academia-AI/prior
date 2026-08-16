"""Analyse seed/direction structure already present in a traced citation run."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from common import load_gold, match_gold
from ledger import load_and_validate


def analyse(run: Path, out_dir: Path, gold_path: Path | None = None) -> dict:
    events = load_and_validate(run)
    candidates = [event for event in events
                  if event.get("event") == "candidate"
                  and event.get("stage") == "snowball_1"]
    decisions = {
        event["work_key"]: event for event in events
        if event.get("event") == "decision" and event.get("stage") == "snowball_1"
    }
    paths_by_work = defaultdict(list)
    for event in events:
        if event.get("event") == "citation_path":
            paths_by_work[event["work_key"]].append(event)
    gold = load_gold(gold_path) if gold_path else []

    attributed = defaultdict(lambda: {
        "candidates": 0, "kept": 0, "targets": set(), "positions": [],
    })
    kept_positions = []
    unattributed = 0
    for position, candidate in enumerate(candidates, 1):
        decision = decisions.get(candidate["work_key"])
        kept = bool(decision and decision["decision"] == "kept")
        if kept:
            kept_positions.append(position)
        paths = paths_by_work.get(candidate["work_key"], [])
        if not paths:
            unattributed += 1
            continue
        path = min(paths, key=lambda event: event["order"])
        key = (path["seed_work_key"], path["seed"]["title"], path["source"],
               path["direction"])
        row = attributed[key]
        row["candidates"] += 1
        row["kept"] += int(kept)
        row["positions"].append(position)
        for item in gold:
            if match_gold(item, candidate["paper"]):
                row["targets"].add(item.gold_id)

    branches = []
    for (seed_key, seed_title, source, direction), values in attributed.items():
        branches.append({
            "seed_work_key": seed_key, "seed_title": seed_title, "source": source,
            "direction": direction, "candidates": values["candidates"],
            "kept": values["kept"],
            "eligible_yield": values["kept"] / max(1, values["candidates"]),
            "targets": len(values["targets"]),
            "first_position": min(values["positions"]),
            "last_position": max(values["positions"]),
        })
    branches.sort(key=lambda row: (-row["targets"], -row["kept"], row["seed_title"]))

    dry_runs = []
    previous = 0
    for position in kept_positions:
        if position - previous > 1:
            dry_runs.append({
                "after_position": previous, "next_keep_position": position,
                "excluded_between": position - previous - 1,
            })
        previous = position
    if candidates and previous < len(candidates):
        dry_runs.append({
            "after_position": previous, "next_keep_position": None,
            "excluded_between": len(candidates) - previous,
        })
    dry_runs.sort(key=lambda row: -row["excluded_between"])

    report = {
        "citation_candidates": len(candidates), "kept": len(kept_positions),
        "attributed_branches": len(branches), "unattributed_candidates": unattributed,
        "longest_dry_runs": dry_runs[:20], "branches": branches,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "citation-trace-analysis.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    with (out_dir / "citation-branches.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(branches[0]) if branches else [])
        if branches:
            writer.writeheader()
            writer.writerows(branches)
    lines = [
        "# Citation trace structure", "",
        f"Candidates: **{len(candidates)}** · broadly kept: **{len(kept_positions)}** · "
        f"first-attributed branches: **{len(branches)}** · unattributed: **{unattributed}**",
        "", "## Highest-yield branches", "",
        "| seed | direction | candidates | kept | yield | frozen targets | positions |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(branches, key=lambda item: (-item["kept"], -item["targets"]))[:20]:
        lines.append(
            f"| {row['seed_title']} | {row['direction']} | {row['candidates']} | "
            f"{row['kept']} | {row['eligible_yield']:.1%} | {row['targets']} | "
            f"{row['first_position']}–{row['last_position']} |"
        )
    lines += ["", "## Longest flat-order dry runs", "",
              "| after | next keep | exclusions between |", "|---:|---:|---:|"]
    for row in dry_runs[:10]:
        lines.append(
            f"| {row['after_position']} | {row['next_keep_position'] or 'end'} | "
            f"{row['excluded_between']} |"
        )
    (out_dir / "citation-trace-analysis.md").write_text("\n".join(lines) + "\n")
    return report


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--gold", type=Path)
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    analyse(args.run, args.out_dir, args.gold)
