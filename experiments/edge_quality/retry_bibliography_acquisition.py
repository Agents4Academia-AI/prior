#!/usr/bin/env python3
"""Retry alternate full-text representations for bibliography failures."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from prior.fulltext import fetch_for_bibliography
from prior.models import Paper
from prior.sources.refextract import bibliography_status


def safe_id(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", pid)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, default=Path("data/prior-core-v0.2/papers_core.jsonl"))
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--only-failures", action="store_true", default=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    papers = [Paper.from_dict(json.loads(line)) for line in args.papers.read_text().splitlines() if line.strip()]
    audit = []
    for i, paper in enumerate(papers, 1):
        source_path = args.input / f"{safe_id(paper.id)}.txt"
        existing = source_path.read_text(errors="replace") if source_path.exists() else None
        before = bibliography_status(existing or "")
        if before == "parsed" and args.only_failures:
            continue
        text, channel, attempts = fetch_for_bibliography(paper, existing_text=existing)
        after = bibliography_status(text or "")
        if text:
            (args.output / f"{safe_id(paper.id)}.txt").write_text(text)
        row = {"paper_id": paper.id, "before": before, "after": after,
               "selected_channel": channel, "attempts": attempts}
        audit.append(row)
        print(f"[{i}/{len(papers)}] {paper.id}: {before} -> {after} ({channel})", flush=True)
    args.audit.write_text(json.dumps({"papers": audit}, indent=2))
    print(json.dumps({"retried": len(audit),
                      "improved_to_parsed": sum(r["before"] != "parsed" and r["after"] == "parsed" for r in audit)},
                     indent=2))


if __name__ == "__main__":
    main()
