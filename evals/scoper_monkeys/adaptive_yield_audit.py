"""Audit eligible yield and frozen-target recovery from adaptive CPU search."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from freeze_external_targets import aliases


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eligible", type=Path, required=True)
    ap.add_argument("--retrieval", type=Path, required=True)
    ap.add_argument("--query-map", type=Path, required=True)
    ap.add_argument("--adaptive-recovery", type=Path, required=True)
    ap.add_argument("--previous-recovery", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    eligible = rows(args.eligible)
    groups = rows(args.retrieval)
    branches = rows(args.query_map)
    query_metadata = []
    for branch in branches:
        for query in branch["queries"]:
            query_metadata.append({"branch_id": branch["branch_id"], "query": query})

    alias_index = {}
    for group in groups:
        for alias in group["aliases"]:
            alias_index.setdefault(alias, group)

    query_yield, query_best, branch_yield = Counter(), Counter(), Counter()
    source_occurrences = Counter()
    unmatched = []
    for decision in eligible:
        paper = decision["paper"]
        group = next((alias_index[a] for a in aliases(paper) if a in alias_index), None)
        if group is None:
            unmatched.append(paper.get("id") or paper.get("title"))
            continue
        query_ids = {hit["query_index"] for hit in group["hits"]}
        branch_ids = {query_metadata[index - 1]["branch_id"] for index in query_ids}
        for index in query_ids:
            query_yield[index] += 1
        for branch_id in branch_ids:
            branch_yield[branch_id] += 1
        for hit in group["hits"]:
            source_occurrences[hit["source"]] += 1
        best = min(group["hits"], key=lambda hit: hit["rank"])
        query_best[best["query_index"]] += 1

    adaptive = json.loads(args.adaptive_recovery.read_text())
    adaptive_ids = {row["gold_id"] for row in adaptive["targets"] if row["recovered"]}
    previous = rows(args.previous_recovery)
    previous_ids = {row["target_id"] for row in previous if row.get("recovered")}
    gold_n = adaptive["gold_n"]

    report = {
        "eligible_candidates": len(eligible),
        "retrieved_novel_pre_cutoff_candidates": len(groups),
        "eligible_rate": len(eligible) / max(1, len(groups)),
        "matched_to_retrieval_trace": len(eligible) - len(unmatched),
        "unmatched": unmatched,
        "source_hit_occurrences_for_eligible": dict(source_occurrences),
        "branch_yield": [
            {"branch_id": branch_id, "eligible": count}
            for branch_id, count in branch_yield.most_common()
        ],
        "query_yield": [
            {
                "query_index": index,
                **query_metadata[index - 1],
                "eligible_any_hit": count,
                "eligible_best_rank_hit": query_best[index],
            }
            for index, count in query_yield.most_common()
        ],
        "frozen_hidden_targets": {
            "targets": gold_n,
            "previously_recovered": len(previous_ids),
            "adaptive_recovered": len(adaptive_ids),
            "adaptive_overlap_previous": len(adaptive_ids & previous_ids),
            "adaptive_unique_additions": len(adaptive_ids - previous_ids),
            "adaptive_unique_target_ids": sorted(adaptive_ids - previous_ids),
            "cumulative_recovered": len(adaptive_ids | previous_ids),
            "cumulative_recovery": len(adaptive_ids | previous_ids) / max(1, gold_n),
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
