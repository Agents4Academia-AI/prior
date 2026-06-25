"""Evaluation scorecard, three views of the gold labels.

Per dimension (contribution / edge / claim) we report correctness under three
label sets:
  1. self-eval  , the LLM judge's labels (annotator `claude`), dense.
  2. human      , real annotators' labels (majority vote), sparse.
  3. aggregated , per item, the human label when present, else the judge's.

Plus judge↔human agreement (how well self-eval tracks the humans on the items
both labelled) and a pass/fail gate per dimension. All live from the annotation
store, it updates as people annotate or as the judge runs.
"""

from __future__ import annotations

import os
from collections import Counter, defaultdict

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


# A model judge labels densely (hundreds+); a human spot-checks a handful. Show only
# dense annotators as "judges" so sparse human labels don't clutter the table.
MIN_JUDGE_LABELS = int(os.environ.get("PRIOR_MIN_JUDGE_LABELS", "10"))


def judges() -> dict:
    """Per dimension, the correctness rate for each MODEL judge (annotators with at
    least MIN_JUDGE_LABELS verdicts), plus pairwise agreement on co-labelled items.
    Sparse annotators (e.g. a human who labelled a few items) are excluded."""
    with graph.session() as s:
        rows = [(r["ann"], r["kind"], r["key"], r["v"]) for r in s.run(
            "MATCH (a:Annotation) RETURN a.annotator AS ann, a.target_kind AS kind, "
            "a.target_key AS key, a.faithful AS v")]
    totals: dict[str, int] = defaultdict(int)
    for a, _, _, v in rows:
        if v:
            totals[a] += 1
    labels = sorted(a for a, n in totals.items() if n >= MIN_JUDGE_LABELS)
    keep = set(labels)
    rows = [r for r in rows if r[0] in keep]
    by: dict[tuple[str, str], list[str]] = defaultdict(list)   # (ann, kind) -> verdicts
    verds: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)  # (kind,key) -> {ann: v}
    for ann, kind, key, v in rows:
        if v:
            by[(ann, kind)].append(v)
            verds[(kind, key)][ann] = v
    dims = []
    for kind in DIMENSIONS:
        rates = {ann: _rate(by[(ann, kind)]) for ann in labels if by.get((ann, kind))}
        dims.append({"kind": kind, "rates": rates})
    pair: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])  # (a,b) -> [agree, total]
    for m in verds.values():
        anns = sorted(m)
        for i in range(len(anns)):
            for j in range(i + 1, len(anns)):
                key = (anns[i], anns[j])
                pair[key][1] += 1
                if m[anns[i]] == m[anns[j]]:
                    pair[key][0] += 1
    agreement = [{"a": a, "b": b, "n": t, "rate": round(ag / t, 3)}
                 for (a, b), (ag, t) in pair.items() if t]
    agreement.sort(key=lambda x: -x["n"])
    return {"labels": labels, "dimensions": dims, "agreement": agreement}


# ── Calibration: do the stored scores track the judge's verdict? ─────────────────
# Each dimension is calibrated against one or more stored scores ("signals").
# Edges carry two: `confidence` (the extractor's raw self-report) and `trust` (the
# consensus score from consensus.py, the one the UI 'min trust' knob actually
# gates on). Nodes carry only `confidence`. We report every available signal so the
# scorecard shows which score is the better faithfulness filter.
_THRESHOLDS = (0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95)
_SIGNALS = {
    "contribution": ("confidence",),
    "claim": ("confidence",),
    "edge": ("confidence", "trust"),
}


def _auc(scores: list[float], labels: list[int]) -> float | None:
    """Rank-based AUC-ROC (Mann-Whitney U), tie-aware. None if one class is empty."""
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):                       # average ranks within tie groups
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    sum_pos = sum(ranks[i] for i in range(len(scores)) if labels[i] == 1)
    return round((sum_pos - pos * (pos + 1) / 2.0) / (pos * neg), 3)


