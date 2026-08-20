"""Consolidate CPU-adaptive retrieval into ranked, provenance-rich novel works."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from freeze_external_targets import aliases

CUTOFF = date(2026, 6, 24)


def events(path: Path):
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def cutoff_bucket(paper: dict, cutoff: date | None = CUTOFF) -> str:
    if cutoff is None:
        return "pre_cutoff"
    raw = paper.get("date") or ""
    if len(raw) == 10:
        return "post_cutoff" if date.fromisoformat(raw) > CUTOFF else "pre_cutoff"
    year = paper.get("year")
    if year and year < 2026: return "pre_cutoff"
    if year and year > 2026: return "post_cutoff"
    return "cutoff_uncertain"


def load_aliases(path: Path) -> set[str]:
    out = set()
    for row in events(path):
        paper = row.get("paper") if row.get("event") == "result" else row.get("paper", row)
        if paper: out |= aliases(paper)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval", type=Path, required=True)
    ap.add_argument("--existing", type=Path, action="append", default=[])
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--cutoff", default=CUTOFF.isoformat(),
                    help="YYYY-MM-DD, or 'none' for a living-corpus run")
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)
    cutoff = None if args.cutoff.lower() == "none" else date.fromisoformat(args.cutoff)
    existing = set()
    for path in args.existing: existing |= load_aliases(path)

    groups = []
    for row in events(args.retrieval):
        if row.get("event") != "result": continue
        paper, paper_aliases = row["paper"], aliases(row["paper"])
        group = next((g for g in groups if g["aliases"] & paper_aliases), None)
        hit = {"query_index": row["query_index"], "query": row["query"],
               "source": row["source"], "rank": row["rank"]}
        if group:
            group["aliases"] |= paper_aliases; group["hits"].append(hit)
            if len(paper.get("abstract") or "") > len(group["paper"].get("abstract") or ""):
                group["paper"] = paper
        else:
            groups.append({"paper": paper, "aliases": set(paper_aliases), "hits": [hit]})

    outputs = defaultdict(list); query_stats = defaultdict(Counter)
    for group in groups:
        hits = group["hits"]; queries = {h["query_index"] for h in hits}; sources = {h["source"] for h in hits}
        group["aliases"] = sorted(group["aliases"])
        group["priority"] = {"best_rank": min(h["rank"] for h in hits),
                             "query_count": len(queries), "source_count": len(sources),
                             "reciprocal_rank_sum": sum(1 / h["rank"] for h in hits)}
        group["seen_in_pre_adaptive_search"] = bool(set(group["aliases"]) & existing)
        group["cutoff_bucket"] = cutoff_bucket(group["paper"], cutoff)
        bucket = "rediscovered" if group["seen_in_pre_adaptive_search"] else group["cutoff_bucket"]
        outputs[bucket].append(group)
        for h in hits:
            query_stats[h["query_index"]]["result_occurrences"] += 1
            if not group["seen_in_pre_adaptive_search"]:
                query_stats[h["query_index"]]["novel_work_hits"] += 1
    for bucket, items in outputs.items():
        items.sort(key=lambda g: (-g["priority"]["source_count"],
                                  -g["priority"]["query_count"],
                                  -g["priority"]["reciprocal_rank_sum"],
                                  g["paper"].get("title", "")))
        (args.out_dir / f"adaptive-{bucket}.jsonl").write_text("".join(
            json.dumps(item, ensure_ascii=False) + "\n" for item in items))
        (args.out_dir / f"adaptive-{bucket}-papers.jsonl").write_text("".join(
            json.dumps(item["paper"], ensure_ascii=False) + "\n" for item in items))
    terminals = [r for r in events(args.retrieval) if r.get("event") == "terminal"]
    status = {"retrieval": str(args.retrieval),
              "cutoff": cutoff.isoformat() if cutoff else None,
              "result_occurrences": sum(1 for r in events(args.retrieval) if r.get("event") == "result"),
              "canonical_works": len(groups), "partitions": {k: len(v) for k, v in outputs.items()},
              "source_failures": sum(r.get("status") == "failed" for r in terminals),
              "query_stats": {str(k): dict(v) for k, v in sorted(query_stats.items())}}
    (args.out_dir / "adaptive-candidates-status.json").write_text(json.dumps(status, indent=2) + "\n")


if __name__ == "__main__":
    main()
