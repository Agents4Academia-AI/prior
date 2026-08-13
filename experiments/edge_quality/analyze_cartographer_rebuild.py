#!/usr/bin/env python3
"""Validate and compare the complete evidence-enriched Cartographer rebuild."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "prior-core-v0.2"
OUT = Path(__file__).parent / "out"
RELATIONS = {"supports", "builds_on", "refines", "contradicts",
             "related", "none", "unclear"}
HARD = {"supports", "builds_on", "refines", "contradicts"}
VALID_DIRECTIONS = {
    "supports": {"symmetric"}, "contradicts": {"symmetric"},
    "builds_on": {"a_to_b", "b_to_a"}, "refines": {"a_to_b", "b_to_a"},
    "related": {"none"}, "none": {"none"}, "unclear": {"none", "unclear"},
}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pid(contribution_id: str) -> str:
    return contribution_id.split("::")[0]


def contribution_pair(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def paper_pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((pid(a), pid(b))))


def graph_from_edges(papers: list[str], edges: list[dict]) -> nx.Graph:
    graph = nx.Graph()
    graph.add_nodes_from(papers)
    for edge in edges:
        a, b = paper_pair(edge["a"], edge["b"])
        if a == b:
            continue
        if graph.has_edge(a, b):
            graph[a][b]["weight"] += 1
        else:
            graph.add_edge(a, b, weight=1)
    return graph


def communities(graph: nx.Graph) -> list[set[str]]:
    if graph.number_of_edges() == 0:
        return [{node} for node in graph]
    return list(nx.community.greedy_modularity_communities(graph, weight="weight"))


def graph_metrics(graph: nx.Graph) -> tuple[dict, list[set[str]]]:
    comms = communities(graph)
    components = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    modularity = (nx.community.modularity(graph, comms, weight="weight")
                  if graph.number_of_edges() else 0.0)
    return {
        "nodes": graph.number_of_nodes(), "paper_pairs": graph.number_of_edges(),
        "weighted_contribution_edges": sum(d["weight"] for *_, d in graph.edges(data=True)),
        "density": round(nx.density(graph), 6),
        "components": len(components), "largest_component": components[0] if components else 0,
        "isolates": len(list(nx.isolates(graph))),
        "bridges": len(list(nx.bridges(graph))),
        "mean_clustering": round(nx.average_clustering(graph, weight=None), 4),
        "communities": len(comms), "modularity": round(modularity, 4),
        "community_sizes": sorted((len(c) for c in comms), reverse=True),
    }, comms


def partition_labels(nodes: list[str], comms: list[set[str]]) -> list[int]:
    lookup = {node: i for i, group in enumerate(comms) for node in group}
    return [lookup[node] for node in nodes]


def main() -> None:
    raw_path = OUT / "cartographer_rebuild_predictions.jsonl"
    manifest_path = OUT / "cartographer_rebuild_candidates.json"
    legacy_path = BUNDLE / "contributions_core_consensus.json"
    paper_path = BUNDLE / "papers_core.jsonl"
    raw = load_jsonl(raw_path)
    manifest = json.loads(manifest_path.read_text())
    candidates = {row["candidate_id"]: row for row in manifest["candidates"]}
    legacy_obj = json.loads(legacy_path.read_text())
    legacy = legacy_obj["edges"] if isinstance(legacy_obj, dict) else legacy_obj
    papers = [json.loads(line)["id"] for line in paper_path.read_text().splitlines()
              if line.strip()]
    paper_rows = [json.loads(line) for line in paper_path.read_text().splitlines()
                  if line.strip()]
    titles = {row["id"]: row.get("title", row["id"]) for row in paper_rows}

    duplicates = len(raw) - len({row["candidate_id"] for row in raw})
    unknown = [row["candidate_id"] for row in raw if row["candidate_id"] not in candidates]
    missing = sorted(set(candidates) - {row["candidate_id"] for row in raw})
    invalid_labels = [row["candidate_id"] for row in raw
                      if row.get("relation") not in RELATIONS]
    invalid_evidence = [row["candidate_id"] for row in raw
                        if row.get("invalid_evidence_ids")]
    confidence_range = [row["candidate_id"] for row in raw
                        if not (0 <= row.get("existence_confidence", -1) <= 1
                                and 0 <= row.get("type_confidence", -1) <= 1)]
    invalid_directions = [row["candidate_id"] for row in raw
                          if row.get("direction") not in
                          VALID_DIRECTIONS.get(row.get("relation"), set())]

    normalized = []
    normalization = Counter()
    for row in raw:
        item = dict(row)
        if item["relation"] in {"related", "none"} and item["direction"] != "none":
            item["raw_direction"] = item["direction"]
            item["direction"] = "none"
            normalization[f"{item['relation']}_direction_to_none"] += 1
        normalized.append(item)
    normalized_path = OUT / "cartographer_rebuild_normalized.jsonl"
    normalized_path.write_text("".join(json.dumps(row) + "\n" for row in normalized))

    legacy_by_pair: dict[str, list[dict]] = defaultdict(list)
    for edge in legacy:
        if pid(edge["src"]) != pid(edge["dst"]):
            legacy_by_pair[contribution_pair(edge["src"], edge["dst"])].append(edge)
    new_by_pair = {row["candidate_id"]: row for row in normalized}
    legacy_pairs, new_pairs = set(legacy_by_pair), set(new_by_pair)
    shared = legacy_pairs & new_pairs
    relation_cross = Counter()
    exact_type = 0
    hard_to_soft = 0
    for key in shared:
        old_types = {edge["relation"] for edge in legacy_by_pair[key]}
        new_type = new_by_pair[key]["relation"]
        exact_type += new_type in old_types
        hard_to_soft += new_type in {"related", "none", "unclear"}
        for old_type in old_types:
            relation_cross[(old_type, new_type)] += 1

    channel_relation = defaultdict(Counter)
    for row in normalized:
        channel_relation["+".join(row["channels"])][row["relation"]] += 1

    legacy_edges = [{"a": edge["src"], "b": edge["dst"],
                     "relation": edge["relation"]}
                    for edge in legacy if pid(edge["src"]) != pid(edge["dst"])]
    policies = {
        "legacy_hard": legacy_edges,
        "relabelled_legacy_all_substantive": [
            row for row in normalized if row["candidate_id"] in legacy_pairs
            and row["relation"] not in {"none", "unclear"}
        ],
        "relabelled_legacy_hard": [
            row for row in normalized if row["candidate_id"] in legacy_pairs
            and row["relation"] in HARD
        ],
        "enriched_union_all_substantive": [
            row for row in normalized if row["relation"] not in {"none", "unclear"}
        ],
        "enriched_union_hard": [row for row in normalized if row["relation"] in HARD],
        "enriched_union_hard_high_confidence": [
            row for row in normalized if row["relation"] in HARD
            and row["existence_confidence"] >= 0.7 and row["type_confidence"] >= 0.7
        ],
    }
    graph_report, graph_objects, partitions = {}, {}, {}
    for name, edges in policies.items():
        graph = graph_from_edges(papers, edges)
        metrics, comms = graph_metrics(graph)
        graph_report[name] = metrics
        graph_objects[name] = graph
        partitions[name] = comms
    stability = {}
    nodes = sorted(papers)
    for left in policies:
        for right in policies:
            if left >= right:
                continue
            stability[f"{left}__vs__{right}"] = round(adjusted_rand_score(
                partition_labels(nodes, partitions[left]),
                partition_labels(nodes, partitions[right])), 4)

    cluster_records = {}
    for name, comms in partitions.items():
        graph = graph_objects[name]
        cluster_records[name] = []
        for index, group in enumerate(sorted(comms, key=lambda value: (-len(value), sorted(value)[0])), 1):
            ranked = sorted(group, key=lambda node: (-graph.degree(node, weight="weight"), node))
            cluster_records[name].append({
                "cluster": index, "size": len(group),
                "representatives": [{"id": node, "title": titles[node],
                                     "weighted_degree": graph.degree(node, weight="weight")}
                                    for node in ranked[:5]],
                "members": [{"id": node, "title": titles[node]} for node in sorted(group)],
            })

    legacy_graph = graph_objects["legacy_hard"]
    direction_comparable = direction_correct = 0
    for key in shared:
        row = new_by_pair[key]
        if row["relation"] not in {"builds_on", "refines"}:
            continue
        matching = [edge for edge in legacy_by_pair[key]
                    if edge["relation"] == row["relation"]]
        if not matching:
            continue
        direction_comparable += 1
        predicted = ((row["a"], row["b"]) if row["direction"] == "a_to_b"
                     else (row["b"], row["a"]))
        direction_correct += any((edge["src"], edge["dst"]) == predicted
                                 for edge in matching)

    report = {
        "mechanical_validation": {
            "expected": len(candidates), "rows": len(raw), "duplicates": duplicates,
            "unknown_candidates": unknown, "missing_candidates": missing,
            "invalid_labels": invalid_labels, "invalid_evidence": invalid_evidence,
            "invalid_confidence": confidence_range,
            "raw_invalid_directions": len(invalid_directions),
            "normalization": dict(normalization),
        },
        "edge_comparison": {
            "legacy_cross_paper_edges": sum(len(v) for v in legacy_by_pair.values()),
            "legacy_unique_contribution_pairs": len(legacy_pairs),
            "enriched_candidate_pairs": len(new_pairs), "shared_candidates": len(shared),
            "new_citation_routed_candidates": len(new_pairs - legacy_pairs),
            "shared_exact_type": exact_type,
            "shared_exact_type_rate": round(exact_type / len(shared), 4),
            "legacy_hard_to_enriched_soft_or_absent": hard_to_soft,
            "legacy_hard_to_enriched_soft_or_absent_rate": round(hard_to_soft / len(shared), 4),
            "direction_comparable_exact_types": direction_comparable,
            "direction_agreement": direction_correct,
            "direction_agreement_rate": (round(direction_correct / direction_comparable, 4)
                                         if direction_comparable else None),
            "legacy_type_to_enriched_type": {
                old: dict(Counter({new: count for (source, new), count in relation_cross.items()
                                   if source == old})) for old in sorted(HARD)
            },
            "channel_relation_distribution": {
                channel: dict(counts) for channel, counts in channel_relation.items()
            },
        },
        "graph_metrics": graph_report,
        "community_adjusted_rand": stability,
        "clusters": cluster_records,
        "legacy_isolates": sorted(nx.isolates(legacy_graph)),
        "enriched_hard_isolates": sorted(nx.isolates(graph_objects["enriched_union_hard"])),
    }
    report_path = OUT / "cartographer_rebuild_analysis.json"
    report_path.write_text(json.dumps(report, indent=2))

    md = ["# Legacy versus evidence-enriched Cartographer", "",
          "## Mechanical validation", "",
          f"- {len(raw)}/{len(candidates)} candidate records present; {duplicates} duplicates.",
          f"- {len(invalid_evidence)} records cite nonexistent evidence IDs.",
          f"- {len(invalid_directions)} raw direction-schema mismatches; "
          f"{sum(normalization.values())} non-directional labels canonicalized in the derived graph.",
          "", "## Contribution-edge comparison", "",
          f"- Shared legacy candidates: {len(shared)}; newly citation-routed candidates: {len(new_pairs-legacy_pairs)}.",
          f"- Exact relation-type agreement: {exact_type}/{len(shared)} ({exact_type/len(shared):.1%}).",
          f"- Legacy hard relations downgraded to related/none/unclear: {hard_to_soft}/{len(shared)} ({hard_to_soft/len(shared):.1%}).",
          "", "## Paper-graph consequences", "",
          "| policy | pairs | weighted edges | components | isolates | bridges | communities | modularity |",
          "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, metrics in graph_report.items():
        md.append(f"| {name} | {metrics['paper_pairs']} | {metrics['weighted_contribution_edges']} | "
                  f"{metrics['components']} | {metrics['isolates']} | {metrics['bridges']} | "
                  f"{metrics['communities']} | {metrics['modularity']:.4f} |")
    md += ["", "Community stability uses adjusted Rand index over all 152 papers:", ""]
    md += [f"- `{key}`: {value}" for key, value in stability.items()]
    md_path = OUT / "cartographer_rebuild_analysis.md"
    md_path.write_text("\n".join(md) + "\n")
    print(json.dumps(report, indent=2))
    print("->", normalized_path, report_path, md_path)


if __name__ == "__main__":
    main()
