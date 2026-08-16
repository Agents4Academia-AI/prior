"""Blind retrieval-depth ablation for frozen Scoper queries.

Collect once at the maximum requested depth without loading gold, then score
prefixes offline. This isolates rank-depth effects from query generation,
screening, and citation expansion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import scoper  # noqa: E402
from prior.sources import arxiv, openalex  # noqa: E402

from common import load_gold, match_gold  # noqa: E402


SOURCES = {"openalex": openalex.search, "arxiv": arxiv.search}


def collect(queries_file: Path, out: Path, *, max_depth: int,
            include_navigation: bool = False, progress=print) -> None:
    import time

    queries = [line.strip() for line in queries_file.read_text().splitlines() if line.strip()]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as handle:
        handle.write(json.dumps({
            "event": "manifest", "queries_file": str(queries_file),
            "queries": queries, "max_depth": max_depth,
            "sources": list(SOURCES), "gold_visible_during_collection": False,
            "policy": "historical source filters; relevance-ranked prefix",
            "include_navigation_records": include_navigation,
        }) + "\n")
        for query_index, query in enumerate(queries, 1):
            for source, search in SOURCES.items():
                try:
                    kwargs = {
                        "max_papers": max_depth,
                        "exclude_reviews": not include_navigation,
                    }
                    if source == "openalex":
                        kwargs["require_abstract"] = not include_navigation
                    papers = search(query, **kwargs)
                    for rank, paper in enumerate(papers, 1):
                        handle.write(json.dumps({
                            "event": "result", "query_index": query_index,
                            "query": query, "source": source, "rank": rank,
                            "paper": paper.to_dict(),
                        }, ensure_ascii=False) + "\n")
                    handle.write(json.dumps({
                        "event": "terminal", "query_index": query_index,
                        "query": query, "source": source,
                        "status": "bounded" if len(papers) >= max_depth else "exhausted",
                        "returned": len(papers), "max_depth": max_depth,
                    }) + "\n")
                    handle.flush()
                    progress(f"{query_index}/{len(queries)} {source}: {len(papers)}")
                except Exception as error:  # noqa: BLE001
                    handle.write(json.dumps({
                        "event": "terminal", "query_index": query_index,
                        "query": query, "source": source, "status": "failed",
                        "error_type": type(error).__name__, "message": str(error)[:500],
                    }) + "\n")
                    handle.flush()
                    progress(f"{query_index}/{len(queries)} {source}: FAILED {error}")
                if source == "arxiv":
                    time.sleep(1.05)


def score(run: Path, gold_file: Path, out: Path, depths: list[int]) -> dict:
    rows = [json.loads(line) for line in run.read_text().splitlines() if line]
    results = [row for row in rows if row.get("event") == "result"]
    gold = load_gold(gold_file)
    report_rows = []
    recovered_at: dict[str, int | None] = {item.gold_id: None for item in gold}
    for depth in depths:
        papers = scoper._dedup_cross_source([
            __import__("prior.models", fromlist=["Paper"]).Paper.from_dict(row["paper"])
            for row in results if row["rank"] <= depth
        ])
        found = []
        for item in gold:
            hit = any(match_gold(item, paper.to_dict()) for paper in papers)
            if hit:
                found.append(item)
                if recovered_at[item.gold_id] is None:
                    recovered_at[item.gold_id] = depth
        by_source = {}
        for source in SOURCES:
            source_papers = [row["paper"] for row in results
                             if row["source"] == source and row["rank"] <= depth]
            by_source[source] = sum(
                any(match_gold(item, paper) for paper in source_papers) for item in gold
            )
        report_rows.append({
            "depth": depth, "candidate_works": len(papers), "targets_found": len(found),
            "target_recall": len(found) / max(1, len(gold)), "by_source": by_source,
        })
    report = {
        "gold_n": len(gold), "depths": report_rows,
        "source_failures": [row for row in rows
                            if row.get("event") == "terminal" and row.get("status") == "failed"],
        "targets": [{
            "gold_id": item.gold_id, "title": item.title,
            "first_depth_bucket": recovered_at[item.gold_id],
        } for item in gold],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    md = [
        "# Scoper retrieval-depth ablation", "",
        f"Frozen targets: **{len(gold)}**. Gold was joined only after collection.", "",
        "| depth per query/source | canonical candidates | targets | recall | OpenAlex | arXiv |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report_rows:
        md.append(
            f"| {row['depth']} | {row['candidate_works']} | {row['targets_found']} | "
            f"{row['target_recall']:.1%} | {row['by_source']['openalex']} | "
            f"{row['by_source']['arxiv']} |"
        )
    failures = report["source_failures"]
    md += ["", f"Source failures: **{len(failures)}**."]
    out.with_suffix(".md").write_text("\n".join(md) + "\n")
    return report


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    collect_ap = sub.add_parser("collect")
    collect_ap.add_argument("--queries", required=True, type=Path)
    collect_ap.add_argument("--out", required=True, type=Path)
    collect_ap.add_argument("--max-depth", type=int, default=200)
    collect_ap.add_argument("--include-navigation", action="store_true")
    score_ap = sub.add_parser("score")
    score_ap.add_argument("--run", required=True, type=Path)
    score_ap.add_argument("--gold", required=True, type=Path)
    score_ap.add_argument("--out", required=True, type=Path)
    score_ap.add_argument("--depths", default="5,10,20,50,100,200")
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    if args.command == "collect":
        collect(args.queries, args.out, max_depth=args.max_depth,
                include_navigation=args.include_navigation)
    else:
        score(args.run, args.gold, args.out,
              [int(value) for value in args.depths.split(",")])
