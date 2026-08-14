#!/usr/bin/env python3
"""Small, resumable test of graph-assisted scientific ideation.

The experiment holds contribution text and generation budget constant while
changing only how a three-contribution source packet is selected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
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
EDGE_OUT = ROOT / "experiments" / "edge_quality" / "out"
OUT = Path(os.environ.get("PRIOR_IDEATION_OUT", Path(__file__).parent / "out"))
HARD = {"supports", "builds_on", "refines", "contradicts"}
ARMS = ("closed_box", "flat", "legacy", "enriched")
PROMPT_VERSION = "graph-ideation-pilot-v1"

IDEA_SYSTEM = """You propose concrete research directions in AI-for-science.
Use only the supplied source contributions. Produce exactly three distinct ideas.
Each must combine all three sources in a meaningful way, state a testable research
question, and give a minimal evaluation. Do not claim the idea is globally novel;
it is only a candidate direction relative to a frozen corpus. Cite sources by their
provided S1/S2/S3 IDs and do not invent findings."""

IDEA_SCHEMA = {"type": "object", "properties": {
    "ideas": {"type": "array", "minItems": 3, "maxItems": 3, "items": {
        "type": "object", "properties": {
            "title": {"type": "string"}, "research_question": {"type": "string"},
            "mechanism": {"type": "string"}, "minimal_evaluation": {"type": "string"},
            "source_ids": {"type": "array", "items": {"type": "string"}},
        }, "required": ["title", "research_question", "mechanism",
                         "minimal_evaluation", "source_ids"]}},
}, "required": ["ideas"]}

JUDGE_SYSTEM = """You are a conservative evaluator of candidate scientific ideas.
The ideas were produced under hidden experimental conditions. Judge each item only
against its supplied source contributions. Scores are integers 1-5. Grounding asks
whether source claims are used faithfully; coherence whether the combination makes
scientific sense; feasibility whether the minimal test is practicable; and corpus
non-redundancy whether the idea goes beyond merely restating its three sources.
This is not a claim of global novelty. Do not infer the hidden condition."""


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((a, b)))


def paper(cid: str) -> str:
    return cid.split("::")[0]


def graph(nodes: list[str], edges: list[tuple[str, str]]) -> nx.Graph:
    g = nx.Graph()
    g.add_nodes_from(nodes)
    for a, b in edges:
        if paper(a) != paper(b):
            g.add_edge(paper(a), paper(b), weight=g.get_edge_data(
                paper(a), paper(b), {"weight": 0})["weight"] + 1)
    return g


def partition(g: nx.Graph) -> dict[str, int]:
    groups = nx.community.greedy_modularity_communities(g, weight="weight")
    return {node: i for i, group in enumerate(groups) for node in group}


def prepare(seed: int = 61, n_seeds: int = 5,
            arms: tuple[str, ...] = ARMS, sampling: str = "stress") -> dict:
    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = grounded["contributions"]
    by_id = {x["id"]: x for x in contributions}
    pids = sorted({paper(x["id"]) for x in contributions})
    legacy_obj = json.loads((BUNDLE / "contributions_core_consensus.json").read_text())
    legacy = legacy_obj["edges"]
    enriched = load_jsonl(EDGE_OUT / "cartographer_rebuild_normalized.jsonl")

    legacy_pairs = [(x["src"], x["dst"]) for x in legacy]
    enriched_substantive = [(x["a"], x["b"]) for x in enriched
                            if x["relation"] not in {"none", "unclear"}]
    # Use every typed edge as an exclusion signal in this stress-test pilot.
    # Confidence thresholds can be ablated later; the text remains visible to judges.
    hard_pairs = {pair(x["a"], x["b"]) for x in enriched if x["relation"] in HARD}
    lg, eg = graph(pids, legacy_pairs), graph(pids, enriched_substantive)
    lp, ep = partition(lg), partition(eg)

    ids = [x["id"] for x in contributions]
    text = [x["statement"] for x in contributions]
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2),
                             min_df=1).fit_transform(text)
    sims = cosine_similarity(matrix)
    index = {cid: i for i, cid in enumerate(ids)}
    contribution_degree = Counter()
    for a, b in legacy_pairs:
        contribution_degree[a] += 1
        contribution_degree[b] += 1

    # Purposive manipulation check: one contribution from each large legacy
    # community whose closest semantic neighbourhood contains a typed edge.
    groups = defaultdict(list)
    for cid in ids:
        groups[lp.get(paper(cid), -1)].append(cid)
    ranked_groups = sorted(groups.values(), key=lambda xs: (-len({paper(x) for x in xs}), xs[0]))
    def stress_score(cid: str) -> tuple:
        i = index[cid]
        nearest = sorted((other for other in ids if paper(other) != paper(cid)),
                         key=lambda other: (-sims[i, index[other]], other))[:10]
        typed_ranks = [rank for rank, other in enumerate(nearest, 1)
                       if pair(cid, other) in hard_pairs]
        return (1 if typed_ranks else 0,
                -(min(typed_ranks) if typed_ranks else 999),
                max((sims[i, index[x]] for x in nearest
                     if pair(cid, x) in hard_pairs), default=0),
                contribution_degree[cid], -index[cid])

    if sampling == "stress":
        seeds = [max(xs, key=stress_score) for xs in ranked_groups[:n_seeds]]
    else:
        # Deterministic stratification across legacy communities. Within each
        # community, prefer contributions with some graph context, but do not
        # select on whether the enriched arm will look favourable.
        queues = [sorted(xs, key=lambda cid: (-contribution_degree[cid], cid))
                  for xs in ranked_groups]
        seeds = []
        while len(seeds) < n_seeds and any(queues):
            for queue in queues:
                if queue and len(seeds) < n_seeds:
                    seeds.append(queue.pop(0))

    def ranked(seed_id: str) -> list[str]:
        i = index[seed_id]
        return sorted((cid for cid in ids if paper(cid) != paper(seed_id)),
                      key=lambda cid: (-sims[i, index[cid]], cid))

    def choose(seed_id: str, arm: str) -> list[str]:
        if arm == "closed_box":
            return [seed_id]
        chosen = [seed_id]
        for cid in ranked(seed_id):
            if any(paper(cid) == paper(x) for x in chosen):
                continue
            if arm == "legacy" and any(lp.get(paper(cid)) == lp.get(paper(x)) for x in chosen):
                continue
            if arm == "enriched":
                if any(ep.get(paper(cid)) == ep.get(paper(x)) for x in chosen):
                    continue
                if any(pair(cid, x) in hard_pairs for x in chosen):
                    continue
            chosen.append(cid)
            if len(chosen) == 3:
                return chosen
        raise RuntimeError(f"could not construct {arm} packet for {seed_id}")

    packets = []
    for seed_id in seeds:
        for arm in arms:
            cids = choose(seed_id, arm)
            packets.append({
                "packet_id": hashlib.sha256(f"{seed}:{seed_id}:{arm}".encode()).hexdigest()[:12],
                "seed_id": seed_id, "arm": arm, "contribution_ids": cids,
                "pairwise_tfidf": [round(float(sims[index[a], index[b]]), 4)
                                   for i, a in enumerate(cids) for b in cids[i + 1:]],
                "legacy_communities": [lp.get(paper(x)) for x in cids],
                "enriched_communities": [ep.get(paper(x)) for x in cids],
                "hard_pairs": sum(pair(a, b) in hard_pairs
                                  for i, a in enumerate(cids) for b in cids[i + 1:]),
                "sources": [{"id": f"S{i}", "contribution_id": cid,
                             "statement": by_id[cid]["statement"]}
                            for i, cid in enumerate(cids, 1)],
            })
    overlaps = []
    for seed_id in seeds:
        rows = {x["arm"]: set(x["contribution_ids"][1:]) for x in packets
                if x["seed_id"] == seed_id}
        overlaps.append({"seed_id": seed_id, **{
            f"{a}_{b}": len(rows[a] & rows[b])
            for i, a in enumerate(arms) for b in arms[i + 1:]}})
    return {"schema_version": 1, "prompt_version": PROMPT_VERSION, "random_seed": seed,
            "n_seeds": len(seeds), "seeds": seeds, "packets": packets,
            "arms": list(arms),
            "sampling": ("purposive typed-edge stress test; not corpus-representative"
                         if sampling == "stress" else
                         "deterministic stratified sample across legacy communities"),
            "manipulation_check": {"partner_overlaps": overlaps}}


def append(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock, path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def generate(manifest: dict, model: str, workers: int) -> None:
    path = OUT / "generations.jsonl"
    done = {x["packet_id"] for x in load_jsonl(path)} if path.exists() else set()
    todo = [x for x in manifest["packets"] if x["packet_id"] not in done]
    lock = threading.Lock()

    def one(packet: dict) -> dict:
        sources = "\n\n".join(f"[{x['id']}] {x['statement']}" for x in packet["sources"])
        system = IDEA_SYSTEM
        if packet["arm"] == "closed_box":
            system = """You propose concrete research directions in AI-for-science.
