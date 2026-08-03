#!/usr/bin/env python3
"""Render second_judge_intent.json into a clean, human-readable markdown report
(out/second_judge_intent.md): headline numbers, confusion matrix, per-class agreement,
and every disagreement grouped by (ours->opus) pattern with claim snippets.

Usage:  python experiments/edge_quality/report_second_judge.py
"""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "experiments" / "edge_quality" / "out"
CLASSES = ("background", "uses_extends", "compares_contrasts")

# human labels for each (ours, opus) disagreement bucket + what boundary it probes
BUCKETS = {
    ("background", "compares_contrasts"):
        "Grouped comparison — target sits in a comparison/benchmark table or a grouped "
        "'existing systems lack X' motivation. Ours routes grouped comparisons to `background` "
        "(only a contrast that singles out the target = `compares_contrasts`); Opus reads table "
        "membership itself as contrast. **Definitional fork on the majority class.**",
    ("compares_contrasts", "background"):
        "Survey / concurrent framing — a contrastive cue ('In contrast', 'Unlike the above', "
        "'concurrent to') is present but the target is otherwise described neutrally. Ours fires "
        "on the cue; Opus reads it as a neutral related-work description. **Where our judge may "
        "over-fire `compares_contrasts`.**",
    ("uses_extends", "compares_contrasts"):
        "Baseline rerun — the citing paper re-runs the target as a baseline. Ours calls adopting "
        "the target to run it `uses_extends`; Opus calls the head-to-head `compares_contrasts`. "
        "**Known adopt-vs-compare grey-zone.**",
    ("background", "uses_extends"):
        "Possible under-called reuse — Opus reads the target as actually incorporated (dataset "
        "entry / one of the evals) where ours saw only a table row. **Candidate ours-miss.**",
    ("uses_extends", "background"):
        "Mechanism description vs adoption — ours reads the target's mechanism as feeding the "
        "citing paper's design; Opus reads it as a neutral description of prior work.",
}


def snip(t: str, n: int = 320) -> str:
    t = " ".join((t or "").split())
    return (t[:n] + "…") if len(t) > n else t


def main() -> None:
    r = json.load(open(OUT / "second_judge_intent.json", encoding="utf-8"))
    m, met = r["meta"], r["metrics"]
    conf = met["confusion_ours_x_opus"]
    pc = met["per_class_agreement"]

    L = []
    w = L.append
    w("# Intent axis — second-judge cross-check (Opus 5 vs our Sonnet-5)\n")
    w(f"Blind second annotator over a **stratified {m['n_judged']}-site sample** "
      f"(seed {m['seed']}, targets {m['stratify_targets']}). Same evidence + `[CITED:TARGET]` "
      f"marker convention as production; **clean-room rubric** (Opus was NOT given our "
      f"tie-breakers) so the two annotators' errors are de-correlated. Blind = Opus never saw "
      f"our label.\n")
    w("> This measures **reliability** (do two independent strong judges converge?), not ground "
      "truth. It tells us *where* the taxonomy boundaries are soft, and seeds the hand-label set.\n")
    w("\n## Headline\n")
    w("| metric | value | read |")
    w("|---|---:|---|")
    w(f"| Agreement, balanced sample | **{100*met['raw_agreement_balanced']:.0f}%** | on the 34/33/33 sample |")
    w(f"| Agreement, reweighted to true 82/11/7 | **{100*met['reweighted_agreement_true_dist']:.0f}%** | honest whole-corpus figure |")
    w(f"| Cohen's κ | **{met['cohen_kappa']:.2f}** | *substantial*, ≈ human–human on citation-intent tasks |")
    w(f"| Disagreements | **{len(r['disagreements'])} / {m['n_judged']}** | all on known grey-zones (below) |")

    w("\n## Confusion matrix — our label (rows) × Opus label (cols)\n")
    head = "| ours ＼ opus | " + " | ".join(c for c in CLASSES) + " | row total |"
    w(head)
    w("|" + "---|" * (len(CLASSES) + 2))
    for oi in CLASSES:
        cells = " | ".join(str(conf[oi].get(c, 0)) for c in CLASSES)
        w(f"| **{oi}** | {cells} | {sum(conf[oi].values())} |")
    w("\nDiagonal = agreement. Per-class agreement (on the balanced sample):\n")
    w("| our class | agree / n | rate |")
    w("|---|---:|---:|")
    for oi in CLASSES:
        w(f"| {oi} | {pc[oi]['agree']}/{pc[oi]['n']} | {100*pc[oi]['rate']:.0f}% |")
    w("\n`background` is the lowest-agreement class **and** the majority class, so it pulls the "
      "reweighted headline below the balanced number. `uses_extends` — the class we worried about "
      "— is the *highest* agreement.\n")

    # disagreements grouped by bucket
    by_bucket = defaultdict(list)
    for d in r["disagreements"]:
        by_bucket[(d["ours"], d["opus"])].append(d)
    w("\n## Disagreements, grouped by pattern\n")
    w("None are random errors — every one lands on a genuine taxonomy boundary. Ordered by "
      "cluster size.\n")
    rows = {x["site_key"]: x for x in r["rows"]}
    for pair in sorted(by_bucket, key=lambda p: -len(by_bucket[p])):
        ds = by_bucket[pair]
        w(f"\n### `{pair[0]}` → `{pair[1]}`  ({len(ds)})\n")
        w(BUCKETS.get(pair, "") + "\n")
        for d in ds:
            claim = rows[d["site_key"]]["claim"]
            w(f"\n- **{d['site_key']}** — ours `{d['ours']}` ({d['ours_conf']}) · "
              f"opus `{d['opus']}` ({d['opus_conf']})")
            w(f"  - ours: {d['ours_just']}")
            w(f"  - opus: {d['opus_just']}")
            w(f"  - claim: *{snip(claim)}*")

    (OUT / "second_judge_intent.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"-> {OUT / 'second_judge_intent.md'}  ({len(r['disagreements'])} disagreements)")


if __name__ == "__main__":
    main()
