#!/usr/bin/env python3
"""Blind 3-way judging of the QA answers — resumable, killable, capped.

RUN THIS IN YOUR OWN TERMINAL. Uses your Claude Code subscription via the Agent SDK.

For each question, `claude-opus-5` sees all THREE answers anonymised as A / B / C
in ONE call and scores each 1-10 on groundedness, correctness and usefulness, plus
per-answer honesty flags (fabricated / hedged / overclaimed) and a forced overall
ranking. One call rather than three pairwise ones: same rubric, a third of the
cost, and the judge sees the alternatives side by side, which is what makes
"grounded" and "vague" separable in the first place.

Presentation order rotates through all 6 permutations of (graph, web, null),
assigned by the question's index in the full list — deterministic, resume-safe,
and position-balanced across the set rather than approximately so.

The judge is told explicitly that an honest "I could not establish this" OUTRANKS
a confident vague answer. Without that the judge rewards fluency, and the two
control questions (which the atlas is SUPPOSED to lose) measure nothing.

  • Checkpointed on question_id → out/qa_judgements.jsonl; re-running skips done.
  • Ctrl+C safe; --dry-run renders the exact prompt with no model call.

Examples:
  python qa_judge.py --dry-run          # free
  python qa_judge.py --limit 2          # pilot
  python qa_judge.py                    # all 8 (resumes if interrupted)
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from pathlib import Path
from typing import Annotated

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"
ANSWERS = OUT_DIR / "answers.jsonl"
QUESTIONS = HERE / "questions.json"
CKPT = OUT_DIR / "qa_judgements.jsonl"

JUDGE_MODEL = "claude-opus-5"
ARMS = ("graph", "web", "null")
SLOTS = ("a", "b", "c")
PERMS = list(itertools.permutations(ARMS))          # 6 presentation orders

JUDGE_SYS = (
    "You are a senior researcher in AI-for-science. A colleague asked a QUESTION and "
    "received THREE independent answers, A, B and C. Score each answer on its own "
    "merits — both may be strong, all may be weak, ties are fine.\n\n"
    "GROUNDEDNESS (1-10) — does it name real, specific papers and state precisely how "
    "they relate, or does it gesture at 'several studies have shown'?\n"
    "  1-2  no specifics; could have been written without reading anything\n"
    "  3-4  names a paper or two, but the relationships are vague\n"
    "  5-6  specific papers, but the connection to the question is loosely argued\n"
    "  7-8  specific papers AND precise, checkable relationships between them\n"
    "  9-10 precise, and the structure of the evidence itself is made clear\n\n"
    "CORRECTNESS (1-10) — are the stated facts and relationships actually true, as far "
    "as you know the literature? A fabricated or misattributed paper is disqualifying: "
    "score 1-3 and set the fabricated flag.\n\n"
    "USEFULNESS (1-10) — could the researcher act on this answer as it stands?\n\n"
    "CRITICAL — how to treat uncertainty: an HONEST answer that says 'I could not "
    "establish this, here is what I can say' OUTRANKS a confident, fluent answer that "
    "is vague or unverifiable. Some of these questions may not be fully answerable; "
    "declining precisely is a good answer and must score well on correctness. Do not "
    "reward length, fluency or confidence for their own sake — several of these answers "
    "may be from systems that cannot see the relevant material, and admitting that is "
    "the correct behaviour, not a weakness.\n\n"
    "Flag per answer: `fabricated` (names a paper/finding/number you believe does not "
    "exist or is misattributed), `hedged` (declined to commit to an answer), "
    "`overclaimed` (asserted completeness — 'these are all the papers that…' — that it "
    "cannot support).\n\n"
    "Finally give an overall RANKING (e.g. 'B>A>C'), name the BEST answer, and say how "
    "big the gap to the next one is (decisive / clear / slight / none).\n\n"
    "Call `submit_judgement` EXACTLY ONCE. One sentence per reason. You have no tools "
    "and no browser — judge from your own knowledge."
)

PROMPT = ("QUESTION: {question}\n\n"
          "=== ANSWER A ===\n{a}\n\n=== ANSWER B ===\n{b}\n\n=== ANSWER C ===\n{c}\n\n"
          "Score all three on groundedness, correctness and usefulness, set the honesty "
          "flags, rank them, and submit.")


def _fields() -> dict:
    s: dict = {}
    for x in SLOTS:
        X = x.upper()
        s[f"{x}_groundedness"] = Annotated[int, f"Answer {X} groundedness, 1-10"]
        s[f"{x}_correctness"] = Annotated[int, f"Answer {X} correctness, 1-10"]
        s[f"{x}_usefulness"] = Annotated[int, f"Answer {X} usefulness, 1-10"]
        s[f"{x}_reason"] = Annotated[str, f"One sentence on Answer {X}"]
        s[f"{x}_fabricated"] = Annotated[bool, f"Answer {X} names something that does not exist"]
        s[f"{x}_hedged"] = Annotated[bool, f"Answer {X} declined to commit"]
        s[f"{x}_overclaimed"] = Annotated[bool, f"Answer {X} asserted unsupportable completeness"]
    s["best_answer"] = Annotated[str, "Which answer is best overall: 'A', 'B' or 'C'"]
    s["ranking"] = Annotated[str, "Full ranking, e.g. 'B>A>C'"]
    s["margin"] = Annotated[str, "Gap from best to second: 'decisive', 'clear', 'slight', 'none'"]
    s["fabrication_notes"] = Annotated[str, "What was fabricated, if anything; else 'none'"]
    return s


JUDGEMENT_SCHEMA = _fields()


def render(ans: dict) -> str:
    a = ans or {}
    named = "; ".join(a.get("papers_named") or []) or "(none named)"
    return (f"{str(a.get('answer','')).strip()}\n\n"
            f"[papers relied on: {named}]\n"
            f"[stated confidence: {a.get('confidence','?')}]\n"
            f"[stated limits: {a.get('limits','')}]")


def load_units() -> list[tuple[dict, dict]]:
    """(question, {arm: row}) for every question complete on ALL THREE arms."""
    qs = {q["question_id"]: q for q in
          json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]}
    rows = [json.loads(l) for l in ANSWERS.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_q: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_q.setdefault(r["question_id"], {})[r["arm"]] = r
    out = []
    for qid, q in qs.items():
        d = by_q.get(qid, {})
        if all(d.get(a) and d[a].get("answer") for a in ARMS):
            out.append((q, d))
        else:
            missing = [a for a in ARMS if not (d.get(a) and d[a].get("answer"))]
            print(f"  (skipping {qid}: no completed answer for {missing})")
    return out


def done_keys() -> set[str]:
    if not CKPT.exists():
        return set()
    return {json.loads(l)["question_id"] for l in
            CKPT.read_text(encoding="utf-8").splitlines() if l.strip()}


def append(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def _clamp(v):
    try:
        return max(1, min(10, int(v)))
    except (TypeError, ValueError):
        return None


async def judge_one(question: str, rendered: dict[str, str], *, model: str,
                    max_turns: int, budget_usd: float) -> dict:
    import time
    from claude_agent_sdk import (query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
                                  ResultMessage)
    holder: dict = {}

    @tool("submit_judgement", "Record your scores for all three answers. Call exactly once.",
          JUDGEMENT_SCHEMA)
    async def submit_judgement(args):
        holder["j"] = {k: args.get(k) for k in JUDGEMENT_SCHEMA}
        return {"content": [{"type": "text", "text": "recorded"}]}

    opts = ClaudeAgentOptions(
        system_prompt=JUDGE_SYS,
        mcp_servers={"io": create_sdk_mcp_server(name="io", tools=[submit_judgement])},
        allowed_tools=["mcp__io__submit_judgement"],
        max_turns=max_turns, model=model,
        permission_mode="bypassPermissions", max_budget_usd=budget_usd,
    )
    t0 = time.time()
    result = None
    async for msg in query(prompt=PROMPT.format(question=question, **rendered), options=opts):
        if isinstance(msg, ResultMessage):
            result = msg
    j = holder.get("j")
    return {"judgement": j, "completed": j is not None,
            "seconds": round(time.time() - t0, 1),
            "num_turns": getattr(result, "num_turns", None),
            "total_cost_usd": getattr(result, "total_cost_usd", None),
            "usage": getattr(result, "usage", None),
            "stop_reason": getattr(result, "stop_reason", None),
            "is_error": getattr(result, "is_error", None)}


def build_row(q: dict, perm: tuple[str, ...], rows: dict[str, dict], res: dict) -> dict:
    """Un-blind A/B/C back onto graph/web/null. Scores lead the row."""
    j = res["judgement"]
    slot_of = {arm: SLOTS[i] for i, arm in enumerate(perm)}   # arm -> 'a'/'b'/'c'
    arm_of = {SLOTS[i]: arm for i, arm in enumerate(perm)}

    def sc(arm, axis):
        return _clamp(j[f"{slot_of[arm]}_{axis}"])

    def fl(arm, name):
        return bool(j.get(f"{slot_of[arm]}_{name}"))

    best_slot = str(j.get("best_answer") or "").strip().lower()[:1]
    best_arm = arm_of.get(best_slot, "unclear")
    ranking = str(j.get("ranking") or "")
    for s in SLOTS:                      # rewrite 'B>A>C' into arm names
        ranking = ranking.replace(s.upper(), arm_of[s])

    row = {
        "question_id": q["question_id"], "family": q["family"],
        "expected_winner": q["expected_winner"],
        "best_answer": best_arm, "margin": str(j.get("margin") or "none").lower(),
        "prediction_hit": best_arm == q["expected_winner"],
        "ranking": ranking,
    }
    for arm in ARMS:
        row[f"{arm}_groundedness"] = sc(arm, "groundedness")
        row[f"{arm}_correctness"] = sc(arm, "correctness")
        row[f"{arm}_usefulness"] = sc(arm, "usefulness")
    for arm in ARMS:
        row[f"{arm}_fabricated"] = fl(arm, "fabricated")
        row[f"{arm}_hedged"] = fl(arm, "hedged")
        row[f"{arm}_overclaimed"] = fl(arm, "overclaimed")
    row["question"] = q["question"]
    for arm in ARMS:
        row[f"{arm}_reason"] = j.get(f"{slot_of[arm]}_reason")
    row["fabrication_notes"] = j.get("fabrication_notes")
    row["presentation_order"] = list(perm)
    row["judge_model"] = res["model"]
    for k in ("seconds", "num_turns", "total_cost_usd", "usage", "stop_reason", "is_error"):
        row[k] = res[k]
    row["gen_cost_usd"] = {a: rows[a].get("total_cost_usd") for a in ARMS}
    row["gen_seconds"] = {a: rows[a].get("seconds") for a in ARMS}
    row["gen_explore"] = {a: rows[a].get("n_explore") for a in ARMS}
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", help="comma-separated question_ids")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--max-turns", type=int, default=6)
    ap.add_argument("--budget", type=float, default=0.80)
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not ANSWERS.exists():
        sys.exit(f"no answers at {ANSWERS} — run qa_gen.py first.")
    units = load_units()
    # permutation is fixed by index in the FULL list, before filtering, so --limit
    # never changes which order a question is judged in
    perm_of = {q["question_id"]: PERMS[i % len(PERMS)] for i, (q, _) in enumerate(units)}
    if args.questions:
        keep = set(args.questions.split(","))
        units = [u for u in units if u[0]["question_id"] in keep]
    if args.limit:
        units = units[: args.limit]
    done = done_keys()
    todo = [u for u in units if u[0]["question_id"] not in done]
    print(f"questions={len(units)} done={len(units) - len(todo)} todo={len(todo)}")

    if args.dry_run:
        for q, rows in todo[:1]:
            perm = perm_of[q["question_id"]]
            rendered = {SLOTS[i]: render(rows[arm]["answer"]) for i, arm in enumerate(perm)}
            print(f"\n--- {q['question_id']} order={perm} ---")
            print(PROMPT.format(question=q["question"], **rendered)[:1500], "...")
        print(f"\n(dry-run) would run {len(todo)} judgements on {args.model}. No model called.")
        return

    import time

    async def go():
        spend = 0.0
        for i, (q, rows) in enumerate(todo, 1):
            perm = perm_of[q["question_id"]]
            rendered = {SLOTS[k]: render(rows[arm]["answer"]) for k, arm in enumerate(perm)}
            print(f"[{i}/{len(todo)}] {q['question_id']} order={'/'.join(perm)}", flush=True)
            try:
                res = await judge_one(q["question"], rendered, model=args.model,
                                      max_turns=args.max_turns, budget_usd=args.budget)
            except KeyboardInterrupt:
                print("\ninterrupted — partial judgement not saved; safe to resume.")
                raise
            if not res["completed"]:
                print(f"    NO-JUDGEMENT (stop={res['stop_reason']}) — not saved, will retry",
                      flush=True)
                continue
            res["model"] = args.model
            row = build_row(q, perm, rows, res)
            append(row)
            spend += res["total_cost_usd"] or 0.0
            hit = "PREDICTED" if row["prediction_hit"] else f"MISS(exp {row['expected_winner']})"
            fab = [a for a in ARMS if row[f"{a}_fabricated"]]
            print(f"    best={row['best_answer']} ({row['margin']}) {hit} | "
                  f"G {row['graph_groundedness']}/{row['graph_correctness']}/{row['graph_usefulness']} "
                  f"W {row['web_groundedness']}/{row['web_correctness']}/{row['web_usefulness']} "
                  f"N {row['null_groundedness']}/{row['null_correctness']}/{row['null_usefulness']}"
                  + (f" | FABRICATED: {fab}" if fab else "")
                  + f"  ${res['total_cost_usd']} (run ${spend:.2f})", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")


if __name__ == "__main__":
    main()
