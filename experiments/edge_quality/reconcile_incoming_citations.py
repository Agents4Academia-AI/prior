#!/usr/bin/env python3
"""Checkpointed all-corpus incoming-citation reconciliation audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prior.models import Paper
from prior.scoper import _same_work
from prior.sources import openalex, semanticscholar


def identities(paper: Paper) -> tuple[list[str], list[str]]:
    oa, s2 = [], []
    for record in paper.all_manifestations():
        rid = str(record.get("id") or "")
        if rid.startswith("openalex:"):
            oa.append(rid)
        if rid.startswith("arxiv:"):
            s2.append("ARXIV:" + rid.split(":", 1)[1].split("v")[0])
    if not s2 and paper.doi:
        s2.append("DOI:" + paper.doi.replace("https://doi.org/", ""))
    return list(dict.fromkeys(oa)), list(dict.fromkeys(s2))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, required=True)
    ap.add_argument("--edges", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--max-results", type=int, default=500)
    args = ap.parse_args()
    papers = [Paper.from_dict(json.loads(line)) for line in args.papers.read_text().splitlines()
              if line.strip()]
    original = json.loads(args.edges.read_text())
    by_pair = {(row["citing_id"], row["cited_id"]): row for row in original["edges"]}
    done: dict[str, dict] = {}
    if args.checkpoint.exists():
        for line in args.checkpoint.read_text().splitlines():
            row = json.loads(line)
            done[row["target_id"]] = row
    for i, target in enumerate(papers, 1):
        if target.id in done:
            continue
        found: dict[tuple[str, str], set[str]] = {}
        oa_ids, s2_ids = identities(target)
        returned: list[tuple[str, Paper]] = []
        for oid in oa_ids:
            returned.extend(("openalex", p) for p in
                            openalex.cited_by(oid, max_results=args.max_results))
        for sid in s2_ids:
            # Central adapter owns S2 pacing, Retry-After, and 429 backoff.
            returned.extend(("semanticscholar", p) for p in
                            semanticscholar.citations(sid, max_results=args.max_results))
        for source, candidate in returned:
            matches = [p for p in papers if p.id != target.id and _same_work(candidate, p)]
            if len(matches) == 1:
                found.setdefault((matches[0].id, target.id), set()).add(source)
        row = {"target_id": target.id, "openalex_ids": oa_ids, "s2_ids": s2_ids,
               "returned_records": len(returned),
               "matches": [{"citing_id": src, "cited_id": dst, "sources": sorted(sources)}
                           for (src, dst), sources in sorted(found.items())]}
        done[target.id] = row
        with args.checkpoint.open("a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(f"incoming: {i}/{len(papers)} {target.id}: {len(returned)} returned, "
              f"{len(found)} corpus matches", flush=True)
    added = 0
    for audit in done.values():
        for match in audit["matches"]:
            pair = match["citing_id"], match["cited_id"]
            provenance = [f"incoming:{source}" for source in match["sources"]]
            if pair in by_pair:
                current = by_pair[pair].setdefault("provenance", [])
                current.extend(value for value in provenance if value not in current)
            else:
                by_pair[pair] = {"citing_id": pair[0], "cited_id": pair[1],
                                 "provenance": provenance}
                added += 1
    result = {"edges": sorted(by_pair.values(), key=lambda row: (row["citing_id"], row["cited_id"])),
              "coverage": {"papers": len(papers), "targets_queried": len(done),
                           "returned_records": sum(r["returned_records"] for r in done.values()),
                           "incoming_matches": sum(len(r["matches"]) for r in done.values()),
                           "existing_edges": len(original["edges"]), "new_edges": added,
                           "total_edges": len(by_pair)},
              "method": "OpenAlex incoming citations plus centrally paced Semantic Scholar citations; exact manifestation-aware work match"}
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["coverage"], indent=2))


if __name__ == "__main__":
    main()
