"""Induce a deterministic, leakage-safe CPU lexical query map with TF-IDF/NMF."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer


DOMAIN_STOPS = {
    "paper", "papers", "study", "studies", "research", "scientific", "science",
    "method", "methods", "approach", "approaches", "result", "results", "using",
    "based", "propose", "proposed", "introduce", "large", "language", "model",
    "models", "llm", "llms", "ai", "artificial", "intelligence", "agent", "agents",
}


def select_terms(component, terms, count: int) -> list[str]:
    """Prefer informative phrases while removing nested/repeated NMF terms."""
    ranked = sorted(range(len(component)),
                    key=lambda i: component[i] * (1.18 if " " in terms[i] else 1.0),
                    reverse=True)
    selected: list[str] = []
    selected_tokens: list[set[str]] = []
    for index in ranked[:150]:
        term = terms[index]; tokens = term.split(); token_set = set(tokens)
        if len(tokens) != len(token_set):
            continue
        if any(token_set <= prior or prior <= token_set or
               len(token_set & prior) / len(token_set | prior) > .5
               for prior in selected_tokens):
            continue
        selected.append(term); selected_tokens.append(token_set)
        if len(selected) == count:
            break
    return selected


def read_role(path: Path, role: str) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line); paper = row.get("paper", row)
        text = " ".join((paper.get("title") or "", paper.get("abstract") or "")).strip()
        if text:
            rows.append({"paper": paper, "role": role, "text": text})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--components", type=int, default=16)
    ap.add_argument("--terms", type=int, default=8)
    ap.add_argument("--representatives", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260819)
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)

    corpus = []
    for role in ("eligible", "retrieval_only", "uncertain"):
        corpus.extend(read_role(args.screen_dir / f"{role}.jsonl", role))
    stops = sorted(set(ENGLISH_STOP_WORDS) | DOMAIN_STOPS)
    vectorizer = TfidfVectorizer(stop_words=stops, ngram_range=(1, 2), min_df=3,
                                 max_df=.70, max_features=20000, sublinear_tf=True)
    matrix = vectorizer.fit_transform(row["text"] for row in corpus)
    nmf = NMF(n_components=args.components, init="nndsvda", random_state=args.seed,
              max_iter=600, l1_ratio=.1)
    weights = nmf.fit_transform(matrix)
    terms = vectorizer.get_feature_names_out()
    branches = []
    queries = []
    for component in range(args.components):
        top_terms = select_terms(nmf.components_[component], terms, args.terms)
        representative_ids = weights[:, component].argsort()[::-1][:args.representatives]
        representatives = [{"title": corpus[i]["paper"].get("title", ""),
                            "role": corpus[i]["role"],
                            "weight": round(float(weights[i, component]), 8)}
                           for i in representative_ids]
        # Two transparent views of each community: its strongest phrases and a
        # broader agentic-science anchor. Duplicate query strings are removed below.
        phrase_terms = top_terms[:3]
        query_a = " ".join(phrase_terms)
        query_b = "large language model scientific agent " + " ".join(top_terms[:3])
        branch_id = f"cpu-nmf-{component + 1:02d}"
        branches.append({"branch_id": branch_id, "component": component,
                         "top_terms": top_terms, "representatives": representatives,
                         "queries": [query_a, query_b]})
        queries.extend((query_a, query_b))
    queries = list(dict.fromkeys(queries))
    manifest = {
        "method": "tfidf-nmf-cpu-query-map/1.0", "gold_visible": False,
        "hidden_targets_loaded": False, "roles": ["eligible", "retrieval_only", "uncertain"],
        "documents": len(corpus), "components": args.components, "seed": args.seed,
        "vectorizer": {"ngram_range": [1, 2], "min_df": 3, "max_df": .70,
                       "max_features": 20000, "sublinear_tf": True,
                       "domain_stops": sorted(DOMAIN_STOPS)},
        "nmf": {"init": "nndsvda", "max_iter": 600, "l1_ratio": .1},
        "screen_input_sha256": {role: hashlib.sha256(
            (args.screen_dir / f"{role}.jsonl").read_bytes()).hexdigest()
            for role in ("eligible", "retrieval_only", "uncertain")},
        "queries": len(queries),
        "limitation": "Lexical communities are a transparent CPU baseline; scientific-document embedding geometry is deferred future work.",
    }
    (args.out_dir / "cpu-query-map.jsonl").write_text("".join(
        json.dumps(row, ensure_ascii=False) + "\n" for row in branches))
    (args.out_dir / "cpu-adaptive-queries.txt").write_text("\n".join(queries) + "\n")
    (args.out_dir / "cpu-query-map-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
