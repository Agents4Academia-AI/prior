"""Freeze and screen a bounded, 152-seed anchored-update cohort.

This utility deliberately separates deterministic cohort construction from the
agentic screen.  The cohort is a retrieval-priority audit cohort, *not* a
probability sample: its role frequencies must never be extrapolated to the full
candidate universe.

``prepare`` requires a corrected, work-resolved ``novel-candidates.jsonl`` and a
frozen strict scope.  It quarantines unresolved identities and invalid evidence,
then freezes a date-stratified, retrieval-priority cohort in a new directory.

``screen`` uses :func:`prior.scoper.scope_exhaustive` and a fresh strict cache in
that directory.  Every invocation writes a new immutable attempt directory, so
an interrupted run can resume without overwriting earlier partitions.  Caches
from the earlier broad-scope experiment are intentionally incompatible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import config, llm, scoper  # noqa: E402
from prior.models import Paper  # noqa: E402


PROTOCOL = "prior.anchored-screening/1.0"
DEFAULT_CAP = 600
DATE_BUCKETS = ("after_snapshot", "on_or_before_snapshot", "date_uncertain")
DATE_FRACTIONS = {
    "after_snapshot": 0.50,
    "on_or_before_snapshot": 0.42,
    "date_uncertain": 0.08,
}
WAVE_COUNTS = {"after_snapshot": 50, "on_or_before_snapshot": 42,
               "date_uncertain": 8}
NON_PROBABILITY_WARNING = (
    "Deterministic date-stratified retrieval-priority cohort; not a probability "
    "sample. Role frequencies and channel yields are descriptive of this cohort "
    "only and must not be extrapolated to the full candidate universe."
)
STRICT_CACHE = "strict-scope-cache.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _evidence_fingerprint(paper: Paper | dict) -> str:
    if isinstance(paper, Paper):
        title, abstract = paper.title, paper.abstract or ""
    else:
        title, abstract = str(paper.get("title") or ""), str(paper.get("abstract") or "")
    return _sha256_bytes((title + "\n" + abstract).encode())


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"expected object at {path}:{line_number}")
        rows.append(value)
    return rows


def _write_jsonl_new(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _new_output_dir(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _paper(row: dict) -> Paper:
    value = row.get("paper", row)
    if not isinstance(value, dict):
        raise ValueError("candidate row has no paper object")
    return Paper.from_dict(value)


def _retrieval(row: dict) -> dict:
    # Corrected identity snapshots keep core provenance at top level; older
    # candidate files nested it under ``retrieval``. Support both without
    # changing the frozen input.
    value = {key: row[key] for key in (
        "work_key", "identity_status", "channels", "seed_work_keys",
        "seed_path_count", "seed_count", "retrieval_occurrences",
        "occurrence_count", "occurrences", "date_bucket",
        "screening_evidence", "identity_unresolved", "state",
    ) if key in row}
    nested = row.get("retrieval") or {}
    if isinstance(nested, dict):
        value.update(nested)
    return value


def _date_bucket(row: dict) -> str:
    raw = str(_retrieval(row).get("date_bucket") or row.get("date_bucket") or "")
    aliases = {
        "post_cutoff": "after_snapshot",
        "after_cutoff": "after_snapshot",
        "pre_cutoff": "on_or_before_snapshot",
        "on_or_before_cutoff": "on_or_before_snapshot",
        "cutoff_uncertain": "date_uncertain",
    }
    value = aliases.get(raw, raw)
    return value if value in DATE_BUCKETS else "date_uncertain"


def _identity_status(row: dict, paper: Paper) -> tuple[bool, list[str]]:
    """Return whether identity is screenable and any quarantine reasons.

    A corrected candidate must bind its trace key to the selected manifestation.
    Explicit unresolved/ambiguous states and an undocumented key/title mismatch
    are quarantined rather than silently screened under the wrong provenance.
    """
    reasons = []
    retrieval = _retrieval(row)
    identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
    statuses = [row.get("state"), row.get("identity_status"),
                retrieval.get("identity_status"), identity.get("status")]
    bad = {"unresolved", "identity_unresolved", "ambiguous", "conflict",
           "quarantined", "invalid"}
    if row.get("identity_unresolved") or retrieval.get("identity_unresolved"):
        reasons.append("explicit_identity_unresolved")
    if identity.get("resolved") is False:
        reasons.append("identity_resolved_false")
    for status in statuses:
        normalized = str(status or "").lower()
        if normalized in bad or normalized.startswith("identity_unresolved"):
            reasons.append(f"identity_status:{normalized}")
    if not paper.id or paper.id.lower() in {"s2:none", "s2:null", "s2:unknown"}:
        reasons.append("missing_source_identifier")
    if not paper.title.strip():
        reasons.append("missing_title")
    traced_key = str(retrieval.get("work_key") or row.get("work_key") or "")
    if not traced_key:
        reasons.append("missing_retrieval_work_key")
    # The corrected work key is intentionally source-independent and may be a
    # DOI/arXiv alias rather than Paper.key()'s normalized title.  When the
    # resolver supplied its identity union, still verify the canonical key is a
    # member (normalizing the resolver's ``id:`` prefix for source IDs).
    identity_keys = {str(key) for key in row.get("identity_keys") or []}
    normalized_keys = identity_keys | {key.removeprefix("id:") for key in identity_keys}
    if traced_key and identity_keys and traced_key not in normalized_keys:
        reasons.append("work_key_not_in_resolved_identity_union")
    return not reasons, sorted(set(reasons))


def _evidence_status(row: dict, paper: Paper) -> tuple[bool, list[str], dict]:
    retrieval = _retrieval(row)
    supplied = retrieval.get("screening_evidence") or row.get("screening_evidence") or {}
    supplied = supplied if isinstance(supplied, dict) else {}
    fingerprint = _evidence_fingerprint(paper)
    reasons = []
    declared = supplied.get("title_abstract_sha256") or supplied.get("evidence_sha256")
    if declared and declared != fingerprint:
        reasons.append("declared_title_abstract_fingerprint_mismatch")
    if supplied.get("truncated") is True:
        reasons.append("evidence_declared_truncated")
    declared_chars = supplied.get("abstract_chars")
    if declared_chars is not None:
        try:
            if int(declared_chars) != len(paper.abstract or ""):
                reasons.append("declared_abstract_length_mismatch")
        except (TypeError, ValueError):
            reasons.append("invalid_declared_abstract_length")
    evidence = {
        "title_abstract_sha256": fingerprint,
        "title_chars": len(paper.title),
        "abstract_chars": len(paper.abstract or ""),
        "truncated": False,
        "verified_against_declared_fingerprint": bool(declared) and not reasons,
    }
    return not reasons, sorted(set(reasons)), evidence


def _has_substantive_abstract(paper: Paper) -> bool:
    return len(re.findall(r"[A-Za-z0-9]+", paper.abstract or "")) >= 5


def _screening_order(cohort: list[dict]) -> list[dict]:
    """Interleave date strata in auditable 50/42/8 waves of 100."""
    strata = {bucket: [row for row in cohort if _date_bucket(row) == bucket]
              for bucket in DATE_BUCKETS}
    order = []
    offsets = {bucket: 0 for bucket in DATE_BUCKETS}
    while len(order) < len(cohort):
        before = len(order)
        for bucket in DATE_BUCKETS:
            start = offsets[bucket]
            end = min(start + WAVE_COUNTS[bucket], len(strata[bucket]))
            order.extend(strata[bucket][start:end])
            offsets[bucket] = end
        if len(order) == before:
            break
    return order


def _priority(row: dict) -> tuple:
    retrieval = _retrieval(row)
    channels = sorted(set(retrieval.get("channels") or []))
    seed_paths = retrieval.get("seed_work_keys") or []
    try:
        seed_count = int(retrieval.get(
            "seed_path_count", retrieval.get("seed_count", len(seed_paths))))
    except (TypeError, ValueError):
        seed_count = len(seed_paths)
    try:
        occurrences = int(retrieval.get(
            "retrieval_occurrences", retrieval.get(
                "occurrence_count", len(retrieval.get("occurrences") or []))))
    except (TypeError, ValueError):
        occurrences = 0
    paper = _paper(row)
    work_key = str(retrieval.get("work_key") or paper.key())
    return (-len(channels), -seed_count, -occurrences,
            paper.title.casefold(), _evidence_fingerprint(paper), work_key, paper.id)


def _targets(cap: int) -> dict[str, int]:
    raw = {bucket: cap * DATE_FRACTIONS[bucket] for bucket in DATE_BUCKETS}
    result = {bucket: int(raw[bucket]) for bucket in DATE_BUCKETS}
    remaining = cap - sum(result.values())
    order = sorted(DATE_BUCKETS, key=lambda b: (-(raw[b] - result[b]), DATE_BUCKETS.index(b)))
    for bucket in order[:remaining]:
        result[bucket] += 1
    return result


def _annotated(row: dict, evidence: dict) -> dict:
    value = dict(row)
    value["screening"] = {
        "cohort_protocol": PROTOCOL,
        "date_bucket": _date_bucket(row),
        "evidence": evidence,
    }
    return value


def prepare(candidate_file: Path, scope_file: Path, out_dir: Path, *,
            cap: int = DEFAULT_CAP) -> dict:
    """Freeze a new immutable, non-probability anchored-screening cohort."""
    if cap <= 0:
        raise ValueError("cap must be positive")
    _new_output_dir(out_dir)
    rows = _read_jsonl(candidate_file)
    scope_text = scope_file.read_text()
    if not scope_text.strip():
        raise ValueError("scope file is empty")

    prelim = []
    identity_unresolved = []
    evidence_invalid = []
    evidence_unavailable = []
    for row in rows:
        paper = _paper(row)
        identity_ok, identity_reasons = _identity_status(row, paper)
        evidence_ok, evidence_reasons, evidence = _evidence_status(row, paper)
        value = _annotated(row, evidence)
        if not identity_ok:
            identity_unresolved.append({**value, "not_screened": {
                "category": "identity_unresolved", "reasons": identity_reasons,
            }})
        elif not evidence_ok:
            evidence_invalid.append({**value, "not_screened": {
                "category": "evidence_invalid", "reasons": evidence_reasons,
            }})
        elif not _has_substantive_abstract(paper):
            evidence_unavailable.append({**value, "not_screened": {
                "category": "evidence_unavailable",
                "reasons": ["complete_abstract_unavailable"],
            }})
        else:
            prelim.append(value)

    # A corrected file must contain one row per work. Quarantine every member of
    # a duplicate key group rather than selecting an arbitrary manifestation.
    key_counts = Counter(str(_retrieval(row).get("work_key") or _paper(row).key())
                         for row in prelim)
    screenable = []
    for row in prelim:
        key = str(_retrieval(row).get("work_key") or _paper(row).key())
        if key_counts[key] > 1:
            identity_unresolved.append({**row, "not_screened": {
                "category": "identity_unresolved",
                "reasons": ["duplicate_canonical_work_key_in_corrected_input"],
            }})
        else:
            screenable.append(row)

    target = _targets(cap)
    selected = []
    selected_fingerprints = set()
    available = {bucket: sorted(
        (row for row in screenable if _date_bucket(row) == bucket), key=_priority)
        for bucket in DATE_BUCKETS}
    for bucket in DATE_BUCKETS:
        for row in available[bucket][:target[bucket]]:
            selected.append(row)
            selected_fingerprints.add(row["screening"]["evidence"]["title_abstract_sha256"])
    if len(selected) < min(cap, len(screenable)):
        remainder = sorted((row for row in screenable
                            if row["screening"]["evidence"]["title_abstract_sha256"]
                            not in selected_fingerprints), key=_priority)
        selected.extend(remainder[:min(cap, len(screenable)) - len(selected)])
    selected.sort(key=lambda row: (DATE_BUCKETS.index(_date_bucket(row)), _priority(row)))

    scope_copy = out_dir / "scope-v1.txt"
    with scope_copy.open("x") as handle:
        handle.write(scope_text)
    cohort_file = out_dir / "cohort-600.jsonl"
    _write_jsonl_new(cohort_file, selected)
    _write_jsonl_new(out_dir / "identity-unresolved.jsonl", identity_unresolved)
    _write_jsonl_new(out_dir / "evidence-invalid.jsonl", evidence_invalid)
    _write_jsonl_new(out_dir / "evidence-unavailable.jsonl", evidence_unavailable)

    selected_dates = Counter(_date_bucket(row) for row in selected)
    manifest = {
        "protocol": PROTOCOL,
        "created_at": _now(),
        "source": {"path": str(candidate_file), "sha256": _sha256_file(candidate_file),
                   "records": len(rows)},
        "scope": {"source_path": str(scope_file), "path": str(scope_copy),
                  "sha256": _sha256_file(scope_copy)},
        "cohort": {"path": str(cohort_file), "sha256": _sha256_file(cohort_file),
                   "requested_cap": cap, "selected": len(selected)},
        "selection": {
            "design": "date-stratified retrieval-priority cohort with complete abstracts",
            "probability_sample": False,
            "extrapolation_permitted": False,
            "warning": NON_PROBABILITY_WARNING,
            "date_targets": target,
            "date_selected": dict(selected_dates),
            "within_stratum_order": [
                "descending channel count", "descending seed-path count",
                "descending retrieval occurrences", "normalized title",
                "title-plus-full-abstract SHA-256", "source identifier",
            ],
        },
        "screening": {
            "scope_exhaustive_protocol": getattr(
                scoper, "_EXHAUSTIVE_SCOPE_PROTOCOL", "scope-exhaustive/1.4"),
            "evidence": "complete stored title and abstract; no prefix truncation",
            "cache_policy": "fresh strict cache only; broad-scope cache import forbidden",
        },
        "not_screened": {
            "identity_unresolved": len(identity_unresolved),
            "evidence_invalid": len(evidence_invalid),
            "evidence_unavailable": len(evidence_unavailable),
        },
    }
    _write_json_new(out_dir / "manifest.json", manifest)
    status = {
        "protocol": PROTOCOL, "phase": "prepared", "status": "complete",
        "candidate_records": len(rows), "screenable_records": len(screenable),
        "cohort_records": len(selected), "date_counts": dict(selected_dates),
        "identity_unresolved": len(identity_unresolved),
        "evidence_invalid": len(evidence_invalid),
        "evidence_unavailable": len(evidence_unavailable),
        "warning": NON_PROBABILITY_WARNING,
    }
    _write_json_new(out_dir / "prepare-status.json", status)
    return status


def _load_and_verify_prepared(out_dir: Path) -> tuple[dict, str, list[dict]]:
    manifest = json.loads((out_dir / "manifest.json").read_text())
    if manifest.get("protocol") != PROTOCOL:
        raise ValueError("prepared directory uses an incompatible protocol")
    scope_path = out_dir / "scope-v1.txt"
    cohort_path = out_dir / "cohort-600.jsonl"
    if _sha256_file(scope_path) != manifest["scope"]["sha256"]:
        raise ValueError("frozen scope fingerprint changed")
    if _sha256_file(cohort_path) != manifest["cohort"]["sha256"]:
        raise ValueError("frozen cohort fingerprint changed")
    rows = _read_jsonl(cohort_path)
    for row in rows:
        paper = _paper(row)
        if not (paper.abstract or "").strip():
            raise ValueError(
                f"frozen screening cohort contains no complete abstract for {paper.id}"
            )
        expected = _evidence_fingerprint(paper)
        recorded = row.get("screening", {}).get("evidence", {}).get(
            "title_abstract_sha256")
        if expected != recorded:
            raise ValueError(f"cohort evidence fingerprint changed for {paper.id}")
    return manifest, scope_path.read_text(), rows


def _screen_config(out_dir: Path, scope_text: str, rows: list[dict], *,
                   model: str) -> dict:
    path = out_dir / "screen-config.json"
    backend = llm.backend()
    value = {
        "protocol": PROTOCOL,
        "scope_exhaustive_protocol": getattr(
            scoper, "_EXHAUSTIVE_SCOPE_PROTOCOL", "scope-exhaustive/1.4"),
        "model": model, "backend": backend,
        "scope_sha256": _sha256_bytes(scope_text.encode()),
        "cohort_evidence_sha256": sorted(
            row["screening"]["evidence"]["title_abstract_sha256"] for row in rows),
        "strict_cache": STRICT_CACHE,
        "broad_cache_reused": False,
    }
    if path.exists():
        existing = json.loads(path.read_text())
        if existing != value:
            raise ValueError("screen configuration differs from the frozen first attempt")
        return existing
    cache = out_dir / STRICT_CACHE
    if cache.exists():
        raise ValueError("unregistered cache present; refusing possible broad-cache reuse")
    _write_json_new(path, value)
    return value


def _validate_cache(out_dir: Path, config_value: dict, scope_text: str,
                    rows: list[dict]) -> None:
    path = out_dir / STRICT_CACHE
    if not path.exists():
        return
    expected = {
        scoper.exhaustive_scope_fingerprint(
            scope_text, _paper(row), model=config_value["model"],
            backend=config_value["backend"])
        for row in rows
    }
    protocol = config_value["scope_exhaustive_protocol"]
    for line_number, row in enumerate(_read_jsonl(path), 1):
        if row.get("protocol") != protocol:
            raise ValueError(f"incompatible cache protocol at line {line_number}")
        if row.get("model") != config_value["model"] or \
                row.get("backend") != config_value["backend"]:
            raise ValueError(f"incompatible cache model/backend at line {line_number}")
        if row.get("fingerprint") not in expected:
            raise ValueError(f"cache record not in frozen cohort at line {line_number}")


def _next_attempt_dir(out_dir: Path) -> Path:
    root = out_dir / "screen-attempts"
    root.mkdir(exist_ok=True)
    existing = [int(path.name) for path in root.iterdir()
                if path.is_dir() and path.name.isdigit()]
    path = root / f"{(max(existing, default=0) + 1):04d}"
    path.mkdir()
    return path


def _existing_complete_attempt(out_dir: Path) -> Path | None:
    root = out_dir / "screen-attempts"
    if not root.exists():
        return None
    for path in sorted(root.iterdir()):
        status = path / "status.json"
        if status.exists() and json.loads(status.read_text()).get("status") == "complete":
            return path
    return None


def _yield_summary(rows: list[dict]) -> dict:
    role_counts = Counter()
    date_role: dict[str, Counter] = defaultdict(Counter)
    channel: dict[str, Counter] = defaultdict(Counter)
    signatures = Counter()
    for row in rows:
        role = row["decision"]["role"]
        role_counts[role] += 1
        bucket = row["screening"]["date_bucket"]
        date_role[bucket][role] += 1
        channels = tuple(sorted(set(_retrieval(row).get("channels") or [])))
        signatures[" + ".join(channels) if channels else "[no channel]"] += 1
        for name in channels:
            channel[name]["screened_any"] += 1
            channel[name][f"{role}_any"] += 1
            if len(channels) == 1:
                channel[name]["screened_unique_to_channel"] += 1
                channel[name][f"{role}_unique_to_channel"] += 1
    return {
        "warning": NON_PROBABILITY_WARNING,
        "role_counts": dict(role_counts),
        "date_by_role": {bucket: dict(date_role[bucket]) for bucket in DATE_BUCKETS},
        "channel_counts": {name: dict(values) for name, values in sorted(channel.items())},
        "channel_signatures": dict(sorted(signatures.items())),
        "channel_count_note": (
            "*_any counts are non-additive because multi-channel records appear in every "
            "contributing channel; *_unique_to_channel counts are mutually exclusive."
        ),
    }


def screen(out_dir: Path, *, model: str | None = None, batch: int = 6,
           max_records: int | None = None, progress=print) -> dict:
    """Run or resume strict screening, writing a new immutable attempt snapshot."""
    if batch <= 0:
        raise ValueError("batch must be positive")
    if max_records is not None and max_records <= 0:
        raise ValueError("max_records must be positive")
    complete = _existing_complete_attempt(out_dir)
    if complete:
        raise FileExistsError(f"screening is already complete; refusing overwrite: {complete}")
    _manifest, scope_text, cohort = _load_and_verify_prepared(out_dir)
    selected_model = model or config.READER_MODEL
    config_value = _screen_config(out_dir, scope_text, cohort, model=selected_model)
    _validate_cache(out_dir, config_value, scope_text, cohort)

    ordered_cohort = _screening_order(cohort)
    active_n = min(max_records or len(cohort), len(cohort))
    active_cohort = ordered_cohort[:active_n]
    missing_evidence = [row for row in active_cohort
                        if not _has_substantive_abstract(_paper(row))]
    screenable_cohort = [row for row in active_cohort
                         if _has_substantive_abstract(_paper(row))]
    papers = [_paper(row) for row in screenable_cohort]
    roles = scoper.scope_exhaustive(
        scope_text, papers, model=selected_model, batch=batch,
        cache_path=out_dir / STRICT_CACHE, progress=progress,
    )
    _validate_cache(out_dir, config_value, scope_text, cohort)

    cohort_by_evidence = {
        row["screening"]["evidence"]["title_abstract_sha256"]: row for row in cohort
    }
    results = {role: [] for role in getattr(
        scoper, "_EXHAUSTIVE_ROLES", ("eligible", "retrieval_only", "uncertain", "excluded"))}
    for row in missing_evidence:
        paper = _paper(row)
        evidence = _evidence_fingerprint(paper)
        results["uncertain"].append({**row, "decision": {
            "fingerprint": scoper.exhaustive_scope_fingerprint(
                scope_text, paper, model=config_value["model"],
                backend=config_value["backend"]),
            "protocol": config_value["scope_exhaustive_protocol"],
            "work_key": paper.key(), "model": config_value["model"],
            "backend": config_value["backend"], "cacheable": False,
            "evidence_sha256": evidence, "role": "uncertain",
            "criterion": "insufficient evidence", "evidence": "",
            "reason": "complete abstract unavailable after source reconciliation",
            "publication_role": "unclear", "has_original_contribution": False,
            "missing_evidence": True,
        }})
    seen = set()
    invalid = []
    for role, items in roles.items():
        for paper, decision in items:
            evidence = _evidence_fingerprint(paper)
            row = cohort_by_evidence.get(evidence)
            problems = []
            if row is None:
                problems.append("decision_not_in_frozen_cohort")
            if evidence in seen:
                problems.append("duplicate_screening_decision")
            if decision.get("evidence_sha256") != evidence:
                problems.append("decision_evidence_fingerprint_mismatch")
            if problems:
                invalid.append({"paper": paper.to_dict(), "decision": decision,
                                "problems": problems})
                continue
            seen.add(evidence)
            value = {**row, "decision": decision}
            results[role].append(value)

    pending = []
    active_evidence = {
        row["screening"]["evidence"]["title_abstract_sha256"]
        for row in active_cohort
    }
    for evidence, row in cohort_by_evidence.items():
        matching = next((value for values in results.values() for value in values
                         if value["screening"]["evidence"]["title_abstract_sha256"] == evidence),
                        None)
        if matching is None:
            reason = ("no_valid_screening_decision" if evidence in active_evidence
                      else "deferred_by_priority_wave")
            pending.append({**row, "pending": {"reason": reason}})
        elif matching["decision"].get("adjudication_required"):
            pending.append({**row, "pending": {"reason": "adjudication_required"}})

    terminal = [row for values in results.values() for row in values
                if not row["decision"].get("adjudication_required")]
    attempt = _next_attempt_dir(out_dir)
    for role, values in results.items():
        _write_jsonl_new(attempt / f"{role}.jsonl", values)
    _write_jsonl_new(attempt / "pending.jsonl", pending)
    _write_jsonl_new(attempt / "invalid-decisions.jsonl", invalid)
    summary = _yield_summary(terminal)
    _write_json_new(attempt / "cohort-yields.json", summary)
    is_complete = active_n == len(cohort) and len(terminal) == len(cohort) \
        and not pending and not invalid
    status = {
        "protocol": PROTOCOL, "finished_at": _now(),
        "status": "complete" if is_complete else "incomplete",
        "cohort_records": len(cohort), "priority_prefix_records": active_n,
        "llm_screened_records": len(screenable_cohort),
        "deferred_by_priority_wave": len(cohort) - active_n,
        "priority_order": "interleaved 100-record waves: 50 after, 42 on/before, 8 uncertain",
        "missing_abstract_uncertain": len(missing_evidence),
        "terminal_decisions": len(terminal),
        "pending_records": len(pending), "invalid_decisions": len(invalid),
        "roles": {role: len(values) for role, values in results.items()},
        "model": config_value["model"], "backend": config_value["backend"],
        "batch": batch, "scope_sha256": config_value["scope_sha256"],
        "cache_sha256": _sha256_file(out_dir / STRICT_CACHE)
        if (out_dir / STRICT_CACHE).exists() else None,
        "broad_cache_reused": False,
        "warning": NON_PROBABILITY_WARNING,
    }
    _write_json_new(attempt / "status.json", status)
    return {**status, "attempt_dir": str(attempt)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="freeze a new immutable 600-record cohort")
    prep.add_argument("--candidates", required=True, type=Path)
    prep.add_argument("--scope", required=True, type=Path,
                      help="frozen strict operational scope-v1.txt")
    prep.add_argument("--out-dir", required=True, type=Path)
    prep.add_argument("--cap", type=int, default=DEFAULT_CAP)
    run = sub.add_parser("screen", help="run/resume the strict four-way screen")
    run.add_argument("--out-dir", required=True, type=Path)
    run.add_argument("--model")
    run.add_argument("--batch", type=int, default=6)
    run.add_argument("--max-records", type=int,
                     help="screen only this priority prefix; increase to resume in waves")
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.candidates, args.scope, args.out_dir, cap=args.cap)
    else:
        result = screen(args.out_dir, model=args.model, batch=args.batch,
                        max_records=args.max_records)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
