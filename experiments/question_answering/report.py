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


def consensus(runs: list[dict]) -> dict:
    """Collapse N judge runs of ONE question into a single row.

    A single judge pass is noisier than the effect it measures: judging q01-q03
    twice on IDENTICAL answers moved 7 of 27 axis scores by a point and flipped
    one of three winners. So scores are MEANS over runs, and the min/max are kept
    so the spread can be shown rather than hidden behind an average.

    Winner is a majority vote; with no majority it is reported as "split", which
    is the honest outcome and not a tie broken by fiat. A flag is set when a
    MAJORITY of runs set it, with the vote count retained.
    """
    n = len(runs)
    out = dict(runs[0])                       # question, family, expectations, text
    out["n_runs"] = n
    for a in ARMS:
        for x in AXES:
            vals = [r[f"{a}_{x}"] for r in runs]
            out[f"{a}_{x}"] = sum(vals) / n
            out[f"{a}_{x}_lo"], out[f"{a}_{x}_hi"] = min(vals), max(vals)
        for f in ("fabricated", "unrecognised", "hedged", "overclaimed"):
            votes = sum(bool(r.get(f"{a}_{f}")) for r in runs)
            out[f"{a}_{f}_votes"] = votes
            out[f"{a}_{f}"] = votes * 2 > n
    votes = {a: sum(1 for r in runs if r["best_answer"] == a) for a in ARMS}
    top = max(votes, key=lambda a: votes[a])
    out["best_votes"] = votes
    out["best_answer"] = top if votes[top] * 2 > n else "split"
    out["unanimous"] = votes[top] == n
    out["prediction_hit"] = out["best_answer"] == out["expected_winner"]
    out["margin"] = max((r["margin"] for r in runs),
                        key=lambda m: sum(1 for r in runs if r["margin"] == m))
    return out


