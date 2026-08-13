#!/usr/bin/env python3
"""Freeze candidates for a legacy-versus-evidence-enriched Cartographer run.

The manifest preserves the legacy semantic candidates and adds a bounded number
of contribution-pair candidates for every resolved intra-corpus citation. Citation
passages improve deterministic alignment when available, but unlocalized citation
facts remain candidates and are explicitly marked as such.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data" / "prior-core-v0.2"
OUT = Path(__file__).parent / "out"
DEFAULT_FULLTEXT = Path(
    "/Users/kk1918_1/Desktop/Projects/hackathon/prior/data_hackathon/fulltext"
)
WORD = re.compile(r"[a-z0-9]+")


def paper_id(contribution_id: str) -> str:
    return contribution_id.split("::")[0]


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted((a, b)))


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def tokens(text: str) -> Counter[str]:
    return Counter(WORD.findall(text.lower()))


def cosine(a: Counter[str], b: Counter[str]) -> float:
    common = sum(a[k] * b[k] for k in a.keys() & b.keys())
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return common / (da * db) if da and db else 0.0


def contribution_text(row: dict) -> str:
    return " ".join(str(row.get(k) or "") for k in
                    ("statement", "problem", "method", "result", "kind"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--citation-pairs-per-edge", type=int, default=2)
    parser.add_argument("--fulltext-dir", type=Path, default=DEFAULT_FULLTEXT)
    parser.add_argument("--output", type=Path,
                        default=OUT / "cartographer_rebuild_candidates.json")
    args = parser.parse_args()
    if args.citation_pairs_per_edge < 1:
        parser.error("--citation-pairs-per-edge must be positive")

    contribution_path = BUNDLE / "contributions_core_grounded.json"
    legacy_path = BUNDLE / "contributions_core_consensus.json"
    citation_path = OUT / "citations_bbl.json"
    context_path = OUT / "citation_map.json"
    paper_path = BUNDLE / "papers_core.jsonl"

    contribution_obj = load_json(contribution_path)
    contributions = (contribution_obj["contributions"]
                     if isinstance(contribution_obj, dict) else contribution_obj)
    by_id = {row["id"]: row for row in contributions}
    by_paper: dict[str, list[dict]] = defaultdict(list)
    vectors = {}
    for row in contributions:
        by_paper[row["paper_id"]].append(row)
        vectors[row["id"]] = tokens(contribution_text(row))

    legacy_obj = load_json(legacy_path)
    legacy = legacy_obj["edges"] if isinstance(legacy_obj, dict) else legacy_obj
    citation_obj = load_json(citation_path)
    citations = citation_obj["edges"] if isinstance(citation_obj, dict) else citation_obj
    contexts = {
        (row["citing_id"], row["cited_id"]): row.get("contexts", [])
        for row in load_json(context_path)
    }
    papers = [json.loads(line) for line in paper_path.read_text().splitlines()
              if line.strip()]
    corpus_ids = {row["id"] for row in papers}

    candidates: dict[str, dict] = {}
    for edge in legacy:
        src, dst = edge["src"], edge["dst"]
        if src not in by_id or dst not in by_id or paper_id(src) == paper_id(dst):
            continue
        key = pair_key(src, dst)
        row = candidates.setdefault(key, {
            "candidate_id": key, "a": min(src, dst), "b": max(src, dst),
            "channels": [], "legacy_edges": [], "citations": [],
        })
        if "semantic" not in row["channels"]:
            row["channels"].append("semantic")
        row["legacy_edges"].append({k: edge.get(k) for k in
                                    ("src", "dst", "relation", "confidence",
                                     "evidence", "similarity", "trust")})

    invalid_citations = []
    aligned = 0
    for citing, cited in citations:
        if citing not in corpus_ids or cited not in corpus_ids or citing == cited:
            invalid_citations.append([citing, cited])
            continue
        left, right = by_paper.get(citing, []), by_paper.get(cited, [])
        if not left or not right:
            invalid_citations.append([citing, cited])
            continue
        passage = " ".join(item.get("text", "") for item in
                           contexts.get((citing, cited), []))
        passage_vector = tokens(passage)
        ranked = []
        for source in left:
            for target in right:
                source_v, target_v = vectors[source["id"]], vectors[target["id"]]
                pair_similarity = cosine(source_v, target_v)
                if passage_vector:
                    score = (0.25 * cosine(passage_vector, source_v)
                             + 0.50 * cosine(passage_vector, target_v)
                             + 0.25 * pair_similarity)
                else:
                    score = pair_similarity
                ranked.append((score, source["id"], target["id"]))
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
        for rank, (score, src, dst) in enumerate(
                ranked[:args.citation_pairs_per_edge], 1):
            key = pair_key(src, dst)
            row = candidates.setdefault(key, {
                "candidate_id": key, "a": min(src, dst), "b": max(src, dst),
                "channels": [], "legacy_edges": [], "citations": [],
            })
            if "citation" not in row["channels"]:
                row["channels"].append("citation")
            row["citations"].append({
                "citing_id": citing, "cited_id": cited,
                "localized": bool(passage_vector), "alignment_rank": rank,
                "alignment_score": round(score, 6),
            })
            aligned += 1

    rows = sorted(candidates.values(), key=lambda row: row["candidate_id"])
    for row in rows:
        row["channels"].sort()
    channel_counts = Counter("+".join(row["channels"]) for row in rows)
    fulltext = {
        pid: (args.fulltext_dir / f"{safe_id(pid)}.txt").exists()
        for pid in sorted(corpus_ids)
    }
    report = {
        "schema_version": 1,
        "method": {
            "legacy": "all cross-paper contribution candidates in the frozen consensus graph",
            "citation": "top deterministic contribution alignments per resolved directed citation",
            "citation_pairs_per_edge": args.citation_pairs_per_edge,
            "alignment": "0.25 context-to-citing + 0.50 context-to-cited + 0.25 contribution cosine; contribution cosine alone without localized context",
        },
        "input_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in
                          (contribution_path, legacy_path, citation_path,
                           context_path, paper_path)},
        "counts": {
            "papers": len(corpus_ids), "contributions": len(contributions),
            "legacy_edges": len(legacy), "resolved_citations": len(citations),
            "localized_citations": len(contexts),
            "citation_alignment_records": aligned,
            "candidate_union": len(rows), "channels": dict(channel_counts),
            "papers_with_fulltext": sum(fulltext.values()),
            "papers_without_fulltext": sum(not value for value in fulltext.values()),
            "invalid_citation_records": len(invalid_citations),
        },
        "missing_fulltext": [pid for pid, present in fulltext.items() if not present],
        "invalid_citations": invalid_citations,
        "candidates": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))
    print("missing full text:", report["missing_fulltext"])
    print("->", args.output)


if __name__ == "__main__":
    main()
