"""Evaluation scorecard — three views of the gold labels.

Per dimension (contribution / edge / claim) we report correctness under three
label sets:
  1. self-eval   — the LLM judge's labels (annotator `claude`), dense.
  2. human       — real annotators' labels (majority vote), sparse.
  3. aggregated  — per item, the human label when present, else the judge's.

Plus judge↔human agreement (how well self-eval tracks the humans on the items
both labelled) and a pass/fail gate per dimension. All live from the annotation
store — it updates as people annotate or as the judge runs.
"""

from __future__ import annotations

from collections import Counter

from . import graph

DIMENSIONS = ("contribution", "edge", "claim")
GATE = {"contribution": ("Contributions faithful", 0.8),
        "edge": ("Relations sound", 0.8),
        "claim": ("Claims grounded", 0.8)}


def _majority(verdicts: list[str]) -> str | None:
    vs = [v for v in verdicts if v]
    return Counter(vs).most_common(1)[0][0] if vs else None


def _rate(verdicts: list[str]) -> dict:
    """{n, correct} where correct = fraction labelled 'correct' (vs incorrect/unsure)."""
    vs = [v for v in verdicts if v]
    ok = sum(1 for v in vs if v == "correct")
    return {"n": len(vs), "correct": round(ok / len(vs), 3) if vs else None}


def scorecard() -> dict:
    rows = graph.annotation_label_sets()
    dims = []
    gates = {}
    for kind in DIMENSIONS:
        items = [r for r in rows if r["kind"] == kind]
        self_v = [r["judge"] for r in items if r["judge"]]
        human_v = [_majority(r["humans"]) for r in items if r["humans"]]
        agg_v = [(_majority(r["humans"]) if r["humans"] else r["judge"]) for r in items
                 if (r["humans"] or r["judge"])]
        both = [(r["judge"], _majority(r["humans"])) for r in items if r["judge"] and r["humans"]]
        agree = sum(1 for j, h in both if j == h)

        agg = _rate(agg_v)
        label, thr = GATE[kind]
        gates[kind] = ("pass" if (agg["correct"] is not None and agg["correct"] >= thr)
                       else "pending" if agg["correct"] is None else "warn")
        dims.append({
            "kind": kind, "gate_label": label, "threshold": thr, "gate": gates[kind],
            "self_eval": _rate(self_v),
            "human": _rate(human_v),
            "aggregated": agg,
            "agreement": {"n": len(both),
                          "rate": round(agree / len(both), 3) if both else None},
        })
    return {"dimensions": dims, "gates": gates,
            "note": "self-eval = Claude's labels; human = annotators (majority); "
                    "aggregated = human where available, else Claude."}
