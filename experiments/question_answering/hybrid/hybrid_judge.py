#!/usr/bin/env python3
"""Blind 3-way judging: hybrid_directed vs hybrid_free vs the incumbent winner.

RUN THIS IN YOUR OWN TERMINAL. Uses your Claude Code subscription.

THE JUDGE IS IMPORTED, NOT FORKED. `JUDGE_SYS`, `JUDGEMENT_SCHEMA`, `render()`,
`judge_one()`, `PROMPT` and `SLOTS` all come straight from ../qa_judge.py, so
these scores are produced by the *same* judge, with the same rubric and the same
seal, as the three-arm result they are being compared with. Only the row
building is new, because that is the part coupled to the arm names.

Three answers per question, so the existing 3-way call fits exactly:

  A/B/C = hybrid_directed, hybrid_free, and the question's INCUMBENT WINNER
          (graph for q01/q04, web for q06 — computed from the parent's
          judgements, not hardcoded)

A pairwise fight would have needed a new rubric and a new prompt for strictly
less information. See PLAN_HYBRID.md §3.

Presentation order rotates exactly as the parent does: a base permutation per
question, rotated once per repeat, so at --repeats 3 every arm appears in every
slot exactly once per question — 3/3/3 over the nine judgements.

  • Checkpointed on (question_id, run) -> hybrid/out/judgements.jsonl.
  • Ctrl+C safe; --dry-run renders the exact prompt with no model call.

  python hybrid_judge.py --dry-run        # free
  python hybrid_judge.py --repeats 3      # the pilot (resumes if interrupted)
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import itertools
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))

from qa_judge import (JUDGE_MODEL, PROMPT, SLOTS, render, judge_one,  # noqa: E402
                      _clamp)

QUESTIONS = PARENT / "questions.json"
PARENT_ANSWERS = PARENT / "out" / "answers.jsonl"          # READ-ONLY
PARENT_JUDGEMENTS = PARENT / "out" / "qa_judgements.jsonl"  # READ-ONLY
HYBRID_ANSWERS = HERE / "out" / "answers.jsonl"
OUT_DIR = HERE / "out"
CKPT = OUT_DIR / "judgements.jsonl"

# the three things being judged. "incumbent" is a ROLE — which real arm filled it
# is recorded per row as `incumbent_arm`.
ARMS3 = ("hybrid_directed", "hybrid_free", "incumbent")
PERMS = list(itertools.permutations(ARMS3))


def _read(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def incumbent_winners() -> dict[str, str]:
    """Per question, the arm the parent's judge picked most often over its runs.

    Computed from ../out/qa_judgements.jsonl rather than hardcoded, so if those
    judgements are ever re-run this follows them instead of going quietly stale.
    """
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in _read(PARENT_JUDGEMENTS):
        votes[r["question_id"]][r["best_answer"]] += 1
    return {qid: c.most_common(1)[0][0] for qid, c in votes.items() if c}


def load_units() -> list[tuple[dict, dict, str]]:
    """(question, {role: answer_row}, incumbent_arm) for questions complete on all three."""
    qs = {q["question_id"]: q for q in
          json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]}
    inc_arm = incumbent_winners()
    parent_by_q: dict[str, dict[str, dict]] = {}
    for r in _read(PARENT_ANSWERS):
        parent_by_q.setdefault(r["question_id"], {})[r["arm"]] = r
    hybrid_by_q: dict[str, dict[str, dict]] = {}
    for r in _read(HYBRID_ANSWERS):
        hybrid_by_q.setdefault(r["question_id"], {})[r["arm"]] = r

    out = []
    for qid in sorted(hybrid_by_q):
        d = dict(hybrid_by_q[qid])
        arm = inc_arm.get(qid)
        if arm is None:
            print(f"  (skipping {qid}: parent has no judgement, so no incumbent)")
            continue
        d["incumbent"] = parent_by_q.get(qid, {}).get(arm) or {}
        missing = [a for a in ARMS3 if not (d.get(a) and d[a].get("answer"))]
        if missing:
            print(f"  (skipping {qid}: no completed answer for {missing})")
            continue
        out.append((qs[qid], d, arm))
    return out


def done_keys() -> set[tuple[str, int]]:
    return {(r["question_id"], int(r.get("run", 0))) for r in _read(CKPT)}


def append(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def build_row(q: dict, perm: tuple[str, ...], rows: dict[str, dict], res: dict,
              incumbent_arm: str, run: int = 0) -> dict:
    """Un-blind A/B/C back onto the three roles. Scores lead the row."""
    j = res["judgement"]
    slot_of = {a: SLOTS[i] for i, a in enumerate(perm)}
    arm_of = {SLOTS[i]: a for i, a in enumerate(perm)}

    best_slot = str(j.get("best_answer") or "").strip().lower()[:1]
    best = arm_of.get(best_slot, "unclear")
    ranking = str(j.get("ranking") or "")
    for s in SLOTS:
        ranking = ranking.replace(s.upper(), arm_of[s])

    row = {
        "question_id": q["question_id"], "run": run, "family": q["family"],
        "incumbent_arm": incumbent_arm,
        "best_answer": best, "margin": str(j.get("margin") or "none").lower(),
        # the pilot's own registered prediction: a hybrid should at least not lose
        # to the arm it contains. See PLAN_HYBRID.md §4.
        "hybrid_won": best in ("hybrid_directed", "hybrid_free"),
        "ranking": ranking,
    }
    for a in ARMS3:
        for axis in ("groundedness", "correctness", "usefulness"):
            row[f"{a}_{axis}"] = _clamp(j[f"{slot_of[a]}_{axis}"])
    for a in ARMS3:
        for flag in ("fabricated", "unrecognised", "hedged", "overclaimed"):
            row[f"{a}_{flag}"] = bool(j.get(f"{slot_of[a]}_{flag}"))
        row[f"{a}_unrecognised_titles"] = j.get(f"{slot_of[a]}_unrecognised_titles")
    row["question"] = q["question"]
    for a in ARMS3:
        row[f"{a}_reason"] = j.get(f"{slot_of[a]}_reason")
    row["fabrication_notes"] = j.get("fabrication_notes")
    row["presentation_order"] = list(perm)
    row["judge_model"] = res["model"]
    for k in ("seconds", "num_turns", "total_cost_usd", "usage", "stop_reason", "is_error"):
        row[k] = res[k]
    row["gen_cost_usd"] = {a: rows[a].get("total_cost_usd") for a in ARMS3}
    row["gen_explore"] = {a: rows[a].get("n_explore") for a in ARMS3}
    row["gen_payload_chars"] = {a: rows[a].get("payload_chars") for a in ARMS3}
    return row


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", help="comma-separated question_ids")
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--max-turns", type=int, default=6)
    ap.add_argument("--budget", type=float, default=0.80)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--repeats", type=int, default=3,
                    help="judge each question N times, each with a DIFFERENT "
                         "presentation order (parent used 3)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--drop", help="comma-separated question_ids to re-judge (free)")
    args = ap.parse_args()

    if args.drop:
        rows = _read(CKPT)
        if not rows:
            print("no judgements to drop.")
            return
        want = {q.strip() for q in args.drop.split(",") if q.strip()}
        keep = [r for r in rows if r["question_id"] not in want]
        with (OUT_DIR / "dropped_judgements.jsonl").open("a", encoding="utf-8") as f:
            for r in rows:
                if r["question_id"] in want:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    print(f"  dropped judgement {r['question_id']} run={r.get('run')}")
        CKPT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                                for r in keep), encoding="utf-8")
        print(f"kept {len(keep)}, dropped {len(rows) - len(keep)}.")
        return

    if not HYBRID_ANSWERS.exists():
        sys.exit(f"no hybrid answers at {HYBRID_ANSWERS} — run hybrid_gen.py first.")
    units = load_units()
    if not units:
        sys.exit("nothing judgeable yet.")
    reps = max(1, args.repeats)

    # Order is fixed by position in the FULL unit list, before filtering, so
    # --questions never changes which order a judgement sees.
    def _order(i: int, r: int) -> tuple[str, ...]:
        base = PERMS[i % len(PERMS)]
        k = r % len(base)
        return base[k:] + base[:k]

    perm_of = {(q["question_id"], r): _order(i, r)
               for i, (q, _, _) in enumerate(units) for r in range(reps)}
    if args.questions:
        keep = set(args.questions.split(","))
        units = [u for u in units if u[0]["question_id"] in keep]
    done = done_keys()
    todo = [(q, rows, arm, r) for (q, rows, arm) in units for r in range(reps)
            if (q["question_id"], r) not in done]
    print(f"questions={len(units)} repeats={reps} "
          f"judgements={len(units) * reps} todo={len(todo)}")
    for q, _, arm in units:
        print(f"  {q['question_id']}: incumbent = {arm}")

    if args.dry_run:
        for q, rows, arm, r in todo[:1]:
            perm = perm_of[(q["question_id"], r)]
            rendered = {SLOTS[i]: render(rows[a]["answer"]) for i, a in enumerate(perm)}
            print(f"\n--- {q['question_id']} run={r} order={perm} ---")
            print(PROMPT.format(question=q["question"], **rendered)[:1800], "...")
        # show the slot balance the rotation will produce
        bal = collections.Counter((a, SLOTS[i])
                                  for (qid, r), p in perm_of.items()
                                  for i, a in enumerate(p))
        print("\nslot balance (arm, slot) -> count:",
              dict(sorted(bal.items())))
        print(f"\n(dry-run) would run {len(todo)} judgements on {args.model}. "
              f"No model called.")
        return

    async def go():
        spend = 0.0
        for i, (q, rows, arm, run) in enumerate(todo, 1):
            perm = perm_of[(q["question_id"], run)]
            rendered = {SLOTS[k]: render(rows[a]["answer"]) for k, a in enumerate(perm)}
            print(f"[{i}/{len(todo)}] {q['question_id']} run={run} "
                  f"order={'/'.join(perm)}", flush=True)
            try:
                res = await judge_one(q["question"], rendered, model=args.model,
                                      max_turns=args.max_turns, budget_usd=args.budget)
            except KeyboardInterrupt:
                print("\ninterrupted — partial judgement not saved; safe to resume.")
                raise
            if not res["completed"]:
                print(f"    NO-JUDGEMENT (stop={res['stop_reason']}) — not saved, "
                      f"will retry", flush=True)
                continue
            res["model"] = args.model
            row = build_row(q, perm, rows, res, arm, run=run)
            append(row)
            spend += res["total_cost_usd"] or 0.0
            fab = [a for a in ARMS3 if row[f"{a}_fabricated"]]
            print(f"    best={row['best_answer']} ({row['margin']}) | "
                  f"D {row['hybrid_directed_groundedness']}/"
                  f"{row['hybrid_directed_correctness']}/"
                  f"{row['hybrid_directed_usefulness']}  "
                  f"F {row['hybrid_free_groundedness']}/"
                  f"{row['hybrid_free_correctness']}/"
                  f"{row['hybrid_free_usefulness']}  "
                  f"{arm[:4].upper()} {row['incumbent_groundedness']}/"
                  f"{row['incumbent_correctness']}/{row['incumbent_usefulness']}"
                  + (f" | FABRICATED: {fab}" if fab else "")
                  + f"  ${res['total_cost_usd']} (run ${spend:.2f})", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")
    print("next:  python routing.py        # free — the call-routing trace")
    print("       python hybrid_report.py  # free -> RESULTS_HYBRID.md")


if __name__ == "__main__":
    main()
