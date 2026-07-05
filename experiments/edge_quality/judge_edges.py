#!/usr/bin/env python3
"""Blind LLM judging of relation edges, identical rubric for every arm.

For a sampled edge the judge sees ONLY the two contributions (statement +
verbatim quote) and the asserted relation type — never which arm produced it.
Verdicts:
  correct      — the asserted type genuinely holds, defensible from the texts
  wrong_type   — the contributions are related, but the asserted type is wrong
  no_relation  — no defensible relation between them at all

Judge model deliberately differs from the labeler (default: claude-opus-4-8).
Checkpointed JSONL; resumable. Emits per-arm accuracy + contradiction-subset
precision.

Usage:
  PRIOR_LLM_BACKEND=claude-cli python3 experiments/edge_quality/judge_edges.py \
      --bundle ../prior-core-v0.2 --arms A B C [--sample 250] [--seed 7]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prior import llm  # noqa: E402

OUT = Path(__file__).parent / "out"

SYSTEM = """You are auditing a literature knowledge graph. Given two research
contributions (each with a verbatim quote from its paper) and an ASSERTED
relation between them, judge the assertion strictly from the texts:
  correct      — the asserted relation type genuinely holds
  wrong_type   — the two are related, but the asserted type is wrong
  no_relation  — there is no defensible relation between them
Novelty framing ("unlike prior work...") is NOT a contradiction. Same broad
topic alone is NOT a relation. Give a one-line reason."""

SCHEMA = {"type": "object", "properties": {
    "verdict": {"type": "string", "enum": ["correct", "wrong_type", "no_relation"]},
    "better_type": {"type": "string"},
    "reason": {"type": "string"}}, "required": ["verdict", "reason"]}


def load_bundle(d: Path):
    obj = json.load(open(d / "contributions_core_grounded.json"))
    contribs = obj["contributions"] if isinstance(obj, dict) else obj
    obj = json.load(open(d / "contributions_core_consensus.json"))
    a_edges = obj["edges"] if isinstance(obj, dict) else obj
    return {c["id"]: c for c in contribs}, a_edges


def edges_of(arm: str, a_edges) -> list[dict]:
    if arm == "A":
        return [{"src": e["src"], "dst": e["dst"], "relation": e["relation"], "arm": "A"}
                for e in a_edges if e["src"] != e["dst"]]
    f = OUT / f"arm{arm}_edges.json"
    return json.load(open(f))["edges"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--arms", nargs="+", default=["A", "B", "C"])
    ap.add_argument("--sample", type=int, default=250, help="edges judged per arm")
    ap.add_argument("--all-contradicts", action="store_true", default=True,
                    help="always judge every contradicts edge (the headline subset)")
    ap.add_argument("--model", default="claude-opus-4-8")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("PRIOR_MAP_WORKERS", "6")))
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    by_id, a_edges = load_bundle(Path(args.bundle))
    rng = random.Random(args.seed)

    tasks = []
    for arm in args.arms:
        edges = [e for e in edges_of(arm, a_edges)
                 if e["src"] in by_id and e["dst"] in by_id
                 and by_id[e["src"]]["paper_id"] != by_id[e["dst"]]["paper_id"]]
        contra = [e for e in edges if e["relation"] == "contradicts"]
        rest = [e for e in edges if e["relation"] != "contradicts"]
        pick = contra + rng.sample(rest, min(args.sample - min(len(contra), args.sample), len(rest)))
        for e in pick:
            key = f"{arm}|{e['src']}|{e['dst']}|{e['relation']}"
            tasks.append((key, arm, e))
        print(f"arm {arm}: {len(edges)} edges -> judging {len(pick)} "
              f"(incl. all {len(contra)} contradicts)", flush=True)

    ckpt = OUT / "judgements.jsonl"
    done_keys = set()
    if ckpt.exists():
        for line in open(ckpt):
            if line.strip():
                done_keys.add(json.loads(line)["key"])
    todo = [(k, a, e) for k, a, e in tasks if k not in done_keys]
    print(f"to judge: {len(todo)} (done: {len(done_keys)})", flush=True)

    def q(c):  # noqa: ANN001
        quote = c.get("quote_verbatim") or c.get("quote") or ""
        return f'{c["statement"]}\n  quote: "{quote[:400]}"'

    lock = threading.Lock()
    timeout = int(os.environ.get("PRIOR_MAP_CALL_TIMEOUT", "120"))

    def judge(key: str, arm: str, e: dict) -> dict:
        ca, cb = by_id[e["src"]], by_id[e["dst"]]
        for _attempt in range(3):
            try:
                out = llm.structured(
            model=args.model, system=SYSTEM,
            user=(f"CONTRIBUTION A:\n  {q(ca)}\n\nCONTRIBUTION B:\n  {q(cb)}\n\n"
                  f"ASSERTED: A —[{e['relation']}]→ B"),
            schema=SCHEMA, tool_name="emit_verdict", max_tokens=300, timeout=timeout)
                break
            except Exception:
                if _attempt == 2:
                    raise
                import time as _t; _t.sleep(20 * (_attempt + 1))
        return {"key": key, "arm": arm, "relation": e["relation"],
                "verdict": out.get("verdict"), "better_type": out.get("better_type", ""),
                "reason": out.get("reason", "")}

    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(judge, *t): t[0] for t in todo}
        for f in as_completed(futs):
            n += 1
            try:
                rec = f.result()
            except Exception as ex:  # noqa: BLE001
                print(f"  [{n}/{len(todo)}] ERROR {futs[f]}: {ex}", flush=True)
                continue
            with lock, open(ckpt, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            if n % 25 == 0 or n == len(todo):
                print(f"  [{n}/{len(todo)}] {rec['arm']} {rec['relation']}: {rec['verdict']}", flush=True)

    # ---- summarize ---------------------------------------------------------
    rows = [json.loads(l) for l in open(ckpt) if l.strip()]
    summary: dict = {}
    for arm in args.arms:
        sub = [r for r in rows if r["arm"] == arm and r.get("verdict")]
        if not sub:
            continue
        c = Counter(r["verdict"] for r in sub)
        contra = [r for r in sub if r["relation"] == "contradicts"]
        cc = Counter(r["verdict"] for r in contra)
        by_rel = defaultdict(Counter)
        for r in sub:
            by_rel[r["relation"]][r["verdict"]] += 1
        summary[arm] = {
            "n": len(sub),
            "correct": round(c["correct"] / len(sub), 3),
            "wrong_type": round(c["wrong_type"] / len(sub), 3),
            "no_relation": round(c["no_relation"] / len(sub), 3),
            "contradicts_n": len(contra),
            "contradicts_precision": round(cc["correct"] / len(contra), 3) if contra else None,
            "by_relation": {k: dict(v) for k, v in by_rel.items()},
        }
    (OUT / "judge_summary.json").write_text(json.dumps(summary, indent=1))
    print("\n==== JUDGE SUMMARY ====")
    for arm, s in summary.items():
        print(f"  arm {arm}: correct {s['correct']:.0%} · wrong_type {s['wrong_type']:.0%} · "
              f"no_relation {s['no_relation']:.0%} · contradicts precision "
              f"{s['contradicts_precision']} (n={s['contradicts_n']})")
    print(f"-> {OUT/'judge_summary.json'}", flush=True)


if __name__ == "__main__":
    main()
