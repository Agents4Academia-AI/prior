"""Repair failed Semantic Scholar branches in a frozen anchored expansion.

The historical expansion ledger is an immutable input.  ``plan`` derives work
only from each branch's *latest HTTP request outcome* and freezes safe fallback
identifiers.  ``run`` appends results to a separate, hash-pinned retry ledger.
It never calls a branch that completed successfully in the base ledger.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior.models import Paper  # noqa: E402
from prior.sources import semanticscholar  # noqa: E402


PROTOCOL = "prior.s2-anchored-retry/1.0"
ANCHORED_PROTOCOL = "prior.anchored-expansion/1.1"
REPORTING_BOUNDARY = "2026-06-24"
S2_ID = re.compile(r"^s2:([0-9a-f]{40})$", re.I)
S2_RAW_ID = re.compile(r"^[0-9a-f]{40}$", re.I)
S2_URL_ID = re.compile(
    r"semanticscholar\.org/paper/(?:[^/?#]+/)?([0-9a-f]{40})(?:$|[/?#])", re.I
)
ARXIV_ID = re.compile(r"^arxiv:(\d{4}\.\d{4,5})(?:v\d+)?$", re.I)
ARXIV_API_ID = re.compile(r"^ARXIV:(\d{4}\.\d{4,5})$", re.I)
DOI_ID = re.compile(r"^10\.\d{4,9}/\S+$", re.I)
DIRECTION_ORDER = ("backward", "forward", "recommendation")
DIRECTIONS = {"backward": 60, "forward": 60, "recommendation": 10}
TERMINAL_RETRY_STATES = {"complete", "identifiers_exhausted", "source_unavailable"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSONL at {path}:{number}: {error}") from error
        if not isinstance(value, dict):
            raise ValueError(f"expected object at {path}:{number}")
        out.append(value)
    return out


def _append(handle, row: dict) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    handle.flush()


def _branch(row: dict) -> tuple[str, str]:
    return str(row.get("seed_work_key") or ""), str(row.get("direction") or "")


def _http_status(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def base_outcomes(
    rows: list[dict],
    expected_branches: Iterable[tuple[str, str]] = (),
) -> dict[tuple[str, str], dict]:
    """Collapse the base ledger to the latest transport outcome per branch.

    A historical ``branch_terminal: complete`` is deliberately insufficient:
    the old non-strict adapter converted a final HTTP 404 into an empty list.
    Only the latest observed HTTP 200 is successful.  Expected branches with no
    request observation are retained as ``unattempted``.
    """
    state: dict[tuple[str, str], dict] = {}
    for branch in expected_branches:
        if not all(branch) or branch[1] not in DIRECTIONS:
            raise ValueError(f"invalid expected branch: {branch!r}")
        if branch in state:
            raise ValueError(f"duplicate expected branch: {branch!r}")
        state[branch] = {
            "seed_work_key": branch[0], "direction": branch[1],
            "latest_http_status": None, "terminal_status": None,
            "result_count": 0, "last_order": 0,
        }
    for order, row in enumerate(rows, 1):
        branch = _branch(row)
        if not all(branch) or branch[1] not in DIRECTIONS:
            continue
        item = state.setdefault(branch, {
            "seed_work_key": branch[0], "direction": branch[1],
            "latest_http_status": None, "terminal_status": None,
            "result_count": 0, "last_order": 0,
        })
        item["last_order"] = order
        if (row.get("event") == "adapter_observation"
                and row.get("kind") == "request_attempt"):
            item["latest_http_status"] = _http_status(row.get("status_code"))
        elif row.get("event") == "result":
            item["result_count"] += 1
        elif row.get("event") == "branch_terminal":
            item["terminal_status"] = row.get("status")
            item["seed_id"] = row.get("seed_id")
    for item in state.values():
        status = item["latest_http_status"]
        item["successful"] = status == 200
        item["state"] = (
            "successful" if status == 200 else
            "unattempted" if status is None else
            "failed_http"
        )
    return state


def _seed_records(seed_snapshot: Path) -> dict[str, tuple[Paper, list[str]]]:
    records: dict[str, tuple[Paper, list[str]]] = {}
    for row in _rows(seed_snapshot):
        payload = row.get("paper", row)
        if not isinstance(payload, dict):
            raise ValueError("seed snapshot rows require a paper object")
        paper = Paper.from_dict(payload)
        key = paper.key()
        if key in records:
            raise ValueError(f"duplicate seed work key: {key}")
        aliases = [str(value) for value in payload.get("work_aliases", [])
                   if isinstance(value, str)]
        records[key] = paper, aliases
    return records


def _normalised_doi(value: str | None) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)
    return value.rstrip(". /,;")


def _normalised_alias(value: str) -> str:
    value = str(value or "").strip()
    if match := ARXIV_ID.fullmatch(value):
        return "arxiv:" + match.group(1).lower()
    doi = _normalised_doi(value)
    if DOI_ID.fullmatch(doi):
        return "doi:" + doi
    if match := S2_ID.fullmatch(value):
        return "s2:" + match.group(1).lower()
    return ""


def _strong_aliases(paper: Paper, serialized_aliases: Iterable[str] = ()) -> set[str]:
    aliases = {_normalised_alias(alias) for alias in paper.identity_aliases()}
    aliases.update(_normalised_alias(alias) for alias in serialized_aliases)
    for item in paper.all_manifestations():
        aliases.add(_normalised_alias(str(item.get("id") or "")))
        doi = _normalised_doi(item.get("doi"))
        if DOI_ID.fullmatch(doi):
            aliases.add("doi:" + doi)
    return {alias for alias in aliases if alias}


def _safe_same_work(seed: Paper, candidate: Paper,
                    serialized_aliases: Iterable[str] = ()) -> tuple[bool, str]:
    shared = _strong_aliases(seed, serialized_aliases) & _strong_aliases(candidate)
    if shared:
        return True, "shared_strong_alias:" + sorted(shared)[0]
    # This fallback is intentionally much stricter than title-only matching.
    # It supports locally observed crosswalks whose returned S2 record omitted
    # externalIds, while requiring author and chronology corroboration.
    left = {name.split()[-1].casefold() for name in seed.authors if name.split()}
    right = {name.split()[-1].casefold() for name in candidate.authors if name.split()}
    if seed.key() == candidate.key() and left and right and left & right and (
            not seed.year or not candidate.year or abs(seed.year - candidate.year) <= 2):
        return True, "exact_title_author_year"
    return False, ""


def _s2_hashes(paper: Paper) -> list[str]:
    found = set()
    for item in paper.all_manifestations():
        raw_id = str(item.get("id") or "").strip()
        if match := S2_ID.fullmatch(raw_id):
            found.add(match.group(1).lower())
        for field in ("url", "pdf_url"):
            if match := S2_URL_ID.search(str(item.get(field) or "")):
                found.add(match.group(1).lower())
    return sorted(found)


def _identifier_candidates(
    seed: Paper,
    base_rows: list[dict],
    serialized_aliases: Iterable[str] = (),
) -> list[dict]:
    """Return validated identifiers ordered S2 hash, arXiv, then DOI.

    S2 hashes are accepted only from the seed itself or from a locally stored
    result conservatively matched to the seed.  Values such as ``s2:None`` can
    never pass the 40-hex validation.
    """
    candidates: list[dict] = []
    seen: set[str] = set()

    def add(identifier: str, basis: str) -> None:
        normalized = identifier.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            candidates.append({"identifier": normalized, "basis": basis})

    # A locally observed S2 id is the most precise crosswalk and costs no
    # discovery/search request.  Never match it on title alone.
    local = []
    for row in base_rows:
        if row.get("event") != "result" or not isinstance(row.get("paper"), dict):
            continue
        paper = Paper.from_dict(row["paper"])
        same, basis = _safe_same_work(seed, paper, serialized_aliases)
        if same:
            local.extend((value, basis) for value in _s2_hashes(paper))
    for value, basis in sorted(set(local)):
        add(value, "local_s2_crosswalk:" + basis)

    for value in _s2_hashes(seed):
        add(value, "seed_s2_id")

    aliases = _strong_aliases(seed, serialized_aliases)
    for alias in sorted(alias for alias in aliases if alias.startswith("arxiv:")):
        match = ARXIV_ID.fullmatch(alias)
        if match:
            add("ARXIV:" + match.group(1).lower(), "seed_arxiv_alias")
    for alias in sorted(alias for alias in aliases if alias.startswith("doi:")):
        doi = _normalised_doi(alias)
        if DOI_ID.fullmatch(doi):
            add("DOI:" + doi, "seed_doi_alias")
    return candidates


def _safe_api_identifier(value: str) -> bool:
    return bool(
        S2_RAW_ID.fullmatch(value)
        or ARXIV_API_ID.fullmatch(value)
        or (value.startswith("DOI:") and DOI_ID.fullmatch(value[4:]))
    )


def prepare(seed_file: Path, out_dir: Path) -> dict:
    """Freeze the exact 152-paper anchor and its initial eligible cohort.

    The June 24 date is a reporting boundary only.  It is not applied as a
    retrieval, publication, eligibility, or screening cutoff.
    """
    source_hash = _sha(seed_file)
    supplied = _rows(seed_file)
    if len(supplied) != 152:
        raise ValueError(f"expected exactly 152 seed Paper rows, got {len(supplied)}")
    papers = []
    for number, row in enumerate(supplied, 1):
        payload = row.get("paper", row)
        if not isinstance(payload, dict):
            raise ValueError(f"seed row {number} is not a Paper object")
        papers.append(Paper.from_dict(payload))
    keys = [paper.key() for paper in papers]
    if len(set(keys)) != len(keys):
        raise ValueError("seed file contains duplicate work keys")
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite anchored output: {out_dir}")
    if _sha(seed_file) != source_hash:
        raise RuntimeError("seed file changed while validating frozen input")

    out_dir.mkdir(parents=True)
    snapshot = out_dir / "seed-snapshot.jsonl"
    with snapshot.open("x") as handle:
        for paper in papers:
            _append(handle, {"paper": paper.to_dict()})
    screen = out_dir / "seed-screen"
    screen.mkdir()
    with (screen / "eligible.jsonl").open("x") as handle:
        for paper in papers:
            _append(handle, {
                "paper": paper.to_dict(),
                "decision": {
                    "role": "eligible",
                    "criterion": "frozen supplied anchor; not re-adjudicated",
                },
            })
    for role in ("retrieval_only", "uncertain", "excluded"):
        (screen / f"{role}.jsonl").touch(exist_ok=False)
    protocol = {
        "experiment": ANCHORED_PROTOCOL,
        "seed_n": 152,
        "seed_source": str(seed_file),
        "seed_sha256": source_hash,
        "seed_snapshot_sha256": _sha(snapshot),
        "reporting_boundary": REPORTING_BOUNDARY,
        "reporting_boundary_semantics": (
            "descriptive reporting split only; not a retrieval, publication, "
            "eligibility, or screening cutoff"
        ),
        "expected_s2_branches": 152 * len(DIRECTION_ORDER),
        "s2_caps": DIRECTIONS,
        "sealed_target_policy": "no target data used during expansion",
    }
    (out_dir / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    if _sha(seed_file) != source_hash:
        raise RuntimeError("seed file changed while freezing anchored input")
    return protocol


def _initial_terminals(rows: list[dict]) -> dict[tuple[str, str], dict]:
    latest = {}
    for row in rows:
        if row.get("event") == "branch_terminal" and all(_branch(row)):
            latest[_branch(row)] = row
    return latest


def _initial_not_found(rows: list[dict]) -> set[tuple[str, str, str]]:
    return {
        (_branch(row)[0], _branch(row)[1], str(row.get("identifier") or ""))
        for row in rows
        if (row.get("event") == "identifier_terminal"
            and row.get("status") == "not_found"
            and _http_status(row.get("http_status")) == 404)
    }


def _initial_status(seed_records: dict[str, tuple[Paper, list[str]]],
                    rows: list[dict]) -> dict:
    terminals = _initial_terminals(rows)
    states = defaultdict(int)
    for work_key in seed_records:
        for direction in DIRECTION_ORDER:
            states[terminals.get((work_key, direction), {}).get("status")
                   or "pending_retry"] += 1
    return {
        "seed_n": len(seed_records),
        "branches": len(seed_records) * len(DIRECTION_ORDER),
        "caps": DIRECTIONS,
        "states": dict(sorted(states.items())),
        "invariant_holds": sum(states.values()) == len(seed_records) * 3,
    }


def s2_expand(seed_snapshot: Path, out_dir: Path, *, progress=print) -> dict:
    """Run/resume all 152 x 3 strict Semantic Scholar branches."""
    seed_hash = _sha(seed_snapshot)
    seeds = _seed_records(seed_snapshot)
    if len(seeds) != 152:
        raise ValueError(f"expected exactly 152 frozen seeds, got {len(seeds)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = out_dir / "s2-expansion-ledger.jsonl"
    if ledger.resolve() == seed_snapshot.resolve():
        raise ValueError("S2 ledger must be separate from frozen seed snapshot")
    existing = _rows(ledger)
    if existing:
        first = existing[0]
        if (first.get("event") != "manifest"
                or first.get("protocol") != ANCHORED_PROTOCOL
                or first.get("seed_snapshot_sha256") != seed_hash
                or first.get("caps") != DIRECTIONS):
            raise ValueError("existing S2 ledger does not match frozen seed protocol")
    terminals = _initial_terminals(existing)
    not_found = _initial_not_found(existing)
    calls = {
        "backward": semanticscholar.references,
        "forward": semanticscholar.citations,
        "recommendation": semanticscholar.recommendations,
    }
    expected = len(seeds) * len(DIRECTION_ORDER)

    with ledger.open("a") as handle:
        if not existing:
            _append(handle, {
                "event": "manifest", "protocol": ANCHORED_PROTOCOL,
                "seed_snapshot": str(seed_snapshot),
                "seed_snapshot_sha256": seed_hash, "seed_n": 152,
                "expected_branches": expected, "caps": DIRECTIONS,
                "recorded_at": _now(),
            })
        branch_number = 0
        for work_key, (paper, serialized_aliases) in seeds.items():
            for direction in DIRECTION_ORDER:
                branch_number += 1
                branch = (work_key, direction)
                if terminals.get(branch, {}).get("status") in TERMINAL_RETRY_STATES:
                    continue
                identifiers = _identifier_candidates(paper, existing, serialized_aliases)
                if not identifiers:
                    terminal = {
                        "event": "branch_terminal", "seed_work_key": work_key,
                        "seed_id": paper.id, "direction": direction,
                        "status": "source_unavailable", "cap": DIRECTIONS[direction],
                        "reason": "no safe S2, arXiv, or DOI identifier",
                        "recorded_at": _now(),
                    }
                    _append(handle, terminal); terminals[branch] = terminal
                    continue
                complete = transient = False
                consumed = 0
                for candidate in identifiers:
                    identifier = candidate["identifier"]
                    key = (work_key, direction, identifier)
                    if key in not_found:
                        consumed += 1
                        continue
                    final_http = None

                    def observe(event: dict) -> None:
                        nonlocal final_http
                        if event.get("kind") == "request_attempt":
                            final_http = _http_status(event.get("status_code"))
                        _append(handle, {
                            "event": "adapter_observation", "seed_work_key": work_key,
                            "direction": direction, "identifier": identifier,
                            "identifier_basis": candidate["basis"], **event,
                        })

                    try:
                        found = calls[direction](
                            identifier, max_results=DIRECTIONS[direction],
                            observe=observe, strict_errors=True)
                        if final_http != 200:
                            raise RuntimeError(
                                f"adapter returned without final HTTP 200 ({final_http})")
                        found = list(found)
                    except Exception as error:  # noqa: BLE001
                        consumed += 1
                        state = "not_found" if final_http == 404 else "pending_retry"
                        _append(handle, {
                            "event": "identifier_terminal", "seed_work_key": work_key,
                            "seed_id": paper.id, "direction": direction,
                            "identifier": identifier, "identifier_basis": candidate["basis"],
                            "status": state, "http_status": final_http,
                            "error_type": type(error).__name__,
                            "message": _error_message(error), "recorded_at": _now(),
                        })
                        if state == "not_found":
                            not_found.add(key)
                            continue
                        transient = True
                        break
                    for rank, result in enumerate(found, 1):
                        payload = result.to_dict() if isinstance(result, Paper) else result
                        if not isinstance(payload, dict):
                            raise TypeError("Semantic Scholar result must be a Paper or object")
                        _append(handle, {
                            "event": "result", "seed_work_key": work_key,
                            "seed_id": paper.id, "direction": direction,
                            "s2_identifier": identifier,
                            "identifier_basis": candidate["basis"], "rank": rank,
                            "paper": payload, "recorded_at": _now(),
                        })
                    terminal = {
                        "event": "branch_terminal", "seed_work_key": work_key,
                        "seed_id": paper.id, "direction": direction,
                        "identifier": identifier, "status": "complete",
                        "http_status": 200, "cap": DIRECTIONS[direction],
                        "returned": len(found), "recorded_at": _now(),
                    }
                    _append(handle, terminal); terminals[branch] = terminal
                    complete = True
                    break
                if not complete:
                    status = "pending_retry" if transient else "identifiers_exhausted"
                    terminal = {
                        "event": "branch_terminal", "seed_work_key": work_key,
                        "seed_id": paper.id, "direction": direction, "status": status,
                        "cap": DIRECTIONS[direction],
                        "reason": ("transient source failure" if transient else
                                   "all safe identifiers returned 404"),
                        "recorded_at": _now(),
                    }
                    _append(handle, terminal); terminals[branch] = terminal
                progress(f"S2 branches {branch_number}/{expected}")

    rows = _rows(ledger)
    status = _initial_status(seeds, rows)
    status_path = out_dir / "s2-status.json"
    status_path.write_text(json.dumps(status, indent=2) + "\n")
    if _sha(seed_snapshot) != seed_hash:
        raise RuntimeError("frozen seed snapshot changed during S2 expansion")
    return status


def _manifest_path(plan_file: Path) -> Path:
    return plan_file.with_suffix(".manifest.json")


def derive_plan(base_ledger: Path, seed_snapshot: Path, output: Path) -> dict:
    """Freeze an offline retry plan without modifying the base artifact."""
    manifest_path = _manifest_path(output)
    if output.exists() or manifest_path.exists():
        target = output if output.exists() else manifest_path
        raise FileExistsError(f"refusing to overwrite retry sidecar: {target}")
    if output.resolve() in {base_ledger.resolve(), seed_snapshot.resolve()}:
        raise ValueError("retry plan must be separate from immutable inputs")

    base_hash = _sha(base_ledger)
    seed_hash = _sha(seed_snapshot)
    base_rows = _rows(base_ledger)
    seeds = _seed_records(seed_snapshot)
    expected = [(work_key, direction) for work_key in seeds
                for direction in DIRECTION_ORDER]
    outcomes = base_outcomes(base_rows, expected)
    plan = []
    for branch in sorted(outcomes):
        outcome = outcomes[branch]
        if outcome["successful"]:
            continue
        seed, serialized_aliases = seeds[branch[0]]
        identifiers = _identifier_candidates(seed, base_rows, serialized_aliases)
        plan.append({
            "seed_work_key": branch[0], "direction": branch[1],
            "cap": DIRECTIONS[branch[1]], "base_state": outcome["state"],
            "base_latest_http_status": outcome["latest_http_status"],
            "base_result_count": outcome["result_count"],
            "seed": seed.to_dict(), "identifiers": identifiers,
        })

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as handle:
        for row in plan:
            _append(handle, row)
    plan_hash = _sha(output)
    counts = defaultdict(int)
    for outcome in outcomes.values():
        counts[outcome["state"]] += 1
    manifest = {
        "protocol": PROTOCOL, "created_at": _now(),
        "base_ledger": str(base_ledger), "base_ledger_sha256": base_hash,
        "seed_snapshot": str(seed_snapshot), "seed_snapshot_sha256": seed_hash,
        "plan": str(output), "plan_sha256": plan_hash,
        "caps": DIRECTIONS,
        "base_branches": len(outcomes),
        "base_successful": counts["successful"],
        "base_final_http_404": sum(
            row["latest_http_status"] == 404 for row in outcomes.values()),
        "base_other_http_failure": sum(
            row["state"] == "failed_http" and row["latest_http_status"] != 404
            for row in outcomes.values()),
        "base_unattempted": counts["unattempted"],
        "planned_branches": len(plan),
        "planned_with_identifier": sum(bool(row["identifiers"]) for row in plan),
        "successful_base_branches_must_not_rerun": True,
        "base_artifact_immutable": True,
    }
    with manifest_path.open("x") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    if _sha(base_ledger) != base_hash or _sha(seed_snapshot) != seed_hash:
        raise RuntimeError("immutable input changed while preparing retry plan")
    return manifest


def _validate_plan(plan_file: Path, base_ledger: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads(_manifest_path(plan_file).read_text())
    if manifest.get("protocol") != PROTOCOL:
        raise ValueError("unsupported or missing retry protocol")
    if manifest.get("base_ledger_sha256") != _sha(base_ledger):
        raise ValueError("base ledger changed after retry plan freeze")
    if manifest.get("plan_sha256") != _sha(plan_file):
        raise ValueError("retry plan changed after freeze")
    if manifest.get("caps") != DIRECTIONS:
        raise ValueError("retry plan caps do not match the frozen protocol")
    plan = _rows(plan_file)
    seen = set()
    base = base_outcomes(_rows(base_ledger))
    for row in plan:
        branch = _branch(row)
        if not all(branch) or branch[1] not in DIRECTIONS or branch in seen:
            raise ValueError(f"invalid or duplicate planned branch: {branch!r}")
        seen.add(branch)
        if base.get(branch, {}).get("successful"):
            raise ValueError(f"retry plan contains successful base branch: {branch!r}")
        if row.get("cap") != DIRECTIONS[branch[1]]:
            raise ValueError(f"incorrect cap for planned branch: {branch!r}")
        for candidate in row.get("identifiers", []):
            if not isinstance(candidate, dict) or not _safe_api_identifier(
                    str(candidate.get("identifier") or "")):
                raise ValueError(f"unsafe identifier in retry plan: {candidate!r}")
    return manifest, plan


def _retry_terminal_rows(rows: list[dict]) -> dict[tuple[str, str], dict]:
    latest = {}
    for row in rows:
        if row.get("event") == "retry_branch_terminal" and all(_branch(row)):
            latest[_branch(row)] = row
    return latest


def _stable_not_found_attempts(rows: list[dict]) -> set[tuple[str, str, str]]:
    return {
        (str(row.get("seed_work_key") or ""), str(row.get("direction") or ""),
         str(row.get("identifier") or ""))
        for row in rows
        if (row.get("event") == "retry_identifier_terminal"
            and row.get("status") == "not_found"
            and _http_status(row.get("http_status")) == 404)
    }


def _ensure_retry_manifest(handle, existing: list[dict], *, plan_file: Path,
                           base_ledger: Path, manifest: dict) -> None:
    expected = {
        "event": "retry_manifest", "protocol": PROTOCOL,
        "base_ledger_sha256": manifest["base_ledger_sha256"],
        "plan_sha256": manifest["plan_sha256"], "caps": DIRECTIONS,
    }
    if not existing:
        _append(handle, {**expected, "plan": str(plan_file),
                         "base_ledger": str(base_ledger), "recorded_at": _now()})
        return
    first = existing[0]
    for field, value in expected.items():
        if first.get(field) != value:
            raise ValueError(f"retry ledger {field} does not match frozen plan")


def _error_message(error: Exception) -> str:
    # HTTP exception strings should not contain credentials, but redact common
    # key spellings defensively before persisting the bounded diagnostic.
    message = str(error)
    message = re.sub(r"(?i)(x-api-key|api[_-]?key)=?[^\s,&]+",
                     r"\1=<redacted>", message)
    return message[:300]


def run_plan(plan_file: Path, base_ledger: Path, output_ledger: Path,
             *, progress=print) -> dict:
    """Run or resume a retry sidecar through the centralized S2 adapter."""
    if output_ledger.resolve() in {base_ledger.resolve(), plan_file.resolve(),
                                  _manifest_path(plan_file).resolve()}:
        raise ValueError("retry ledger must be separate from immutable inputs")
    manifest, plan = _validate_plan(plan_file, base_ledger)
    existing = _rows(output_ledger)
    terminals = _retry_terminal_rows(existing)
    stable_not_found = _stable_not_found_attempts(existing)
    output_ledger.parent.mkdir(parents=True, exist_ok=True)
    calls = {
        "backward": semanticscholar.references,
        "forward": semanticscholar.citations,
        "recommendation": semanticscholar.recommendations,
    }

    with output_ledger.open("a") as handle:
        _ensure_retry_manifest(handle, existing, plan_file=plan_file,
                               base_ledger=base_ledger, manifest=manifest)
        for number, row in enumerate(plan, 1):
            branch = _branch(row)
            prior_state = terminals.get(branch, {}).get("status")
            if prior_state in TERMINAL_RETRY_STATES:
                continue
            identifiers = row.get("identifiers", [])
            if not identifiers:
                _append(handle, {
                    "event": "retry_branch_terminal", "seed_work_key": branch[0],
                    "direction": branch[1], "status": "source_unavailable",
                    "reason": "no safe alternate identifier", "recorded_at": _now(),
                })
                continue

            branch_complete = False
            transient_failure = False
            attempted_or_rejected = 0
            for identifier_row in identifiers:
                identifier = str(identifier_row["identifier"])
                attempt_key = (branch[0], branch[1], identifier)
                if attempt_key in stable_not_found:
                    attempted_or_rejected += 1
                    continue

                last_http: int | None = None

                def observe(event: dict) -> None:
                    nonlocal last_http
                    if event.get("kind") == "request_attempt":
                        last_http = _http_status(event.get("status_code"))
                    _append(handle, {
                        "event": "adapter_observation", "seed_work_key": branch[0],
                        "direction": branch[1], "identifier": identifier,
                        "identifier_basis": identifier_row["basis"], **event,
                    })

                try:
                    found = calls[branch[1]](
                        identifier, max_results=row["cap"], observe=observe,
                        strict_errors=True,
                    )
                    if last_http != 200:
                        raise RuntimeError(
                            f"adapter returned without final HTTP 200 ({last_http})")
                except Exception as error:  # noqa: BLE001 - ledger must retain source state
                    attempted_or_rejected += 1
                    state = "not_found" if last_http == 404 else "pending_retry"
                    _append(handle, {
                        "event": "retry_identifier_terminal",
                        "seed_work_key": branch[0], "direction": branch[1],
                        "identifier": identifier,
                        "identifier_basis": identifier_row["basis"], "status": state,
                        "http_status": last_http, "error_type": type(error).__name__,
                        "message": _error_message(error), "recorded_at": _now(),
                    })
                    if state == "not_found":
                        stable_not_found.add(attempt_key)
                        continue
                    transient_failure = True
                    break  # preserve ordered fallbacks; retry this identifier later

                found = list(found)
                for rank, paper in enumerate(found, 1):
                    payload = paper.to_dict() if isinstance(paper, Paper) else paper
                    if not isinstance(payload, dict):
                        raise TypeError("Semantic Scholar result must be a Paper or object")
                    _append(handle, {
                        "event": "result", "seed_work_key": branch[0],
                        "direction": branch[1], "identifier": identifier,
                        "identifier_basis": identifier_row["basis"], "rank": rank,
                        "paper": payload, "recorded_at": _now(),
                    })
                _append(handle, {
                    "event": "retry_branch_terminal", "seed_work_key": branch[0],
                    "direction": branch[1], "identifier": identifier,
                    "status": "complete", "http_status": 200,
                    "returned": len(found), "recorded_at": _now(),
                })
                terminals[branch] = {"status": "complete"}
                branch_complete = True
                break

            if not branch_complete:
                if transient_failure:
                    status, reason = "pending_retry", "transient source failure"
                elif attempted_or_rejected == len(identifiers):
                    status, reason = "identifiers_exhausted", "all safe identifiers returned 404"
                else:  # defensive; all normal paths above are exhaustive
                    status, reason = "pending_retry", "retry interrupted"
                terminal = {
                    "event": "retry_branch_terminal", "seed_work_key": branch[0],
                    "direction": branch[1], "status": status, "reason": reason,
                    "recorded_at": _now(),
                }
                _append(handle, terminal)
                terminals[branch] = terminal
            progress(f"S2 retry branches {number}/{len(plan)}")

    return retry_status(base_ledger, output_ledger)


def retry_status(base_ledger: Path, retry_ledger: Path) -> dict:
    """Report base preservation and current sidecar state without network I/O."""
    base = base_outcomes(_rows(base_ledger))
    latest = _retry_terminal_rows(_rows(retry_ledger))
    states = defaultdict(int)
    base_states = defaultdict(int)
    for branch, outcome in base.items():
        base_states[outcome["state"]] += 1
        if outcome["successful"]:
            states["base_complete"] += 1
            continue
        retry_state = latest.get(branch, {}).get("status")
        if retry_state == "complete":
            states["retry_complete"] += 1
        elif retry_state in {"identifiers_exhausted", "source_unavailable"}:
            states[retry_state] += 1
        else:
            states["pending_retry"] += 1
    complete = states["base_complete"] + states["retry_complete"]
    return {
        "branches": len(base),
        "base_states": dict(sorted(base_states.items())),
        "states": dict(sorted(states.items())),
        "complete": complete,
        "open": len(base) - complete,
        "invariant_holds": sum(states.values()) == len(base),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_cmd = sub.add_parser("prepare")
    prepare_cmd.add_argument("--seed-file", required=True, type=Path)
    prepare_cmd.add_argument("--out-dir", required=True, type=Path)
    expand_cmd = sub.add_parser("s2-expand")
    expand_cmd.add_argument("--seed-snapshot", required=True, type=Path)
    expand_cmd.add_argument("--out-dir", required=True, type=Path)
    plan = sub.add_parser("plan")
    plan.add_argument("--base-ledger", required=True, type=Path)
    plan.add_argument("--seed-snapshot", required=True, type=Path)
    plan.add_argument("--output", required=True, type=Path)
    run = sub.add_parser("run")
    run.add_argument("--plan", required=True, type=Path)
    run.add_argument("--base-ledger", required=True, type=Path)
    run.add_argument("--output-ledger", required=True, type=Path)
    status = sub.add_parser("status")
    status.add_argument("--base-ledger", required=True, type=Path)
    status.add_argument("--retry-ledger", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.seed_file, args.out_dir)
    elif args.command == "s2-expand":
        result = s2_expand(args.seed_snapshot, args.out_dir)
    elif args.command == "plan":
        result = derive_plan(args.base_ledger, args.seed_snapshot, args.output)
    elif args.command == "run":
        result = run_plan(args.plan, args.base_ledger, args.output_ledger)
    else:
        result = retry_status(args.base_ledger, args.retry_ledger)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
