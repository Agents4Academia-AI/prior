#!/usr/bin/env python3
"""Assign every extracted reference an auditable terminal resolution state."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from rapidfuzz.fuzz import ratio

from prior.models import Paper
from prior.sources.refextract import bibliography_status, reference_entries
from prior.sources.refresolve import (CorpusIndex, ResolvedRef, map_to_corpus,
                                      REFERENCE_CHAR_CAP, resolve_reference,
                                      _default_resolver)

ARXIV_RE = re.compile(r"arxiv[:\s]*(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)", re.I)
NAVIGATION = re.compile(r"(?:purchase details|change username|show more references|references is not available)", re.I)


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def stated_identity(raw: str) -> ResolvedRef | None:
    if match := ARXIV_RE.search(raw):
        return ResolvedRef(reference=raw, arxiv_id=match.group(1), source="stated",
                           match_method="arxiv", match_score=1.0)
    if match := DOI_RE.search(raw):
        return ResolvedRef(reference=raw, doi=match.group(1), source="stated",
                           match_method="doi", match_score=1.0)
    return None


def ambiguous_candidates(raw: str, papers: list[Paper]) -> list[dict]:
    # Diagnostic only: never promote fuzzy similarity to an edge.
    value = norm(raw)
    scores = []
    for paper in papers:
        for manifestation in paper.all_manifestations():
            title = norm(manifestation.get("title") or "")
            if len(title) >= 20:
                score = ratio(title, value) / 100
                if score >= .86:
                    scores.append((score, paper.id, manifestation.get("title") or paper.title))
    unique = {}
    for score, pid, title in scores:
        if pid not in unique or score > unique[pid]["score"]:
            unique[pid] = {"paper_id": pid, "title": title, "score": score}
    return sorted(unique.values(), key=lambda row: row["score"], reverse=True)[:5]


def exact_corpus_candidates(raw: str, papers: list[Paper]) -> list[str]:
    """Conservative offline join: a complete normalized work title is present."""
    value = norm(raw)
    hits = set()
    for paper in papers:
        for manifestation in paper.all_manifestations():
            title = norm(manifestation.get("title") or "")
            if len(title) >= 25 and title in value:
                hits.add(paper.id)
    return sorted(hits)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, required=True)
    ap.add_argument("--fulltext", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--network", action="store_true",
                    help="Run the slow pinned multi-source resolver for entries without stable IDs")
    args = ap.parse_args()
    papers = [Paper.from_dict(json.loads(line)) for line in args.papers.read_text().splitlines() if line.strip()]
    index = CorpusIndex.from_papers(papers)
    done = {}
    if args.checkpoint.exists():
        for line in args.checkpoint.read_text().splitlines():
            row = json.loads(line); done[row["reference_id"]] = row
    resolver = None
    rows = dict(done)
    for pi, paper in enumerate(papers, 1):
        path = args.fulltext / f"{safe_id(paper.id)}.txt"
        text = path.read_text(errors="replace") if path.exists() else ""
        entries = reference_entries(text)
        if not entries:
            rid = f"{paper.id}::retrieval"
            rows[rid] = {"reference_id": rid, "citing_id": paper.id,
                         "state": "retrieval_unavailable", "raw": "",
                         "bibliography_status": bibliography_status(text)}
            continue
        for ei, entry in enumerate(entries, 1):
            rid = f"{paper.id}::ref{ei:04d}"
            if rid in rows:
                continue
            raw = entry.raw
            row = {"reference_id": rid, "citing_id": paper.id, "raw": raw,
                   "marker": entry.label, "marker_style": entry.marker_style}
            if NAVIGATION.search(raw):
                row["state"] = "non_bibliographic"
            elif len(raw) > REFERENCE_CHAR_CAP:
                row["state"] = "malformed"
            else:
                resolved = stated_identity(raw)
                exact = exact_corpus_candidates(raw, papers) if resolved is None else []
                if len(exact) == 1:
                    row["state"], row["target_id"] = "resolved_in_corpus", exact[0]
                    row["resolution"] = {"method": "exact_normalized_title", "score": 1.0,
                                         "source": "corpus"}
                    if exact[0] == paper.id:
                        row["state"] = "non_bibliographic"
                        row["note"] = "self-reference identity; excluded from citation edges"
                    resolved = None
                elif len(exact) > 1:
                    row["state"] = "ambiguous"
                    row["candidates"] = [{"paper_id": pid, "method": "exact_normalized_title"}
                                         for pid in exact]
                    resolved = None
                if resolved is None:
                    if "state" not in row and args.network and resolver is None:
                        resolver = _default_resolver()
                    if "state" not in row and resolver is not None:
                        resolved = resolve_reference(raw, resolver=resolver)
                if "state" in row:
                    pass
                elif resolved:
                    row["resolution"] = {"doi": resolved.doi, "arxiv_id": resolved.arxiv_id,
                                         "title": resolved.title, "source": resolved.source,
                                         "method": resolved.match_method,
                                         "score": resolved.match_score}
                    target = map_to_corpus(resolved, index)
                    if target and target != paper.id:
                        row["state"], row["target_id"] = "resolved_in_corpus", target
                    elif target == paper.id:
                        row["state"], row["target_id"] = "non_bibliographic", target
                        row["note"] = "self-reference identity; excluded from citation edges"
                    else:
                        row["state"] = "resolved_external"
                else:
                    candidates = ambiguous_candidates(raw, papers)
                    row["state"] = "ambiguous" if len(candidates) > 1 else "unresolved"
                    if candidates:
                        row["candidates"] = candidates
            rows[rid] = row
            with args.checkpoint.open("a") as fh:
                fh.write(json.dumps(row) + "\n")
        if pi % 10 == 0:
            print(f"ledger: {pi}/{len(papers)} papers, {len(rows)} records", flush=True)
    ordered = sorted(rows.values(), key=lambda row: row["reference_id"])
    counts = {}
    for row in ordered:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    args.output.write_text(json.dumps({"records": ordered, "coverage": counts,
                                      "method": ("manifestation-aware corpus alias index; stable IDs; exact full-title join; "
                                                 + ("pinned multi-source resolver; " if args.network else "")
                                                 + "fuzzy candidates never promoted")}, indent=2))
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
