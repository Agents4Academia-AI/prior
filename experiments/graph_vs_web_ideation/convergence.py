#!/usr/bin/env python3
"""How similar are the GRAPH and WEB ideas for the SAME seed? (zero cost, no LLM)

If the two arms keep landing on the same idea, a novelty winrate near 50% means
"the web found the same thing", not "the graph is worthless" — so we measure and
REPORT convergence rather than letting it hide in the winrate. This is purely
informational: similar ideas are still both scored by the judge (one may be
written out better), it just tells us how much of the signal is a real fork.

Lexical TF-IDF cosine over the idea text (same vectorizer family as select_seeds;
no embeddings, no network). Run after generation:

  python convergence.py                 # reads out/generations.jsonl
  python convergence.py --file X.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HERE = Path(__file__).resolve().parent
FIELDS = ("title", "gap", "proposed_study", "expected_result", "grounding")
HIGH = 0.45   # flag as "likely same core idea" above this (report-only threshold)


def idea_text(idea: dict) -> str:
    return " ".join(str((idea or {}).get(f, "")) for f in FIELDS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "out" / "generations.jsonl"))
    args = ap.parse_args()
    rows = [json.loads(l) for l in Path(args.file).read_text(encoding="utf-8").splitlines()
            if l.strip()]

    # pair the two arms by seed
    by_seed: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_seed.setdefault(r["seed_id"], {})[r["arm"]] = r
    pairs = [(sid, d["graph"], d["web"]) for sid, d in sorted(by_seed.items())
             if "graph" in d and "web" in d and d["graph"].get("idea") and d["web"].get("idea")]
    if not pairs:
        print("no complete graph+web pairs found.")
        return

    # one shared vocabulary across every idea, then cosine per seed
    texts = [idea_text(r["idea"]) for _, g, w in pairs for r in (g, w)]
    tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english").fit_transform(texts)

    print(f"{'seed':5} {'cos':>5}  graph title  /  web title")
    sims = []
    for i, (sid, g, w) in enumerate(pairs):
        sim = float(cosine_similarity(tfidf[2 * i], tfidf[2 * i + 1])[0, 0])
        sims.append(sim)
        flag = "  <-- likely same core idea" if sim >= HIGH else ""
        print(f"{sid:5} {sim:5.2f}  {g['idea']['title'][:46]}  /  {w['idea']['title'][:46]}{flag}")

    n_high = sum(s >= HIGH for s in sims)
    print(f"\nmean cosine {sum(sims) / len(sims):.2f} over {len(sims)} pairs; "
          f"{n_high}/{len(sims)} flagged >= {HIGH} (report-only — all pairs still judged).")


if __name__ == "__main__":
    main()
