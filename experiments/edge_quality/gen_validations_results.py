#!/usr/bin/env python3
"""Emit out/validations_results.md: raw results of the two intent validations
(S2 silver eval + Opus-5 second-judge re-eval) with every disagreement edge and its
output justifications. No interpretation — straight dump from the JSON artifacts.

Usage:  python experiments/edge_quality/gen_validations_results.py
"""
from __future__ import annotations
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "experiments" / "edge_quality" / "out"
CLASSES = ("background", "uses_extends", "compares_contrasts")
S2MAP = {"background": "background", "methodology": "uses_extends"}


def map_s2(ints):
    for w in ("methodology", "background"):
        if w in ints:
            return S2MAP[w]
    return None


def main() -> None:
    L = []
    w = L.append

    # ── S2 eval ───────────────────────────────────────────────────────────
    s2 = json.load(open(OUT / "s2_intent_eval.json", encoding="utf-8"))
    intent = json.load(open(OUT / "citations_intent.json", encoding="utf-8"))
    cmap = json.load(open(OUT / "citation_map.json", encoding="utf-8"))
    cm_ctx = {r["citing_id"] + "->" + r["cited_id"]: [(c.get("text") or "") for c in (r.get("contexts") or [])]
              for r in cmap}
    intent_sites = {e["citing_id"] + "->" + e["cited_id"]: e["sites"] for e in intent["edges"]}

    def has_cjk(t):
        return any("一" <= ch <= "鿿" for ch in t)

    def orig_for(k):
        """First non-CJK context's claim (from citation_map) + its justification (from intent);
        fall back to index 0 if every context is CJK."""
        texts = cm_ctx.get(k, [])
        idx = next((i for i, t in enumerate(texts) if not has_cjk(t)), 0)
        claim = texts[idx] if texts else ""
        sites = intent_sites.get(k, [])
        just = sites[idx]["justification"] if idx < len(sites) else (sites[0]["justification"] if sites else "")
        return just, claim

    m = s2["meta"]

    w("# Validation results\n")
    w("## 1. S2 intent eval — `s2_intent_eval.json`\n")
    w(f"- our typed edges: {m['n_our_edges']}")
    w(f"- present in S2 ref graph: {m['n_in_s2']}")
    w(f"- carrying an intent tag: {m['n_labelled']}")
    w(f"- flagged isInfluential: {m['n_influential']}")
    w(f"- mapping: {m['mapping']}")
    w(f"- agreement on comparable classes (background/uses_extends): "
      f"{s2['agreement_comparable']['agree']}/{s2['agreement_comparable']['total']}")
    w(f"- cross (our intent × mapped S2 intent): {json.dumps(s2['cross'])}")
    w(f"- isInfluential by our intent [not_influential, influential]: "
      f"{json.dumps(s2['influential_by_intent'])}")
    w(f"- note: {m['note']}\n")

    labelled = {k: v for k, v in s2["edges"].items() if v["s2_intents"]}
    dis = {k: v for k, v in labelled.items()
           if (map_s2(v["s2_intents"]) not in (None, v["our_intent"])) or v["our_intent"] == "compares_contrasts"}
    w(f"### Disagreement edges ({len(dis)})\n")
    for k, v in dis.items():
        w(f"#### {k}")
        w(f"- s2_title: {v['s2_title']}")
        w(f"- s2_intents: {v['s2_intents']} → mapped: {map_s2(v['s2_intents'])}")
        w(f"- isInfluential: {v['isInfluential']}")
        w(f"- our_intent: {v['our_intent']}")
        oj, oc = orig_for(k)
        w(f"- our justification: {oj}")
        w(f"- claim: {' '.join((oc or '').split())}")
        w("")

    # ── second-judge eval ─────────────────────────────────────────────────
    sj = json.load(open(OUT / "second_judge_intent.json", encoding="utf-8"))
    sm, met = sj["meta"], sj["metrics"]
    conf = met["confusion_ours_x_opus"]
    pc = met["per_class_agreement"]

    w("## 2. Second-judge re-eval — `second_judge_intent.json`\n")
    w(f"- second model: {sm['second_model']} | our model: {sm['our_model']}")
    w(f"- sample: {sm['n_judged']} sites, seed {sm['seed']}, stratify targets {sm['stratify_targets']}")
    w(f"- raw agreement (balanced sample): {met['raw_agreement_balanced']}")
    w(f"- reweighted agreement (true distribution): {met['reweighted_agreement_true_dist']}")
    w(f"- Cohen's kappa: {met['cohen_kappa']}")
    w(f"- note: {sm['note']}\n")
    w("Confusion matrix — our label (rows) × Opus label (cols):\n")
    w("| ours ＼ opus | " + " | ".join(CLASSES) + " | row total |")
    w("|" + "---|" * (len(CLASSES) + 2))
    for oi in CLASSES:
        cells = " | ".join(str(conf[oi].get(c, 0)) for c in CLASSES)
        w(f"| {oi} | {cells} | {sum(conf[oi].values())} |")
    w("\nPer-class agreement:\n")
    w("| our class | agree / n | rate |")
    w("|---|---|---|")
    for oi in CLASSES:
        w(f"| {oi} | {pc[oi]['agree']}/{pc[oi]['n']} | {pc[oi]['rate']} |")
    w("")

    ds = sj["disagreements"]
    w(f"### Disagreement edges ({len(ds)})\n")
    for d in ds:
        w(f"#### {d['site_key']}")
        w(f"- ours: {d['ours']} ({d['ours_conf']}) — {d['ours_just']}")
        w(f"- opus: {d['opus']} ({d['opus_conf']}) — {d['opus_just']}")
        w(f"- claim: {' '.join((d['claim'] or '').split())}")
        w("")

    (OUT / "validations_results.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"-> {OUT / 'validations_results.md'}")


if __name__ == "__main__":
    main()
