"""Prepare one leakage-safe, bounded CPU adaptive-search round.

The round augments the useful corpus with newly screened eligible papers,
re-induces the same deterministic TF-IDF/NMF geometry, matches new communities
to the prior map, and emits queries only for materially changed communities.
Hidden recovery targets are never loaded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from cpu_query_map import DOMAIN_STOPS, read_role, select_terms


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def paper_key(row: dict) -> str:
    paper = row.get("paper", row)
    pid = str(paper.get("id") or "").strip().lower()
    if pid:
        return pid
    title = " ".join(str(paper.get("title") or "").lower().split())
    return "title:" + title


def jaccard(left: list[str], right: list[str]) -> float:
    a = {token for term in left for token in term.split()}
    b = {token for term in right for token in term.split()}
    return len(a & b) / max(1, len(a | b))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-screen-dir", type=Path, required=True)
    ap.add_argument("--new-eligible", type=Path, required=True)
    ap.add_argument("--prior-map", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--components", type=int, default=16)
    ap.add_argument("--max-branches", type=int, default=8)
    ap.add_argument("--seed", type=int, default=20260820)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    screen_dir = args.out_dir / "screen-input"
    screen_dir.mkdir(exist_ok=True)

    for role in ("retrieval_only", "uncertain"):
        shutil.copyfile(args.base_screen_dir / f"{role}.jsonl", screen_dir / f"{role}.jsonl")

    base_eligible = rows(args.base_screen_dir / "eligible.jsonl")
    additions = rows(args.new_eligible)
    merged: dict[str, dict] = {}
    for row in base_eligible + additions:
        merged.setdefault(paper_key(row), row)
    eligible_path = screen_dir / "eligible.jsonl"
    eligible_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n"
                                     for row in merged.values()))

    corpus = []
    for role in ("eligible", "retrieval_only", "uncertain"):
        corpus.extend(read_role(screen_dir / f"{role}.jsonl", role))
    addition_keys = {paper_key(row) for row in additions}
    stops = sorted(set(ENGLISH_STOP_WORDS) | DOMAIN_STOPS)
    vectorizer = TfidfVectorizer(stop_words=stops, ngram_range=(1, 2), min_df=3,
                                 max_df=.70, max_features=20000, sublinear_tf=True)
    matrix = vectorizer.fit_transform(row["text"] for row in corpus)
    nmf = NMF(n_components=args.components, init="nndsvda", random_state=args.seed,
              max_iter=600, l1_ratio=.1)
    weights = nmf.fit_transform(matrix)
    terms = vectorizer.get_feature_names_out()
    old = rows(args.prior_map)

    addition_counts: Counter[int] = Counter()
    for index, row in enumerate(corpus):
        if paper_key(row["paper"]) in addition_keys:
            addition_counts[int(weights[index].argmax())] += 1

    branches = []
    for component in range(args.components):
        top_terms = select_terms(nmf.components_[component], terms, 8)
        similarities = [(jaccard(top_terms, prior["top_terms"]), prior) for prior in old]
        similarity, match = max(similarities, key=lambda item: item[0])
        count = addition_counts[component]
        changed = similarity < .65 or (count >= 2 and similarity < .85)
        query_a = " ".join(top_terms[:3])
        query_b = "large language model scientific agent " + query_a
        branches.append({
            "branch_id": f"cpu-r2-nmf-{component + 1:02d}",
            "component": component,
            "top_terms": top_terms,
            "new_eligible_dominant_count": count,
            "closest_prior_branch": match["branch_id"],
            "term_jaccard": round(similarity, 6),
            "materially_changed": changed,
            "queries": [query_a, query_b],
        })

    selected = sorted((branch for branch in branches if branch["materially_changed"]),
                      key=lambda branch: (-branch["new_eligible_dominant_count"],
                                          branch["term_jaccard"], branch["branch_id"]))
    selected = selected[:args.max_branches]
    selected_ids = {branch["branch_id"] for branch in selected}
    for branch in branches:
        branch["selected"] = branch["branch_id"] in selected_ids
    queries = list(dict.fromkeys(query for branch in selected for query in branch["queries"]))

    (args.out_dir / "round2-query-map.jsonl").write_text("".join(
        json.dumps(branch, ensure_ascii=False) + "\n" for branch in branches))
    (args.out_dir / "round2-queries.txt").write_text("\n".join(queries) + "\n")
    manifest = {
        "method": "bounded-tfidf-nmf-cpu-round/1.0",
        "hidden_targets_loaded": False,
        "selection_frozen_before_retrieval": True,
        "base_documents": sum(1 for role in ("eligible", "retrieval_only", "uncertain")
                              for _ in (args.base_screen_dir / f"{role}.jsonl").open()),
        "new_eligible_rows": len(additions),
        "merged_documents": len(corpus),
        "components": args.components,
        "seed": args.seed,
        "material_change_rule": "term Jaccard <0.65, or >=2 additions dominant and Jaccard <0.85",
        "max_branches": args.max_branches,
        "selected_branches": [branch["branch_id"] for branch in selected],
        "queries": len(queries),
        "retrieval_ceiling": "200 records per query/source; rank-yield stopping assessed after common screening",
        "citation_policy": "one hop from the 47 newly eligible round-one papers",
        "input_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in
                         (args.new_eligible, args.prior_map)},
    }
    (args.out_dir / "round2-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
