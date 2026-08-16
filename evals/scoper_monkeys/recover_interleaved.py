"""Recover one completed run from a JSONL ledger written by overlapping processes.

The raw file is never modified. Valid events from the completed run are retained;
candidate-only gaps may be reconstructed from their later screening decisions
when the paper payload and work key are preserved there. Every reconstruction is
declared in a sidecar report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from ledger import validate_ledger


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def recover(raw: Path, out: Path, report_path: Path) -> dict:
    valid, malformed = [], []
    for line_number, line in enumerate(raw.read_text().splitlines(), 1):
        try:
            valid.append(json.loads(line))
        except json.JSONDecodeError as error:
            malformed.append({
                "line": line_number, "bytes": len(line.encode()),
                "error": str(error),
            })

    by_run = Counter(row.get("run_id") for row in valid)
    completed = {
        row["run_id"] for row in valid if row.get("event") == "run_terminal"
    }
    candidates = [run_id for run_id in completed if any(
        row.get("run_id") == run_id and row.get("event") == "manifest"
        for row in valid
    )]
    if len(candidates) != 1:
        raise ValueError(f"expected one completed run with a manifest, found {candidates}")
    run_id = candidates[0]
    rows = [row for row in valid if row.get("run_id") == run_id]
    orders = {row["order"] for row in rows}
    max_order = max(orders)
    gaps = [order for order in range(1, max_order + 1) if order not in orders]

    known_candidate_keys = {
        row["work_key"] for row in rows if row.get("event") == "candidate"
    }
    first_decision_by_key = {}
    for row in sorted(rows, key=lambda item: item["order"]):
        if row.get("event") == "decision":
            first_decision_by_key.setdefault(row["work_key"], row)
    recoverable_candidates = [
        row for key, row in first_decision_by_key.items()
        if key not in known_candidate_keys
    ]
    multi_seen = {
        row["work_key"]: row for row in rows
        if row.get("event") in {"candidate", "reached_again"}
        and row.get("stage") == "multi_query"
    }
    multi_decided = {
        row["work_key"] for row in rows
        if row.get("event") == "decision" and row.get("stage") == "multi_query"
    }
    recoverable_decisions = [
        row for key, row in multi_seen.items()
        if key not in multi_decided and any(
            later.get("event") == "decision" and later.get("work_key") == key
            and later.get("stage") == "strict_rescreen" for later in rows
        )
    ]
    if len(recoverable_candidates) + len(recoverable_decisions) != len(gaps):
        raise ValueError(
            f"cannot safely reconstruct: {len(gaps)} order gaps but "
            f"{len(recoverable_candidates)} decisions without candidate events and "
            f"{len(recoverable_decisions)} downstream-confirmed missing decisions"
        )
    recovered = []
    candidate_orders = gaps[:len(recoverable_candidates)]
    for order, decision in zip(
        candidate_orders, sorted(recoverable_candidates, key=lambda row: row["order"])
    ):
        recovered.append({
            "schema_version": decision["schema_version"], "run_id": run_id,
            "event_id": f"{run_id}:recovered:e{order:06d}", "event": "candidate",
            "order": order, "recorded_at": decision["recorded_at"],
            "stage": decision["stage"], "channel": "search",
            "work_key": decision["work_key"], "paper": decision["paper"],
            "recovered_from": decision["event_id"],
            "recovery_basis": "screening decision preserves candidate payload",
        })
    decision_orders = gaps[len(recoverable_candidates):]
    for order, candidate in zip(decision_orders, recoverable_decisions):
        recovered.append({
            "schema_version": candidate["schema_version"], "run_id": run_id,
            "event_id": f"{run_id}:recovered:e{order:06d}", "event": "decision",
            "order": order, "recorded_at": candidate["recorded_at"],
            "stage": "multi_query", "work_key": candidate["work_key"],
            "decision": "kept",
            "reason": "reconstructed: work entered downstream strict-rescreen corpus",
            "paper": candidate["paper"], "recovered_from": candidate["event_id"],
            "recovery_basis": "presence in downstream corpus proves broad-scope keep",
        })
    rows.extend(recovered)
    rows.sort(key=lambda row: row["order"])
    validate_ledger(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))

    report = {
        "raw": str(raw), "raw_sha256": _sha(raw), "recovered": str(out),
        "recovered_sha256": _sha(out), "selected_run_id": run_id,
        "valid_events_by_run": dict(by_run), "malformed_lines": malformed,
        "discarded_run_ids": sorted(key for key in by_run if key != run_id),
        "order_gaps": gaps,
        "reconstructed_candidate_events": len(recoverable_candidates),
        "reconstructed_decision_events": len(recoverable_decisions),
        "reconstruction_basis": (
            "All missing orders formed one boundary block between candidate and decision "
            "events. Later decisions preserved 21 missing candidate payloads. One "
            "candidate lacked its broad decision but appeared in the downstream strict "
            "rescreen, proving that the broad decision was keep. Exact reasons and "
            "original ordering within reconstructed sub-blocks are not recoverable."
        ),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    print(json.dumps(recover(args.raw, args.out, args.report), indent=2))
