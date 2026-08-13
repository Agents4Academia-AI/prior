#!/usr/bin/env python3
"""Paired contribution-edge ablation: semantic vs context vs context+intent.

Sonnet labels each edge independently under three conditions. Opus then judges
the unique resulting assertions from the raw contribution and citation evidence,
blind to condition. Both phases are deterministic, checkpointed, and resumable.
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
RELATIONS = ["supports", "builds_on", "refines", "contradicts", "related", "none", "unclear"]

LABEL_SYSTEM = """Classify the relationship between exactly two extracted scientific
contributions using only the evidence supplied. Same topic is not enough.
- supports: materially compatible findings/evidence that corroborate one another
- builds_on: one explicitly uses or extends the other's method, artifact, or result
- refines: one qualifies, narrows, corrects, or makes the other more precise
- contradicts: the same construct/question has genuinely incompatible claims/findings
- related: substantive relationship, but none of the four types is defensible
- none: no substantive relationship established
- unclear: evidence is insufficient
For builds_on/refines, direction says which contribution acts on the other.
For supports/contradicts use symmetric. Citation contrast is not automatically
contradiction; background citation is not automatically a semantic relation."""

LABEL_SCHEMA = {"type": "object", "properties": {
    "relation": {"type": "string", "enum": RELATIONS},
    "direction": {"type": "string", "enum": ["a_to_b", "b_to_a", "symmetric", "none", "unclear"]},
    "confidence": {"type": "number"},
    "reason": {"type": "string"},
}, "required": ["relation", "direction", "confidence", "reason"]}

JUDGE_SYSTEM = """Audit an asserted relationship between two scientific contributions.
Use only the supplied contribution statements, source quotes, and raw citation passages.
Judge the asserted TYPE and DIRECTION together.
- correct: the assertion is defensible from the evidence
- wrong_type: a substantive relationship exists, but type or direction is wrong
- no_relation: no substantive contribution-level relationship is established
Be conservative. Topical similarity and background citation alone are insufficient.
Contrast is not automatically contradiction. Return one concise grounded reason."""

JUDGE_SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": ["correct", "wrong_type", "no_relation"]},
    "better_relation": {"type": "string", "enum": RELATIONS},
    "better_direction": {"type": "string", "enum": ["a_to_b", "b_to_a", "symmetric", "none", "unclear"]},
    "confidence": {"type": "number"},
    "reason": {"type": "string"},
}, "required": ["verdict", "better_relation", "better_direction", "confidence", "reason"]}


def pid(cid: str) -> str:
    return cid.split("::")[0]


def pkey(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def quote(c: dict) -> str:
    return (c.get("quote_verbatim") or c.get("quote") or c.get("evidence") or "")[:900]


def base_prompt(ca: dict, cb: dict) -> str:
    return (f"CONTRIBUTION A:\n{ca['statement']}\nSOURCE QUOTE A: {quote(ca)}\n\n"
            f"CONTRIBUTION B:\n{cb['statement']}\nSOURCE QUOTE B: {quote(cb)}")


def citation_prompt(citation: dict) -> str:
    direction = "A's paper cites B's paper" if citation["citing_id"] == citation["a_pid"] else "B's paper cites A's paper"
    sites = "\n\n".join(
        f"SITE {i}: {site.get('claim', '')[:1400]}"
        for i, site in enumerate(citation.get("sites", [])[:3], 1)
    )
    return f"CITATION DIRECTION: {direction}\nRAW CITATION PASSAGES:\n{sites}"


def load(population: str = "shared"):
    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contribs = grounded["contributions"] if isinstance(grounded, dict) else grounded
    by_id = {c["id"]: c for c in contribs}
    sem_obj = json.loads((BUNDLE / "contributions_core_consensus.json").read_text())
    sem_edges = sem_obj["edges"] if isinstance(sem_obj, dict) else sem_obj
    intent = json.loads((OUT / "citations_intent.json").read_text())["edges"]
    citations = {pkey(e["citing_id"], e["cited_id"]): e for e in intent}
    citation_nodes = {node for key in citations for node in key.split("|")}
    eligible = []
    for i, edge in enumerate(sem_edges):
        a, b = pid(edge["src"]), pid(edge["dst"])
        key = pkey(a, b)
        in_population = (
            key in citations if population == "shared"
            else key not in citations and a in citation_nodes and b in citation_nodes
        )
        if a != b and in_population and edge["src"] in by_id and edge["dst"] in by_id:
            cit = ({**citations[key], "a_pid": a, "b_pid": b}
                   if key in citations else None)
            eligible.append({"edge_id": f"e{i}:{edge['src']}->{edge['dst']}", "edge": edge,
                             "ca": by_id[edge["src"]], "cb": by_id[edge["dst"]],
                             "pair": key, "citation": cit,
                             "intent": cit["intent"] if cit else None})
    return eligible


def stratified_sample(items: list[dict], n: int, seed: int,
                      *, unique_pairs: bool = True) -> list[dict]:
    rng = random.Random(seed)
    groups = defaultdict(list)
    for item in items:
        groups[(item["edge"]["relation"], item["intent"])].append(item)
    for values in groups.values():
        rng.shuffle(values)
    strata = list(groups)
    rng.shuffle(strata)
    picked, used_pairs = [], set()
    while len(picked) < n:
        progress = False
        for stratum in strata:
            while (unique_pairs and groups[stratum]
                   and groups[stratum][0]["pair"] in used_pairs):
                groups[stratum].pop(0)
            if groups[stratum] and len(picked) < n:
                item = groups[stratum].pop(0)
                picked.append(item)
                if unique_pairs:
                    used_pairs.add(item["pair"])
                progress = True
        if not progress:
            break
    return picked


def read_jsonl(path: Path, key_field: str) -> dict:
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row[key_field]] = row
    return rows


def append_jsonl(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock, path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--seed", type=int, default=31)
    ap.add_argument("--label-model", default="sonnet")
    ap.add_argument("--judge-model", default="opus")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--conditions", nargs="+", choices=["S", "SC", "SCI"],
                    default=["S", "SC", "SCI"])
    ap.add_argument("--population", choices=["shared", "semantic_only"], default="shared")
    ap.add_argument("--allow-repeated-pairs", action="store_true",
                    help="sample contribution edges independently, including multiple edges per paper pair")
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()

    sample = stratified_sample(load(args.population), args.n, args.seed,
                               unique_pairs=not args.allow_repeated_pairs)
    run_name = f"{args.population}_rebuild_seed{args.seed}_n{args.n}"
    manifest_path = OUT / f"{run_name}_sample.json"
    manifest = [{"edge_id": x["edge_id"], "pair": x["pair"],
                 "current_relation": x["edge"]["relation"], "intent": x["intent"],
                 "src": x["edge"]["src"], "dst": x["edge"]["dst"]} for x in sample]
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print("sample strata:", dict(Counter((x["edge"]["relation"], x["intent"]) for x in sample)))
    print("->", manifest_path)
    if args.prepare_only:
        return

    conditions = args.conditions
    pred_path = OUT / f"{run_name}_predictions.jsonl"
    predictions = read_jsonl(pred_path, "task_key")
    tasks = [(x, condition) for x in sample for condition in conditions
             if f"{x['edge_id']}|{condition}" not in predictions]
    rng = random.Random(args.seed + 1)
    rng.shuffle(tasks)
    lock = threading.Lock()

    def label(item: dict, condition: str) -> dict:
        user = base_prompt(item["ca"], item["cb"])
        if condition in ("SC", "SCI") and item["citation"]:
            user += "\n\n" + citation_prompt(item["citation"])
        if condition == "SCI" and item["intent"]:
            user += f"\n\nINDEPENDENT CITATION-INTENT LABEL: {item['intent']}"
        out = llm.structured(model=args.label_model, system=LABEL_SYSTEM, user=user,
                             schema=LABEL_SCHEMA, tool_name="emit_relation",
                             max_tokens=450, timeout=args.timeout, retries=3)
        return {"task_key": f"{item['edge_id']}|{condition}", "edge_id": item["edge_id"],
                "condition": condition, "current_relation": item["edge"]["relation"],
                "callum_intent": item["intent"], **out}

    print(f"label phase: {len(tasks)} remaining / {len(sample)*3}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(label, *task): task for task in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"label [{i}/{len(tasks)}] ERROR: {exc}", flush=True)
                continue
            append_jsonl(pred_path, row, lock)
            predictions[row["task_key"]] = row
            print(f"label [{i}/{len(tasks)}] {row['condition']} {row['relation']}", flush=True)

    # Judge each unique assertion for an edge once; reuse it if conditions agree.
    judge_path = OUT / f"{run_name}_judgements.jsonl"
    judgements = read_jsonl(judge_path, "assertion_key")
    assertion_tasks = {}
    item_by_id = {x["edge_id"]: x for x in sample}
    for pred in predictions.values():
        assertion_key = f"{pred['edge_id']}|{pred['relation']}|{pred['direction']}"
        assertion_tasks[assertion_key] = pred
    todo = [(key, pred) for key, pred in assertion_tasks.items() if key not in judgements]
    rng.shuffle(todo)

    def judge(assertion_key: str, pred: dict) -> dict:
        item = item_by_id[pred["edge_id"]]
        user = base_prompt(item["ca"], item["cb"])
        if item["citation"]:
            user += "\n\n" + citation_prompt(item["citation"])
        user += f"\n\nASSERTED RELATION: {pred['relation']}\nASSERTED DIRECTION: {pred['direction']}"
        out = llm.structured(model=args.judge_model, system=JUDGE_SYSTEM, user=user,
                             schema=JUDGE_SCHEMA, tool_name="emit_judgement",
                             max_tokens=450, timeout=args.timeout, retries=3)
        return {"assertion_key": assertion_key, "edge_id": pred["edge_id"],
                "asserted_relation": pred["relation"], "asserted_direction": pred["direction"], **out}

    print(f"judge phase: {len(todo)} unique assertions remaining / {len(assertion_tasks)}")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(judge, *task): task for task in todo}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"judge [{i}/{len(todo)}] ERROR: {exc}", flush=True)
                continue
            append_jsonl(judge_path, row, lock)
            judgements[row["assertion_key"]] = row
            print(f"judge [{i}/{len(todo)}] {row['asserted_relation']}: {row['verdict']}", flush=True)

    rows = []
    for pred in predictions.values():
        assertion_key = f"{pred['edge_id']}|{pred['relation']}|{pred['direction']}"
        if assertion_key in judgements:
            judged = {f"judge_{k}": v for k, v in judgements[assertion_key].items()
                      if k not in ("edge_id", "assertion_key")}
            # For an asserted `none`, the judge's `no_relation` verdict confirms
            # rather than rejects the assertion. Keep the raw verdict and score
            # this combination as correct in condition comparisons.
            raw_verdict = judged.get("judge_verdict")
            judged["judge_effective_verdict"] = (
                "correct" if pred["relation"] == "none" and raw_verdict == "no_relation"
                else raw_verdict
            )
            rows.append({**pred, **judged})
    verdict_score = {"no_relation": 0, "wrong_type": 1, "correct": 2}
    summary = {"n_edges": len(sample), "conditions": {}, "paired": {}}
    for condition in conditions:
        sub = [r for r in rows if r["condition"] == condition]
        vc = Counter(r["judge_effective_verdict"] for r in sub)
        summary["conditions"][condition] = {
            "n": len(sub), "predictions": dict(Counter(r["relation"] for r in sub)),
            "verdicts": dict(vc),
            "correct_rate": round(vc["correct"] / len(sub), 3) if sub else None,
            "mean_label_confidence": round(sum(r["confidence"] for r in sub) / len(sub), 3) if sub else None,
        }
    by_edge = defaultdict(dict)
    for row in rows:
        by_edge[row["edge_id"]][row["condition"]] = row
    for left, right in (("S", "SC"), ("SC", "SCI"), ("S", "SCI")):
        comparable = [d for d in by_edge.values() if left in d and right in d]
        delta = [verdict_score[d[right]["judge_effective_verdict"]] - verdict_score[d[left]["judge_effective_verdict"]]
                 for d in comparable]
        summary["paired"][f"{left}_to_{right}"] = {
            "n": len(delta), "improved": sum(x > 0 for x in delta),
            "worsened": sum(x < 0 for x in delta), "unchanged": sum(x == 0 for x in delta),
            "label_changed": sum(d[left]["relation"] != d[right]["relation"] or
                                 d[left]["direction"] != d[right]["direction"] for d in comparable),
        }
    summary_path = OUT / f"{run_name}_summary.json"
    detail_path = OUT / f"{run_name}_results.json"
    summary_path.write_text(json.dumps(summary, indent=1))
    detail_path.write_text(json.dumps(rows, indent=1))
    print(json.dumps(summary, indent=1))
    print("->", summary_path, detail_path)


if __name__ == "__main__":
    main()
