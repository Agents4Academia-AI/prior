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
            row["automatic_diagnosis"] = "not_retrieved_or_not_indexed"
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
    return "\n".join(lines) + "\n"


def main(args) -> None:
    events = load_events(args.run)
    gold = load_gold(args.gold)
    report = analyse(events, gold, title_threshold=args.title_threshold)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (out / "report.md").write_text(_markdown(report))
    with (out / "misses.csv").open("w", newline="") as handle:
        fields = [
            "gold_id", "title", "year", "automatic_diagnosis", "first_stage",
            "decision", "decision_reason", "match_score", "manual_category",
            "manual_notes",
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
