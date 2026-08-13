#!/usr/bin/env python3
"""Localize reconciled citation edges in cached full text without inference."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from prior.sources.refextract import ReferenceEntry, reference_entries, _bibliography_block


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def arxiv_id(paper: dict) -> str:
    for field in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5})(?:v\d+)?", str(paper.get(field) or ""), re.I)
        if m: return m.group(1)
    return ""


def safe_id(pid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", pid)


def window(text: str, start: int, end: int, radius: int = 500) -> str:
    return re.sub(r"\s+", " ", text[max(0, start-radius):min(len(text), end+radius)]).strip()


def doi(paper: dict) -> str:
    value = str(paper.get("doi") or "").lower()
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value).strip()


def paper_identifiers(paper: dict) -> tuple[set[str], set[str], list[str]]:
    records = [paper, *(paper.get("manifestations") or [])]
    arxiv_ids, dois, titles = set(), set(), []
    for record in records:
        if value := arxiv_id(record): arxiv_ids.add(value)
        if value := doi(record): dois.add(value)
        if value := norm(record.get("title") or ""): titles.append(value)
    return arxiv_ids, dois, titles


def matching_entry(entries: list[ReferenceEntry], paper: dict) -> ReferenceEntry | None:
    """Match only stable identifiers or a near-verbatim title; never infer."""
    arxiv_ids, target_dois, titles = paper_identifiers(paper)
    for entry in entries:
        raw_norm = norm(entry.raw)
        if any(re.search(rf"(?<![\d.]){re.escape(aid)}(?!\d)", entry.raw, re.I)
               for aid in arxiv_ids):
            return entry
        if any(target_doi in entry.raw.lower() for target_doi in target_dois):
            return entry
        if any(len(title) >= 25 and title in raw_norm for title in titles):
            return entry
    return None


def body_marker_matches(body: str, entry: ReferenceEntry) -> list[re.Match[str]]:
    if entry.marker_style == "numeric":
        number = int(entry.label)
        matches = []
        pattern = r"(?:\[\s*\d{1,4}(?:\s*[-–—,;]\s*\d{1,4})*\s*\]|\(\s*\d{1,3}\s*\))"
        for m in re.finditer(pattern, body):
            nums = [int(x) for x in re.findall(r"\d{1,4}", m.group(0))]
            if number in nums or any(a <= number <= b for a, b in zip(nums, nums[1:]) if a < b):
                matches.append(m)
        return matches
    if entry.marker_style == "author_year":
        author, year = entry.label.split("|", 1)
        surname = author.split()[0]
        pattern = rf"\b{re.escape(surname)}(?:\s+et\s+al\.)?[^.\n]{{0,45}}?\b{re.escape(year)}\b"
        return list(re.finditer(pattern, body, re.I))
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, default=Path("data/prior-core-v0.2/papers_core.jsonl"))
    ap.add_argument("--fulltext", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("experiments/edge_quality/out"))
    ap.add_argument("--edges", default="citations_reconciled.json")
    ap.add_argument("--output", default="citation_contexts_reconciled_v2.json")
    args = ap.parse_args()
    papers = {p["id"]: p for p in (json.loads(x) for x in args.papers.read_text().splitlines() if x.strip())}
    reconciled = json.loads((args.out / args.edges).read_text())["edges"]
    latex = json.loads((args.out / "citation_contexts.json").read_text())
    rows = []
    counts = {"latex_context": 0, "exact_arxiv_id": 0, "exact_normalized_title": 0,
              "bibliography_numeric_marker": 0, "bibliography_author_year_marker": 0,
              "listed_without_body_marker": 0, "context_unavailable": 0,
              "fulltext_unavailable": 0}
    for edge in reconciled:
        src, dst = edge["citing_id"], edge["cited_id"]
        key = f"{src}->{dst}"
        if key in latex:
            rows.append({**edge, "context_status": "latex_context", "contexts": latex[key]})
            counts["latex_context"] += 1; continue
        path = args.fulltext / f"{safe_id(src)}.txt"
        if not path.exists():
            rows.append({**edge, "context_status": "fulltext_unavailable", "contexts": []})
            counts["fulltext_unavailable"] += 1; continue
        text = path.read_text(errors="replace")
        target = papers[dst]
        entries = reference_entries(text)
        entry = matching_entry(entries, target)
        if entry and entry.marker_style != "unmarked":
            block = _bibliography_block(text)
            body = text[:-len(block)] if block else text
            marker_matches = body_marker_matches(body, entry)
            if marker_matches:
                status = f"bibliography_{entry.marker_style}_marker"
                contexts = [window(body, m.start(), m.end()) for m in marker_matches[:5]]
                rows.append({**edge, "context_status": status, "contexts": contexts,
                             "reference_entry": entry.raw, "reference_marker": entry.label})
                counts[status] += 1
                continue
        if entry:
            # Do not mistake a title/identifier in the reference list for a
            # supporting passage. The edge is evidenced, but its body marker
            # could not be recovered from this text representation.
            rows.append({**edge, "context_status": "listed_without_body_marker", "contexts": [],
                         "reference_entry": entry.raw, "reference_marker": entry.label})
            counts["listed_without_body_marker"] += 1
            continue
        aid = arxiv_id(target)
        match = re.search(rf"(?<![\d.]){re.escape(aid)}(?![\d])", text) if aid else None
        status = "exact_arxiv_id" if match else ""
        if not match:
            title = norm(target.get("title") or "")
            # Locate in a normalized shadow string. This preserves offsets because
            # every non-alphanumeric run becomes one space only approximately, so
            # use a regex over the original text instead for the final passage.
            words = [re.escape(w) for w in title.split()]
            if len(title) >= 25 and words:
                match = re.search(r"\W+".join(words), text, re.I)
                status = "exact_normalized_title" if match else ""
        if match:
            rows.append({**edge, "context_status": status,
                         "contexts": [window(text, match.start(), match.end())]})
            counts[status] += 1
        else:
            rows.append({**edge, "context_status": "context_unavailable", "contexts": []})
            counts["context_unavailable"] += 1
    result = {"edges": rows, "coverage": {"edges": len(rows), **counts},
              "method": "existing LaTeX context, else exact arXiv-id/title occurrence in cached citing full text"}
    result["method"] = ("existing LaTeX context; bibliography entry to numeric/author-year body marker; "
                        "else exact arXiv-id/title occurrence; listed-only edges remain passage-free")
    (args.out / args.output).write_text(json.dumps(result, indent=2))
    print(json.dumps(result["coverage"], indent=2))


if __name__ == "__main__":
    main()
