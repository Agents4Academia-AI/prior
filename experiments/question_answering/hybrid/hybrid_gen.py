#!/usr/bin/env python3
"""Run the two hybrid arms over the pilot subset — resumable, killable, capped.

RUN THIS IN YOUR OWN TERMINAL (not from inside a Claude Code session). Uses your
Claude Code subscription via the Agent SDK. Same safety contract as ../qa_gen.py:

  • Checkpointed: each finished (question_id, arm) is appended to
    hybrid/out/answers.jsonl the instant it completes. Re-running SKIPS what is
    there — kill and resume freely.
  • Ctrl+C safe: a partial unit is never written.
  • Capped: --max-turns and --budget per answer, serial, --sleep between calls.
  • --dry-run assembles the plan and prompts with NO model call.

Questions come from ../questions.json and the incumbent answers are read from
../out/answers.jsonl. NEITHER IS WRITTEN TO. Everything this script produces
lands in hybrid/out/.

Scale: 2 arms x 4 questions = 8 units, roughly $2.50-4.00, about 12 minutes.

  python hybrid_gen.py --dry-run                     # free
  python hybrid_gen.py --questions q06 --arm hybrid_directed   # one cell
  python hybrid_gen.py                               # the pilot (resumes)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

import hybrid_arms                                                   # noqa: E402
from hybrid_arms import HYBRID_ARMS                                  # noqa: E402

QUESTIONS = PARENT / "questions.json"
OUT_DIR = HERE / "out"
CKPT = OUT_DIR / "answers.jsonl"

MODEL_DEFAULT = "claude-sonnet-5"        # same generator as all three parent arms
SUBSET_DEFAULT = "q01,q03,q04,q06"       # see PLAN_HYBRID.md §3 and §8


def load_questions(which: str) -> list[dict]:
    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    keep = [w.strip() for w in which.split(",") if w.strip()]
    by_id = {q["question_id"]: q for q in qs}
    missing = [k for k in keep if k not in by_id]
    if missing:
        sys.exit(f"unknown question_id(s): {missing}")
    return [by_id[k] for k in keep]


def done_keys() -> set[tuple[str, str]]:
    if not CKPT.exists():
        return set()
    return {(r["question_id"], r["arm"]) for r in
            (json.loads(l) for l in
             CKPT.read_text(encoding="utf-8").splitlines() if l.strip())}


def append(row: dict, path: Path | None = None) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with (path or CKPT).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("all",) + HYBRID_ARMS, default="all")
    ap.add_argument("--questions", default=SUBSET_DEFAULT,
                    help=f"comma-separated question_ids (default: {SUBSET_DEFAULT})")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    # The hybrids have two environments to work through, so they need more room
    # than the parent's 14. The cap is a runaway guard, not a target.
    ap.add_argument("--max-turns", type=int, default=18)
    ap.add_argument("--budget", type=float, default=1.00,
                    help="max_budget_usd per answer")
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="move no-answer rows out of the checkpoint so they re-run (free)")
    ap.add_argument("--drop", help="comma-separated qid:arm cells to remove from the "
                                   "checkpoint so they re-run, e.g. 'q06:hybrid_free'. "
                                   "Archived to out/dropped.jsonl. (free)")
    args = ap.parse_args()

    if args.drop or args.prune:
        if not CKPT.exists():
            print("no checkpoint yet.")
            return
        rows = [json.loads(l) for l in
                CKPT.read_text(encoding="utf-8").splitlines() if l.strip()]
        if args.drop:
            cells = {tuple(c.split(":", 1)) for c in args.drop.split(",") if ":" in c}
            gone = [r for r in rows if (r["question_id"], r["arm"]) in cells]
            dest, verb = OUT_DIR / "dropped.jsonl", "dropped"
            missing = cells - {(r["question_id"], r["arm"]) for r in gone}
            for qid, arm in sorted(missing):
                print(f"  !! {qid}:{arm} was not in the checkpoint — nothing dropped")
        else:
            gone = [r for r in rows if not r.get("completed")]
            dest, verb = OUT_DIR / "failures.jsonl", "pruned"
        keep = [r for r in rows if r not in gone]
        for r in gone:
            append(r, dest)
            print(f"  {verb} {r['question_id']} [{r['arm']}] — will re-run")
        CKPT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                for r in keep), encoding="utf-8")
        print(f"kept {len(keep)}, {verb} {len(gone)}.")
        return

    qs = load_questions(args.questions)
    arms = list(HYBRID_ARMS) if args.arm == "all" else [args.arm]
    units = [(q, a) for q in qs for a in arms]
    done = done_keys()
    todo = [(q, a) for (q, a) in units if (q["question_id"], a) not in done]
    print(f"questions={[q['question_id'] for q in qs]} arms={arms} "
          f"units={len(units)} done={len(units) - len(todo)} todo={len(todo)}")

    if args.dry_run:
        from qa_arms import TASK
        for q, a in todo:
            sys_len = len(hybrid_arms.HYBRID_SYS[a])
            print(f"\n--- [{a}] {q['question_id']} ({q['family']}, "
                  f"incumbent-beating target) · system prompt {sys_len:,}ch ---")
            print(TASK.format(question=q["question"])[:260], "...")
        print(f"\n(dry-run) would run {len(todo)} units on {args.model}; "
              f"max_turns={args.max_turns} budget=${args.budget}/answer. "
              f"No model called.")
        return

    from qa_arms import run_one, GraphAtlas
    atlas = GraphAtlas()

    async def go():
        spend = 0.0
        for i, (q, a) in enumerate(todo, 1):
            print(f"[{i}/{len(todo)}] {a:16} · {q['question_id']} · "
                  f"{q['question'][:48]}", flush=True)
            try:
                res = await run_one(a, q["question"], atlas, model=args.model,
                                    max_turns=args.max_turns, budget_usd=args.budget)
            except KeyboardInterrupt:
                print("\ninterrupted — partial unit not saved; safe to resume.")
                raise
            row = {"question_id": q["question_id"], "family": q["family"],
                   "expected_winner": q["expected_winner"], **res}
            if res["completed"]:
                append(row)
            else:
                append(row, OUT_DIR / "failures.jsonl")
                print("    !! NO ANSWER after nudges — parked in out/failures.jsonl, "
                      "NOT checkpointed; re-running retries it.", flush=True)
            spend += res.get("total_cost_usd") or 0.0
            ans = res.get("answer") or {}
            # the routing headline, visible while it runs: how the two
            # environments were actually mixed on this question
            calls = [t["tool"].replace("mcp__graph__", "") for t in res["tool_args"]]
            n_atlas = sum(1 for t in res["tool_args"] if t["tool"].startswith("mcp__graph__"))
            n_web = sum(1 for t in res["tool_args"] if t["tool"] in ("WebSearch", "WebFetch"))
            first = calls[0] if calls else "(none)"
            print(f"    {'ok' if res['completed'] else 'NO-ANSWER'}  "
                  f"conf={ans.get('confidence')} "
                  f"papers={len(ans.get('papers_named') or [])} | "
                  f"first={first} atlas={n_atlas} web={n_web} "
                  f"payload={res['payload_chars']:,}ch {res['seconds']}s "
                  f"${res.get('total_cost_usd')} (run ${spend:.2f})", flush=True)
            print(f"    calls: {' -> '.join(calls) or '(none)'}", flush=True)
            if res.get("off_arm_tools"):
                print(f"    !! SEAL BREACH: {a} used {res['off_arm_tools']} — "
                      f"delete this row and investigate before judging.", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")
    print("next:  python ../check_leakage.py --file out/answers.jsonl")
    print("       python ../verify_named.py  --file out/answers.jsonl")
    print("       python hybrid_judge.py --repeats 3")


if __name__ == "__main__":
    main()
