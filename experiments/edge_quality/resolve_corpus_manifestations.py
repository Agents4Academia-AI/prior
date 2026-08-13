#!/usr/bin/env python3
"""Resolve and preserve cross-source manifestations for a frozen corpus."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prior.models import Paper
from prior.scoper import resolve_manifestations


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, default=Path("data/prior-core-v0.2/papers_core.jsonl"))
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    papers = [Paper.from_dict(json.loads(line)) for line in args.papers.read_text().splitlines() if line.strip()]
    resolve_manifestations(papers)
    args.output.write_text("\n".join(json.dumps(p.to_dict()) for p in papers) + "\n")
    counts = {"papers": len(papers),
              "with_alternate_manifestations": sum(bool(p.manifestations) for p in papers),
              "manifestations": sum(len(p.manifestations) for p in papers)}
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