def flags(j: dict, arm: str) -> str:
    on = [n for n in ("fabricated", "unrecognised", "hedged", "overclaimed")
          if j.get(f"{arm}_{n}")]
    return ", ".join(on) if on else "—"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "out" / "REPORT.md"))
    args = ap.parse_args()

    qs = {q["question_id"]: q for q in
          json.loads((HERE / "questions.json").read_text(encoding="utf-8"))["questions"]}
    answers = load(HERE / "out" / "answers.jsonl")
    runs_by_q: dict[str, list[dict]] = {}
    for j in load(HERE / "out" / "qa_judgements.jsonl"):
        runs_by_q.setdefault(j["question_id"], []).append(j)
    judged = {qid: consensus(rs) for qid, rs in runs_by_q.items()}
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

    # seal gate — v1 silently let Bash/Skill/WebSearch into the graph and null arms
    breaches = [(r["question_id"], r["arm"], r["off_arm_tools"])
                for r in answers if r.get("off_arm_tools")]
    if breaches:
        A("> 🚨 **SEAL BREACH — these rows reached outside their arm and must be "
          "discarded, not judged:**  ")
        for qid, arm, tls in breaches:
            A(f"> `{qid}` [{arm}]: used {tls}  ")
        A("")
    elif any("off_arm_tools" in r for r in answers):
        A("> ✅ Arm seal intact — no answer used a tool outside its environment.\n")

    # ── scoreboard ───────────────────────────────────────────────────────────
    A("## Scoreboard\n")
    A("Scores are groundedness / correctness / usefulness, each 1-10.\n")
    nruns = {j["n_runs"] for j in judged.values()} or {0}
    if max(nruns) > 1:
        A(f"Each question was judged **{'/'.join(str(n) for n in sorted(nruns))} "
          f"times**, each run with a different presentation order. Scores are means; "
          f"the winner column shows the vote as graph/web/null. See "
          f"*Judge reliability* below for the spread.\n")
    A("| q | expected | best | margin | prediction | GRAPH | WEB | NULL |")
    A("|---|---|---|---|---|---|---|---|")
    for qid in order:
        j = judged.get(qid)
        if not j:
            A(f"| {qid} | {qs[qid]['expected_winner']} | *not judged* | | | | | |")
            continue
        cells = [f"{j[f'{a}_groundedness']:.1f}/{j[f'{a}_correctness']:.1f}"
                 f"/{j[f'{a}_usefulness']:.1f}" for a in ARMS]
        win = f"**{j['best_answer']}**"
        if j["n_runs"] > 1:
            v = j["best_votes"]
            win += f" ({'/'.join(str(v[a]) for a in ARMS)})"
        A(f"| **{qid}** | {j['expected_winner']} | {win} | {j['margin']} | "
          f"{'✅ hit' if j['prediction_hit'] else '❌ miss'} | " + " | ".join(cells) + " |")
    A("")

    if judged:
        # CONTROLS ARE NOT POOLED WITH THE STRUCTURAL QUESTIONS. c01/c02 are
        # designed for the graph arm to LOSE — c01 has nothing in the corpus at
        # all. Averaging them in drags the graph mean down by design and makes the
        # headline number meaningless in both directions. They are reported
        # separately, where "graph loses" is the intended result, not a deficit.
        def _mean_block(title: str, js: list[dict], note: str = "") -> None:
            if not js:
                return
            A(f"### {title}  *(n={len(js)})*\n")
            if note:
                A(f"{note}\n")
            A("| arm | groundedness | correctness | usefulness | fabricated | "
              "unrecognised | hedged | overclaimed |")
            A("|---|---|---|---|---|---|---|---|")
            for a in ARMS:
                m = [sum(j[f"{a}_{x}"] for j in js) / len(js) for x in AXES]
                # .get(): judgements made before the fabricated/unrecognised split
                # carry no `unrecognised` key, and a partial re-judge mixes both
                # count QUESTIONS where a majority of runs set the flag
                fl = [sum(bool(j.get(f"{a}_{n}")) for j in js)
                      for n in ("fabricated", "unrecognised", "hedged", "overclaimed")]
                A(f"| {LABEL[a]} | {m[0]:.1f} | {m[1]:.1f} | {m[2]:.1f} | "
                  f"{fl[0]}/{len(js)} | {fl[1]}/{len(js)} | {fl[2]}/{len(js)} | "
                  f"{fl[3]}/{len(js)} |")
            A("")

        struct = [j for j in judged.values() if not j["family"].startswith("control")]
        ctrl = [j for j in judged.values() if j["family"].startswith("control")]
        _mean_block("Mean scores — STRUCTURAL questions", struct,
                    "The questions the atlas is supposed to help with.")
        _mean_block("Mean scores — CONTROLS", ctrl,
                    "**The graph arm is supposed to lose these.** c01 is outside the "
                    "corpus entirely; c02 needs numbers the bundle does not hold. A "
                    "graph win here would mean the judge or the blinding is broken.")
        if any("unrecognised" not in " ".join(j.keys()) for j in judged.values()):
            A("> ⚠️ Some judgements predate the `fabricated`/`unrecognised` split "
              "(judge v2) and count 0 unrecognised by construction. Re-judge those "
              "questions before comparing the two columns.\n")

        # Two winner definitions, because they DISAGREE and hiding that would be
        # the dishonest choice. `best_answer` is the judge's holistic call; the
        # axis total is a flat unweighted sum it never agreed to. On q02 the judge
        # named graph best while web led 25-24 on the sum.
        A("**Who won, by both definitions** — they are not the same measure:\n")
        A("| set | judge's `best_answer` | highest axis total |")
        A("|---|---|---|")
        for name, js in (("structural (q01-q06)", struct), ("controls (c01-c02)", ctrl)):
            if not js:
                continue
            hol, tot = {a: 0 for a in ARMS}, {a: 0 for a in ARMS}
            for j in js:
                hol[j["best_answer"]] = hol.get(j["best_answer"], 0) + 1
                sums = {a: sum(j[f"{a}_{x}"] for x in AXES) for a in ARMS}
                tot[max(sums, key=lambda a: sums[a])] += 1
            f = lambda d: " / ".join(f"{a} {d[a]}" for a in ARMS)      # noqa: E731
            A(f"| {name} | {f(hol)} | {f(tot)} |")
        A("")
        A("> Where the two disagree the margin was `slight` — that is the "
          "instrument telling you the answers were close, and it should be "
          "reported rather than resolved by picking the more flattering rule.\n")

        A("**Lift over the null arm, STRUCTURAL questions only** (the number that "
          "says what each environment is worth):\n")
        A("| arm | Δ groundedness | Δ correctness | Δ usefulness |")
        A("|---|---|---|---|")
        js = struct or list(judged.values())
        base = {x: sum(j[f"null_{x}"] for j in js) / len(js) for x in AXES}
        for a in ("graph", "web"):
            d = [sum(j[f"{a}_{x}"] for j in js) / len(js) - base[x] for x in AXES]
            A(f"| {LABEL[a]} | {d[0]:+.1f} | {d[1]:+.1f} | {d[2]:+.1f} |")
        A("")

    # ── judge reliability ───────────────────────────────────────────────────
    multi = [j for j in judged.values() if j["n_runs"] > 1]
    if multi:
        A("### Judge reliability\n")
        A("The same judge, the same answers, a different presentation order. This is "
          "the noise floor every score above sits on — and it is the reason not to "
          "lean on win counts.\n")
        A("| q | runs | winner | unanimous? | widest axis spread |")
        A("|---|---|---|---|---|")
        spreads = []
        for qid in order:
            j = judged.get(qid)
            if not j or j["n_runs"] < 2:
                continue
            worst, where = 0, ""
            for a in ARMS:
                for x in AXES:
                    d = j[f"{a}_{x}_hi"] - j[f"{a}_{x}_lo"]
                    if d > worst:
                        worst, where = d, f"{a} {x} {j[f'{a}_{x}_lo']}-{j[f'{a}_{x}_hi']}"
            spreads.append(worst)
            v = j["best_votes"]
            A(f"| {qid} | {j['n_runs']} | {j['best_answer']} "
              f"({'/'.join(str(v[a]) for a in ARMS)}) | "
              f"{'yes' if j['unanimous'] else '**no**'} | "
              f"{worst} pt{'s' if worst != 1 else ''}"
              f"{' (' + where + ')' if where else ''} |")
        A("")
        unan = sum(1 for j in multi if j["unanimous"])
        A(f"> **{unan} of {len(multi)}** questions had a unanimous winner. "
          f"Median widest axis spread: "
          f"**{sorted(spreads)[len(spreads) // 2] if spreads else 0} points**. "
          f"Any margin at or below that is a tie, whatever the mean says.\n")

    # ── cost / effort ────────────────────────────────────────────────────────
    A("## Efficiency\n")
    A("**`payload chars`** is the headline (PLAN §5) — the direct count of what the "
      "tools returned, summed by our own code, so nothing in the harness can move "
      "it. **Lower is better.** `context` = input + cache_creation + cache_read, "
      "what the model actually had to process.\n")
    A("> `tokens_in` (input + cache_creation) was the ORIGINAL pre-registered "
      "headline and is kept here so the record is complete, but it is **not** a "
      "measure of ingestion: `cache_creation` tracks how the conversation prefix "
      "was re-chunked across turns. On q01/graph, payload fell ~5,500 tokens "
      "between v2 and v3 while cache_creation rose 27,345. See PLAN §5.\n")
    A("| q | arm | **payload chars** | context | tokens_in | tool calls | turns | seconds | cost |")
    A("|---|---|---|---|---|---|---|---|---|")
    tot: dict[str, list[float]] = {a: [0.0, 0.0, 0] for a in ARMS}
    eff: dict[str, list[int]] = {a: [0, 0, 0, 0, 0] for a in ARMS}  # tok, calls, chars, n, ctx
    for qid in order:
        for a in ARMS:
            r = by_q[qid].get(a)
            if not r:
                continue
            ans = r.get("answer") or {}
            n = len(ans.get("papers_named") or [])
            ti, pc = r.get("tokens_in") or 0, r.get("payload_chars") or 0
            cx = r.get("context_total") or 0
            A(f"| {qid} | {a} | **{pc:,}** | {cx:,} | {ti:,} | {r['n_explore']} | "
              f"{r.get('num_turns', '?')} | {r['seconds']} | "
              f"${r.get('total_cost_usd', 0):.3f} |")
            tot[a][0] += r.get("total_cost_usd") or 0
            tot[a][1] += r.get("seconds") or 0
            tot[a][2] += n
            eff[a][0] += ti
            eff[a][1] += r["n_explore"]
            eff[a][2] += pc
            eff[a][3] += 1
            eff[a][4] += cx
    A("")
    A("**Means per answer** — the number the compactness claim lives or dies on:\n")
    A("| arm | payload chars | context | tokens_in | tool calls | papers named | cost |")
    A("|---|---|---|---|---|---|---|")
    for a in ARMS:
        k = eff[a][3] or 1
        A(f"| {LABEL[a]} | **{eff[a][2] / k:,.0f}** | {eff[a][4] / k:,.0f} | "
          f"{eff[a][0] / k:,.0f} | {eff[a][1] / k:.1f} | "
          f"{tot[a][2] / k:.1f} | ${tot[a][0] / k:.3f} |")
    A("")
    # Scored on payload_chars, the headline, and ONLY over questions where BOTH
    # arms have a row. A partial run otherwise compares one arm's mean over 1
    # question against the other's over 4, which is not a comparison at all.
    paired = [q for q in order if by_q[q].get("graph") and by_q[q].get("web")]
    gi = wi = 0.0
    if paired:
        gi = sum(by_q[q]["graph"].get("payload_chars") or 0 for q in paired) / len(paired)
        wi = sum(by_q[q]["web"].get("payload_chars") or 0 for q in paired) / len(paired)
    if gi and wi:
        ok = gi < wi
        A(f"> **{'✅' if ok else '❌'} Compactness prediction "
          f"{'HOLDS' if ok else 'FAILS'}** — over the {len(paired)} question(s) "
          f"answered by BOTH arms ({', '.join(paired)}), the graph arm pulls "
          f"{gi:,.0f} payload chars per answer against web's {wi:,.0f} "
          f"({gi / wi:.2f}×).\n")
    if len(paired) < len(order):
        A(f"> ⚠️ Partial run: {len(paired)} of {len(order)} questions have both a "
          f"graph and a web row. The per-arm means above are computed over "
          f"DIFFERENT question sets and are not comparable until the run "
          f"completes.\n")
    A("### Stated confidence\n")
    A("| q | arm | papers named | confidence |")
    A("|---|---|---|---|")
    for qid in order:
        for a in ARMS:
            r = by_q[qid].get(a)
            if not r:
                continue
            ans = r.get("answer") or {}
            A(f"| {qid} | {a} | {len(ans.get('papers_named') or [])} | "
              f"{ans.get('confidence', '?')} |")
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
            A(f"**Effort:** {r['n_explore']} exploration calls, "
              f"{r.get('payload_chars') or 0:,} payload chars, "
              f"{r.get('context_total') or 0:,} context, {r['seconds']}s, "
              f"${r.get('total_cost_usd', 0):.3f}")
            if a == "graph" and r.get("tool_args"):
                used: dict[str, int] = {}
                for t in r["tool_args"]:
                    used[t["tool"].replace("mcp__graph__", "")] = \
                        used.get(t["tool"].replace("mcp__graph__", ""), 0) + 1
                A(f"  \n**Graph tools used:** " +
                  ", ".join(f"`{k}`×{v}" for k, v in sorted(used.items(), key=lambda x: -x[1])))
                A("  \n**Call trace:** " + " → ".join(
                    f"{t['tool'].replace('mcp__graph__', '')}"
                    f"({(t.get('result_chars') or 0):,}ch)" for t in r["tool_args"]))
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