def _calibration_pairs(collection: str | None) -> dict[tuple[str, str], list[tuple[float, int]]]:
    """Per (kind, signal), [(score, correct01)] joining each artifact's stored score
    to the judge's `faithful` verdict. 'unsure' and score-less items are dropped."""
    pairs: dict[tuple[str, str], list[tuple[float, int]]] = {
        (kind, sig): [] for kind, sigs in _SIGNALS.items() for sig in sigs}
    cf = " {collection:$c}" if collection else ""
    with graph.session() as s:
        verd = {(r["k"], r["key"]): r["v"] for r in s.run(
            "MATCH (a:Annotation {annotator:'claude'}) "
            "RETURN a.target_kind AS k, a.target_key AS key, a.faithful AS v")}

        def add(kind, signal, key, score):
            v = verd.get((kind, key))
            if v in ("correct", "incorrect") and score is not None:
                pairs[(kind, signal)].append((float(score), 1 if v == "correct" else 0))

        for r in s.run(f"MATCH (k:Contribution{cf}) RETURN k.id AS key, k.confidence AS conf", c=collection):
            add("contribution", "confidence", r["key"], r["conf"])
        for r in s.run(f"MATCH (c:Claim{cf}) RETURN c.id AS key, c.confidence AS conf", c=collection):
            add("claim", "confidence", r["key"], r["conf"])
        for r in s.run(
            f"MATCH (a:Contribution{cf})-[rel]->(b:Contribution{cf}) "
            "WHERE type(rel) IN ['SUPPORTS','BUILDS_ON','REFINES','CONTRADICTS'] "
            "RETURN a.id AS src, b.id AS dst, type(rel) AS rel, "
            "rel.confidence AS conf, rel.trust AS trust", c=collection):
            key = f"{r['src']}|{r['rel']}|{r['dst']}"
            add("edge", "confidence", key, r["conf"])
            add("edge", "trust", key, r["trust"])
    return pairs


def _calibrate_one(kind: str, signal: str, data: list[tuple[float, int]], nbins: int) -> dict:
    """AUC, reliability curve, threshold curve, and ECE for one (kind, signal)."""
    n = len(data)
    scores = [c for c, _ in data]
    labels = [y for _, y in data]

    buckets: dict[int, list[tuple[float, int]]] = defaultdict(list)
    for c, y in data:
        buckets[min(int(c * nbins), nbins - 1)].append((c, y))
    reliability = []
    for b in range(nbins):
        items = buckets.get(b)
        if not items:
            continue
        reliability.append({
            "lo": round(b / nbins, 2), "hi": round((b + 1) / nbins, 2), "n": len(items),
            "score": round(sum(c for c, _ in items) / len(items), 3),
            "acc": round(sum(y for _, y in items) / len(items), 3)})

    thresholds = []
    for t in _THRESHOLDS:
        kept = [y for c, y in data if c >= t]
        thresholds.append({
            "t": t, "kept": len(kept),
            "coverage": round(len(kept) / n, 3) if n else None,
            "accuracy": round(sum(kept) / len(kept), 3) if kept else None})

    ece = (round(sum((bb["n"] / n) * abs(bb["acc"] - bb["score"]) for bb in reliability), 3)
           if n else None)
    return {
        "kind": kind, "signal": signal, "n": n,
        "auc": _auc(scores, labels),
        "accuracy": round(sum(labels) / n, 3) if n else None,
        "mean_score": round(sum(scores) / n, 3) if n else None,
        "ece": ece, "reliability": reliability, "thresholds": thresholds}


def calibration(collection: str | None = None, *, nbins: int = 10) -> dict:
    """Per (dimension, signal): AUC-ROC of the stored score vs the judge verdict, a
    reliability curve (binned score -> empirical accuracy), accuracy/coverage at a
    grid of thresholds, and ECE. Edges report both `confidence` and `trust` (the
    knob's signal). Per-kind only, pooling dimensions inflates AUC. 'unsure'
    verdicts excluded."""
    pairs = _calibration_pairs(collection)
    dims = [_calibrate_one(kind, sig, pairs[(kind, sig)], nbins)
            for kind in DIMENSIONS for sig in _SIGNALS[kind]]
    return {"dimensions": dims,
            "note": "x = stored score, y = judge 'faithful'. AUC = how well the score "
                    "ranks faithful above unfaithful (0.5 = chance). Edges show both the "
                    "extractor 'confidence' and the consensus 'trust' (the UI knob's "
                    "signal). Per-kind only; pooling inflates AUC. 'unsure' excluded."}
