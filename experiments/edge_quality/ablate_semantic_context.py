#!/usr/bin/env python3
"""Controlled evidence-depth ablation for semantic-only contribution edges.

The same frozen edge pairs are labelled under four increasingly rich conditions:
C   contribution statements only
CQ  contribution statements plus their extraction source quotes
R   CQ plus deterministic, relation-oriented passages retrieved from both papers
F   CQ plus chunked full-paper context (within a fixed per-paper character cap)

Every condition must cite supplied evidence IDs. An independent judge receives the
full-paper packets and scores existence, type, direction, and evidence sufficiency
separately. Outputs are append-only JSONL so a subscription-backed run can resume.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
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
DEFAULT_FULLTEXT = Path("/Users/kk1918_1/Desktop/Projects/hackathon/prior/data_hackathon/fulltext")
RELATIONS = ["supports", "builds_on", "refines", "contradicts", "related", "none", "unclear"]

SYSTEM = """Classify the relationship between exactly two extracted scientific
contributions using only the supplied evidence. Same topic is not enough.
- supports: comparable findings/evidence materially corroborate one another
- builds_on: one explicitly uses or extends the other's method, artifact, or result
- refines: one qualifies, narrows, corrects, or makes the other more precise
- contradicts: the same construct/question has genuinely incompatible findings
- related: a substantive relationship exists but no stronger type is defensible
- none: no substantive relationship is established
- unclear: the available evidence is insufficient
For builds_on/refines, state direction; supports/contradicts are symmetric.
Return the exact evidence IDs that establish the relation. If no supplied passage
establishes a hard type, use related, none, or unclear rather than extrapolating."""

LABEL_SCHEMA = {"type": "object", "properties": {
    "relation": {"type": "string", "enum": RELATIONS},
    "direction": {"type": "string", "enum": ["a_to_b", "b_to_a", "symmetric", "none", "unclear"]},
    "existence_confidence": {"type": "number"},
    "type_confidence": {"type": "number"},
    "evidence_ids": {"type": "array", "items": {"type": "string"}},
    "reason": {"type": "string"},
}, "required": ["relation", "direction", "existence_confidence", "type_confidence", "evidence_ids", "reason"]}

JUDGE_SYSTEM = """Audit a proposed relationship using the supplied full-paper
evidence packet. Score four questions independently: whether a substantive relation
exists, whether its type is defensible, whether direction is defensible, and whether
the cited evidence suffices. Do not reward plausible claims unsupported by the text.
Topical similarity is not a hard relation. `related` is itself a valid type: mark
type_correct=yes when `related` is the best defensible label, even though no hard
epistemic type is established. For `related`, direction is not applicable and must
not affect type correctness. If type_correct=no, better_relation MUST differ from
the proposed relation. Return a conservative better label."""

JUDGE_SCHEMA = {"type": "object", "properties": {
    "existence": {"type": "string", "enum": ["yes", "no", "unclear"]},
    "type_correct": {"type": "string", "enum": ["yes", "no", "not_applicable", "unclear"]},
    "direction_correct": {"type": "string", "enum": ["yes", "no", "not_applicable", "unclear"]},
    "evidence_sufficient": {"type": "string", "enum": ["yes", "no", "unclear"]},
    "better_relation": {"type": "string", "enum": RELATIONS},
    "better_direction": {"type": "string", "enum": ["a_to_b", "b_to_a", "symmetric", "none", "unclear"]},
    "confidence": {"type": "number"},
    "reason": {"type": "string"},
}, "required": ["existence", "type_correct", "direction_correct", "evidence_sufficient",
                 "better_relation", "better_direction", "confidence", "reason"]}


def paper_id(cid: str) -> str:
    return cid.split("::")[0]


def safe_id(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", pid)


def source_quote(c: dict) -> str:
    return (c.get("quote_verbatim") or c.get("quote") or c.get("evidence") or "").strip()


def chunks(text: str, prefix: str, size: int = 1400) -> list[tuple[str, str]]:
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paras) < 8:  # flattened HTML/PDF text: use overlapping character windows
        paras = [re.sub(r"\s+", " ", text[i:i + size]).strip()
                 for i in range(0, len(text), size - 250)]
    return [(f"{prefix}{i:03d}", p[:size]) for i, p in enumerate(paras) if len(p) > 80]


def terms(text: str) -> list[str]:
    stop = {"the", "and", "for", "that", "with", "this", "from", "using", "into", "their", "paper",
            "method", "results", "study", "model", "based", "are", "was", "were", "has", "have"}
    return [w for w in re.findall(r"[a-z][a-z0-9-]{2,}", text.lower()) if w not in stop]


def retrieve(all_chunks: list[tuple[str, str]], query: str, k: int = 8) -> list[tuple[str, str]]:
    q = Counter(terms(query))
    n = len(all_chunks)
    df = Counter()
    docs = []
    for cid, text in all_chunks:
        tf = Counter(terms(text))
        docs.append((cid, text, tf))
        df.update(tf.keys())
    scored = []
    for cid, text, tf in docs:
        score = sum(q[t] * tf[t] * math.log((n + 1) / (df[t] + 1)) for t in q)
        relation_bonus = sum(tf[t] for t in ("compare", "compared", "unlike", "extends", "improves",
                                              "limitation", "contrary", "consistent", "outperform"))
        scored.append((score + 0.25 * relation_bonus, cid, text))
    return [(cid, text) for _, cid, text in sorted(scored, reverse=True)[:k]]


def render(items: list[tuple[str, str]]) -> str:
    return "\n\n".join(f"[{cid}] {text}" for cid, text in items)


def read_jsonl(path: Path, key: str) -> dict:
    out = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                out[row[key]] = row
    return out


def append_jsonl(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock, path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=47)
    ap.add_argument("--conditions", nargs="+", choices=["C", "CQ", "R", "F"], default=["C", "CQ", "R", "F"])
    ap.add_argument("--label-model", default="sonnet")
    ap.add_argument("--judge-model", default="opus")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--fulltext-dir", type=Path, default=DEFAULT_FULLTEXT)
    ap.add_argument("--fulltext-chars", type=int, default=48000)
    ap.add_argument("--prepare-only", action="store_true")
    ap.add_argument("--labels-only", action="store_true",
                    help="stop after the label phase; use this before selecting costly judge calls")
    ap.add_argument("--judge-policy", choices=["all", "relation_disagreements", "full_only"], default="all",
                    help="judge all outputs, or all conditions only where relation labels differ and F otherwise")
    ap.add_argument("--judge-output-tag", default="",
                    help="write a separate judgement file, e.g. opus, without overwriting prior audits")
    args = ap.parse_args()

    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    cs = grounded["contributions"] if isinstance(grounded, dict) else grounded
    by_id = {c["id"]: c for c in cs}
    frozen = json.loads((OUT / "semantic_only_rebuild_seed31_n438_sample.json").read_text())
    eligible = [x for x in frozen if x["src"] in by_id and x["dst"] in by_id and
                all((args.fulltext_dir / f"{safe_id(p)}.txt").exists() for p in x["pair"].split("|"))]
    groups = defaultdict(list)
    for x in eligible:
        groups[x["current_relation"]].append(x)
    rng = random.Random(args.seed)
    for g in groups.values():
        rng.shuffle(g)
    # Round-robin preserves rare original hard types without claiming they are true.
    sample, used_pairs = [], set()
    order = ["contradicts", "refines", "builds_on", "supports"]
    while len(sample) < args.n:
        progress = False
        for rel in order:
            while groups[rel] and groups[rel][0]["pair"] in used_pairs:
                groups[rel].pop(0)
            if groups[rel] and len(sample) < args.n:
                x = groups[rel].pop(0)
                sample.append(x); used_pairs.add(x["pair"]); progress = True
        if not progress:
            break

    run = f"semantic_context_seed{args.seed}_n{len(sample)}"
    packets = {}
    manifest = []
    for x in sample:
        ca, cb = by_id[x["src"]], by_id[x["dst"]]
        ta = (args.fulltext_dir / f"{safe_id(paper_id(x['src']))}.txt").read_text(errors="replace")
        tb = (args.fulltext_dir / f"{safe_id(paper_id(x['dst']))}.txt").read_text(errors="replace")
        ac, bc = chunks(ta[:args.fulltext_chars], "A"), chunks(tb[:args.fulltext_chars], "B")
        query = ca["statement"] + " " + cb["statement"]
        packets[x["edge_id"]] = {"ca": ca, "cb": cb, "ac": ac, "bc": bc,
                                  "retrieved": retrieve(ac, query) + retrieve(bc, query)}
        manifest.append({**x, "fulltext_chars": args.fulltext_chars,
                         "paper_a_chars_available": len(ta), "paper_b_chars_available": len(tb)})
    (OUT / f"{run}_sample.json").write_text(json.dumps(manifest, indent=1))
    print("sample:", Counter(x["current_relation"] for x in sample), "->", run, flush=True)
    if args.prepare_only:
        return

    pred_path = OUT / f"{run}_predictions.jsonl"
    predictions = read_jsonl(pred_path, "task_key")
    tasks = [(x, c) for x in sample for c in args.conditions if f"{x['edge_id']}|{c}" not in predictions]
    rng.shuffle(tasks)
    lock = threading.Lock()

    def prompt(x: dict, condition: str) -> str:
        p = packets[x["edge_id"]]; ca, cb = p["ca"], p["cb"]
        base = f"CONTRIBUTION A [CA]: {ca['statement']}\nCONTRIBUTION B [CB]: {cb['statement']}"
        if condition in ("CQ", "R", "F"):
            base += f"\n\n[AQ] {source_quote(ca)[:1200]}\n\n[BQ] {source_quote(cb)[:1200]}"
        if condition == "R":
            base += "\n\nRETRIEVED FULL-TEXT PASSAGES:\n" + render(p["retrieved"])
        if condition == "F":
            base += "\n\nPAPER A FULL-TEXT PACKET:\n" + render(p["ac"])
            base += "\n\nPAPER B FULL-TEXT PACKET:\n" + render(p["bc"])
        return base

    def label(x: dict, condition: str) -> dict:
        out = llm.structured(model=args.label_model, system=SYSTEM, user=prompt(x, condition),
                             schema=LABEL_SCHEMA, tool_name="emit_relation", max_tokens=600,
                             timeout=args.timeout, retries=3)
        return {"task_key": f"{x['edge_id']}|{condition}", "edge_id": x["edge_id"],
                "condition": condition, "current_relation": x["current_relation"], **out}

    print(f"label phase: {len(tasks)} remaining", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fs = {pool.submit(label, *t): t for t in tasks}
        for i, f in enumerate(as_completed(fs), 1):
            try:
                row = f.result(); append_jsonl(pred_path, row, lock); predictions[row["task_key"]] = row
                print(f"label [{i}/{len(tasks)}] {row['condition']} {row['relation']}", flush=True)
            except Exception as exc: print(f"label [{i}/{len(tasks)}] ERROR {exc}", flush=True)

    if args.labels_only:
        summary = {c: dict(Counter(
            p["relation"] for p in predictions.values() if p["condition"] == c
        )) for c in args.conditions}
        print(json.dumps({"n_predictions": len(predictions), "relations": summary}, indent=2), flush=True)
        return

    tag = f"_{args.judge_output_tag}" if args.judge_output_tag else ""
    judge_path = OUT / f"{run}_judgements{tag}.jsonl"
    judgements = read_jsonl(judge_path, "task_key")
    selected = list(predictions.values())
    if args.judge_policy == "relation_disagreements":
        by_edge = defaultdict(list)
        for pred in selected:
            by_edge[pred["edge_id"]].append(pred)
        selected = []
        for edge_preds in by_edge.values():
            if len({p["relation"] for p in edge_preds}) > 1:
                selected.extend(edge_preds)
            else:
                selected.extend(p for p in edge_preds if p["condition"] == "F")
    elif args.judge_policy == "full_only":
        selected = [p for p in selected if p["condition"] == "F"]
    todo = [p for p in selected if p["task_key"] not in judgements]

    def judge(pred: dict) -> dict:
        x = next(y for y in sample if y["edge_id"] == pred["edge_id"])
        p = packets[x["edge_id"]]
        cited = set(pred.get("evidence_ids", []))
        evidence = [(cid, txt) for cid, txt in p["ac"] + p["bc"] if cid in cited]
        # Never expose the legacy Prior label or task metadata to the verifier.
        proposal = {k: pred[k] for k in ("relation", "direction", "existence_confidence",
                                          "type_confidence", "evidence_ids", "reason") if k in pred}
        user = prompt(x, "F") + "\n\nPROPOSAL:\n" + json.dumps(proposal) + \
               "\n\nCITED PASSAGES (resolved):\n" + render(evidence)
        out = llm.structured(model=args.judge_model, system=JUDGE_SYSTEM, user=user,
                             schema=JUDGE_SCHEMA, tool_name="emit_audit", max_tokens=650,
                             timeout=args.timeout, retries=3)
        return {"task_key": pred["task_key"], "edge_id": pred["edge_id"],
                "condition": pred["condition"], **out}

    print(f"judge phase: {len(todo)} remaining", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fs = {pool.submit(judge, p): p for p in todo}
        for i, f in enumerate(as_completed(fs), 1):
            try:
                row = f.result(); append_jsonl(judge_path, row, lock); judgements[row["task_key"]] = row
                print(f"judge [{i}/{len(todo)}] {row['condition']} {row['type_correct']}", flush=True)
            except Exception as exc: print(f"judge [{i}/{len(todo)}] ERROR {exc}", flush=True)

    summary = {"run": run, "n_edges": len(sample), "conditions": {}}
    for c in args.conditions:
        ps = [p for p in predictions.values() if p["condition"] == c]
        js = [judgements[p["task_key"]] for p in ps if p["task_key"] in judgements]
        summary["conditions"][c] = {
            "n_predictions": len(ps), "relations": dict(Counter(p["relation"] for p in ps)),
            "n_judged": len(js), "existence": dict(Counter(j["existence"] for j in js)),
            "type_correct": dict(Counter(j["type_correct"] for j in js)),
            "direction_correct": dict(Counter(j["direction_correct"] for j in js)),
            "evidence_sufficient": dict(Counter(j["evidence_sufficient"] for j in js)),
        }
    (OUT / f"{run}_summary{tag}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
