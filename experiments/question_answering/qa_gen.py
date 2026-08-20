#!/usr/bin/env python3
"""Drive the three QA arms over the questions — resumable, killable, budget-capped.

RUN THIS IN YOUR OWN TERMINAL (not from inside a Claude Code session), so you
control it and can Ctrl+C. Uses your Claude Code subscription via the Agent SDK.

Safety / cost design (same contract as ../graph_vs_web_ideation/gen.py):
  • Checkpointed: each finished (question_id, arm) is appended to out/answers.jsonl
    the instant it completes. Re-running SKIPS what's there — kill and resume freely.
  • Ctrl+C safe: a partial unit is never written.
  • Capped: --max-turns and --budget per answer; --sleep between calls; serial.
  • --dry-run assembles prompts and prints the plan with NO model call.

Scale: 8 questions x 3 arms = 24 units, ~$10, one sitting.

Examples:
  python qa_gen.py --dry-run                    # free: see what would run
  python qa_gen.py --limit 1                    # tiny live pilot (1 question, 3 arms)
  python qa_gen.py --questions q04 --arm graph  # one cell
  python qa_gen.py                              # everything (resumes if interrupted)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
QUESTIONS = HERE / "questions.json"
OUT_DIR = HERE / "out"
CKPT = OUT_DIR / "answers.jsonl"

MODEL_DEFAULT = "claude-sonnet-5"     # generator for all three arms; judge is separate
ARMS = ("graph", "web", "null")


def load_questions(which: str | None) -> list[dict]:
    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    if which:
        keep = set(which.split(","))
        qs = [q for q in qs if q["question_id"] in keep]
    return qs


def done_keys() -> set[tuple[str, str]]:
    if not CKPT.exists():
        return set()
    return {(r["question_id"], r["arm"]) for r in
            (json.loads(l) for l in CKPT.read_text(encoding="utf-8").splitlines() if l.strip())}


def append(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("all",) + ARMS, default="all")
    ap.add_argument("--questions", help="comma-separated question_ids (default: all)")
    ap.add_argument("--limit", type=int, help="cap number of questions (after filtering)")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--max-turns", type=int, default=14)
    ap.add_argument("--budget", type=float, default=0.60, help="max_budget_usd per answer")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between calls")
    ap.add_argument("--dry-run", action="store_true", help="no model call; just plan")
    args = ap.parse_args()

    qs = load_questions(args.questions)
    if args.limit:
        qs = qs[: args.limit]
    arms = list(ARMS) if args.arm == "all" else [args.arm]

    units = [(q, a) for q in qs for a in arms]
    done = done_keys()
    todo = [(q, a) for (q, a) in units if (q["question_id"], a) not in done]
    print(f"questions={len(qs)} arms={arms} units={len(units)} "
          f"done={len(units) - len(todo)} todo={len(todo)}")

    if args.dry_run:
        from qa_arms import TASK
        for q, a in todo[:3]:
            print(f"\n--- [{a}] {q['question_id']} ({q['family']}, "
                  f"expect {q['expected_winner']}) ---")
            print(TASK.format(question=q["question"])[:300], "...")
        print(f"\n(dry-run) would run {len(todo)} units on {args.model}; "
              f"max_turns={args.max_turns} budget=${args.budget}/answer. No model called.")
        return

    import time
    from qa_arms import run_one, GraphAtlas
    atlas = GraphAtlas()

    async def go():
        spend = 0.0
        for i, (q, a) in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {a:5} · {q['question_id']} · {q['question'][:52]}",
                  flush=True)
            try:
                res = await run_one(a, q["question"], atlas, model=args.model,
                                    max_turns=args.max_turns, budget_usd=args.budget)
            except KeyboardInterrupt:
                print("\ninterrupted — partial unit not saved; safe to resume.")
                raise
            row = {"question_id": q["question_id"], "family": q["family"],
                   "expected_winner": q["expected_winner"], **res}
            append(row)                                   # persist immediately
            spend += res.get("total_cost_usd") or 0.0
            ans = res.get("answer") or {}
            flag = "ok" if res["completed"] else "NO-ANSWER"
            print(f"    {flag}  conf={ans.get('confidence')} "
                  f"papers={len(ans.get('papers_named') or [])} "
                  f"explore={res['n_explore']} {res['seconds']}s "
                  f"${res.get('total_cost_usd')} (run ${spend:.2f})", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")


if __name__ == "__main__":
    main()
