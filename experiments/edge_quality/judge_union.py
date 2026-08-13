#!/usr/bin/env python3
"""Blind diagnostic judge over semantic-only, citation-only, and shared pairs.

The judge never sees Prior's asserted semantic relation or Callum's intent label.
It first judges the papers from their extracted contributions, then separately
reports what an available citation passage establishes. Sampling and outputs are
deterministic, checkpointed, and resumable.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import llm  # noqa: E402

OUT = Path(__file__).parent / "out"
BUNDLE = ROOT / "data" / "prior-core-v0.2"

SYSTEM = """You are independently auditing two graphs of scientific literature.
Judge only from the supplied paper titles, extracted contributions, verbatim source
quotes, and (when present) citation passages. Do not use outside knowledge.

First assess whether the papers' CONTRIBUTIONS have a substantive cross-paper
relationship. Same broad topic is not enough. Choose one best label:
- supports: materially compatible findings or evidence that corroborate each other
- builds_on: one contribution explicitly uses or extends the other's work
- refines: one qualifies, narrows, corrects, or makes the other more precise
- contradicts: same construct/question with genuinely incompatible claims/findings
- related: substantive relationship exists but none of the four types is defensible
- none: no substantive contribution-level relationship is established

Then, if citation passages are present, assess them separately. A citation is a fact;
its intent and evidential value are inferences. A background citation need not imply a
contribution relation, and compare/contrast is not automatically contradiction.
Return concise reasons grounded in the supplied text. Abstain with unclear when needed."""

SCHEMA = {
    "type": "object",
    "properties": {
        "contribution_relation": {
            "type": "string",
            "enum": ["supports", "builds_on", "refines", "contradicts", "related", "none", "unclear"],
        },
        "direction": {
            "type": "string",
            "enum": ["a_to_b", "b_to_a", "symmetric", "unclear", "none"],
        },
        "relation_confidence": {"type": "number"},
        "relation_reason": {"type": "string"},
        "citation_intent": {
            "type": "string",
            "enum": ["background", "uses_extends", "compares_contrasts", "mixed", "no_citation", "unclear"],
        },
        "citation_support": {
            "type": "string",
            "enum": ["supports", "partial", "does_not", "inconclusive", "no_citation"],
        },
        "citation_changes_relation_assessment": {
            "type": "string",
            "enum": ["strengthens", "weakens", "changes_type", "no_change", "no_citation", "unclear"],
        },
        "citation_reason": {"type": "string"},
    },
    "required": [
        "contribution_relation", "direction", "relation_confidence", "relation_reason",
        "citation_intent", "citation_support", "citation_changes_relation_assessment",
        "citation_reason",
    ],
}


def paper_id(contribution_id: str) -> str:
    return contribution_id.split("::")[0]


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def load_data():
    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = grounded["contributions"] if isinstance(grounded, dict) else grounded
    by_paper = defaultdict(list)
    for contribution in contributions:
        by_paper[contribution["paper_id"]].append(contribution)

    consensus = json.loads((BUNDLE / "contributions_core_consensus.json").read_text())
    semantic_edges = consensus["edges"] if isinstance(consensus, dict) else consensus
    semantic = defaultdict(list)
    for edge in semantic_edges:
        a, b = paper_id(edge["src"]), paper_id(edge["dst"])
        if a != b:
            semantic[pair_key(a, b)].append(edge)

    intent_obj = json.loads((OUT / "citations_intent.json").read_text())
    typed_obj = json.loads((OUT / "citations_typed.json").read_text())
    typed = {(e["citing_id"], e["cited_id"]): e for e in typed_obj["edges"]}
    citations = {}
    for edge in intent_obj["edges"]:
        a, b = edge["citing_id"], edge["cited_id"]
        citations[pair_key(a, b)] = {
            **edge,
            "typed": typed.get((a, b), {}),
        }

    papers = {}
    for line in (BUNDLE / "papers_core.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            papers[row["id"]] = row
    return papers, by_paper, semantic, citations


def render_contributions(items: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(items[:6], 1):
        quote = c.get("quote_verbatim") or c.get("quote") or c.get("evidence") or ""
        blocks.append(f"{i}. {c['statement']}\n   SOURCE QUOTE: {quote[:700]}")
    return "\n".join(blocks) or "(no extracted contribution available)"


def build_user(a: str, b: str, papers, by_paper, citation: dict | None) -> str:
    pa, pb = papers.get(a, {}), papers.get(b, {})
    parts = [
        f"PAPER A: {pa.get('title', a)}\nCONTRIBUTIONS A:\n{render_contributions(by_paper[a])}",
        f"PAPER B: {pb.get('title', b)}\nCONTRIBUTIONS B:\n{render_contributions(by_paper[b])}",
    ]
    if citation:
        citing = citation["citing_id"]
        orientation = "A cites B" if citing == a else "B cites A"
        sites = citation.get("sites", [])[:3]
        passages = "\n\n".join(
            f"SITE {i}: {s.get('claim', '')[:1200]}" for i, s in enumerate(sites, 1)
        )
        parts.append(f"CITATION DIRECTION: {orientation}\nCITATION PASSAGES:\n{passages}")
    else:
        parts.append("CITATION PASSAGES: none supplied")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-region", type=int, default=15)
    parser.add_argument("--seed", type=int, default=23)
    parser.add_argument("--model", default="opus")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    papers, by_paper, semantic, citations = load_data()
    cit_keys = set(citations)
    citation_nodes = {node for key in cit_keys for node in key.split("|")}
    # Hold the node set fixed to the 116 papers represented in Callum's
    # contextualized citation graph. Otherwise "semantic only" silently includes
    # pairs involving the other 36 atlas papers and the regions are incomparable.
    sem_keys = {
        key for key in semantic
        if all(node in citation_nodes for node in key.split("|"))
    }
    regions = {
        "semantic_only": sorted(sem_keys - cit_keys),
        "citation_only": sorted(cit_keys - sem_keys),
        "both": sorted(sem_keys & cit_keys),
    }
    rng = random.Random(args.seed)
    sample = []
    for region, keys in regions.items():
        picked = rng.sample(keys, min(args.per_region, len(keys)))
        for key in picked:
            a, b = key.split("|")
            sample.append({
                "key": key,
                "region": region,
                "a": a,
                "b": b,
                "semantic_edges": semantic.get(key, []),
                "citation": citations.get(key),
            })

    manifest = OUT / f"union_judge_sample_seed{args.seed}_n{args.per_region}.json"
    manifest.write_text(json.dumps(sample, indent=1))
    print("regions:", {k: len(v) for k, v in regions.items()})
    print("sample:", dict(Counter(x["region"] for x in sample)), "->", manifest)
    if args.prepare_only:
        return

    checkpoint = OUT / f"union_judgements_seed{args.seed}_n{args.per_region}.jsonl"
    done = {}
    if checkpoint.exists():
        for line in checkpoint.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                done[row["key"]] = row
    todo = [x for x in sample if x["key"] not in done]
    print(f"to judge: {len(todo)} (already done: {len(done)})")
    lock = threading.Lock()

    def judge(item: dict) -> dict:
        result = llm.structured(
            model=args.model,
            system=SYSTEM,
            user=build_user(item["a"], item["b"], papers, by_paper, item["citation"]),
            schema=SCHEMA,
            tool_name="emit_union_verdict",
            max_tokens=700,
            timeout=args.timeout,
            retries=3,
        )
        current_types = sorted({e["relation"] for e in item["semantic_edges"]})
        callum_intent = item["citation"].get("intent") if item["citation"] else None
        callum_support = item["citation"].get("typed", {}).get("support") if item["citation"] else None
        return {
            "key": item["key"], "region": item["region"],
            "current_semantic_types": current_types,
            "callum_intent": callum_intent, "callum_support": callum_support,
            **result,
        }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(judge, item): item for item in todo}
        for n, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[{n}/{len(todo)}] ERROR {item['key']}: {exc}", flush=True)
                continue
            with lock, checkpoint.open("a") as handle:
                handle.write(json.dumps(row) + "\n")
            print(f"[{n}/{len(todo)}] {row['region']}: {row['contribution_relation']}", flush=True)

    rows = [json.loads(line) for line in checkpoint.read_text().splitlines() if line.strip()]
    summary = {}
    for region in regions:
        subset = [r for r in rows if r["region"] == region]
        if not subset:
            continue
        relations = Counter(r["contribution_relation"] for r in subset)
        current_match = sum(
            r["contribution_relation"] in r["current_semantic_types"] for r in subset
            if r["current_semantic_types"]
        )
        with_sem = sum(bool(r["current_semantic_types"]) for r in subset)
        summary[region] = {
            "n": len(subset),
            "judge_relations": dict(relations),
            "substantive_rate": round(sum(r["contribution_relation"] not in ("none", "unclear") for r in subset) / len(subset), 3),
            "current_type_exact_match": round(current_match / with_sem, 3) if with_sem else None,
            "citation_changes": dict(Counter(r["citation_changes_relation_assessment"] for r in subset)),
            "intent_agreement": round(sum(r["citation_intent"] == r["callum_intent"] for r in subset if r["callum_intent"]) /
                                      max(1, sum(bool(r["callum_intent"]) for r in subset)), 3),
        }
    summary_path = OUT / f"union_judge_summary_seed{args.seed}_n{args.per_region}.json"
    summary_path.write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    print("->", summary_path)


if __name__ == "__main__":
    main()
