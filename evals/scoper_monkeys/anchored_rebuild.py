"""Rebuild a corrected anchored-expansion snapshot from immutable ledgers."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchored_identity import resolve_occurrences  # noqa: E402
from prior.models import Paper  # noqa: E402


BOUNDARY = date(2026, 6, 24)
PROTOCOL = "prior.anchored-expansion-rebuild/1.0"


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows) -> None:
    with path.open("x") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, value: dict) -> None:
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False); handle.write("\n")


def _version() -> str:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, check=True,
            capture_output=True, text=True).stdout.strip()
        return revision + ("+dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _occurrence(*, occurrence_id: str, paper: dict, channel: str,
                seed_work_key: str = "", rank=None, provenance=None) -> dict:
    return {
        "occurrence_id": occurrence_id, "paper": paper, "channel": channel,
        "seed_work_key": seed_work_key, "rank": rank,
        "provenance": provenance or {},
    }


def load_occurrences(source_dir: Path, seed_snapshot: Path,
                     retry_ledger: Path | None = None) -> tuple[list[dict], list[dict], dict]:
    """Normalize every saved result occurrence without reading hidden targets."""
    occurrences, source_unresolved = [], []
    seeds = _rows(seed_snapshot)
    for index, row in enumerate(seeds, 1):
        paper = row.get("paper", row)
        occurrences.append(_occurrence(
            occurrence_id=f"seed:{index:04d}:{paper.get('id')}", paper=paper,
            channel="seed", seed_work_key=Paper.from_dict(paper).key(),
            provenance={"file": str(seed_snapshot), "line": index}))

    backward_candidates_path = source_dir / "citation-backward-candidates.jsonl"
    backward_edges_path = source_dir / "citation-backward-edges.jsonl"
    backward_candidates = {
        row["paper"]["id"]: row["paper"] for row in _rows(backward_candidates_path)
    }
    used_backward = set()
    for line, edge in enumerate(_rows(backward_edges_path), 1):
        paper = backward_candidates.get(edge.get("cited_id"))
        if not paper:
            source_unresolved.append({
                "stage": "openalex_backward", "reason": "citation_identifier_unresolved",
                "edge": edge, "provenance": {"file": str(backward_edges_path), "line": line},
            })
            continue
        used_backward.add(edge["cited_id"])
        occurrences.append(_occurrence(
            occurrence_id=f"oa-back:{line:06d}", paper=paper,
            channel="openalex_backward", seed_work_key=edge.get("seed_work_key", ""),
            provenance={"file": str(backward_edges_path), "line": line,
                        "cited_id": edge.get("cited_id")}))
    for index, (paper_id, paper) in enumerate(sorted(backward_candidates.items()), 1):
        if paper_id not in used_backward:
            occurrences.append(_occurrence(
                occurrence_id=f"oa-back-unlinked:{index:06d}", paper=paper,
                channel="openalex_backward", provenance={
                    "file": str(backward_candidates_path),
                    "reason": "candidate_without_resolved_edge"}))

    forward_path = source_dir / "citation-forward-ledger.jsonl"
    for line, row in enumerate(_rows(forward_path), 1):
        if row.get("event") != "result" or not row.get("paper"):
            continue
        occurrences.append(_occurrence(
            occurrence_id=f"oa-forward:{line:06d}", paper=row["paper"],
            channel="openalex_forward", seed_work_key=row.get("seed_work_key", ""),
            rank=row.get("page_rank"), provenance={"file": str(forward_path), "line": line,
                                                   "task_id": row.get("task_id")}))

    s2_paths = [source_dir / "s2-expansion-ledger.jsonl"]
    if retry_ledger and retry_ledger.exists():
        s2_paths.append(retry_ledger)
    for path_index, path in enumerate(s2_paths):
        prefix = "s2-base" if path_index == 0 else "s2-retry"
        for line, row in enumerate(_rows(path), 1):
            if row.get("event") != "result" or not row.get("paper"):
                continue
            direction = row.get("direction")
            occurrences.append(_occurrence(
                occurrence_id=f"{prefix}:{line:07d}", paper=row["paper"],
                channel=f"s2_{direction}", seed_work_key=row.get("seed_work_key", ""),
                rank=row.get("rank"), provenance={
                    "file": str(path), "line": line,
                    "identifier": row.get("identifier") or row.get("s2_identifier"),
                    "identifier_basis": row.get("identifier_basis"),
                }))
    inputs = [seed_snapshot, backward_candidates_path, backward_edges_path,
              forward_path, source_dir / "s2-expansion-ledger.jsonl"]
    if retry_ledger and retry_ledger.exists():
        inputs.append(retry_ledger)
    return occurrences, source_unresolved, {
        "inputs": [{"path": str(path), "sha256": _sha(path)} for path in inputs],
        "seed_records": len(seeds), "raw_result_occurrences": len(occurrences) - len(seeds),
    }


def _date_bucket(paper: Paper) -> str:
    raw, precision = str(paper.date or ""), str(paper.date_precision or "")
    year = paper.year
    try:
        if precision == "day" and len(raw) >= 10:
            return "after_snapshot" if date.fromisoformat(raw[:10]) > BOUNDARY \
                else "on_or_before_snapshot"
        if precision == "month" and len(raw) >= 7:
            month = raw[:7]
            return ("on_or_before_snapshot" if month < BOUNDARY.isoformat()[:7]
                    else "after_snapshot" if month > BOUNDARY.isoformat()[:7]
                    else "date_uncertain")
        value = int(raw[:4]) if len(raw) >= 4 and raw[:4].isdigit() else int(year or 0)
        if value:
            return ("on_or_before_snapshot" if value < BOUNDARY.year
                    else "after_snapshot" if value > BOUNDARY.year
                    else "date_uncertain")
    except (ValueError, TypeError):
        pass
    return "date_uncertain"


def rebuild(source_dir: Path, seed_snapshot: Path, out_dir: Path,
            *, retry_ledger: Path | None = None) -> dict:
    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output directory: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    occurrences, source_unresolved, receipt = load_occurrences(
        source_dir, seed_snapshot, retry_ledger)
    resolution = resolve_occurrences(occurrences)

    groups, candidates, novel, conflicts = [], [], [], []
    rediscovered_seed_keys = set()
    per_channel_occurrences = Counter()
    per_channel_groups: dict[str, set[str]] = defaultdict(set)
    for group in resolution.groups:
        all_channels = set(group["channels"])
        retrieval_channels = sorted(all_channels - {"seed"})
        if not retrieval_channels:
            continue
        seen_in_seed = "seed" in all_channels
        if seen_in_seed:
            rediscovered_seed_keys.add(group["work_key"])
        retrieval_occurrences = [row for row in group["occurrences"]
                                 if row.get("channel") != "seed"]
        paper = Paper.from_dict(group["paper"])
        bucket = _date_bucket(paper)
        evidence_hash = "sha256:" + hashlib.sha256(
            (paper.title + "\n" + (paper.abstract or "")).encode()).hexdigest()
        row = {
            "work_key": group["work_key"], "identity_status": group["identity_status"],
            "paper": group["paper"], "identity_keys": group["identity_keys"],
            "match_bases": group["match_bases"], "channels": retrieval_channels,
            "seed_work_keys": sorted({value.get("seed_work_key") for value in retrieval_occurrences
                                      if value.get("seed_work_key")}),
            "seed_path_count": len({value.get("seed_work_key") for value in retrieval_occurrences
                                    if value.get("seed_work_key")}),
            "retrieval_occurrences": len(retrieval_occurrences),
            "seen_in_seed": seen_in_seed, "date_bucket": bucket,
            "screening_evidence": {
                "abstract_chars": len(paper.abstract or ""),
                "title_abstract_sha256": evidence_hash, "truncated": False,
            },
        }
        groups.append(group); candidates.append(row)
        for value in retrieval_occurrences:
            per_channel_occurrences[value["channel"]] += 1
            per_channel_groups[value["channel"]].add(group["work_key"])
        if not seen_in_seed:
            novel.append(row)
            if "conflict" in group["identity_status"]:
                conflicts.append(row)

    order = lambda row: (row["seen_in_seed"], -len(row["channels"]),
                         -row["seed_path_count"], -row["retrieval_occurrences"],
                         row["paper"]["title"].casefold(), row["work_key"])
    candidates.sort(key=order); novel.sort(key=order); conflicts.sort(key=order)
    novel_screenable = [row for row in novel if "conflict" not in row["identity_status"]]
    _write_jsonl(out_dir / "work-groups.jsonl", groups)
    _write_jsonl(out_dir / "candidate-snapshot.jsonl", candidates)
    _write_jsonl(out_dir / "novel-candidates.jsonl", novel)
    _write_jsonl(out_dir / "novel-screenable.jsonl", novel_screenable)
    _write_jsonl(out_dir / "identity-conflicts.jsonl", conflicts)
    _write_jsonl(out_dir / "identity-unresolved-occurrences.jsonl", resolution.unresolved)
    _write_jsonl(out_dir / "identity-audit.jsonl", resolution.audit)
    _write_jsonl(out_dir / "source-unresolved.jsonl", source_unresolved)

    status = {
        "protocol": PROTOCOL, "created_at": datetime.now(timezone.utc).isoformat(),
        "hidden_targets_joined": False, "code_version": _version(),
        "seed_records": receipt["seed_records"],
        "raw_result_occurrences": receipt["raw_result_occurrences"],
        "resolved_retrieval_groups": len(candidates), "novel_vs_seed": len(novel),
        "novel_screenable": len(novel_screenable), "identity_conflict_groups": len(conflicts),
        "identity_unresolved_occurrences": len(resolution.unresolved),
        "source_unresolved_edges": len(source_unresolved),
        "seed_rediscovered": len(rediscovered_seed_keys),
        "seed_not_rediscovered": receipt["seed_records"] - len(rediscovered_seed_keys),
        "date_buckets_novel_screenable": {
            bucket: sum(row["date_bucket"] == bucket for row in novel_screenable)
            for bucket in ("on_or_before_snapshot", "after_snapshot", "date_uncertain")},
        "missing_abstract_novel_screenable": sum(not row["paper"].get("abstract")
                                                  for row in novel_screenable),
        "multi_channel_novel_screenable": sum(len(row["channels"]) > 1
                                                for row in novel_screenable),
        "retrieval_occurrences_by_channel": dict(sorted(per_channel_occurrences.items())),
        "resolved_groups_by_channel": {
            channel: len(values) for channel, values in sorted(per_channel_groups.items())},
        "accounting_invariant": (
            sum(group["occurrence_count"] for group in resolution.groups)
            + len(resolution.unresolved) == len(occurrences)),
    }
    _write_json(out_dir / "status.json", status)
    protocol = {
        "experiment": "152-seeded living-evidence expansion",
        "claim_boundary": "bounded one-hop anchored expansion; not exhaustive recall",
        "seed_snapshot_immutable": True, "seed_n": receipt["seed_records"],
        "snapshot_boundary": BOUNDARY.isoformat(),
        "date_policy": "reporting partition only; no retrieval or eligibility cutoff",
        "channels": ["openalex_backward", "openalex_forward", "s2_backward",
                     "s2_forward", "s2_recommendation"],
        "identity_policy": "valid source IDs/DOI/arXiv plus conservative title proposals; unresolved and metadata-conflict records quarantined",
        "screening_policy": "full title and abstract; strict operational scope applied only after this freeze",
        "raw_api_replay": False,
        "trace_policy": "normalized result, source, seed, direction and rank traces retained",
        **receipt,
    }
    _write_json(out_dir / "protocol.json", protocol)
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--seed-snapshot", required=True, type=Path)
    parser.add_argument("--retry-ledger", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    result = rebuild(args.source_dir, args.seed_snapshot, args.out_dir,
                     retry_ledger=args.retry_ledger)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
