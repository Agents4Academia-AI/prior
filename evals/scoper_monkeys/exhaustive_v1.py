"""Checkpointed exhaustive-v1 search: deep inclusive retrieval + four-way scope."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import scoper  # noqa: E402
from prior.models import Paper  # noqa: E402

from depth_ablation import collect  # noqa: E402


def run(topic_file: Path, queries: Path, out_dir: Path, *, max_depth: int,
        model: str | None = None, progress=print) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    retrieval = out_dir / "retrieval.jsonl"
    if not retrieval.exists():
        collect(queries, retrieval, max_depth=max_depth,
                include_navigation=True, progress=progress)
    rows = [json.loads(line) for line in retrieval.read_text().splitlines() if line]
    papers = [Paper.from_dict(row["paper"]) for row in rows if row.get("event") == "result"]
    candidates = scoper._dedup_cross_source(papers)
    (out_dir / "candidates.jsonl").write_text(
        "".join(json.dumps(paper.to_dict(), ensure_ascii=False) + "\n"
                for paper in candidates)
    )
    progress(f"deep inclusive retrieval: {len(candidates)} canonical candidates")
    roles = scoper.scope_exhaustive(
        topic_file.read_text(), candidates, model=model,
        cache_path=out_dir / "scope-cache.jsonl", progress=progress,
    )
    for role, items in roles.items():
        (out_dir / f"{role}.jsonl").write_text("".join(
            json.dumps({"paper": paper.to_dict(), "decision": decision},
                       ensure_ascii=False) + "\n"
            for paper, decision in items
        ))
    (out_dir / "status.json").write_text(json.dumps({
        "stage": "search_screened", "max_depth": max_depth,
        "queries_file": str(queries), "gold_visible": False,
        "roles": {role: len(items) for role, items in roles.items()},
        "next": "evolving query-map expansion and citation queue",
    }, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, type=Path)
    ap.add_argument("--queries", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--max-depth", type=int, default=200)
    ap.add_argument("--model")
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    run(args.topic, args.queries, args.out_dir, max_depth=args.max_depth,
        model=args.model)
