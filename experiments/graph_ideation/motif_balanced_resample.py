#!/usr/bin/env python3
"""Build a distinct-paper, edge-evidence-balanced sample of graph gaps."""
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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402
from temporal_gap_closure import GAP_SCHEMA, GAP_SYSTEM, read_jsonl  # noqa: E402

BUNDLE = ROOT / "data" / "prior-core-v0.2"
EDGE_PATH = ROOT / "experiments" / "edge_quality" / "out" / "cartographer_rebuild_normalized.jsonl"
MOTIFS = ("contradiction_resolution", "boundary_generalization",
          "replication_validation", "system_integration", "missing_feedback_loop")
RELATION_MOTIF = {"contradicts": "contradiction_resolution",
                  "builds_on": "boundary_generalization", "refines": "boundary_generalization",
                  "supports": "replication_validation", "related": "system_integration"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-motif", type=int, default=4)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    contributions = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())["contributions"]
    by_id = {x["id"]: x for x in contributions}
    edges = [x for x in read_jsonl(EDGE_PATH)
             if x["relation"] not in {"none", "unclear"} and x["a"] in by_id and x["b"] in by_id]
    graph = nx.Graph()
    pair_edges = defaultdict(list)
    for edge in edges:
        graph.add_edge(edge["a"], edge["b"])
        pair_edges[tuple(sorted((edge["a"], edge["b"])))].append(edge)

    def papers(ids: list[str]) -> set[str]:
        return {by_id[x]["paper_id"] for x in ids}

    packets, used_pairs = [], set()
    grouped = defaultdict(list)
    for edge in edges:
        motif = RELATION_MOTIF.get(edge["relation"])
        if motif:
            grouped[motif].append(edge)
    for motif in MOTIFS[:-1]:
        ranked = sorted(grouped[motif], key=lambda x: (
            -x.get("existence_confidence", 0), -x.get("type_confidence", 0), x["candidate_id"]))
        for edge in ranked:
            base = [edge["a"], edge["b"]]
            if len(papers(base)) < 2:
                continue
            candidates = sorted((set(graph.neighbors(base[0])) | set(graph.neighbors(base[1]))) - set(base),
                                key=lambda x: (-graph.degree(x), x))
            third = next((x for x in candidates if len(papers([*base, x])) == 3), None)
            if not third:
                continue
            key = tuple(sorted(base))
            if key in used_pairs:
                continue
            used_pairs.add(key)
            packets.append({"motif": motif, "contribution_ids": [*base, third],
                "edge_evidence": {"relation": edge["relation"],
                    "existence_confidence": edge.get("existence_confidence"),
                    "type_confidence": edge.get("type_confidence"), "reason": edge.get("reason")}})
            if sum(x["motif"] == motif for x in packets) == args.per_motif:
                break

    # Open wedges: two evidenced neighbours of a center without a labelled edge
    # between them. These operationalize a missing feedback/connection candidate.
    for center in sorted(graph, key=lambda x: (-graph.degree(x), x)):
        neighbours = sorted(graph.neighbors(center), key=lambda x: (-graph.degree(x), x))
        found = None
        for i, left in enumerate(neighbours):
            for right in neighbours[i + 1:]:
                if not pair_edges.get(tuple(sorted((left, right)))) and len(papers([center, left, right])) == 3:
                    found = [center, left, right]
                    break
            if found:
                break
        if found:
            packets.append({"motif": "missing_feedback_loop", "contribution_ids": found,
                "edge_evidence": {"relation": "open_wedge", "center": center}})
        if sum(x["motif"] == "missing_feedback_loop" for x in packets) == args.per_motif:
            break

    for packet in packets:
        packet["packet_id"] = hashlib.sha256(
            f"balanced:{packet['motif']}:{','.join(packet['contribution_ids'])}".encode()).hexdigest()[:12]
        packet["paper_ids"] = [by_id[x]["paper_id"] for x in packet["contribution_ids"]]
        packet["sources"] = [{"id": f"S{i}", "contribution_id": cid,
                              "statement": by_id[cid]["statement"]}
                             for i, cid in enumerate(packet["contribution_ids"], 1)]
    if len(packets) != len(MOTIFS) * args.per_motif:
        raise ValueError(f"could only build {len(packets)} balanced packets")
    (args.out / "manifest.json").write_text(json.dumps({"motifs": list(MOTIFS),
        "per_motif": args.per_motif, "packets": packets}, indent=2))

    output = args.out / "gap_predictions.jsonl"
    existing = read_jsonl(output) if output.exists() else []
    done = {x["packet_id"] for x in existing}
    lock = threading.Lock()

    def predict(packet: dict) -> dict:
        system = GAP_SYSTEM + f"\nThe evidence packet was selected for the supported motif `{packet['motif']}`. Formulate that kind of gap; do not substitute a different motif."
        result = llm.structured(model=args.model, system=system,
            user=json.dumps({"edge_evidence": packet["edge_evidence"], "sources": packet["sources"]}),
            schema=GAP_SCHEMA, tool_name="emit_gap", max_tokens=1800, retries=3)
        result["gap_type"] = packet["motif"]
        return {"packet_id": packet["packet_id"], "motif": packet["motif"],
                "model": args.model, **result}

    todo = [x for x in packets if x["packet_id"] not in done]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(predict, x): x for x in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with lock, output.open("a") as handle:
                handle.write(json.dumps(row) + "\n")
            print(f"balanced {i}/{len(todo)} {row['motif']}", flush=True)

    rows = read_jsonl(output)
    texts = [f"{x['gap_statement']} {x['missing_evidence']}" for x in rows]
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(texts)
    similarity = cosine_similarity(matrix)
    values = [similarity[i, j] for i in range(len(rows)) for j in range(i + 1, len(rows))]
    summary = {"packets": len(rows), "distinct_paper_packets": sum(
        len(set(x["paper_ids"])) == 3 for x in packets),
        "motif_counts": {m: sum(x["motif"] == m for x in rows) for m in MOTIFS},
        "mean_pairwise_tfidf": round(sum(values) / len(values), 4),
        "semantic_dispersion": round(1 - sum(values) / len(values), 4)}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
