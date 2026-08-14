#!/usr/bin/env python3
"""Traverse Prior, select auditable gap motifs, and generate candidate studies."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402
from run_pilot import IDEA_SCHEMA  # noqa: E402

BUNDLE = ROOT / "data" / "prior-core-v0.2"
EDGE_PATH = ROOT / "experiments" / "edge_quality" / "out" / "cartographer_rebuild_normalized.jsonl"
HARD = {"supports", "builds_on", "refines", "contradicts"}
GAP_TYPES = ["benchmark_reconciliation", "replication_validation",
             "boundary_generalization", "contradiction_resolution",
             "system_integration", "missing_feedback_loop",
             "infrastructure_tooling", "fragile_claim", "other"]

SELECT_SYSTEM = """You select one useful, auditable research gap from a local
scientific contribution graph. The seed, its one/two-hop candidates, typed edges,
and open wedges are supplied. Choose exactly two candidate contributions to combine
with the seed. Use three distinct underlying papers unless there is an explicitly
justified reason that two independent contributions from one paper are essential.
Prefer cumulative field needs: missing controlled comparisons,
unsupported generalization, fragile claims, unresolved contradictions, absent
feedback loops, independent validation, or infrastructure that enables later work.
Do not maximize distance or novelty. A missing edge is only a candidate gap, so
state precisely what evidence is absent and what study could resolve it. Use only
listed contribution IDs and preserve the seed ID."""

SELECT_SCHEMA = {"type": "object", "properties": {
    "gap_type": {"type": "string", "enum": GAP_TYPES},
    "source_contribution_ids": {"type": "array", "items": {"type": "string"}},
    "gap_statement": {"type": "string"}, "missing_evidence": {"type": "string"},
    "proposed_resolution": {"type": "string"},
    "graph_evidence": {"type": "array", "items": {"type": "string"}},
    "reason": {"type": "string"},
}, "required": ["gap_type", "source_contribution_ids", "gap_statement",
                 "missing_evidence", "proposed_resolution", "graph_evidence", "reason"]}

GEN_SYSTEM = """You design concrete studies that resolve an evidence-grounded gap
identified in a scientific contribution graph. Produce exactly three distinct study
designs addressing the supplied gap. Each must meaningfully use all three S1/S2/S3
contributions, state a testable question, explain its mechanism, and give a minimal
evaluation. Prefer cumulative scientific value over flashiness. Do not claim global
novelty, invent findings, or invent citations."""


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def append(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock, path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--stage", choices=("select", "generate", "all"), default="all")
    args = parser.parse_args()
    manifest_path = args.out / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    seeds = manifest["seeds"]
    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = grounded["contributions"]
    by_id = {x["id"]: x for x in contributions}
    edges = [x for x in read_jsonl(EDGE_PATH) if x["relation"] not in {"none", "unclear"}]

    graph = nx.Graph()
    graph.add_nodes_from(by_id)
    pair_edges = defaultdict(list)
    for edge in edges:
        graph.add_edge(edge["a"], edge["b"])
        pair_edges[tuple(sorted((edge["a"], edge["b"])))].append(edge)
    groups = nx.community.greedy_modularity_communities(graph)
    community = {node: i for i, group in enumerate(groups) for node in group}

    def edge_summary(a: str, b: str) -> list[dict]:
        return [{"relation": x["relation"], "direction": x["direction"],
                 "channels": x["channels"],
                 "existence_confidence": x["existence_confidence"],
                 "type_confidence": x["type_confidence"], "reason": x["reason"][:500]}
                for x in pair_edges.get(tuple(sorted((a, b))), [])]

    def traversal(seed: str) -> dict:
        direct = sorted(graph.neighbors(seed), key=lambda x: (-graph.degree(x), x))[:12]
        second_paths = []
        seen = {seed, *direct}
        for middle in direct:
            for target in sorted(graph.neighbors(middle), key=lambda x: (-graph.degree(x), x)):
                if target in seen:
                    continue
                second_paths.append((middle, target))
                seen.add(target)
                if len(second_paths) >= 8:
                    break
            if len(second_paths) >= 8:
                break
        candidate_ids = direct + [x[1] for x in second_paths]
        candidates = [{"contribution_id": cid, "paper_id": by_id[cid]["paper_id"],
                       "statement": by_id[cid]["statement"],
                       "kind": by_id[cid].get("kind"), "community": community.get(cid),
                       "degree": graph.degree(cid),
                       "connection_to_seed": edge_summary(seed, cid),
                       "two_hop_via": next((mid for mid, target in second_paths if target == cid), None)}
                      for cid in candidate_ids]
        open_wedges = []
        for i, a in enumerate(direct):
            for b in direct[i + 1:]:
                if not pair_edges.get(tuple(sorted((a, b)))):
                    open_wedges.append({"left": a, "center": seed, "right": b,
                                        "left_relation": edge_summary(seed, a),
                                        "right_relation": edge_summary(seed, b)})
        return {"seed": {"contribution_id": seed,
                         "paper_id": by_id[seed]["paper_id"],
                         "statement": by_id[seed]["statement"],
                         "community": community.get(seed), "degree": graph.degree(seed)},
                "candidates": candidates, "open_wedges": open_wedges[:20]}

    traversals = {seed: traversal(seed) for seed in seeds}
    (args.out / "gap_traversals.json").write_text(json.dumps(traversals, indent=2))
    selection_path = args.out / "gap_aware_selections.jsonl"
    done = {x["seed_id"] for x in read_jsonl(selection_path)} if selection_path.exists() else set()
    lock = threading.Lock()

    def select(seed: str) -> dict:
        result = llm.structured(model=args.model, system=SELECT_SYSTEM,
            user=json.dumps(traversals[seed]), schema=SELECT_SCHEMA,
            tool_name="emit_gap", max_tokens=1500, retries=3, timeout=300)
        ids = result["source_contribution_ids"]
        allowed = {x["contribution_id"] for x in traversals[seed]["candidates"]}
        if len(ids) != 3 or ids[0] != seed or set(ids[1:]) - allowed or len(set(ids)) != 3:
            raise ValueError(f"invalid sources for {seed}: {ids}")
        if len({by_id[cid]["paper_id"] for cid in ids}) != 3:
            raise ValueError(f"sources do not represent three distinct papers for {seed}: {ids}")
        return {"seed_id": seed, "model": args.model, **result}

    if args.stage in {"select", "all"}:
        todo = [x for x in seeds if x not in done]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(select, x): x for x in todo}
            for i, future in enumerate(as_completed(futures), 1):
                row = future.result()
                append(selection_path, row, lock)
                print(f"gap-select {i}/{len(todo)} {row['gap_type']}", flush=True)
    if args.stage == "select":
        return

    selections = {x["seed_id"]: x for x in read_jsonl(selection_path)}
    gap_packets = []
    for seed in seeds:
        sel = selections[seed]
        paper_ids = [by_id[cid]["paper_id"] for cid in sel["source_contribution_ids"]]
        packet_id = hashlib.sha256(f"gap-aware-v1:{seed}".encode()).hexdigest()[:12]
        gap_packets.append({"packet_id": packet_id, "seed_id": seed, "arm": "gap_aware",
            "contribution_ids": sel["source_contribution_ids"], "pairwise_tfidf": [],
            "paper_ids": paper_ids, "unique_paper_count": len(set(paper_ids)),
            "legacy_communities": [],
            "enriched_communities": [community.get(x) for x in sel["source_contribution_ids"]],
            "hard_pairs": sum(bool(set(x["relation"] for x in pair_edges.get(tuple(sorted((a, b))), [])) & HARD)
                              for i, a in enumerate(sel["source_contribution_ids"])
                              for b in sel["source_contribution_ids"][i + 1:]),
            "sources": [{"id": f"S{i}", "contribution_id": cid,
                         "statement": by_id[cid]["statement"]}
                        for i, cid in enumerate(sel["source_contribution_ids"], 1)],
            "gap": {k: sel[k] for k in ("gap_type", "gap_statement", "missing_evidence",
                                          "proposed_resolution", "graph_evidence", "reason")}})
    manifest["packets"] = [x for x in manifest["packets"] if x["arm"] != "gap_aware"] + gap_packets
    manifest["arms"] = list(dict.fromkeys([*manifest["arms"], "gap_aware"]))
    manifest_path.write_text(json.dumps(manifest, indent=2))

    generation_path = args.out / "generations.jsonl"
    generated = {x["packet_id"] for x in read_jsonl(generation_path)}

    def generate(packet: dict) -> dict:
        sources = "\n\n".join(f"[{x['id']}] {x['statement']}" for x in packet["sources"])
        prompt = f"GRAPH-IDENTIFIED GAP:\n{json.dumps(packet['gap'])}\n\nSOURCES:\n{sources}"
        result = {}
        for _ in range(3):
            result = llm.structured(model=args.model, system=GEN_SYSTEM, user=prompt,
                schema=IDEA_SCHEMA, tool_name="emit_ideas", max_tokens=3600,
                retries=3, timeout=300)
            if len(result.get("ideas", [])) == 3:
                break
        if len(result.get("ideas", [])) != 3:
            raise ValueError(f"invalid idea payload for {packet['packet_id']}: {result}")
        return {"packet_id": packet["packet_id"], "seed_id": packet["seed_id"],
                "arm": "gap_aware", "model": args.model,
                "prompt_version": "gap-aware-ideation-v1", **result}

    todo_packets = [x for x in gap_packets if x["packet_id"] not in generated]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(generate, x): x for x in todo_packets}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            append(generation_path, row, lock)
            print(f"gap-generate {i}/{len(todo_packets)} {row['packet_id']}", flush=True)


if __name__ == "__main__":
    main()
