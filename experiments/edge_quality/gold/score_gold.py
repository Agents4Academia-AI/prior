#!/usr/bin/env python3
"""Score the hand-labelled gold set against the Sonnet judge.

Input: the labelling Sheet downloaded as CSV (File > Download > Comma-separated values).
It carries both your gold_* columns and the judge columns, so nothing else is needed.

Two headline numbers, both unbiased, reported separately:

  1. RANDOM-SAMPLE ACCURACY — sites with sample_type=random_eval. This block was drawn
     uniformly and stored in random order, so any labelled prefix of it is still a
     uniform sample. Simple mean, Wilson 95% CI. This is the number to quote.
  2. STRATIFIED REWEIGHTED ACCURACY — uses random_eval + strat_topup. Estimates
     P(correct | judge=c) per predicted class, then reweights by the true predicted-class
     distribution over all 809 sites. Same estimand, lower variance on the rare classes;
     it is also what makes per-class precision/recall and macro-F1 estimable.

`disagreement` sites are EXCLUDED from both (they were deliberately enriched for hard
cases) and reported on their own, as the referee on the two open taxonomy forks.

Usage:
    python experiments/edge_quality/gold/score_gold.py --sheet ~/Downloads/sheet.csv
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "edge_quality" / "out"
CLASSES = ("background", "uses_extends", "compares_contrasts")
SKIP = "SKIP"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True, help="the labelling sheet downloaded as CSV")
    ap.add_argument("--out", default=str(OUT / "gold_eval.md"))
    args = ap.parse_args()

    sites = {r["site_key"]: r for r in csv.DictReader(open(args.sheet, encoding="utf-8"))}

    lab, skipped = [], 0
    for s in sites.values():
        gi = (s.get("gold_intent") or "").strip()
        if not gi:
            continue
        if gi == SKIP:
            skipped += 1
            continue
        lab.append({**s, "gold_intent": gi,
                    "gold_support": (s.get("gold_support") or "").strip(),
                    "gold_priority": (s.get("gold_priority") or "").strip(),
                    "gold_notes": (s.get("gold_notes") or "").strip()})

    L = []
    w = L.append
    w("# Gold-set evaluation — intent axis\n")
    w(f"- labelled sites: **{len(lab)}** (+{skipped} skipped)")
    by_type = Counter(r["sample_type"] for r in lab)
    w("- by sample block: " + ", ".join(f"`{k}`={v}" for k, v in sorted(by_type.items())))
    w("- gold class mix: " + ", ".join(f"{c}={sum(1 for r in lab if r['gold_intent'] == c)}"
                                       for c in CLASSES) + "\n")

    # ── 1. unbiased random-sample accuracy ────────────────────────────────
    rnd = [r for r in lab if r["sample_type"] == "random_eval"]
    k = sum(1 for r in rnd if r["gold_intent"] == r["judge_intent"])
    lo, hi = wilson(k, len(rnd))
    w("## 1. Random-sample accuracy (the headline)\n")
    if rnd:
        w(f"**{pct(k / len(rnd))}**  ({k}/{len(rnd)} sites)  ·  95% CI [{pct(lo)}, {pct(hi)}]\n")
    else:
        w("_no random_eval sites labelled yet_\n")
    w("> Site-level. Sites on the same edge/paper are not independent, so the true CI is a "
      "little wider than the binomial one above.\n")

    # ── 2. stratified reweighted estimate + macro-F1 ──────────────────────
    pool = [r for r in lab if r["sample_type"] in ("random_eval", "strat_topup")]
    # true predicted-class distribution over ALL sites
    wts = Counter(r["judge_intent"] for r in sites.values())
    tot = sum(wts.values())
    cond = {}   # P(gold=g | judge=c), estimated within each predicted class
    n_c = {}
    for c in CLASSES:
        sub = [r for r in pool if r["judge_intent"] == c]
        n_c[c] = len(sub)
        cnt = Counter(r["gold_intent"] for r in sub)
        cond[c] = {g: (cnt.get(g, 0) / len(sub) if sub else 0.0) for g in CLASSES}

    w("## 2. Stratified reweighted estimate\n")
    w("| judge class | pop. weight | n labelled | P(correct \\| judge=c) |")
    w("|---|---|---|---|")
    acc_rw, covered = 0.0, 0
    for c in CLASSES:
        wt = wts[c] / tot
        w(f"| {c} | {pct(wt)} | {n_c[c]} | " + (pct(cond[c][c]) if n_c[c] else "—") + " |")
        if n_c[c]:
            acc_rw += wt * cond[c][c]
            covered += wts[c]
    w("")
    if covered == tot:
        w(f"**Reweighted accuracy: {pct(acc_rw)}**\n")
    else:
        w(f"_Reweighted accuracy needs all three classes labelled "
          f"({pct(covered / tot)} of the population covered so far)._\n")

    # reweighted joint P(judge=c, gold=g) -> precision / recall / F1
    joint = {c: {g: (wts[c] / tot) * cond[c][g] for g in CLASSES} for c in CLASSES}
    w("### Reweighted confusion (population-scaled), judge (rows) × gold (cols)\n")
    w("| judge ＼ gold | " + " | ".join(CLASSES) + " |")
    w("|" + "---|" * (len(CLASSES) + 1))
    for c in CLASSES:
        w(f"| {c} | " + " | ".join(pct(joint[c][g]) for g in CLASSES) + " |")
    w("")
    w("| class | precision | recall | F1 |")
    w("|---|---|---|---|")
    f1s = []
    for c in CLASSES:
        prec = cond[c][c] if n_c[c] else 0.0
        denom = sum(joint[c2][c] for c2 in CLASSES)
        rec = (joint[c][c] / denom) if denom else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        f1s.append(f1)
        w(f"| {c} | {pct(prec)} | {pct(rec)} | {f1:.3f} |")
    w(f"\n**macro-F1 = {sum(f1s) / len(f1s):.3f}**\n")

    # ── 3. the disagreement block: who was right ─────────────────────────
    dis = [r for r in lab if r["sample_type"] == "disagreement"]
    w("## 3. Second-judge disagreement block (referee on the forks)\n")
    if not dis:
        w("_none labelled yet_\n")
    else:
        ours = sum(1 for r in dis if r["gold_intent"] == r["judge_intent"])
        opus = sum(1 for r in dis if r["gold_intent"] == r["sj_opus"])
        neither = sum(1 for r in dis
                      if r["gold_intent"] not in (r["judge_intent"], r["sj_opus"]))
        w(f"On {len(dis)} labelled hard cases: **ours right {ours}**, **Opus right {opus}**, "
          f"neither {neither}.\n")
        forks = defaultdict(lambda: [0, 0])
        for r in dis:
            f = forks[r["sj_pair"]]
            if r["gold_intent"] == r["judge_intent"]:
                f[0] += 1
            elif r["gold_intent"] == r["sj_opus"]:
                f[1] += 1
        w("| fork (ours→opus) | gold sides with ours | with Opus |")
        w("|---|---|---|")
        for pair, (a, b) in sorted(forks.items()):
            w(f"| {pair} | {a} | {b} |")
        w("\n> These sites are deliberately enriched for hard cases — never fold them into "
          "the accuracy numbers above.\n")

    # ── 4. secondary axes ────────────────────────────────────────────────
    w("## 4. Secondary axes (where labelled)\n")
    for axis, jcol in (("support", "judge_support"), ("priority", "judge_priority")):
        sub = [r for r in lab if r[f"gold_{axis}"]]
        if not sub:
            w(f"- `{axis}`: not labelled yet")
            continue
        agree = sum(1 for r in sub if r[f"gold_{axis}"] == r[jcol])
        lo2, hi2 = wilson(agree, len(sub))
        w(f"- `{axis}`: **{pct(agree / len(sub))}** ({agree}/{len(sub)}), 95% CI [{pct(lo2)}, {pct(hi2)}]")
    w("")

    # ── 5. quality-gate slice ────────────────────────────────────────────
    w("## 5. Accuracy by quality gate\n")
    w("| slice | n | accuracy |")
    w("|---|---|---|")
    clean = [r for r in lab if r["sample_type"] != "disagreement"]
    for name, sub in (("bibtex_valid = True", [r for r in clean if r["bibtex_valid"] == "True"]),
                      ("bibtex_valid = False (blob)", [r for r in clean if r["bibtex_valid"] != "True"]),
                      ("citee abstract ok", [r for r in clean if r["citee_abstract_ok"] == "True"]),
                      ("citee abstract short", [r for r in clean if r["citee_abstract_ok"] != "True"])):
        if sub:
            a = sum(1 for r in sub if r["gold_intent"] == r["judge_intent"])
            w(f"| {name} | {len(sub)} | {pct(a / len(sub))} |")
    w("")

    # ── 6. every miss, for eyeballing ────────────────────────────────────
    miss = [r for r in lab if r["gold_intent"] != r["judge_intent"]]
    w(f"## 6. Misses ({len(miss)})\n")
    for r in miss:
        w(f"#### {r['site_key']}  ·  `{r['sample_type']}`")
        w(f"- **citing:** {r['citing_title']} ({r['citing_year']})")
        w(f"- **cited:** {r['cited_title']} ({r['cited_year']})")
        w(f"- gold: **{r['gold_intent']}** · judge: {r['judge_intent']} ({r['judge_intent_conf']})"
          + (f" · opus: {r['sj_opus']}" if r["sj_opus"] else ""))
        w(f"- judge said: {r['judge_intent_just']}")
        if r["gold_notes"]:
            w(f"- my note: {r['gold_notes']}")
        w(f"- claim: {r['claim']}")
        w("")

    Path(args.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"-> {args.out}")
    if rnd:
        print(f"random-sample accuracy: {pct(k / len(rnd))} ({k}/{len(rnd)})")


if __name__ == "__main__":
    main()
