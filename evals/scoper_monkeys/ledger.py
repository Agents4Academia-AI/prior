"""Versioned JSONL ledger helpers for instrumented Scoper evaluations."""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "prior.scoper-ledger/1.0"
EVENT_TYPES = {
    "manifest", "query", "candidate", "reached_again", "decision", "snapshot",
    "retrieval_request", "retrieval_result", "source_failure", "deduplication",
    "branch_snapshot",
    "seed", "citation_path",
}
QUERY_KINDS = {"probe", "reformulation"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def code_version(root: Path) -> str:
    """Return the checked-out revision, visibly marked when locally modified."""
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        return revision + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def new_run_id() -> str:
    return f"scoper:{uuid.uuid4()}"


def validate_event(row: dict) -> None:
    """Validate the stable ledger envelope and event-specific minimum fields."""
    required = {"schema_version", "run_id", "event_id", "event", "order", "recorded_at"}
    missing = sorted(required - row.keys())
    if missing:
        raise ValueError(f"ledger event missing fields: {missing}")
    if row["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {row['schema_version']!r}")
    if row["event"] not in EVENT_TYPES:
        raise ValueError(f"unsupported event type: {row['event']!r}")
    if not isinstance(row["order"], int) or row["order"] < 1:
        raise ValueError("order must be a positive integer")
    if row["event"] == "manifest":
        for field in ("case", "scope", "scope_sha256", "code_version", "parameters"):
            if field not in row:
                raise ValueError(f"manifest missing field: {field}")
    elif row["event"] == "query":
        if row.get("kind") not in QUERY_KINDS or not row.get("queries"):
            raise ValueError("query requires kind and a non-empty queries list")
        if row["kind"] == "reformulation" and not row.get("motivation"):
            raise ValueError("reformulation query requires motivation")
    elif row["event"] in {"candidate", "reached_again"}:
        for field in ("stage", "channel", "work_key", "paper"):
            if field not in row:
                raise ValueError(f"{row['event']} missing field: {field}")
    elif row["event"] == "decision":
        for field in ("stage", "work_key", "decision", "reason", "paper"):
            if field not in row:
                raise ValueError(f"decision missing field: {field}")
    elif row["event"] == "retrieval_request":
        for field in ("branch_id", "source", "query", "parameters"):
            if field not in row:
                raise ValueError(f"retrieval_request missing field: {field}")
    elif row["event"] == "retrieval_result":
        for field in ("branch_id", "source", "query", "source_rank", "work_key", "paper"):
            if field not in row:
                raise ValueError(f"retrieval_result missing field: {field}")
    elif row["event"] == "source_failure":
        for field in ("branch_id", "source", "query", "error_type", "retry_or_fallback"):
            if field not in row:
                raise ValueError(f"source_failure missing field: {field}")
    elif row["event"] == "deduplication":
        for field in ("branch_id", "work_key", "retained_id", "variant_ids", "basis"):
            if field not in row:
                raise ValueError(f"deduplication missing field: {field}")
    elif row["event"] == "branch_snapshot":
        for field in ("branch_id", "stage", "returned_unique", "globally_new",
                      "newly_included", "corpus_after"):
            if field not in row:
                raise ValueError(f"branch_snapshot missing field: {field}")
    elif row["event"] == "seed":
        for field in ("branch_id", "seed_role", "work_key", "paper"):
            if field not in row:
                raise ValueError(f"seed missing field: {field}")
    elif row["event"] == "citation_path":
        for field in ("branch_id", "source", "hop", "direction", "seed_work_key",
                      "work_key", "endpoint", "seed", "paper"):
            if field not in row:
                raise ValueError(f"citation_path missing field: {field}")
    elif row["event"] == "snapshot" and "stage" not in row:
        raise ValueError("snapshot missing field: stage")


def validate_ledger(rows: list[dict]) -> None:
    if not rows or rows[0].get("event") != "manifest":
        raise ValueError("ledger must begin with one manifest event")
    run_ids = {row.get("run_id") for row in rows}
    if len(run_ids) != 1:
        raise ValueError("all ledger events must share one run_id")
    orders = [row.get("order") for row in rows]
    if orders != list(range(1, len(rows) + 1)):
        raise ValueError("ledger order must be contiguous and start at 1")
    event_ids = [row.get("event_id") for row in rows]
    if len(event_ids) != len(set(event_ids)):
        raise ValueError("event_id values must be unique")
    for row in rows:
        validate_event(row)


def load_and_validate(path: str | Path) -> list[dict]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    validate_ledger(rows)
    return rows