You receive only a seed topic and no retrieved literature. Produce exactly three
distinct ideas informed by that seed and your internal knowledge. Each must state
a testable research question and a minimal evaluation. Do not claim global novelty,
invent citations, or imply that a literature search has been performed. Use S1 only
to identify the supplied seed topic."""
        result = llm.structured(model=model, system=system,
            user=f"SOURCE CONTRIBUTIONS:\n{sources}", schema=IDEA_SCHEMA,
            tool_name="emit_ideas", max_tokens=1400, retries=3, timeout=240)
        return {"packet_id": packet["packet_id"], "seed_id": packet["seed_id"],
                "arm": packet["arm"], "model": model,
                "prompt_version": PROMPT_VERSION, **result}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, x): x for x in todo}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            append(path, row, lock)
            print(f"generation {i}/{len(todo)} {row['packet_id']}", flush=True)


def judge(manifest: dict, model: str, workers: int, seed: int) -> None:
    generations = {x["packet_id"]: x for x in load_jsonl(OUT / "generations.jsonl")}
    path = OUT / os.environ.get("PRIOR_IDEATION_JUDGEMENTS", "judgements.jsonl")
    done = {x["seed_id"] for x in load_jsonl(path)} if path.exists() else set()
    seed_ids = [x for x in manifest["seeds"] if x not in done]
    lock = threading.Lock()

    def one(seed_id: str) -> dict:
        rng = random.Random(f"{seed}:{seed_id}")
        items = []
        source_lookup = {}
        for packet in (x for x in manifest["packets"] if x["seed_id"] == seed_id):
            source_lookup[packet["packet_id"]] = packet["sources"]
            for number, idea in enumerate(generations[packet["packet_id"]]["ideas"], 1):
                items.append({"key": f"{packet['packet_id']}:{number}", "idea": idea,
                              "sources": packet["sources"]})
        rng.shuffle(items)
        schema = {"type": "object", "properties": {"scores": {"type": "array",
            "items": {"type": "object", "properties": {
                "key": {"type": "string"},
                "grounding": {"type": "integer", "minimum": 1, "maximum": 5},
                "coherence": {"type": "integer", "minimum": 1, "maximum": 5},
                "feasibility": {"type": "integer", "minimum": 1, "maximum": 5},
                "corpus_nonredundancy": {"type": "integer", "minimum": 1, "maximum": 5},
                "reason": {"type": "string"}},
                "required": ["key", "grounding", "coherence", "feasibility",
                             "corpus_nonredundancy", "reason"]}}}, "required": ["scores"]}
        result = llm.structured(model=model, system=JUDGE_SYSTEM,
            user=json.dumps(items), schema=schema, tool_name="emit_scores",
            max_tokens=7000, retries=3, timeout=300)
        expected = {x["key"] for x in items}
        received = {x["key"] for x in result.get("scores", [])}
        metrics = ("grounding", "coherence", "feasibility", "corpus_nonredundancy")
        if expected != received or any(
                not isinstance(score.get(metric), int) or not 1 <= score[metric] <= 5
                for score in result.get("scores", []) for metric in metrics):
            raise ValueError(f"invalid score payload missing={expected-received} extra={received-expected}")
        arm_by_packet = {x["packet_id"]: x["arm"] for x in manifest["packets"]}
        for score in result["scores"]:
            score["arm"] = arm_by_packet[score["key"].split(":")[0]]
        return {"seed_id": seed_id, "model": model, "scores": result["scores"]}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(one, x): x for x in seed_ids}
        for i, future in enumerate(as_completed(futures), 1):
            row = future.result()
            append(path, row, lock)
            print(f"judge {i}/{len(seed_ids)} {row['seed_id']}", flush=True)


def summarize(manifest: dict) -> dict:
    generations = load_jsonl(OUT / "generations.jsonl")
    judgement_path = OUT / os.environ.get("PRIOR_IDEATION_JUDGEMENTS", "judgements.jsonl")
    judgements = load_jsonl(judgement_path) if judgement_path.exists() else []
    values = defaultdict(lambda: defaultdict(list))
    for row in judgements:
        for x in row["scores"]:
            for metric in ("grounding", "coherence", "feasibility", "corpus_nonredundancy"):
                values[x["arm"]][metric].append(x[metric])
    result = {"packets": len(manifest["packets"]),
              "ideas": sum(len(x.get("ideas", [])) for x in generations),
              "judged_ideas": sum(len(x["scores"]) for x in judgements),
              "means": {arm: {m: round(sum(v) / len(v), 3) for m, v in metrics.items()}
                        for arm, metrics in values.items()},
              "selection": {arm: {
                  "mean_pairwise_tfidf": round(sum(
                      (sum(x["pairwise_tfidf"]) / len(x["pairwise_tfidf"]))
                      if x["pairwise_tfidf"] else 0
                      for x in manifest["packets"] if x["arm"] == arm
                  ) / manifest["n_seeds"], 4),
                  "hard_pairs": sum(x["hard_pairs"] for x in manifest["packets"] if x["arm"] == arm),
              } for arm in manifest["arms"]},
              "caveat": "Corpus-relative pilot; LLM scores are screening evidence, not human validation or true novelty."}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("prepare", "generate", "judge", "all"), default="all")
    parser.add_argument("--seed", type=int, default=61)
    parser.add_argument("--n-seeds", type=int, default=5)
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--sampling", choices=("stress", "stratified"), default="stress")
    parser.add_argument("--use-existing-manifest", action="store_true")
    parser.add_argument("--model", default=config.CARTOGRAPHER_MODEL)
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.use_existing_manifest:
        manifest = json.loads((OUT / "manifest.json").read_text())
    else:
        manifest = prepare(args.seed, args.n_seeds, tuple(args.arms), args.sampling)
        (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({"seeds": manifest["seeds"],
                      "manipulation_check": manifest["manipulation_check"]}, indent=2))
    if args.stage == "prepare":
        return
    if args.stage in {"generate", "all"}:
        generate(manifest, args.model, args.workers)
    if args.stage in {"judge", "all"}:
        judge(manifest, args.model, args.workers, args.seed)
    print(json.dumps(summarize(manifest), indent=2))


if __name__ == "__main__":
    main()
