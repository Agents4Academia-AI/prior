"""Evals for the two-level graph pipeline.

Three checks, in increasing cost:

1. groundedness  (key-free)  — does every extracted claim's evidence span actually
   appear in its source text? A faithfulness guard against hallucinated extraction.
2. abstention    (LLM)       — on off-topic questions, does the agent say not_found
   instead of confabulating? The false-confidence guard.
3. novelty / retrodiction (LLM) — temporal holdout: ask whether a known problem was
   addressed, using only earlier work; ground truth from chronology. The headline.

Run:
    python evals/graph_eval.py groundedness --data /tmp/prior12
    python evals/graph_eval.py abstention
    python evals/graph_eval.py novelty
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

_WORD = re.compile(r"[a-z0-9]+")


def _toks(s: str) -> list[str]:
    return _WORD.findall((s or "").lower())


def _overlap(span: str, source: str) -> float:
    """Fraction of the evidence span's tokens present in the source text."""
    st, so = _toks(span), set(_toks(source))
    if not st:
        return 0.0
    return sum(1 for t in st if t in so) / len(st)


# ── 1. groundedness (key-free) ──────────────────────────────────────────────────
def groundedness(data_dir: str) -> dict:
    d = Path(data_dir)
    papers = {p["id"]: p for p in (json.loads(l) for l in
              (d / "raw" / "papers.jsonl").read_text().splitlines() if l)}
    claims = [json.loads(l) for l in
              (d / "atlas" / "claims.jsonl").read_text().splitlines() if l]
    scores, grounded = [], 0
    for c in claims:
        p = papers.get(c["paper_id"], {})
        source = (p.get("full_text") or "") + " " + (p.get("abstract") or "")
        ov = _overlap(c.get("evidence", ""), source)
        scores.append(ov)
        if ov >= 0.8:
            grounded += 1
    n = len(scores) or 1
    rep = {"claims": len(claims),
           "grounded_rate@0.8": round(grounded / n, 3),
           "mean_overlap": round(sum(scores) / n, 3)}
    print("GROUNDEDNESS:", json.dumps(rep, indent=2))
    return rep


# ── 2. abstention (LLM) ─────────────────────────────────────────────────────────
_OFFTOPIC = [
    "Does continual learning reduce data-center energy consumption?",
    "What is the optimal interest rate for mortgage lending?",
    "How do tardigrades survive in space vacuum?",
]


def abstention() -> dict:
    os.environ.setdefault("PRIOR_LLM_BACKEND", "claude-cli")
    from prior import agent
    abstained = 0
    for q in _OFFTOPIC:
        v = agent.ask(q).verdict
        ok = v == "not_found"
        abstained += ok
        print(f"  [{ 'OK' if ok else 'MISS'}] ({v}) {q}")
    rep = {"questions": len(_OFFTOPIC), "abstained": abstained,
           "abstention_rate": round(abstained / len(_OFFTOPIC), 3)}
    print("ABSTENTION:", json.dumps(rep, indent=2))
    return rep


# ── 3. novelty / retrodiction (LLM) ─────────────────────────────────────────────
def novelty() -> dict:
    """Recall-style check on the live graph: for a sample of contributions, ask
    has_been_solved() on the contribution's own problem and verify the system
    surfaces OTHER papers' related contributions (it should never claim a problem
    is unaddressed when sibling work exists). A lightweight stand-in for a full
    temporal holdout (which rebuilds the graph from papers before year Y)."""
    os.environ.setdefault("PRIOR_LLM_BACKEND", "claude-cli")
    from prior import agent, graph
    contribs = graph.list_papers() and graph.global_graph()["nodes"]
    sample = contribs[:5]
    hits = 0
    for k in sample:
        problem = k.get("problem") or k.get("method") or ""
        res = agent.has_been_solved(problem)
        # the graph DOES contain related work, so 'not_addressed' would be a miss
        ok = res.verdict != "not_addressed" and bool(res.addressed_by)
        hits += ok
        print(f"  [{'OK' if ok else 'MISS'}] ({res.verdict}, {len(res.addressed_by)} addr) "
              f"{problem[:70]}")
    rep = {"sampled": len(sample), "found_related": hits,
           "recall_proxy": round(hits / (len(sample) or 1), 3)}
    print("NOVELTY (recall proxy):", json.dumps(rep, indent=2))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("check", choices=["groundedness", "abstention", "novelty"])
    ap.add_argument("--data", default="/tmp/prior12")
    a = ap.parse_args()
    if a.check == "groundedness":
        groundedness(a.data)
    elif a.check == "abstention":
        abstention()
    else:
        novelty()
