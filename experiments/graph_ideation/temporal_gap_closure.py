#!/usr/bin/env python3
"""Prompt-matched temporal holdout for graph-identified research gaps."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import config, llm  # noqa: E402

BUNDLE = ROOT / "data" / "prior-core-v0.2"
EDGE_PATH = ROOT / "experiments" / "edge_quality" / "out" / "cartographer_rebuild_normalized.jsonl"
ARMS = ("gap_aware", "flat", "cross_cluster", "centrality", "matched_random")
HARD = {"supports", "builds_on", "refines", "contradicts"}

GAP_SYSTEM = """You receive exactly three scientific contributions published
before a temporal cutoff. Identify the single most consequential, concrete piece of
missing evidence exposed by considering them together. Prefer a controlled
comparison, unresolved contradiction, boundary/generalization test, replication,
missing feedback loop, or enabling infrastructure over a vague new capability.
Use only supplied evidence. Do not claim global novelty, mention future work, or
assume any result. Return a testable gap and a minimal study that could resolve it."""

GAP_SCHEMA = {"type": "object", "properties": {
    "gap_statement": {"type": "string"}, "missing_evidence": {"type": "string"},
    "minimal_study": {"type": "string"},
    "gap_type": {"type": "string", "enum": ["benchmark_reconciliation",
        "replication_validation", "boundary_generalization", "contradiction_resolution",
        "system_integration", "missing_feedback_loop", "infrastructure_tooling", "other"]},
    "reason": {"type": "string"}},
    "required": ["gap_statement", "missing_evidence", "minimal_study", "gap_type", "reason"]}

JUDGE_SYSTEM = """Judge whether each later contribution addresses a gap predicted
using only earlier literature. Labels: closes = directly supplies the requested
missing evidence; partly_addresses = materially advances it but leaves essential
parts unresolved; unrelated = does not address it. Be conservative. Lexical or
topic similarity is insufficient. Use only the supplied later contribution and its
supporting quote. Condition labels are hidden. Return every key exactly once."""

JUDGE_ITEM = {"type": "object", "properties": {
    "key": {"type": "string"},
    "label": {"type": "string", "enum": ["closes", "partly_addresses", "unrelated"]},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "supporting_quote": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["key", "label", "confidence", "supporting_quote", "reason"]}
JUDGE_SCHEMA = {"type": "object", "properties": {
    "results": {"type": "array", "items": JUDGE_ITEM}}, "required": ["results"]}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def append(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock, path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")


def work_key(paper: dict) -> str:
    """Best-effort manifestation key used only to prevent temporal leakage.

    Prefer persistent identifiers; otherwise collapse arXiv versions and exact
    normalized titles. This is conservative: uncertain works remain distinct.
    """
    doi = str(paper.get("doi") or "").lower().replace("https://doi.org/", "").strip()
    arxiv = re.search(r"(?:arxiv[:./]|abs/|pdf/)(\d{4}\.\d{4,5})(?:v\d+)?", " ".join(
        str(paper.get(k) or "") for k in ("id", "doi", "url", "pdf_url")), re.I)
    if arxiv:
        return f"arxiv:{arxiv.group(1)}"
    if doi:
        return f"doi:{doi}"
    title = re.sub(r"[^a-z0-9]+", " ", str(paper.get("title") or "").lower()).strip()
    return f"title:{title}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cutoff", default="2025-07-01")
    parser.add_argument("--seeds", type=int, default=12)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=1408)
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--stage", choices=("predict", "judge", "summarize", "all"), default="all")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    obj = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = obj["contributions"]
    by_id = {x["id"]: x for x in contributions}
    papers = {x["id"]: x for x in read_jsonl(BUNDLE / "papers_core.jsonl")}
    family = {pid: work_key(paper) for pid, paper in papers.items()}
    early = [x for x in contributions if x.get("date") and x["date"] < args.cutoff]
    late = [x for x in contributions if x.get("date") and x["date"] >= args.cutoff]
    early_ids, late_ids = {x["id"] for x in early}, {x["id"] for x in late}
    edges = [x for x in read_jsonl(EDGE_PATH)
             if x["relation"] not in {"none", "unclear"} and x["a"] in early_ids and x["b"] in early_ids]
    graph = nx.Graph()
    graph.add_nodes_from(early_ids)
    pair_edges = defaultdict(list)
    for edge in edges:
        graph.add_edge(edge["a"], edge["b"])
        pair_edges[tuple(sorted((edge["a"], edge["b"])))].append(edge)
    communities = nx.community.greedy_modularity_communities(graph)
    community = {node: i for i, group in enumerate(communities) for node in group}

    texts = [x["statement"] for x in early]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(texts)
    index = {x["id"]: i for i, x in enumerate(early)}
    similarity = cosine_similarity(matrix)

    eligible = [x["id"] for x in early if graph.degree(x["id"]) >= 2]
    buckets = defaultdict(list)
    for cid in eligible:
        buckets[community.get(cid, -1)].append(cid)
    for values in buckets.values():
        values.sort(key=lambda x: (-graph.degree(x), x))
    seed_ids = []
    while len(seed_ids) < args.seeds and any(buckets.values()):
        for key in sorted(buckets):
            if buckets[key] and len(seed_ids) < args.seeds:
                seed_ids.append(buckets[key].pop(0))

    def distinct(seed_id: str, candidates: list[str], n: int = 2) -> list[str]:
        papers = {by_id[seed_id]["paper_id"]}
        chosen = []
        for cid in candidates:
            paper = by_id[cid]["paper_id"]
            if cid != seed_id and paper not in papers:
                chosen.append(cid)
                papers.add(paper)
            if len(chosen) == n:
                break
        return chosen

    rng = random.Random(args.seed)
    packets = []
    for seed_id in seed_ids:
        ranked_semantic = [early[i]["id"] for i in similarity[index[seed_id]].argsort()[::-1]]
        flat = distinct(seed_id, ranked_semantic)
        cross = distinct(seed_id, sorted(ranked_semantic,
            key=lambda x: (community.get(x) == community.get(seed_id),
                           -similarity[index[seed_id], index[x]])))
        neighborhood = set(graph.neighbors(seed_id))
        for middle in list(neighborhood):
            neighborhood.update(graph.neighbors(middle))
        graph_ranked = sorted(neighborhood, key=lambda x: (
            -sum(any(e["relation"] in HARD for e in pair_edges.get(tuple(sorted((x, y))), []))
                 for y in neighborhood | {seed_id}),
            -graph.degree(x), -similarity[index[seed_id], index[x]], x))
        gap = distinct(seed_id, graph_ranked)
        central = distinct(seed_id, sorted(early_ids, key=lambda x: (-graph.degree(x), x)))
        pool = [x for x in early_ids if x != seed_id]
        rng.shuffle(pool)
        target_communities = [community.get(x) for x in gap]
        matched = distinct(seed_id, sorted(pool, key=lambda x: (
            community.get(x) not in target_communities,
            min((abs(graph.degree(x) - graph.degree(y)) for y in gap), default=0))))
        choices = {"gap_aware": gap, "flat": flat, "cross_cluster": cross,
                   "centrality": central, "matched_random": matched}
        for arm, partners in choices.items():
            if len(partners) != 2:
                continue
            ids = [seed_id, *partners]
            packet_id = hashlib.sha256(f"{args.cutoff}:{arm}:{seed_id}".encode()).hexdigest()[:12]
            packets.append({"packet_id": packet_id, "seed_id": seed_id, "arm": arm,
                "contribution_ids": ids, "paper_ids": [by_id[x]["paper_id"] for x in ids],
                "sources": [{"id": f"S{i}", "contribution_id": cid,
                             "statement": by_id[cid]["statement"]}
                            for i, cid in enumerate(ids, 1)]})
    manifest = {"cutoff": args.cutoff, "early_contributions": len(early),
                "late_contributions": len(late), "seed_ids": seed_ids,
                "arms": list(ARMS), "packets": packets,
                "retrospective_corpus_caveat": True}
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2))

    predictions_path = args.out / "gap_predictions.jsonl"
    existing = read_jsonl(predictions_path) if predictions_path.exists() else []
    done = {x["packet_id"] for x in existing}
    lock = threading.Lock()

    def predict(packet: dict) -> dict:
        result = llm.structured(model=args.model, system=GAP_SYSTEM,
            user=json.dumps(packet["sources"]), schema=GAP_SCHEMA,
            tool_name="emit_gap", max_tokens=1800, retries=3)
        aliases = {"controlled_comparison": "benchmark_reconciliation",
                   "comparative_evaluation": "benchmark_reconciliation",
                   "replication": "replication_validation",
                   "generalization": "boundary_generalization"}
        result["gap_type"] = aliases.get(result.get("gap_type"), result.get("gap_type"))
        if result.get("gap_type") not in GAP_SCHEMA["properties"]["gap_type"]["enum"]:
            raise ValueError(f"invalid gap payload: {result}")
        return {"packet_id": packet["packet_id"], "seed_id": packet["seed_id"],
                "arm": packet["arm"], "model": args.model, **result}

    if args.stage in {"predict", "all"}:
        todo = [x for x in packets if x["packet_id"] not in done]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(predict, x): x for x in todo}
            for i, future in enumerate(as_completed(futures), 1):
                row = future.result()
                append(predictions_path, row, lock)
                print(f"predict {i}/{len(todo)} {row['arm']}", flush=True)
    if args.stage == "predict":
        return

    predictions = read_jsonl(predictions_path)
    late_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    late_texts = [x["statement"] for x in late]
    late_matrix = late_vectorizer.fit_transform(late_texts)
    query_matrix = late_vectorizer.transform([
        f"{x['gap_statement']} {x['missing_evidence']} {x['minimal_study']}" for x in predictions])
    scores = cosine_similarity(query_matrix, late_matrix)
    candidate_rows = []
    for prediction, row_scores in zip(predictions, scores):
        seed_family = family.get(by_id[prediction["seed_id"]]["paper_id"])
        eligible_late = [idx for idx in row_scores.argsort()[::-1]
                         if family.get(late[idx]["paper_id"]) != seed_family]
        top = eligible_late[:args.top_k]
        for rank, idx in enumerate(top, 1):
            contribution = late[idx]
            key = f"{prediction['packet_id']}:{rank}"
            candidate_rows.append({"key": key, "packet_id": prediction["packet_id"],
                "seed_id": prediction["seed_id"], "arm": prediction["arm"], "rank": rank,
                "similarity": round(float(row_scores[idx]), 6),
                "gap": {k: prediction[k] for k in ("gap_statement", "missing_evidence", "minimal_study")},
                "later": {"contribution_id": contribution["id"],
                          "paper_id": contribution["paper_id"], "date": contribution["date"],
                          "statement": contribution["statement"], "quote": contribution.get("quote", "")}})
    (args.out / "later_candidates.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in candidate_rows))

    judgements_path = args.out / "closure_judgements.jsonl"
    existing = read_jsonl(judgements_path) if judgements_path.exists() else []
    judged_seeds = {x["seed_id"] for x in existing}
    by_seed = defaultdict(list)
    for row in candidate_rows:
        by_seed[row["seed_id"]].append(row)

    def judge(item: tuple[str, list[dict]]) -> dict:
        seed_id, rows = item
        shuffled = list(rows)
        random.Random(f"{args.seed}:{seed_id}").shuffle(shuffled)
        expected = {x["key"] for x in rows}
        result_rows = []
        for start in range(0, len(shuffled), 10):
            chunk = shuffled[start:start + 10]
            chunk_expected = {x["key"] for x in chunk}
            chunk_by_key = {x["key"]: x for x in chunk}
            collected = {}
            for _ in range(3):
                missing = chunk_expected - set(collected)
                if not missing:
                    break
                payload = [{k: chunk_by_key[key][k] for k in ("key", "gap", "later")}
                           for key in sorted(missing)]
                result = llm.structured(model=args.model, system=JUDGE_SYSTEM,
                    user=json.dumps(payload), schema=JUDGE_SCHEMA,
                    tool_name="emit_closure", max_tokens=4200, retries=3)
                for result_row in result.get("results", []):
                    # Some providers occasionally return a JSON-encoded scalar
                    # inside an otherwise schema-valid array. Ignore it and let
                    # the missing-key retry recover the item.
                    if isinstance(result_row, dict) and result_row.get("key") in missing:
                        collected[result_row["key"]] = result_row
            if chunk_expected != set(collected):
                raise ValueError(f"invalid closure chunk missing={chunk_expected-set(collected)}")
            result_rows.extend(collected.values())
        received = {x["key"] for x in result_rows}
        valid = {"closes", "partly_addresses", "unrelated"}
        if expected != received or any(x.get("label") not in valid for x in result_rows):
            raise ValueError(f"invalid closure payload missing={expected-received} extra={received-expected}")
        lookup = {x["key"]: x for x in rows}
        for row in result_rows:
            row.update({k: lookup[row["key"]][k] for k in
                        ("packet_id", "arm", "rank", "similarity")})
            row["later_contribution_id"] = lookup[row["key"]]["later"]["contribution_id"]
        return {"seed_id": seed_id, "model": args.model, "results": result_rows}

    if args.stage in {"judge", "all"}:
        todo = [(x, rows) for x, rows in sorted(by_seed.items()) if x not in judged_seeds]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(judge, x): x[0] for x in todo}
            for i, future in enumerate(as_completed(futures), 1):
                row = future.result()
                append(judgements_path, row, lock)
                print(f"judge {i}/{len(todo)} {row['seed_id']}", flush=True)
    if args.stage == "judge":
        return

    all_judgements = read_jsonl(judgements_path)
    labels, reciprocal, seeds_with = defaultdict(Counter), defaultdict(list), defaultdict(int)
    for batch in all_judgements:
        per_arm = defaultdict(list)
        for row in batch["results"]:
            labels[row["arm"]][row["label"]] += 1
            per_arm[row["arm"]].append(row)
        for arm, rows in per_arm.items():
            hits = sorted(x["rank"] for x in rows if x["label"] != "unrelated")
            reciprocal[arm].append(1 / hits[0] if hits else 0)
            seeds_with[arm] += bool(hits)
    summary = {"cutoff": args.cutoff, "seeds": len(seed_ids), "top_k": args.top_k,
        "arms": {arm: {"labels": dict(labels[arm]),
            "address_precision_at_k": round((labels[arm]["closes"] + labels[arm]["partly_addresses"])
                                            / max(1, sum(labels[arm].values())), 4),
            "close_precision_at_k": round(labels[arm]["closes"] / max(1, sum(labels[arm].values())), 4),
            "seed_hit_rate": round(seeds_with[arm] / max(1, len(seed_ids)), 4),
            "mean_reciprocal_rank": round(sum(reciprocal[arm]) / max(1, len(reciprocal[arm])), 4)}
                 for arm in ARMS},
        "caveat": "Later candidates are top-k semantic retrieval from a retrospectively assembled corpus; precision/yield, not exhaustive recall."}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
