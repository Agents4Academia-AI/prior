"""Shared schemas, gold parsing, and identity matching for Scoper monkey evals."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_WORD = re.compile(r"[a-z0-9]+")


def normalise_doi(value: str | None) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value.rstrip(" .")


def normalise_arxiv(value: str | None) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^(?:arxiv:|https?://arxiv\.org/(?:abs|pdf)/)", "", value)
    return re.sub(r"v\d+$", "", value).removesuffix(".pdf")


def title_tokens(value: str | None) -> set[str]:
    return set(_WORD.findall((value or "").lower()))


def title_key(value: str | None) -> str:
    return " ".join(_WORD.findall((value or "").lower()))


def title_similarity(a: str | None, b: str | None) -> float:
    aa, bb = title_tokens(a), title_tokens(b)
    return len(aa & bb) / max(1, len(aa | bb))


@dataclass(frozen=True)
class GoldItem:
    gold_id: str
    title: str
    doi: str = ""
    arxiv: str = ""
    year: int | None = None


def _bib_field(entry: str, name: str) -> str:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*", entry, re.I)
    if not match:
        return ""
    pos = match.end()
    if pos < len(entry) and entry[pos] == "{":
        depth = 0
        for end in range(pos, len(entry)):
            if entry[end] == "{":
                depth += 1
            elif entry[end] == "}":
                depth -= 1
                if depth == 0:
                    return entry[pos + 1:end]
    quoted = re.match(r'"([^"]*)"|([^,\s}]+)', entry[pos:])
    return (quoted.group(1) or quoted.group(2)) if quoted else ""


def _gold_from_rows(rows: Iterable[dict]) -> list[GoldItem]:
    out: list[GoldItem] = []
    for index, row in enumerate(rows):
        title = " ".join(re.sub(r"[{}]", "", str(row.get("title", ""))).split())
        if not title:
            continue
        year_text = str(row.get("year", "") or "")
        out.append(GoldItem(
            gold_id=str(row.get("gold_id") or row.get("id") or f"gold:{index:05d}"),
            title=title,
            doi=normalise_doi(str(row.get("doi", "") or "")),
            arxiv=normalise_arxiv(str(row.get("arxiv", "") or "")),
            year=int(year_text) if year_text.isdigit() else None,
        ))
    return out


def load_gold(path: str | Path) -> list[GoldItem]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return _gold_from_rows(
            json.loads(line) for line in path.read_text().splitlines() if line.strip()
        )
    if suffix == ".csv":
        with path.open(newline="") as handle:
            return _gold_from_rows(csv.DictReader(handle))
    if suffix == ".bib":
        rows = []
        for index, entry in enumerate(re.split(r"\n(?=@)", path.read_text())):
            title = _bib_field(entry, "title")
            if not title:
                continue
            year = _bib_field(entry, "year")
            doi = _bib_field(entry, "doi")
            arxiv = _bib_field(entry, "eprint")
            key = re.match(r"@\w+\s*{\s*([^,]+)", entry)
            rows.append({
                "gold_id": key.group(1).strip() if key else f"gold:{index:05d}",
                "title": title,
                "year": year,
                "doi": doi,
                "arxiv": arxiv,
            })
        return _gold_from_rows(rows)
    raise ValueError(f"gold must be .bib, .jsonl, or .csv, got {path}")


def paper_identity(paper: dict) -> dict[str, str]:
    pid = str(paper.get("id", ""))
    arxiv = pid.split(":", 1)[1] if pid.startswith("arxiv:") else paper.get("arxiv", "")
    return {
        "id": pid,
        "doi": normalise_doi(str(paper.get("doi", "") or "")),
        "arxiv": normalise_arxiv(str(arxiv or "")),
        "title": str(paper.get("title", "") or ""),
        "title_key": title_key(str(paper.get("title", "") or "")),
    }


def match_gold(gold: GoldItem, paper: dict, *, title_threshold: float = 0.82) -> float:
    identity = paper_identity(paper)
    if gold.doi and identity["doi"] and gold.doi == identity["doi"]:
        return 1.0
    if gold.arxiv and identity["arxiv"] and gold.arxiv == identity["arxiv"]:
        return 1.0
    return title_similarity(gold.title, identity["title"]) if (
        title_similarity(gold.title, identity["title"]) >= title_threshold
    ) else 0.0


def best_gold_match(
    gold: GoldItem, papers: Iterable[dict], *, title_threshold: float = 0.82
) -> tuple[dict | None, float]:
    best, score = None, 0.0
    for paper in papers:
        candidate = match_gold(gold, paper, title_threshold=title_threshold)
        if candidate > score:
            best, score = paper, candidate
    return best, score


def load_events(path: str | Path) -> list[dict]:
    events = [
        json.loads(line)
        for line in Path(path).read_text().splitlines()
        if line.strip()
    ]
    # Legacy traces remain scoreable; versioned ledgers are validated before use.
    if events and "schema_version" in events[0]:
        from ledger import validate_ledger
        validate_ledger(events)
    return events
