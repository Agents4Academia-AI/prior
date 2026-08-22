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

v2: arms are SEALED (see qa_arms.py) and every row now records `tokens_in`
(input + cache_creation) and `payload_chars` — the pre-registered efficiency
metrics. A SEAL BREACH warning means the row is contaminated; delete it.

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


def append(row: dict, path: Path | None = None) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with (path or CKPT).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def main() -> None:
    # answers and judge prose contain arrows, dashes and accents; Windows
    # consoles default to cp1252 and would die mid-run on one of them
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("all",) + ARMS, default="all")
    ap.add_argument("--questions", help="comma-separated question_ids (default: all)")
    ap.add_argument("--limit", type=int, help="cap number of questions (after filtering)")
    ap.add_argument("--model", default=MODEL_DEFAULT)
    ap.add_argument("--max-turns", type=int, default=14)
    # 0.60 was too tight: q01/web spent it on 8 searches and was cut off before it
    # could deliver, wasting the whole unit. The cap is a runaway guard, not a
    # target — a unit that dies at the cap costs full price and returns nothing.
    ap.add_argument("--budget", type=float, default=1.20,
                    help="max_budget_usd per answer")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between calls")
    ap.add_argument("--dry-run", action="store_true", help="no model call; just plan")
    ap.add_argument("--prune", action="store_true",
                    help="move no-answer rows out of the checkpoint so they re-run "
                         "(free, no model call)")
    ap.add_argument("--drop", help="comma-separated qid:arm cells to remove from the "
                                   "checkpoint so they re-run, e.g. 'q04:graph,q05:null'. "
                                   "For rows that COMPLETED but are not usable — a "
                                   "retry-degraded submission, say. Dropped rows are "
                                   "archived to out/dropped.jsonl. (free, no model call)")
    args = ap.parse_args()

    if args.drop:
        if not CKPT.exists():
            print("no checkpoint to drop from.")
            return
        cells = {tuple(c.split(":", 1)) for c in args.drop.split(",") if ":" in c}
        rows = [json.loads(l) for l in
                CKPT.read_text(encoding="utf-8").splitlines() if l.strip()]
        keep = [r for r in rows if (r["question_id"], r["arm"]) not in cells]
        gone = [r for r in rows if (r["question_id"], r["arm"]) in cells]
        for r in gone:
            append(r, OUT_DIR / "dropped.jsonl")
            print(f"  dropped {r['question_id']} [{r['arm']}] — archived, will re-run")
        missing = cells - {(r["question_id"], r["arm"]) for r in gone}
        for qid, arm in sorted(missing):
            print(f"  !! {qid}:{arm} was not in the checkpoint — nothing dropped")
        CKPT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                for r in keep), encoding="utf-8")
        print(f"kept {len(keep)}, dropped {len(gone)}.")
        return

    if args.prune:
        if not CKPT.exists():
            print("no checkpoint to prune.")
            return
        rows = [json.loads(l) for l in
                CKPT.read_text(encoding="utf-8").splitlines() if l.strip()]
        keep = [r for r in rows if r.get("completed")]
        drop = [r for r in rows if not r.get("completed")]
        for r in drop:
            append(r, OUT_DIR / "failures.jsonl")
            print(f"  pruned {r['question_id']} [{r['arm']}] — will re-run")
        CKPT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                for r in keep), encoding="utf-8")
        print(f"kept {len(keep)} completed, pruned {len(drop)}.")
        return

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
            # Only CHECKPOINT completed units. A no-answer row written to the
            # checkpoint would count as done on resume and silently leave a hole in
            # the design; park it separately so a re-run retries it.
            if res["completed"]:
                append(row)
            else:
                append(row, CKPT.parent / "failures.jsonl")
                print("    !! NO ANSWER after nudges — parked in out/failures.jsonl, "
                      "NOT checkpointed; re-running will retry this unit.", flush=True)
            spend += res.get("total_cost_usd") or 0.0
            ans = res.get("answer") or {}
            flag = "ok" if res["completed"] else "NO-ANSWER"
            print(f"    {flag}  conf={ans.get('confidence')} "
                  f"papers={len(ans.get('papers_named') or [])} "
                  f"calls={res['n_explore']} nudges={res['n_nudges']} "
                  f"payload={res['payload_chars']:,}ch "
                  f"ctx={res.get('context_total') or 0:,} "
                  f"tok_in={res['tokens_in']:,} {res['seconds']}s "
                  f"${res.get('total_cost_usd')} (run ${spend:.2f})", flush=True)
            # the seal's canary: v1 silently let Bash/Skill/WebSearch into the graph
            # and null arms. If this ever fires, the row is contaminated — bin it.
            if res.get("off_arm_tools"):
                print(f"    !! SEAL BREACH: {a} arm used {res['off_arm_tools']} "
                      f"— delete this row and investigate before judging.", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")


if __name__ == "__main__":
    main()
