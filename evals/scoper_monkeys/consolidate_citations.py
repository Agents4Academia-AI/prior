"""Deterministically consolidate traced citation results into a screening queue."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior.models import Paper  # noqa: E402
from adaptive_expansion import _read_role, _receipt, _write_jsonl  # noqa: E402


def _events(path: Path):
    for line in path.read_text().splitlines() if path.exists() else []:
        try:
            yield json.loads(line)
        except ValueError:
            continue


def consolidate(screen_dir: Path, out_dir: Path) -> dict:
    known = {}
    for role in ("eligible", "retrieval_only", "uncertain"):
        for paper, _ in _read_role(screen_dir / f"{role}.jsonl"):
            known[paper.key()] = role

    provenance = defaultdict(lambda: {"channels": set(), "seed_work_keys": set()})
    papers = {}
    back_edges = defaultdict(set)
    for row in _events(out_dir / "citation-backward-edges.jsonl"):
        if row.get("resolved"):
            back_edges[row["cited_id"]].add(row["seed_work_key"])
    for row in _events(out_dir / "citation-backward-candidates.jsonl"):
        paper = Paper.from_dict(row["paper"])
        key = paper.key()
        papers[key] = paper
        provenance[key]["channels"].add("backward")
        provenance[key]["seed_work_keys"].update(back_edges.get(paper.id, ()))
    for row in _events(out_dir / "citation-forward-ledger.jsonl"):
        if row.get("event") != "result":
            continue
        paper = Paper.from_dict(row["paper"])
        key = paper.key()
        current = papers.get(key)
        if current is None or len(paper.abstract or "") > len(current.abstract or ""):
            papers[key] = paper
        provenance[key]["channels"].add("forward")
        provenance[key]["seed_work_keys"].add(row["seed_work_key"])

    new_rows, rediscovered_rows = [], []
    for key in sorted(papers):
        paper = papers[key]
        prov = provenance[key]
        row = {"paper": paper.to_dict(), "work_key": key,
               "channels": sorted(prov["channels"]),
               "seed_work_keys": sorted(prov["seed_work_keys"]),
               "seed_count": len(prov["seed_work_keys"])}
        (rediscovered_rows if key in known else new_rows).append(row)
    new_file = out_dir / "citation-new-candidates.jsonl"
    rediscovered_file = out_dir / "citation-rediscovered-useful.jsonl"
    _write_jsonl(new_file, new_rows)
    _write_jsonl(rediscovered_file, rediscovered_rows)
    status_file = out_dir / "citation-consolidation-status.json"
    status = {"citation_canonical_works": len(papers),
              "new_candidate_works": len(new_rows),
              "rediscovered_useful_works": len(rediscovered_rows),
              "both_directions": sum(len(row["channels"]) == 2 for row in new_rows),
              "forward_source_status": json.loads(
                  (out_dir / "citation-forward-status.json").read_text()).get("stage_status"),
              "screening_status": "not_screened",
              "gold_visible": False}
    status_file.write_text(json.dumps(status, indent=2) + "\n")
    _receipt(out_dir, "consolidate_citations",
             [screen_dir / f"{r}.jsonl" for r in ("eligible", "retrieval_only", "uncertain")] +
             [out_dir / "citation-backward-candidates.jsonl",
              out_dir / "citation-backward-edges.jsonl",
              out_dir / "citation-forward-ledger.jsonl"],
             [new_file, rediscovered_file, status_file], deterministic=True)
    return status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen-dir", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    print(json.dumps(consolidate(args.screen_dir, args.out_dir), indent=2))


if __name__ == "__main__":
    main()
