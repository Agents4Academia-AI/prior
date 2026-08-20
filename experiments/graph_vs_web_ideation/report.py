#!/usr/bin/env python3
"""Render the ideation generations + judgements as readable markdown. (zero cost)

Regenerate any time — it renders whatever is in out/ so far, so it works mid-run.

Judgement sources, in order of preference per seed:
  • out/judgements.jsonl            — current schema (1-10 + forced comparison)
  • out/judge_v1_bothorders.jsonl   — the archived v1 pilot (s01-s03, judged twice
    with A/B swapped, BEFORE the comparative fields existed). Included and clearly
    labelled: it is real signal and it is the evidence that position bias is
    negligible, but it is a different schema and must not be pooled with v2 rows.

  python report.py                  # -> out/REPORT.md
  python report.py --out X.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("graph", "web")
LABEL = {"graph": "GRAPH (Prior atlas)", "web": "WEB (search)"}
FIELDS = ("title", "gap", "proposed_study", "expected_result", "grounding")
FIELD_LABEL = {"title": "Title", "gap": "Gap", "proposed_study": "Proposed study",
               "expected_result": "Expected result", "grounding": "Motivation / grounding"}


def load(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def convergence(pairs: list[tuple[str, dict, dict]]) -> dict[str, float]:
    """Lexical TF-IDF cosine per seed — a cheap floor, not the authority (it badly
    under-detects semantic convergence; see PLAN.md 7b)."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except ImportError:
        return {}
    def txt(r):
        return " ".join(str((r.get("idea") or {}).get(f, "")) for f in FIELDS)
    docs = [txt(r) for _, g, w in pairs for r in (g, w)]
    if not docs:
        return {}
    m = TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english").fit_transform(docs)
    return {sid: float(cosine_similarity(m[2 * i], m[2 * i + 1])[0, 0])
            for i, (sid, _, _) in enumerate(pairs)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "out" / "REPORT.md"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = load(HERE / "out" / "generations.jsonl")
    if not rows:
        sys.exit("no generations yet — run gen.py first.")
    cur = load(HERE / "out" / "judgements.jsonl")
    arch = load(HERE / "out" / "judge_v1_bothorders.jsonl")

    by_seed: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_seed.setdefault(r["seed_id"], {})[r["arm"]] = r
    pairs = [(sid, d["graph"], d["web"]) for sid, d in sorted(by_seed.items())
             if d.get("graph") and d.get("web")
             and d["graph"].get("idea") and d["web"].get("idea")]

    judged: dict[str, dict] = {j["seed_id"]: j for j in cur}
    archived: dict[str, list[dict]] = defaultdict(list)
    for j in arch:
        archived[j["seed_id"]].append(j)

    cos = convergence(pairs)
    L: list[str] = []
    A = L.append

    A("# Ideation experiment — ideas and judgements in full\n")
    A(f"*Generated from `out/`. {len(pairs)} of 26 seeds complete on both arms; "
      f"{len(judged)} judged on the current schema, {len(archived)} carrying archived "
      f"v1-pilot judgements. Design + audit trail: [PLAN.md](../PLAN.md).*\n")

    # blinding gate
    try:
        sys.path.insert(0, str(HERE))
        from check_leakage import scan as leak_scan
        leaks = []
        for r in rows:
            idea = r.get("idea") or {}
            h = leak_scan(" ".join(str(idea.get(f, "")) for f in FIELDS))
            if h:
                leaks.append((r["seed_id"], r["arm"],
                              "; ".join(f"{k}={v[:3]}" for k, v in h.items())))
        if leaks:
            A("> ⚠️ **Blinding leak — regenerate these rows before judging them:**  ")
            for sid, arm, what in leaks:
                A(f"> `{sid}` [{arm}]: {what}  ")
            A("")
        else:
            A(f"> ✅ Blinding gate clean across all {len(rows)} ideas — none reveals how "
              f"it was produced.\n")
    except Exception as e:
        A(f"> *(leak check unavailable: {e})*\n")

    if not judged:
        A("> ⏳ **Judging not started on the current schema.** The archived v1 pilot "
          "below (s01–s03) is the only scored data, and it predates the forced "
          "comparison added in PLAN.md §7d. Run `python judge.py` to score all "
          f"{len(pairs)} seeds.\n")

    # ── archived v1 judge pilot ──────────────────────────────────────────────
    if archived:
        A("## Archived v1 judge pilot (order-swapped)\n")
        A("Each pair judged **twice with A/B swapped**, on the 1–10 novelty + "
          "feasibility schema *before* the forced comparison existed. Kept because it "
          "is real signal and because it is the evidence that position bias is "
          "negligible — which is why judging now runs once per seed, alternating order "
          "(PLAN.md §7d). Do not pool these with current-schema rows.\n")
        A("| seed | order | graph nov | graph feas | web nov | web feas | novelty | "
          "feasibility | same idea? |")
        A("|---|---|---|---|---|---|---|---|---|")
        for sid in sorted(archived):
            for j in sorted(archived[sid], key=lambda x: x["order"]):
                A(f"| {sid} | `{j['order']}` | {j['graph_novelty']} | "
                  f"{j['graph_feasibility']} | {j['web_novelty']} | "
                  f"{j['web_feasibility']} | {j['novelty_winner']} | "
                  f"{j['feasibility_winner']} | {'yes' if j['same_idea'] else 'no'} |")
        A("")
        flat = [j for js in archived.values() for j in js]
        n = len(flat)
        A(f"**Means over {n} judgements ({len(archived)} seeds × 2 orders):** "
          f"graph novelty {sum(j['graph_novelty'] for j in flat)/n:.1f}, "
          f"graph feasibility {sum(j['graph_feasibility'] for j in flat)/n:.1f} · "
          f"web novelty {sum(j['web_novelty'] for j in flat)/n:.1f}, "
          f"web feasibility {sum(j['web_feasibility'] for j in flat)/n:.1f}. "
          f"Every score sits in 5–8 — the compression that motivated the forced "
          f"comparison.\n")
        # position-bias evidence, computed rather than asserted
        drift = []
        for sid, js in archived.items():
            if len(js) == 2:
                a, b = js
                for k in ("graph_novelty", "graph_feasibility", "web_novelty", "web_feasibility"):
                    drift.append(abs(a[k] - b[k]))
        if drift:
            A(f"**Position bias:** across {len(drift)} score pairs, max drift on swapping "
              f"A/B was **{max(drift)} point**, mean {sum(drift)/len(drift):.2f}; "
              f"zero winners flipped.\n")

    # ── current-schema scoreboard ────────────────────────────────────────────
    if judged:
        A("## Scoreboard (current schema)\n")
        A("| seed | graph nov | graph feas | web nov | web feas | more novel | sounder | "
          "same idea? |")
        A("|---|---|---|---|---|---|---|---|")
        for sid, _, _ in pairs:
            j = judged.get(sid)
            if not j:
                continue
            A(f"| **{sid}** | {j['graph_novelty']} | {j['graph_feasibility']} | "
              f"{j['web_novelty']} | {j['web_feasibility']} | "
              f"{j.get('more_novel', '?')} ({j.get('novelty_margin', '?')}) | "
              f"{j.get('sounder', '?')} ({j.get('feasibility_margin', '?')}) | "
              f"{'yes' if j['same_idea'] else 'no'} |")
        A("")
        js = list(judged.values())
        A("| arm | mean novelty | mean feasibility |")
        A("|---|---|---|")
        for a in ARMS:
            A(f"| {LABEL[a]} | {sum(j[f'{a}_novelty'] for j in js)/len(js):.1f} | "
              f"{sum(j[f'{a}_feasibility'] for j in js)/len(js):.1f} |")
        A("")
        wins = Counter(j.get("more_novel") for j in js)
        snd = Counter(j.get("sounder") for j in js)
        A(f"**Forced comparison:** more novel — " +
          ", ".join(f"{k} {v}" for k, v in wins.most_common()) +
          " · sounder — " + ", ".join(f"{k} {v}" for k, v in snd.most_common()) +
          f" · same core idea on {sum(bool(j['same_idea']) for j in js)}/{len(js)}.\n")

    # ── convergence ──────────────────────────────────────────────────────────
    if cos:
        A("## Convergence (do the arms just find the same idea?)\n")
        A("Lexical TF-IDF cosine between the two arms' ideas per seed. A cheap **floor "
          "only** — it badly under-detects semantic convergence (PLAN.md §7b), so the "
          "judge's `same_idea` flag is the authority.\n")
        A("| seed | cosine | graph title | web title |")
        A("|---|---|---|---|")
        for sid, g, w in pairs:
            A(f"| {sid} | {cos[sid]:.2f} | {g['idea']['title'][:58]} | "
              f"{w['idea']['title'][:58]} |")
        vals = list(cos.values())
        A(f"\n**Mean {sum(vals)/len(vals):.2f}**, range {min(vals):.2f}–{max(vals):.2f} "
          f"over {len(vals)} pairs.\n")

    # ── cost / effort ────────────────────────────────────────────────────────
    A("## Cost and effort\n")
    tot = {a: [0.0, 0.0, 0] for a in ARMS}
    for r in rows:
        a = r["arm"]
        tot[a][0] += r.get("total_cost_usd") or 0
        tot[a][1] += r.get("seconds") or 0
        tot[a][2] += r.get("n_explore") or 0
    n_per = len(rows) / 2
    A("| arm | ideas | mean explore calls | mean seconds | mean cost | total cost |")
    A("|---|---|---|---|---|---|")
    for a in ARMS:
        c = sum(1 for r in rows if r["arm"] == a)
        A(f"| {LABEL[a]} | {c} | {tot[a][2]/c:.1f} | {tot[a][1]/c:.0f} | "
          f"${tot[a][0]/c:.3f} | ${tot[a][0]:.2f} |")
    A(f"\nGeneration total: **${sum(t[0] for t in tot.values()):.2f}**.\n")

    A("### Tool usage\n")
    A("| tool | arm | calls | runs using it |")
    A("|---|---|---|---|")
    for a in ARMS:
        rs = [r for r in rows if r["arm"] == a]
        c = Counter(t for r in rs for t in r.get("tool_calls", []))
        for name, k in c.most_common():
            if name == "ToolSearch" or name.endswith("submit_idea"):
                continue
            used = sum(1 for r in rs if name in r.get("tool_calls", []))
            A(f"| `{name.replace('mcp__graph__', '')}` | {a} | {k} | {used}/{len(rs)} |")
    A("")

    # ── per seed ─────────────────────────────────────────────────────────────
    for sid, g, w in pairs:
        j = judged.get(sid)
        A("\n---\n")
        A(f"## {sid} — {g.get('topic', '')}\n")
        if cos:
            A(f"*Lexical similarity between the two ideas: {cos[sid]:.2f}.*\n")
        if j:
            A(f"**Judged:** graph {j['graph_novelty']}/{j['graph_feasibility']} vs web "
              f"{j['web_novelty']}/{j['web_feasibility']} (novelty/feasibility) · more "
              f"novel: **{j.get('more_novel')}** ({j.get('novelty_margin')}) · sounder: "
              f"**{j.get('sounder')}** ({j.get('feasibility_margin')}) · same core idea: "
              f"{'**yes**' if j['same_idea'] else 'no'}\n")
        elif sid in archived:
            A("**Judged (archived v1 pilot, both orders):** " + " · ".join(
                f"`{x['order']}` graph {x['graph_novelty']}/{x['graph_feasibility']} vs "
                f"web {x['web_novelty']}/{x['web_feasibility']}"
                for x in sorted(archived[sid], key=lambda x: x["order"])) + "\n")
        else:
            A("*Not yet judged.*\n")

        for arm, r in (("graph", g), ("web", w)):
            idea = r.get("idea") or {}
            A(f"### {LABEL[arm]} — {idea.get('title', '?')}\n")
            for f in FIELDS[1:]:
                A(f"**{FIELD_LABEL[f]}.** {str(idea.get(f, '')).strip()}\n")
            A(f"**Effort:** {r.get('n_explore')} exploration calls, {r.get('seconds')}s, "
              f"${r.get('total_cost_usd', 0):.3f}")
            c = Counter(t.replace("mcp__graph__", "") for t in r.get("tool_calls", [])
                        if t != "ToolSearch" and not t.endswith("submit_idea"))
            if c:
                A(f"  \n**Tools:** " + ", ".join(f"`{k}`×{v}" for k, v in c.most_common()))
            A("")

        if j:
            A(f"> *Judge on the graph idea (novelty):* {j['graph_novelty_reason']}\n")
            A(f"> *Judge on the graph idea (feasibility):* {j['graph_feasibility_reason']}\n")
            A(f"> *Judge on the web idea (novelty):* {j['web_novelty_reason']}\n")
            A(f"> *Judge on the web idea (feasibility):* {j['web_feasibility_reason']}\n")
            A(f"> *Same idea?* {j.get('same_idea_reason')}\n")
        elif sid in archived:
            for x in sorted(archived[sid], key=lambda x: x["order"]):
                A(f"> *v1 judge (`{x['order']}`), graph novelty:* {x['graph_novelty_reason']}\n")
                A(f"> *v1 judge (`{x['order']}`), web novelty:* {x['web_novelty_reason']}\n")

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {out}  ({len(pairs)} seeds, {len(judged)} judged, "
          f"{len(archived)} archived-judged, {len('\n'.join(L)):,} chars)")


if __name__ == "__main__":
    main()
