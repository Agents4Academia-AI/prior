#!/usr/bin/env python3
"""Recover intra-corpus citation edges from cached full-text bibliographies.

This is deterministic and domain-independent: stable identifiers win, with a
near-verbatim normalized title as the final conservative channel.  It performs
no network calls and records the matched reference string for auditability.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from prior.sources.refextract import bibliography_status, reference_entries


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def safe_id(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", pid)


def identifiers(paper: dict) -> tuple[set[str], set[str]]:
    records = [paper, *(paper.get("manifestations") or [])]
    arxiv_ids, dois = set(), set()
    for record in records:
        haystack = " ".join(str(record.get(k) or "") for k in ("id", "url", "doi", "pdf_url"))
        arxiv_ids.update(re.findall(
            r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5})(?:v\d+)?", haystack, re.I))
        value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "",
                       str(record.get("doi") or "").lower()).strip()
        if value:
            dois.add(value)
    return arxiv_ids, dois


def match_target(raw: str, candidates: list[dict]) -> tuple[str, str] | None:
    lowered, normalized = raw.lower(), norm(raw)
    hits = []
    for paper in candidates:
        arxiv_ids, dois = identifiers(paper)
        titles = [paper.get("title") or ""] + [m.get("title") or "" for m in paper.get("manifestations") or []]
        if any(re.search(rf"(?<![\d.]){re.escape(arxiv)}(?!\d)", raw, re.I)
               for arxiv in arxiv_ids):
            hits.append((paper["id"], "arxiv_id"))
        elif any(doi in lowered for doi in dois):
            hits.append((paper["id"], "doi"))
        elif any(len(title := norm(value)) >= 25 and title in normalized for value in titles):
            hits.append((paper["id"], "exact_normalized_title"))
    unique = {(pid, method) for pid, method in hits}
    pids = {pid for pid, _ in unique}
    return next(iter(unique)) if len(pids) == 1 else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, default=Path("data/prior-core-v0.2/papers_core.jsonl"))
    ap.add_argument("--fulltext", type=Path, required=True)
    ap.add_argument("--existing", type=Path, default=Path("experiments/edge_quality/out/citations_reconciled.json"))
    ap.add_argument("--output", type=Path, default=Path("experiments/edge_quality/out/citations_reconciled_v2.json"))
    args = ap.parse_args()
    papers = [json.loads(line) for line in args.papers.read_text().splitlines() if line.strip()]
    original = json.loads(args.existing.read_text())
    by_pair = {(e["citing_id"], e["cited_id"]): dict(e) for e in original["edges"]}
    parsed_sources = parsed_entries = matched_entries = new_edges = 0
    source_statuses: dict[str, str] = {}
    for source in papers:
        path = args.fulltext / f"{safe_id(source['id'])}.txt"
        if not path.exists():
            source_statuses[source["id"]] = "text_unavailable"
            continue
        text = path.read_text(errors="replace")
        source_statuses[source["id"]] = bibliography_status(text)
        entries = reference_entries(text)
        if entries:
            parsed_sources += 1
            parsed_entries += len(entries)
        candidates = [p for p in papers if p["id"] != source["id"]]
        for entry in entries:
            match = match_target(entry.raw, candidates)
            if not match:
                continue
            target_id, method = match
            matched_entries += 1
            pair = source["id"], target_id
            evidence = {"method": method, "reference": entry.raw,
                        "marker_style": entry.marker_style, "marker": entry.label}
            if pair in by_pair:
                by_pair[pair].setdefault("bibliography_evidence", []).append(evidence)
            else:
                by_pair[pair] = {"citing_id": pair[0], "cited_id": pair[1],
                                 "provenance": [f"bibliography:{method}"],
                                 "bibliography_evidence": [evidence]}
                new_edges += 1
    result = {"edges": sorted(by_pair.values(), key=lambda e: (e["citing_id"], e["cited_id"])),
              "coverage": {"papers": len(papers), "parsed_sources": parsed_sources,
                           "parsed_entries": parsed_entries, "matched_entries": matched_entries,
                           "existing_edges": len(original["edges"]), "new_edges": new_edges,
                           "total_edges": len(by_pair)},
              "source_statuses": source_statuses,
              "method": "exact arXiv ID, DOI, or normalized title in parsed bibliography entries"}
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["coverage"], indent=2))


if __name__ == "__main__":
    main()
