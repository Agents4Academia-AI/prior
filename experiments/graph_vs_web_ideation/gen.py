#!/usr/bin/env python3
"""Drive both ideation arms over the seeds — resumable, killable, budget-capped.

RUN THIS IN YOUR OWN TERMINAL (not from inside a Claude Code session), so you
control it and can Ctrl+C. It uses your Claude Code subscription via the Agent SDK.

Safety / cost design:
  • Checkpointed: each finished (seed, arm) is appended to out/generations.jsonl
    the instant it completes. Re-running SKIPS what's already there — kill and
    resume freely.
  • Ctrl+C safe: a partial unit is never written; the loop stops cleanly.
  • Capped: --max-turns and --budget bound each idea; --sleep throttles between
    calls; serial by design (one call at a time) so it can't hammer your quota.
  • --dry-run assembles prompts and prints an estimate with NO model call.

Examples:
  python gen.py --dry-run                      # free: see what would run
  python gen.py --limit 1                      # tiny live pilot (1 seed, both arms)
  python gen.py --seeds s01,s05 --arm graph    # specific seeds / one arm
  python gen.py                                # full run (resumes if interrupted)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDS = HERE / "seeds.json"
OUT_DIR = HERE / "out"
CKPT = OUT_DIR / "generations.jsonl"

MODEL_DEFAULT = "claude-sonnet-5"   # generator (both arms); judge is separate


def load_seeds(which: str | None) -> list[dict]:
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))["seeds"]
    if which:
        keep = set(which.split(","))
        seeds = [s for s in seeds if s["seed_id"] in keep]
    return seeds


def done_keys() -> set[tuple[str, str]]:
    if not CKPT.exists():
        return set()
    keys = set()
    for line in CKPT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            keys.add((r["seed_id"], r["arm"]))
    return keys


def append(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:       # atomic-ish append per line
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("both", "graph", "web"), default="both")
    ap.add_argument("--seeds", help="comma-separated seed_ids (default: all)")
    ap.add_argument("--limit", type=int, help="cap number of seeds (after filtering)")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--max-turns", type=int, default=16)
    ap.add_argument("--budget", type=float, default=0.75, help="max_budget_usd per idea")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between calls")
    ap.add_argument("--dry-run", action="store_true", help="no model call; just plan")
    args = ap.parse_args()

    seeds = load_seeds(args.seeds)
    if args.limit:
        seeds = seeds[: args.limit]
    arms = ["graph", "web"] if args.arm == "both" else [args.arm]

    units = [(s, a) for s in seeds for a in arms]
    done = done_keys()
    todo = [(s, a) for (s, a) in units if (s["seed_id"], a) not in done]
    print(f"seeds={len(seeds)} arms={arms} units={len(units)} "
          f"done={len(units) - len(todo)} todo={len(todo)}")

    if args.dry_run:
        from arms import TASK
        for s, a in todo[:6]:
            print(f"\n--- [{a}] {s['seed_id']}: {s['topic']} ---")
            print(TASK.format(topic=s["topic"])[:240], "...")
        print(f"\n(dry-run) would run {len(todo)} units on {args.model}; "
              f"max_turns={args.max_turns} budget=${args.budget}/idea. No model called.")
        return

    # live: import here so --dry-run never needs the SDK
    import time
    from arms import run_one, GraphAtlas
    atlas = GraphAtlas()

    async def go():
        for i, (s, a) in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {a} · {s['seed_id']} · {s['topic'][:50]}", flush=True)
            try:
                res = await run_one(a, s["topic"], atlas, model=args.model,
                                    max_turns=args.max_turns, budget_usd=args.budget)
            except KeyboardInterrupt:
                print("\ninterrupted — partial unit not saved; safe to resume.")
                raise
            row = {"seed_id": s["seed_id"], **res}
            append(row)                                  # persist immediately
            flag = "ok" if res["completed"] else "NO-IDEA"
            print(f"    {flag}  turns={res['num_turns']} tools={res['n_tool_calls']} "
                  f"{res['seconds']}s cost={res.get('total_cost_usd')}", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")


if __name__ == "__main__":
    main()
