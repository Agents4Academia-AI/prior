#!/usr/bin/env python3
"""Vocabulary-collapse experiment — stage 2: match generated claims to atlas.

For each raw-LLM-generated claim, show BM25 top-k atlas contributions and ask
for a STRICT verdict: does the claim describe the SAME specific contribution
(same system / benchmark / method / finding), or none of them? Topical
similarity is explicitly not a match — that lesson comes straight from the
edge-quality experiment ("shared topic alone is not a defensible relation").

Checkpointed: out/matches.jsonl keyed by (prompt, idx, claim_no).

Usage:
  PRIOR_LLM_BACKEND=claude-cli python3 match_claims.py --bundle ../../../prior-core-v0.2
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prior import llm  # noqa: E402
from rank_bm25 import BM25Okapi  # noqa: E402

OUT = Path(__file__).parent / "out"
GEN = OUT / "generations.jsonl"
CKPT = OUT / "matches.jsonl"

SYSTEM = ("You match a claimed research contribution against candidate "
          "contributions extracted from actual papers.\n"
          "Verdict rule — STRICT identity, not topic: answer with a "
          "candidate's id ONLY if the claim describes the SAME specific "
          "contribution — the same system, benchmark, method, dataset or "
          "empirical finding — allowing for paraphrase. If the claim is "
          "merely in the same research area, or describes a similar-but-"
          "different system, answer \"none\". If the claim is a generic "
          "theme (e.g. 'LLM agents can help science') with no specific "
          "referent, answer \"none\" and set generic=true.")

SCHEMA = {"type": "object",
          "properties": {"match": {"type": "string"},
                         "generic": {"type": "boolean"},
                         "reason": {"type": "string"}},
          "required": ["match", "reason"]}

_tok = lambda s: re.findall(r"[a-z0-9]+", s.lower())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--cands", type=int, default=6)
    ap.add_argument("--model", default=os.environ.get("PRIOR_COLLAPSE_MODEL", "claude-sonnet-4-6"))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("PRIOR_MAP_WORKERS", "5")))
    args = ap.parse_args()

    contribs = json.load(open(Path(args.bundle) / "contributions_core_grounded.json"))
    if isinstance(contribs, dict):
        contribs = contribs.get("contributions", contribs)
    corpus = [_tok(c["statement"]) for c in contribs]
    bm25 = BM25Okapi(corpus)

    done = set()
    if CKPT.exists():
        for line in open(CKPT):
            if line.strip():
                r = json.loads(line)
                done.add(r["key"])

    tasks = []
    for line in open(GEN):
        if not line.strip():
            continue
        g = json.loads(line)
        for j, claim in enumerate(g["claims"]):
            arm = g.get("arm", "memory")
            key = (f"search#{g['prompt']}#{g['idx']}#{j}" if arm == "search"
                   else f"{g['prompt']}#{g['idx']}#{j}")
            if key not in done:
                tasks.append((key, claim))
    print(f"claims to match: {len(tasks)} (done: {len(done)})", flush=True)

    lock = threading.Lock()

    def run(key: str, claim: str) -> dict:
        scores = bm25.get_scores(_tok(claim))
        top = sorted(range(len(contribs)), key=lambda i: scores[i], reverse=True)[:args.cands]
        listing = "\n".join(f"- id: {contribs[i]['id']}\n  statement: {contribs[i]['statement']}"
                            for i in top)
        out = llm.structured(
            model=args.model, system=SYSTEM,
            user=(f"CLAIM:\n  {claim}\n\nCANDIDATE CONTRIBUTIONS:\n{listing}\n\n"
                  f"Answer with the matching candidate id, or \"none\"."),
            schema=SCHEMA, max_tokens=300,
            timeout=int(os.environ.get("PRIOR_MAP_CALL_TIMEOUT", "120")))
        m = (out.get("match") or "none").strip()
        valid = {contribs[i]["id"] for i in top}
        if m != "none" and m not in valid:
            m = "none"  # hallucinated id → no match
        return {"key": key, "claim": claim, "match": m,
                "generic": bool(out.get("generic", False)),
                "reason": out.get("reason", "")}

    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run, k, c): k for k, c in tasks}
        for f in as_completed(futs):
            k = futs[f]
            n += 1
            try:
                row = f.result()
            except Exception as e:  # noqa: BLE001
                print(f"  [{n}/{len(tasks)}] ERROR {k}: {e}", flush=True)
                continue
            with lock:
                with open(CKPT, "a") as fh:
                    fh.write(json.dumps(row) + "\n")
            if n % 25 == 0:
                print(f"  [{n}/{len(tasks)}] {k}: {row['match']}", flush=True)

    total = sum(1 for _ in open(CKPT)) if CKPT.exists() else 0
    print(f"DONE: {total} matched -> {CKPT}", flush=True)


if __name__ == "__main__":
    main()
