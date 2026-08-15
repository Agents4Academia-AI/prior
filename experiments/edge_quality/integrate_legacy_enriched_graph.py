#!/usr/bin/env python3
"""Integrate corrected citation evidence into the fixed legacy edge universe."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "prior-core-v0.2"
OUT = Path(__file__).parent / "out"
HARD = {"supports", "builds_on", "refines", "contradicts"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def graph(nodes: set[str], edges: list[tuple[str, str]]) -> nx.Graph:
    result = nx.Graph()
    result.add_nodes_from(nodes)
    result.add_edges_from(edges)
    return result


def metrics(value: nx.Graph) -> dict:
    components = list(nx.connected_components(value))
    communities = (list(nx.community.greedy_modularity_communities(value))
                   if value.number_of_edges() else [{node} for node in value])
    return {
        "nodes": value.number_of_nodes(),
        "edges": value.number_of_edges(),
        "components": len(components),
        "largest_component": max(map(len, components), default=0),
        "isolates": len(list(nx.isolates(value))),
        "bridges": len(list(nx.bridges(value))),
        "mean_clustering": round(nx.average_clustering(value), 4),
        "communities": len(communities),
        "modularity": round(nx.community.modularity(value, communities), 4),
    }


def main() -> None:
    legacy_obj = json.loads((BUNDLE / "contributions_core_consensus.json").read_text())
    legacy = legacy_obj["edges"] if isinstance(legacy_obj, dict) else legacy_obj
    contribution_obj = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = (contribution_obj["contributions"]
                     if isinstance(contribution_obj, dict) else contribution_obj)
    nodes = {row["id"] for row in contributions}
    legacy_by_pair = {pair_key(row["src"], row["dst"]): row for row in legacy}

    original = {row["candidate_id"]: row for row in
                load_jsonl(OUT / "cartographer_rebuild_normalized.jsonl")
                if row["candidate_id"] in legacy_by_pair}
    corrected = {row["candidate_id"]: row for row in
                 load_jsonl(OUT / "legacy_missing_citation_context_predictions.jsonl")}
    if len(legacy_by_pair) != 989 or len(original) != 989 or len(corrected) != 160:
        raise RuntimeError({"legacy": len(legacy_by_pair), "original": len(original),
                            "corrected": len(corrected)})
    if not set(corrected) <= set(legacy_by_pair):
        raise RuntimeError("corrected predictions contain non-legacy pairs")

    merged = []
    normalized = Counter()
    for key in sorted(legacy_by_pair):
        row = dict(corrected.get(key, original[key]))
        row["relabel_source"] = ("citation_context_correction"
                                 if key in corrected else "august_enriched_run")
        if row["relation"] in {"related", "none", "unclear"} and row["direction"] != "none":
            row["raw_direction"] = row["direction"]
            row["direction"] = "none"
            normalized[f"{row['relation']}_direction_to_none"] += 1
        merged.append(row)

    merged_path = OUT / "legacy_fulltext_citation_enriched_predictions.jsonl"
    merged_path.write_text("".join(json.dumps(row) + "\n" for row in merged))

    enriched_edges = [{
        "src": row["a"] if row["direction"] != "b_to_a" else row["b"],
        "dst": row["b"] if row["direction"] != "b_to_a" else row["a"],
        "relation": row["relation"],
        "direction": row["direction"],
        "existence_confidence": row["existence_confidence"],
        "type_confidence": row["type_confidence"],
        "evidence_ids": row["evidence_ids"],
        "reason": row["reason"],
        "citation_directions": row.get("citation_directions", []),
        "relabel_source": row["relabel_source"],
    } for row in merged]
    graph_path = OUT / "legacy_fulltext_citation_enriched_graph.json"
    graph_path.write_text(json.dumps({
        "_meta": {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_policy": "same 989 contribution pairs retained by legacy graph",
            "evidence_policy": "quotes + retrieved full text; parent-paper citation evidence where available",
            "corrected_missing_citation_pairs": len(corrected),
            "normalization": dict(normalized),
        },
        "contributions": contributions,
        "edges": enriched_edges,
    }, indent=2))

    relation_transitions = Counter(
        (legacy_by_pair[row["candidate_id"]]["relation"], row["relation"])
        for row in merged
    )
    legacy_graph = graph(nodes, [(row["src"], row["dst"]) for row in legacy])
    substantive = [row for row in merged if row["relation"] not in {"none", "unclear"}]
    hard = [row for row in merged if row["relation"] in HARD]
    substantive_graph = graph(nodes, [(row["a"], row["b"]) for row in substantive])
    hard_graph = graph(nodes, [(row["a"], row["b"]) for row in hard])
    report = {
        "validation": {
            "legacy_pairs": len(legacy_by_pair), "merged_pairs": len(merged),
            "corrected_pairs": len(corrected), "duplicates": len(merged) - len({r["candidate_id"] for r in merged}),
            "invalid_evidence": sum(bool(row.get("invalid_evidence_ids")) for row in merged),
            "normalization": dict(normalized),
        },
        "relations": {
            "legacy": dict(Counter(row["relation"] for row in legacy)),
            "enriched": dict(Counter(row["relation"] for row in merged)),
            "exact_type_agreement": sum(
                legacy_by_pair[row["candidate_id"]]["relation"] == row["relation"]
                for row in merged),
            "transitions": {f"{old} -> {new}": count
                            for (old, new), count in sorted(relation_transitions.items())},
        },
        "topology": {
            "legacy": metrics(legacy_graph),
            "enriched_all_substantive": metrics(substantive_graph),
            "enriched_hard": metrics(hard_graph),
        },
    }
    report_path = OUT / "legacy_fulltext_citation_enriched_comparison.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("->", merged_path, graph_path, report_path)


if __name__ == "__main__":
    main()
