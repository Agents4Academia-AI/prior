#!/usr/bin/env python3
"""Portfolio-level analysis for the forest-versus-trees ideation demo."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import embeddings  # noqa: E402

BUNDLE = ROOT / "data" / "prior-core-v0.2"
EDGE_OUT = ROOT / "experiments" / "edge_quality" / "out"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def paper(cid: str) -> str:
    return cid.split("::")[0]


def idea_text(idea: dict) -> str:
    return " ".join(str(idea.get(k, "")) for k in
                    ("title", "research_question", "mechanism", "minimal_evaluation"))


def entropy(values: list[int]) -> tuple[float, float]:
    counts = Counter(values)
    probs = [n / len(values) for n in counts.values()] if values else []
    h = -sum(p * math.log(p) for p in probs)
    return h, math.exp(h) if probs else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--embedding-method", choices=("local_model", "tfidf_svd"),
                        default="tfidf_svd")
    args = parser.parse_args()
    manifest = json.loads((args.out / "manifest.json").read_text())
    generations = read_jsonl(args.out / "generations.jsonl")
    packets = {x["packet_id"]: x for x in manifest["packets"]}
    selected = [x for x in generations if x["packet_id"] in packets]

    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    corpus = grounded["contributions"]
    corpus_ids = [x["id"] for x in corpus]
    corpus_texts = [x["statement"] for x in corpus]

    edges = read_jsonl(EDGE_OUT / "cartographer_rebuild_normalized.jsonl")
    graph = nx.Graph()
    graph.add_nodes_from({paper(x) for x in corpus_ids})
    for edge in edges:
        if edge["relation"] in {"none", "unclear"}:
            continue
        a, b = paper(edge["a"]), paper(edge["b"])
        if a != b:
            graph.add_edge(a, b, weight=graph.get_edge_data(a, b, {"weight": 0})["weight"] + 1)
    groups = nx.community.greedy_modularity_communities(graph, weight="weight")
    community = {node: i for i, group in enumerate(groups) for node in group}

    rows = []
    for generation in selected:
        packet = packets[generation["packet_id"]]
        for number, idea in enumerate(generation["ideas"], 1):
            rows.append({"key": f"{generation['packet_id']}:{number}",
                         "arm": generation["arm"], "seed_id": generation["seed_id"],
                         "text": idea_text(idea), "idea": idea, "packet": packet})

    all_text = corpus_texts + [x["text"] for x in rows]
    if args.embedding_method == "local_model":
        vectors = np.asarray(embeddings.embed(all_text), dtype=float)
        model_name = os.environ.get("PRIOR_EMBED_MODEL", "mixedbread-ai/mxbai-embed-large-v1")
    else:
        tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2,
                                sublinear_tf=True).fit_transform(all_text)
        dimensions = min(128, tfidf.shape[0] - 1, tfidf.shape[1] - 1)
        vectors = normalize(TruncatedSVD(n_components=dimensions, random_state=61)
                            .fit_transform(tfidf))
        model_name = f"tfidf-svd-{dimensions}"
    corpus_vectors, idea_vectors = vectors[:len(corpus)], vectors[len(corpus):]
    similarities = cosine_similarity(idea_vectors, corpus_vectors)
    for row, scores in zip(rows, similarities):
        order = np.argsort(-scores)[:5]
        row["antecedents"] = [{"contribution_id": corpus_ids[i],
                               "similarity": round(float(scores[i]), 5),
                               "statement": corpus_texts[i]} for i in order]

    report = {"schema_version": 1,
              "embedding_model": model_name,
              "n_corpus_contributions": len(corpus), "n_ideas": len(rows), "arms": {}}
    for arm in manifest["arms"]:
        indices = [i for i, x in enumerate(rows) if x["arm"] == arm]
        arm_rows = [rows[i] for i in indices]
        vec = idea_vectors[indices]
        sim = cosine_similarity(vec)
        upper = sim[np.triu_indices(len(vec), 1)]
        within_seed = []
        for seed_id in manifest["seeds"]:
            local = [i for i, x in enumerate(arm_rows) if x["seed_id"] == seed_id]
            if len(local) > 1:
                s = cosine_similarity(vec[local])
                within_seed.extend(s[np.triu_indices(len(local), 1)].tolist())
        source_ids = [cid for x in arm_rows[::3] for cid in x["packet"]["contribution_ids"]]
        source_communities = [community.get(paper(cid), -1) for cid in source_ids]
        h, effective = entropy(source_communities)
        packet_cross = []
        for packet in (x for x in manifest["packets"] if x["arm"] == arm):
            cs = {community.get(paper(cid), -1) for cid in packet["contribution_ids"]}
            packet_cross.append(len(cs) > 1)
        report["arms"][arm] = {
            "ideas": len(arm_rows),
            "portfolio_mean_pairwise_cosine": round(float(upper.mean()), 5),
            "portfolio_semantic_dispersion": round(float(1 - upper.mean()), 5),
            "within_seed_mean_pairwise_cosine": round(float(np.mean(within_seed)), 5),
            "within_seed_semantic_dispersion": round(float(1 - np.mean(within_seed)), 5),
            "mean_nearest_corpus_similarity": round(float(np.mean([
                x["antecedents"][0]["similarity"] for x in arm_rows])), 5),
            "unique_source_contributions": len(set(source_ids)),
            "unique_source_papers": len({paper(x) for x in source_ids}),
            "communities_covered": len(set(source_communities)),
            "source_community_entropy": round(h, 5),
            "effective_source_communities": round(effective, 5),
            "cross_community_packet_rate": round(sum(packet_cross) / len(packet_cross), 5),
            "typed_source_pairs": sum(x["hard_pairs"] for x in manifest["packets"]
                                      if x["arm"] == arm),
        }
    (args.out / "portfolio_analysis.json").write_text(json.dumps(report, indent=2))
    with (args.out / "antecedent_candidates.jsonl").open("w") as f:
        for row in rows:
            f.write(json.dumps({k: row[k] for k in
                ("key", "arm", "seed_id", "idea", "antecedents")}) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
