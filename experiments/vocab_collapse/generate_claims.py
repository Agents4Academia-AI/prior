#!/usr/bin/env python3
"""Vocabulary-collapse experiment — stage 1: raw-LLM generation.

Does a frontier LLM, asked what a field has contributed, produce a census or a
smear? (Artiles et al. 2026, arXiv:2603.01092: Claude's top-10 atoms appear in
~96% of its generations.) We ask the model — with NO atlas content in the
prompt — to enumerate the field's key contributions, over many independent
calls (each call is an isolated claude-cli session), and later match the
output against the 581 extracted atlas contributions.

Checkpointed: out/generations.jsonl (one row per completed call); re-running
mops up failures.

Usage:
  PRIOR_LLM_BACKEND=claude-cli python3 generate_claims.py --calls-per-prompt 12 --k 15
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prior import llm  # noqa: E402

OUT = Path(__file__).parent / "out"
CKPT = OUT / "generations.jsonl"

TOPIC = ("AI/LLM agents for the scientific process (2024-2026): autonomous "
         "research systems, hypothesis generation, scientific benchmarks and "
         "evaluation, AI peer review, literature/knowledge agents, "
         "lab-automation agents")

# Three phrasings so no single prompt drives the result.
PROMPTS = {
    "survey": ("You are surveying the research literature on {topic}. List the "
               "{k} most important contributions of this literature. Each item: "
               "a standalone, specific claim of what a specific system, method, "
               "benchmark or finding contributed. No preamble."),
    "establish": ("What has the research literature on {topic} established so "
                  "far? Give {k} distinct, concrete contributions — each one "
                  "specific (a particular system, benchmark, method or "
                  "finding), not a theme or a generality."),
    "expert": ("As an expert writing the related-work section of a paper on "
               "{topic}, enumerate the {k} key contributions you would cite. "
               "Each entry: one sentence stating exactly what that work "
               "contributed."),
}

SYSTEM = ("You answer from your own knowledge of the research literature. "
          "Produce only the requested list, in the JSON schema given — no "
          "hedging, no preamble.")

SCHEMA = {"type": "object",
          "properties": {"claims": {"type": "array", "items": {"type": "string"}}},
          "required": ["claims"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calls-per-prompt", type=int, default=12)
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--model", default=os.environ.get("PRIOR_COLLAPSE_MODEL", "claude-sonnet-4-6"))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("PRIOR_MAP_WORKERS", "5")))
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    done = set()
    if CKPT.exists():
        for line in open(CKPT):
            if line.strip():
                r = json.loads(line)
                done.add((r["prompt"], r["idx"]))

    tasks = [(p, i) for p in PROMPTS for i in range(args.calls_per_prompt)
             if (p, i) not in done]
    print(f"calls to run: {len(tasks)} (done: {len(done)})", flush=True)

    lock = threading.Lock()

    def run(p: str, i: int) -> dict:
        out = llm.structured(
            model=args.model, system=SYSTEM,
            user=PROMPTS[p].format(topic=TOPIC, k=args.k),
            schema=SCHEMA, max_tokens=2400,
            timeout=int(os.environ.get("PRIOR_MAP_CALL_TIMEOUT", "180")))
        claims = [c.strip() for c in out.get("claims", []) if isinstance(c, str) and c.strip()]
        return {"prompt": p, "idx": i, "model": args.model, "claims": claims}

    n = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run, p, i): (p, i) for p, i in tasks}
        for f in as_completed(futs):
            p, i = futs[f]
            n += 1
            try:
                row = f.result()
            except Exception as e:  # noqa: BLE001
                print(f"  [{n}/{len(tasks)}] ERROR {p}#{i}: {e}", flush=True)
                continue
            with lock:
                with open(CKPT, "a") as fh:
                    fh.write(json.dumps(row) + "\n")
            print(f"  [{n}/{len(tasks)}] {p}#{i}: {len(row['claims'])} claims", flush=True)

    total = sum(1 for _ in open(CKPT)) if CKPT.exists() else 0
    print(f"DONE: {total} completed calls -> {CKPT}", flush=True)


if __name__ == "__main__":
    main()
