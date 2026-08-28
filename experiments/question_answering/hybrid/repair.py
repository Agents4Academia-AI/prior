#!/usr/bin/env python3
"""Recover answers the submit-gate bug threw away. FREE — no model call.

WHAT HAPPENED. `qa_arms._submit_tool` is first-complete-wins, and its notion of
"complete" is `answer non-blank AND papers_named non-empty`. A smoke test —

    answer="Test", papers_named=["Test Paper"], confidence="high", limits="test"

— satisfies that, so when a model probed the tool before committing, the probe
was locked in and the real answer that followed was discarded. Two rows in the
first hybrid batch were destroyed this way and the judge scored them 1/1/1.

WHY THIS IS A RECOVERY, NOT A DO-OVER. Every attempt was already logged on the
row as `submissions`, before any of this was known. This script re-applies the
FIXED selection rule (`hybrid_arms.pick_best`) to that log and stores what the
fixed harness would have stored. It is the same rule the code now runs live, it
is deterministic, and it cannot pick a *nicer* answer — only the fullest
submission that clears the probe bar. Nothing is regenerated and nothing is
re-worded.

Where no logged submission clears the bar, the row is genuinely lost: it is
moved to out/failures.jsonl so `hybrid_gen.py` re-runs it, rather than being
quietly patched up.

The original file is archived to out/pre_repair.jsonl either way, so both sides
of the repair stay comparable.

  python repair.py            # free — show what WOULD change
  python repair.py --apply    # free — do it
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from hybrid_arms import pick_best, is_probe, MIN_ANSWER_CHARS       # noqa: E402

ANSWERS = HERE / "out" / "answers.jsonl"
ARCHIVE = HERE / "out" / "pre_repair.jsonl"
FAILURES = HERE / "out" / "failures.jsonl"
JUDGEMENTS = HERE / "out" / "judgements.jsonl"


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes")
    args = ap.parse_args()

    if not ANSWERS.exists():
        sys.exit(f"no answers at {ANSWERS}")
    rows = [json.loads(l) for l in
            ANSWERS.read_text(encoding="utf-8").splitlines() if l.strip()]

    keep, lost, fixed = [], [], []
    for r in rows:
        subs = r.get("submissions") or []
        stored = str((r.get("answer") or {}).get("answer") or "")
        best = pick_best(subs)
        if best is None or str(best.get("answer") or "") == stored:
            keep.append(r)
            continue
        probe, why = is_probe(best)
        tag = f"{r['question_id']}/{r['arm']}"
        if probe:
            print(f"  UNRECOVERABLE  {tag:28} best of {len(subs)} submissions is "
                  f"still a probe ({why}) — will re-run")
            r["repair"] = {"outcome": "unrecoverable", "reason": why,
                           "n_submissions": len(subs)}
            lost.append(r)
        else:
            print(f"  RECOVERED      {tag:28} {len(stored):>5}ch -> "
                  f"{len(best['answer']):>5}ch, "
                  f"{len(best.get('papers_named') or [])} papers "
                  f"(submission {subs.index(best) + 1} of {len(subs)})")
            r["repair"] = {"outcome": "recovered",
                           "discarded_chars": len(stored),
                           "recovered_chars": len(best["answer"]),
                           "n_submissions": len(subs),
                           "rule": f"pick_best: passes bar (>={MIN_ANSWER_CHARS}ch, "
                                   f"papers named, real limits), then longest"}
            r["answer"] = best
            keep.append(r)
            fixed.append(tag)

    if not fixed and not lost:
        print("nothing to repair — every row already stores its best submission.")
        return

    affected = sorted({t.split("/")[0] for t in fixed}
                      | {r["question_id"] for r in lost})
    print(f"\n{len(fixed)} recovered, {len(lost)} unrecoverable.")

    if not args.apply:
        print("\n(dry run — nothing written. re-run with --apply)")
        return

    shutil.copyfile(ANSWERS, ARCHIVE)
    ANSWERS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n"
                               for r in keep), encoding="utf-8")
    if lost:
        with FAILURES.open("a", encoding="utf-8") as f:
            for r in lost:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"archived the originals to {ARCHIVE.name}; "
          f"{len(keep)} rows kept, {len(lost)} parked in {FAILURES.name}.")

    # The judge saw all three answers side by side, so a question that carried a
    # destroyed answer has invalid scores for the OTHER two as well — a 1/1/1
    # answer in the lineup changes both the ranking and the contrast the other
    # answers are read against. Those questions have to be judged again.
    if JUDGEMENTS.exists():
        print(f"\n!! judgements for {', '.join(affected)} were made against the "
              f"destroyed answers and are now invalid.")
        print(f"   python hybrid_judge.py --drop {','.join(affected)}")


if __name__ == "__main__":
    main()
