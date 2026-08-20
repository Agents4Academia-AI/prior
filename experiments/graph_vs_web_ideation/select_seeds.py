#!/usr/bin/env python3
"""Derive broad topic seeds from the corpus (data-driven, zero LLM / no cost).

Both experiment arms receive the same lightweight *topic label* each round, so
they stay on the corpus's subject and their ideas can be paired. To pick topics
that actually cover the corpus (not my guesses), we cluster the 152 papers by
TF-IDF over title+abstract+their contribution statements, then read off each
cluster's distinctive terms and representative papers.

Output: `seeds_draft.json` — clusters with keyterms + representative titles. A
human (me) then writes clean broad labels into `seeds.json` from this evidence
(kept separate so the labels are reviewable and the clustering is reproducible).

Reads (this branch): canonical v12 (for contribution statements) + papers_core.
Run:  python experiments/graph_vs_web_ideation/select_seeds.py --k 24
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[2]
EQ = ROOT / "experiments" / "edge_quality" / "out"
BUNDLE = ROOT / "data" / "prior-core-v0.2"
CANONICAL = EQ / "canonical_semantic_candidates_enriched_evidence_v12.json"
PAPERS = BUNDLE / "papers_core.jsonl"
OUT = Path(__file__).parent / "seeds_draft.json"

STOP_EXTRA = {  # corpus-generic terms that would dominate every cluster label
    "ai", "llm", "llms", "model", "models", "agent", "agents", "research",
    "paper", "papers", "task", "tasks", "based", "using", "novel", "propose",
    "approach", "method", "methods", "system", "systems", "framework", "data",
    "results", "large", "language", "scientific", "science", "use", "used",
}


def load_docs() -> tuple[list[str], list[dict]]:
    canon = json.loads(CANONICAL.read_text(encoding="utf-8"))
    stmts_by_paper: dict[str, list[str]] = defaultdict(list)
    for c in canon["contributions"]:
        stmts_by_paper[c["paper_id"]].append(c.get("statement", ""))
    papers = [json.loads(l) for l in PAPERS.read_text(encoding="utf-8").splitlines() if l.strip()]
    docs, meta = [], []
    for p in papers:
        text = " ".join([p.get("title", ""), p.get("abstract", "")]
                        + stmts_by_paper.get(p["id"], []))
        docs.append(text)
        meta.append({"id": p["id"], "title": p.get("title", "?"), "year": p.get("year")})
    return docs, meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=24, help="number of topic clusters")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    docs, meta = load_docs()
    vec = TfidfVectorizer(stop_words=list(STOP_EXTRA) + ["english"], ngram_range=(1, 2),
                          min_df=2, max_df=0.5, token_pattern=r"[a-zA-Z][a-zA-Z-]{2,}")
    # sklearn wants a real stop list; pass english + extras explicitly
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2,
                          max_df=0.5, token_pattern=r"[a-zA-Z][a-zA-Z-]{2,}")
    X = vec.fit_transform(docs)
    terms = vec.get_feature_names_out()

    km = KMeans(n_clusters=args.k, random_state=args.seed, n_init=10).fit(X)
    labels = km.labels_
    centroids = km.cluster_centers_

    clusters = []
    for c in range(args.k):
        members = [i for i in range(len(docs)) if labels[i] == c]
        if not members:
            continue
        # distinctive terms: top centroid weights, minus corpus-generic ones
        ranked = centroids[c].argsort()[::-1]
        keyterms, seen = [], set()
        for ti in ranked:
            t = terms[ti]
            base = t.replace(" ", "")
            if any(w in STOP_EXTRA for w in t.split()) or base in seen:
                continue
            keyterms.append(t)
            seen.add(base)
            if len(keyterms) >= 8:
                break
        # representative papers: closest members to the centroid
        import numpy as np
        sims = (X[members] @ centroids[c].reshape(-1, 1)).ravel()
        order = np.array(members)[np.argsort(sims)[::-1]]
        reps = [meta[i]["title"] for i in order[:4]]
        clusters.append({"cluster": c, "size": len(members),
                         "keyterms": keyterms, "representative_titles": reps})

    clusters.sort(key=lambda x: x["size"], reverse=True)
    OUT.write_text(json.dumps({"k": args.k, "n_papers": len(docs),
                               "clusters": clusters}, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"wrote {OUT}  ({len(clusters)} non-empty clusters over {len(docs)} papers)")
    for cl in clusters:
        print(f"  [{cl['size']:>2}] {', '.join(cl['keyterms'][:5])}")


if __name__ == "__main__":
    main()
