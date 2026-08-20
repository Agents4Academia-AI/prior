#!/usr/bin/env python3
"""Render the answers + judgements as readable markdown. (zero cost, no LLM)

Regenerate any time — it renders whatever is in out/ so far, so it works mid-run
with only a couple of questions done.

  python report.py                  # -> out/REPORT.md
  python report.py --out X.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("graph", "web", "null")
LABEL = {"graph": "GRAPH (Prior atlas)", "web": "WEB (search)", "null": "NULL (closed book)"}
AXES = ("groundedness", "correctness", "usefulness")


def load(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def flags(j: dict, arm: str) -> str:
    on = [n for n in ("fabricated", "hedged", "overclaimed") if j.get(f"{arm}_{n}")]
    return ", ".join(on) if on else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "out" / "REPORT.md"))
    args = ap.parse_args()

    qs = {q["question_id"]: q for q in
          json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]}
    answers = load(HERE / "out" / "answers.jsonl")
    judged = {j["question_id"]: j for j in load(HERE / "out" / "qa_judgements.jsonl")}
    by_q: dict[str, dict[str, dict]] = {}
    for r in answers:
        by_q.setdefault(r["question_id"], {})[r["arm"]] = r
    if not by_q:
        sys.exit("no answers yet — run qa_gen.py first.")

    order = [q for q in qs if q in by_q]
    L: list[str] = []
    A = L.append

    A("# QA experiment — answers and judgements in full\n")
    A(f"*Generated from `out/answers.jsonl` + `out/qa_judgements.jsonl`. "
      f"{len(order)} of {len(qs)} questions answered, {len(judged)} judged. "
      f"Design + registered predictions: [PLAN.md](../PLAN.md).*\n")

    # blinding gate — surfaced here so a leak can never be quietly read past
    try:
        from check_leakage import scan as leak_scan
        leaks = []
        for r in answers:
            a = r.get("answer") or {}
            h = leak_scan(" ".join(str(a.get(f, "")) for f in ("answer", "limits")))
            if h:
                leaks.append((r["question_id"], r["arm"],
                              "; ".join(f"{k}={v[:3]}" for k, v in h.items())))
        if leaks:
            A("> ⚠️ **Blinding leak — these rows are not safely judgeable and should be "
              "regenerated, then re-judged:**  ")
            for qid, arm, what in leaks:
                A(f"> `{qid}` [{arm}]: {what}  ")
            A("")
        else:
            A("> ✅ Blinding gate clean — no answer reveals how it was produced.\n")
    except Exception as e:                      # never let the gate break the report
        A(f"> *(leak check unavailable: {e})*\n")

    # ── scoreboard ───────────────────────────────────────────────────────────
    A("## Scoreboard\n")
    A("Scores are groundedness / correctness / usefulness, each 1-10.\n")
    A("| q | expected | best | margin | prediction | GRAPH | WEB | NULL |")
    A("|---|---|---|---|---|---|---|---|")
    for qid in order:
        j = judged.get(qid)
        if not j:
            A(f"| {qid} | {qs[qid]['expected_winner']} | *not judged* | | | | | |")
            continue
        cells = [f"{j[f'{a}_groundedness']}/{j[f'{a}_correctness']}/{j[f'{a}_usefulness']}"
                 for a in ARMS]
        A(f"| **{qid}** | {j['expected_winner']} | **{j['best_answer']}** | {j['margin']} | "
          f"{'✅ hit' if j['prediction_hit'] else '❌ miss'} | " + " | ".join(cells) + " |")
    A("")

    if judged:
        A("### Mean scores so far\n")
        A("| arm | groundedness | correctness | usefulness | fabricated | hedged | overclaimed |")
        A("|---|---|---|---|---|---|---|")
        for a in ARMS:
            js = list(judged.values())
            m = [sum(j[f"{a}_{x}"] for j in js) / len(js) for x in AXES]
            fl = [sum(bool(j[f"{a}_{n}"]) for j in js)
                  for n in ("fabricated", "hedged", "overclaimed")]
            A(f"| {LABEL[a]} | {m[0]:.1f} | {m[1]:.1f} | {m[2]:.1f} | "
              f"{fl[0]}/{len(js)} | {fl[1]}/{len(js)} | {fl[2]}/{len(js)} |")
        A("")
        A("**Lift over the null arm** (the number that says what each environment is worth):\n")
        A("| arm | Δ groundedness | Δ correctness | Δ usefulness |")
        A("|---|---|---|---|")
        js = list(judged.values())
        base = {x: sum(j[f"null_{x}"] for j in js) / len(js) for x in AXES}
        for a in ("graph", "web"):
            d = [sum(j[f"{a}_{x}"] for j in js) / len(js) - base[x] for x in AXES]
            A(f"| {LABEL[a]} | {d[0]:+.1f} | {d[1]:+.1f} | {d[2]:+.1f} |")
        A("")

    # ── cost / effort ────────────────────────────────────────────────────────
    A("## Cost and effort\n")
    A("| q | arm | explore calls | seconds | cost | papers named | confidence |")
    A("|---|---|---|---|---|---|---|")
    tot: dict[str, list[float]] = {a: [0.0, 0.0, 0] for a in ARMS}
    for qid in order:
        for a in ARMS:
            r = by_q[qid].get(a)
            if not r:
                continue
            ans = r.get("answer") or {}
            n = len(ans.get("papers_named") or [])
            A(f"| {qid} | {a} | {r['n_explore']} | {r['seconds']} | "
              f"${r.get('total_cost_usd', 0):.3f} | {n} | {ans.get('confidence', '?')} |")
            tot[a][0] += r.get("total_cost_usd") or 0
            tot[a][1] += r.get("seconds") or 0
            tot[a][2] += n
    A("")
    jc = sum(j.get("total_cost_usd") or 0 for j in judged.values())
    A(f"Generation total: **${sum(t[0] for t in tot.values()):.2f}** "
      f"(" + ", ".join(f"{a} ${tot[a][0]:.2f}" for a in ARMS) + f"). "
      f"Judging total: **${jc:.2f}**.\n")

    # ── per question ─────────────────────────────────────────────────────────
    for qid in order:
        q = qs[qid]
        j = judged.get(qid)
        A("\n---\n")
        A(f"## {qid} — {q['family']}\n")
        A(f"> {q['question']}\n")
        A(f"**Expected winner:** `{q['expected_winner']}`  ")
        if j:
            A(f"**Judged best:** `{j['best_answer']}` ({j['margin']} margin) — "
              f"{'prediction hit' if j['prediction_hit'] else '**PREDICTION MISS**'}  ")
            A(f"**Ranking:** {j['ranking']}  ")
            A(f"**Presentation order:** {' / '.join(j['presentation_order'])}\n")
        A(f"<details><summary>What the atlas actually holds (never shown to any arm)</summary>\n\n"
          f"{q['graph_structure']}\n\n</details>\n")

        for a in ARMS:
            r = by_q[qid].get(a)
            if not r:
                continue
            ans = r.get("answer") or {}
            A(f"### {LABEL[a]}\n")
            if j:
                A(f"**{j[f'{a}_groundedness']}** grounded · **{j[f'{a}_correctness']}** correct "
                  f"· **{j[f'{a}_usefulness']}** useful · flags: {flags(j, a)}\n")
            A(str(ans.get("answer", "")).strip() + "\n")
            named = ans.get("papers_named") or []
            A(f"**Papers named ({len(named)}):** " +
              ("; ".join(named) if named else "*none*") + "  ")
            A(f"**Stated confidence:** {ans.get('confidence', '?')}  ")
            A(f"**Stated limits:** {ans.get('limits', '—')}  ")
            A(f"**Effort:** {r['n_explore']} exploration calls, {r['seconds']}s, "
              f"${r.get('total_cost_usd', 0):.3f}")
            if a == "graph" and r.get("tool_args"):
                used: dict[str, int] = {}
                for t in r["tool_args"]:
                    used[t["tool"].replace("mcp__graph__", "")] = \
                        used.get(t["tool"].replace("mcp__graph__", ""), 0) + 1
                A(f"  \n**Graph tools used:** " +
                  ", ".join(f"`{k}`×{v}" for k, v in sorted(used.items(), key=lambda x: -x[1])))
            A("")
            if j:
                A(f"> *Judge:* {j[f'{a}_reason']}\n")

        if j:
            A(f"**Fabrication notes:** {j['fabrication_notes']}\n")
            A(f"*Judged in {j['seconds']}s for ${j.get('total_cost_usd', 0):.3f}.*\n")

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {out}  ({len(order)} questions, {len(judged)} judged, "
          f"{len('\n'.join(L)):,} chars)")


if __name__ == "__main__":
    main()
