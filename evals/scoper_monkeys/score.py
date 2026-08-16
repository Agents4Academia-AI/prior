"""Offline scoring for Scoper monkey runs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from common import best_gold_match, load_events, load_gold, match_gold


def _unique_candidates(events: list[dict]) -> list[dict]:
    seen, out = set(), []
    for event in events:
        if event.get("event") != "candidate":
            continue
        key = event["work_key"]
        if key in seen:
            continue
        seen.add(key)
        out.append(event)
    return out


def _decisions(events: list[dict]) -> dict[str, dict]:
    return {
        event["work_key"]: event for event in events
        if event.get("event") == "decision"
    }


def analyse(events: list[dict], gold, *, title_threshold: float = 0.82) -> dict:
    manifest = next(event for event in events if event.get("event") == "manifest")
    candidates = _unique_candidates(events)
    decisions = _decisions(events)
    citation_paths = [event for event in events if event.get("event") == "citation_path"]
    source_failures = [event for event in events if event.get("event") == "source_failure"]
    terminals = [event for event in events if event.get("event") == "branch_terminal"]
    run_terminal = next(
        (event for event in reversed(events) if event.get("event") == "run_terminal"),
        None,
    )
    stages = []
    for event in candidates:
        if event["stage"] not in stages:
            stages.append(event["stage"])

    gold_rows = []
    for item in gold:
        event, score = None, 0.0
        for candidate in candidates:
            candidate_score = match_gold(
                item, candidate["paper"], title_threshold=title_threshold
            )
            if candidate_score > score:
                event, score = candidate, candidate_score
        decision = decisions.get(event["work_key"]) if event else None
        path, path_score = None, 0.0
        for candidate_path in citation_paths:
            candidate_score = match_gold(
                item, candidate_path["paper"], title_threshold=title_threshold
            )
            if candidate_score > path_score:
                path, path_score = candidate_path, candidate_score
        gold_rows.append({
            "gold_id": item.gold_id,
            "title": item.title,
            "year": item.year,
            "found": bool(event),
            "match_score": round(score, 3),
            "first_stage": event["stage"] if event else "",
            "work_key": event["work_key"] if event else "",
            "decision": decision.get("decision", "") if decision else "",
            "decision_reason": decision.get("reason", "") if decision else "",
            "candidate_order": event.get("order") if event else None,
            "decision_order": decision.get("order") if decision else None,
            "citation_source": path.get("source", "") if path else "",
            "citation_direction": path.get("direction", "") if path else "",
            "citation_seed_title": path.get("seed", {}).get("title", "") if path else "",
            "citation_seed_work_key": path.get("seed_work_key", "") if path else "",
            "citation_branch_id": path.get("branch_id", "") if path else "",
        })

    cumulative = []
    found_stages: set[str] = set()
    for stage in stages:
        found_stages.add(stage)
        discovered = [row for row in gold_rows if row["first_stage"] in found_stages]
        accepted = [row for row in discovered if row["decision"] == "kept"]
        cumulative.append({
            "stage": stage,
            "discovered": len(discovered),
            "discovery_recall": round(len(discovered) / max(1, len(gold)), 4),
            "accepted": len(accepted),
            "accepted_recall": round(len(accepted) / max(1, len(gold)), 4),
        })

    budgets = []
    decided = sorted(
        (event for event in events if event.get("event") == "decision"),
        key=lambda event: event["order"],
    )
    for budget in (50, 100, 250, 500):
        prefix = decided[:budget]
        kept_papers = [event["paper"] for event in prefix if event["decision"] == "kept"]
        hits = sum(
            bool(best_gold_match(item, kept_papers, title_threshold=title_threshold)[0])
            for item in gold
        )
        budgets.append({
            "screened": min(budget, len(decided)),
            "gold_accepted": hits,
            "accepted_recall": round(hits / max(1, len(gold)), 4),
        })

    snapshots = []
    for event in events:
        if event.get("event") != "snapshot":
            continue
        stage_set = set()
        for stage in stages:
            stage_set.add(stage)
            if stage == event["stage"]:
                break
        true_hits = sum(row["first_stage"] in stage_set for row in gold_rows)
        accepted_hits = sum(
            row["first_stage"] in stage_set and row["decision"] == "kept"
            for row in gold_rows
        )
        snapshots.append({
            "stage": event["stage"],
            "candidates": event.get("candidates", 0),
            "new_kept": event.get("new_kept", 0),
            "yield_rate": event.get("yield_rate"),
            "stop_triggered": event.get("stop_triggered", False),
            "stop_reason": event.get("stop_reason", ""),
            "true_discovery_recall": round(true_hits / max(1, len(gold)), 4),
            "true_accepted_recall": round(accepted_hits / max(1, len(gold)), 4),
            "estimated_recall": (event.get("completeness") or {}).get("recall"),
        })

    branches = [
        {key: event.get(key) for key in (
            "branch_id", "stage", "query", "returned_unique", "globally_new",
            "rediscovered", "newly_included", "eligible_yield", "corpus_after",
            "attribution",
        )}
        for event in events if event.get("event") == "branch_snapshot"
    ]

    for row in gold_rows:
        if not row["found"]:
            row["automatic_diagnosis"] = (
                "not_retrieved_with_source_failures" if source_failures
                else "not_retrieved_query_depth_or_index_gap"
            )
        elif row["decision"] == "dropped":
            row["automatic_diagnosis"] = (
                "prefilter_rejection"
                if row["decision_reason"].startswith("pre-filtered:")
                else "scope_filter_rejection"
            )
        elif not row["decision"]:
            row["automatic_diagnosis"] = "retrieved_not_screened"
        else:
            row["automatic_diagnosis"] = "recovered"

    return {
        "case": manifest["case"],
        "gold_n": len(gold),
        "candidate_n": len(candidates),
        "decision_n": len(decided),
        "cumulative": cumulative,
        "budgets": budgets,
        "stopping": snapshots,
        "branches": branches,
        "source_failures": [
            {key: event.get(key) for key in (
                "branch_id", "stage", "source", "query", "error_type", "message",
                "retry_or_fallback",
            )}
            for event in source_failures
        ],
        "branch_terminal_counts": {
            status: sum(event.get("status") == status for event in terminals)
            for status in ("exhausted", "bounded", "failed", "waived", "pending")
        },
        "run_terminal": ({key: run_terminal.get(key) for key in
                          ("status", "reason", "open_tasks")} if run_terminal else None),
        "gold": gold_rows,
    }


def _markdown(report: dict) -> str:
    lines = [
        f"# Scoper monkeys — {report['case']}",
        "",
        f"Gold: **{report['gold_n']}** · unique candidates: "
        f"**{report['candidate_n']}** · screened: **{report['decision_n']}**",
        "",
        "## Recall by stage",
        "",
        "| stage | found | discovery recall | accepted | accepted recall |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in report["cumulative"]:
        lines.append(
            f"| {row['stage']} | {row['discovered']} | "
            f"{row['discovery_recall']:.1%} | {row['accepted']} | "
            f"{row['accepted_recall']:.1%} |"
        )
    lines += [
        "",
        "## Recall by screening budget",
        "",
        "| screened | accepted gold | accepted recall |",
        "|---:|---:|---:|",
    ]
    for row in report["budgets"]:
        lines.append(
            f"| {row['screened']} | {row['gold_accepted']} | "
            f"{row['accepted_recall']:.1%} |"
        )
    if report.get("branches"):
        lines += [
            "", "## Query-branch growth", "",
            "| branch | returned | globally new | rediscovered | newly included | yield | corpus |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for row in report["branches"]:
            lines.append(
                f"| {row['branch_id']} | {row['returned_unique']} | {row['globally_new']} | "
                f"{row['rediscovered']} | {row['newly_included']} | "
                f"{row['eligible_yield']:.1%} | {row['corpus_after']} |"
            )
    lines += [
        "",
        "## Stopping calibration",
        "",
        "| stage | stop? | reason | estimated recall | true discovery | true accepted |",
        "|---|---|---|---:|---:|---:|",
    ]
    for row in report["stopping"]:
        estimated = "—" if row["estimated_recall"] is None else (
            f"{row['estimated_recall']:.1%}"
        )
        lines.append(
            f"| {row['stage']} | {'yes' if row['stop_triggered'] else 'no'} | "
            f"{row['stop_reason'] or '—'} | {estimated} | "
            f"{row['true_discovery_recall']:.1%} | "
            f"{row['true_accepted_recall']:.1%} |"
        )
    terminal = report.get("run_terminal")
    if terminal:
        lines += [
            "", "## Methodological run status", "",
            f"Status: **{terminal['status']}** — {terminal['reason']}.", "",
            "Branch terminal states: " + ", ".join(
                f"{key}={value}" for key, value in
                report.get("branch_terminal_counts", {}).items() if value
            ) + ".",
        ]
    failures = report.get("source_failures", [])
    if failures:
        by_source = {}
        for failure in failures:
            by_source[failure["source"]] = by_source.get(failure["source"], 0) + 1
        lines += [
            "", "## Source failures", "",
            " · ".join(f"{source}: **{count}**" for source, count in sorted(by_source.items())),
        ]
    recovered_paths = [row for row in report["gold"] if row.get("citation_branch_id")]
    if recovered_paths:
        lines += [
            "", "## Hidden targets recovered through citation paths", "",
            "| target | source | direction | seed |",
            "|---|---|---|---|",
        ]
        for row in recovered_paths:
            lines.append(
                f"| {row['title']} | {row['citation_source']} | "
                f"{row['citation_direction']} | {row['citation_seed_title']} |"
            )
    return "\n".join(lines) + "\n"


def main(args) -> None:
    events = load_events(args.run)
    gold = load_gold(args.gold)
    report = analyse(events, gold, title_threshold=args.title_threshold)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "report.md").write_text(_markdown(report))
    with (out / "queries.csv").open("w", newline="") as handle:
        fields = ["order", "stage", "branch_id", "kind", "query", "motivation"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for event in events:
            if event.get("event") != "query":
                continue
            for query in event.get("queries", []):
                writer.writerow({
                    "order": event.get("order"), "stage": event.get("stage", ""),
                    "branch_id": event.get("branch_id", ""),
                    "kind": event.get("kind", ""), "query": query,
                    "motivation": event.get("motivation", ""),
                })
    with (out / "retrieval_tasks.csv").open("w", newline="") as handle:
        fields = [
            "order", "event", "stage", "branch_id", "parent_branch_id", "source",
            "query", "parameters", "status", "reason", "error_type", "message",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for event in events:
            if event.get("event") not in {
                "retrieval_request", "source_failure", "branch_terminal"
            }:
                continue
            writer.writerow({
                key: (json.dumps(event.get(key), sort_keys=True)
                      if key == "parameters" else event.get(key, ""))
                for key in fields
            })
    with (out / "misses.csv").open("w", newline="") as handle:
        fields = [
            "gold_id", "title", "year", "automatic_diagnosis", "first_stage",
            "decision", "decision_reason", "match_score", "manual_category",
            "citation_source", "citation_direction", "citation_seed_title",
            "citation_seed_work_key", "citation_branch_id", "manual_notes",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in report["gold"]:
            if row["automatic_diagnosis"] != "recovered":
                writer.writerow(row | {"manual_category": "", "manual_notes": ""})
    print(out / "report.md")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--title-threshold", type=float, default=0.82)
    return ap


if __name__ == "__main__":
    main(parser().parse_args())
