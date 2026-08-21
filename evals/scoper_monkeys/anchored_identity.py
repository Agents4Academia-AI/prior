"""Deterministic, offline work/manifestation reconciliation for anchored runs."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import dates, scoper  # noqa: E402
from prior.models import Paper  # noqa: E402

OA_ID = re.compile(r"^(?:openalex:)?W\d+$", re.I)
ARXIV_ID = re.compile(r"^arxiv:(\d{4}\.\d{4,5})(?:v\d+)?$", re.I)
S2_ID = re.compile(r"^s2:[0-9a-f]{40}$", re.I)
ARXIV_LOCATOR = re.compile(
    r"(?:arxiv[:./]|abs/|pdf/)(\d{4}\.\d{4,5})(?:v\d+)?", re.I
)
DOI = re.compile(r"^10\.\d{4,9}/[-._;()/:a-z0-9]+$", re.I)
DOI_ID = re.compile(
    r"^(?:doi:|https?://(?:dx\.)?doi\.org/)(10\.\d{4,9}/\S+)$", re.I
)
UNRESOLVED_ID = re.compile(
    r"^(?:(?:s2|openalex|arxiv):)?(?:none|null|unknown|unresolved)?$", re.I
)
SOURCE_RANK = {"openalex": 0, "arxiv": 1, "semanticscholar": 2}


def _dump(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _title(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]", " ", (value or "").lower()).split())


def _doi(value) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)
    return value.rstrip(". /,;")


def _valid_id(value) -> str:
    value = str(value or "").strip()
    if OA_ID.fullmatch(value):
        return "openalex:" + value.rsplit(":", 1)[-1].upper()
    if match := ARXIV_ID.fullmatch(value):
        return "arxiv:" + match.group(1).lower()
    if S2_ID.fullmatch(value):
        return value.lower()
    if match := DOI_ID.fullmatch(value):
        doi = _doi(match.group(1))
        if DOI.fullmatch(doi):
            return "doi:" + doi
    return ""


def _is_unresolved_stub(paper: Paper) -> bool:
    """Explicit placeholder records are quarantined despite stray metadata."""
    return bool(UNRESOLVED_ID.fullmatch(str(paper.id or "").strip()))


def _paper_records(paper: Paper) -> list[dict]:
    primary = {name: copy.deepcopy(getattr(paper, name))
               for name in Paper.__dataclass_fields__}  # type: ignore[attr-defined]
    nested = primary.pop("manifestations", []) or []
    primary["manifestations"] = []
    return [primary, *(copy.deepcopy(row) for row in nested if isinstance(row, dict))]


def _identity(paper: Paper) -> tuple[set[str], list[str]]:
    """Validated union keys plus identifiers ignored as malformed."""
    keys, malformed = set(), []
    for row in _paper_records(paper):
        raw_id = str(row.get("id") or "").strip()
        if raw_id:
            valid = _valid_id(raw_id)
            if valid:
                keys.add(valid)
            else:
                malformed.append(raw_id)
        haystack = " ".join(str(row.get(name) or "") for name in
                            ("id", "url", "pdf_url", "doi"))
        for match in ARXIV_LOCATOR.finditer(haystack):
            keys.add("arxiv:" + match.group(1).lower())
        if row.get("doi"):
            doi = _doi(row["doi"])
            if DOI.fullmatch(doi):
                keys.add("doi:" + doi)
                match = re.fullmatch(
                    r"10\.48550/arxiv\.(\d{4}\.\d{4,5})(?:v\d+)?", doi, re.I
                )
                if match:
                    keys.add("arxiv:" + match.group(1).lower())
            else:
                malformed.append(str(row["doi"]))
    return keys, sorted(set(malformed))


@dataclass
class IdentityResolution:
    groups: list[dict]
    unresolved: list[dict]
    audit: list[dict]

    def __iter__(self):
        return iter((self.groups, self.unresolved, self.audit))

    def to_dict(self) -> dict:
        return {"groups": self.groups, "unresolved": self.unresolved,
                "audit": self.audit}

    @property
    def resolved(self) -> list[dict]:
        """Alias that makes the resolved/unresolved partition explicit."""
        return self.groups


class _UF:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.members = {index: {index} for index in range(size)}

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> bool:
        left, right = self.find(left), self.find(right)
        if left == right:
            return False
        root, other = min(left, right), max(left, right)
        self.parent[other] = root
        self.members[root].update(self.members.pop(other))
        return True


def _component_keys(uf: _UF, root: int, records: list[dict]) -> set[str]:
    return set().union(*(records[index]["keys"]
                         for index in uf.members[uf.find(root)]))


def _conflicts(uf: _UF, left: int, right: int, records: list[dict]) -> list[dict]:
    left_keys, right_keys = (_component_keys(uf, left, records),
                             _component_keys(uf, right, records))
    out = []
    for prefix in ("doi:", "arxiv:"):
        a = {key for key in left_keys if key.startswith(prefix)}
        b = {key for key in right_keys if key.startswith(prefix)}
        if a and b and a.isdisjoint(b):
            out.append({"namespace": prefix[:-1], "left": sorted(a), "right": sorted(b)})
    return out


def _canonical_key(records: list[dict]) -> str:
    keys = set().union(*(record["keys"] for record in records))
    for prefix in ("arxiv:", "doi:", "openalex:", "s2:"):
        matches = sorted(key for key in keys if key.startswith(prefix))
        if matches:
            return matches[0]
    return "title:" + sorted(record["title"] for record in records)[0]


def _occurrence_counts(records: list[dict]) -> dict:
    """Lossless deterministic count summary; occurrences remain attached too."""
    channels = Counter(record["row"]["channel"] for record in records)
    seeds = Counter(
        record["row"]["seed_work_key"] for record in records
        if record["row"]["seed_work_key"]
    )
    provenance = Counter(_dump(record["row"]["provenance"])
                         for record in records)
    return {
        "channels": sorted(channels),
        "channel_occurrence_counts": dict(sorted(channels.items())),
        "seed_work_keys": sorted(seeds),
        "seed_work_key_occurrence_counts": dict(sorted(seeds.items())),
        "seed_path_count": len(seeds),
        "retrieval_occurrences": len(records),
        "provenance_occurrence_counts": [
            {"provenance": json.loads(value), "occurrence_count": count}
            for value, count in sorted(provenance.items())
        ],
    }


def _representative(records: list[dict]) -> tuple[Paper, list[dict], dict]:
    base = min(records, key=lambda record: (
        SOURCE_RANK.get(record["paper"].source, 9), record["paper"].id.lower(),
        record["occurrence_id"],
    ))
    best = min(records, key=lambda record: (
        -len(record["paper"].abstract or ""),
        SOURCE_RANK.get(record["paper"].source, 9), record["occurrence_id"],
    ))
    paper = Paper.from_dict(base["row"]["paper"])
    if best["paper"].abstract:
        paper.abstract = best["paper"].abstract
        if best is not base:
            paper.abstract_source = (best["paper"].abstract_source
                                     or f"identity_merge:{best['paper'].id}")
    paper.referenced_works = sorted(set().union(
        *(set(record["paper"].referenced_works) for record in records)
    ))
    paper.cited_by_count = max(record["paper"].cited_by_count for record in records)
    if earliest := dates.earliest([record["paper"] for record in records]):
        paper.date, paper.date_precision, paper.date_source = earliest
    variants = {}
    for record in records:
        for payload in _paper_records(record["paper"]):
            variants.setdefault(_dump(payload), payload)
    manifestations = [variants[key] for key in sorted(variants)]
    base_payload = _dump(_paper_records(base["paper"])[0])
    paper.manifestations = [copy.deepcopy(payload) for payload in manifestations
                            if _dump(payload) != base_payload]
    return paper, manifestations, {
        "canonical_record_occurrence_id": base["occurrence_id"],
        "best_abstract_occurrence_id": best["occurrence_id"],
        "earliest_date": {"date": paper.date, "precision": paper.date_precision,
                          "source": paper.date_source},
    }


def resolve_occurrences(occurrences: Iterable[dict]) -> IdentityResolution:
    """Return resolved groups, unresolved occurrences, and audit/ambiguity rows."""
    staged = []
    for supplied in occurrences:
        if not isinstance(supplied, dict) or not supplied.get("channel") or "paper" not in supplied:
            raise ValueError("each occurrence requires paper and channel")
        row = copy.deepcopy(supplied)
        payload = row["paper"].to_dict() if isinstance(row["paper"], Paper) else row["paper"]
        payload = copy.deepcopy(payload)
        payload.setdefault("abstract", "")
        payload.setdefault("url", "")
        paper = Paper.from_dict(payload)
        row["paper"] = payload
        row.setdefault("seed_work_key", "")
        row.setdefault("rank", None)
        row.setdefault("provenance", {})
        serial = _dump(row)
        occurrence_id = str(row.get("occurrence_id") or
                            "occ:" + hashlib.sha256(serial.encode()).hexdigest()[:24])
        staged.append((occurrence_id, serial, row, paper))
    staged.sort(key=lambda item: (item[0], item[1]))
    if len({item[0] for item in staged}) != len(staged):
        raise ValueError("occurrence_id values must be unique")

    records, unresolved, audit = [], [], []
    for occurrence_id, _serial, row, paper in staged:
        row["occurrence_id"] = occurrence_id
        keys, malformed = _identity(paper)
        stub = str(paper.id or "").lower() in {"s2:", "s2:none", "s2:null", "s2:unknown"}
        if stub or not keys:
            reason = "unresolved_s2_stub" if stub else "no_valid_stable_identifier"
            unresolved.append({"occurrence_id": occurrence_id,
                               "state": "identity_unresolved", "reason": reason,
                               "malformed_identifiers": malformed, "occurrence": row})
            audit.append({"kind": "identity_unresolved", "reason": reason,
                          "occurrence_id": occurrence_id, "paper_id": paper.id})
            continue
        records.append({"occurrence_id": occurrence_id, "row": row, "paper": paper,
                        "keys": keys, "malformed": malformed,
                        "title": _title(paper.title)})
        if malformed:
            audit.append({"kind": "malformed_identifier_ignored",
                          "occurrence_id": occurrence_id,
                          "malformed_identifiers": malformed})

    uf, merges = _UF(len(records)), []
    identity_index, title_index = defaultdict(list), defaultdict(list)
    for index, record in enumerate(records):
        for key in record["keys"]:
            identity_index[key].append(index)
        if record["title"]:
            title_index[record["title"]].append(index)
    for key in sorted(identity_index):
        indices = sorted(identity_index[key])
        for left, right in zip(indices, indices[1:]):
            if uf.union(left, right):
                merges.append((left, right, "shared_strong_identifier:" + key))

    # Exact titles are an index/proposal only. They never bypass the conservative
    # matcher or merge components with incompatible DOI/arXiv evidence.
    for title in sorted(title_index):
        initial_roots = sorted({uf.find(index) for index in title_index[title]})
        for a, b in itertools.combinations(initial_roots, 2):
            left, right = uf.find(a), uf.find(b)
            if left == right:
                continue
            conflicts = _conflicts(uf, left, right, records)
            left_rows = [i for i in title_index[title] if uf.find(i) == left]
            right_rows = [i for i in title_index[title] if uf.find(i) == right]
            pair = next(((i, j) for i in left_rows for j in right_rows
                         if scoper._same_work(records[i]["paper"], records[j]["paper"])), None)
            distinctive = len(title) >= 24 and len(title.split()) >= 4
            if conflicts or pair is None or not distinctive:
                audit.append({
                    "kind": "ambiguous_title_match",
                    "reason": ("incompatible_strong_identifiers" if conflicts else
                               "conservative_matcher_rejected" if pair is None else
                               "title_not_distinctive_enough"),
                    "normalized_title": title, "conflicts": conflicts,
                    "left_occurrence_ids": sorted(records[i]["occurrence_id"]
                                                  for i in uf.members[left]),
                    "right_occurrence_ids": sorted(records[i]["occurrence_id"]
                                                   for i in uf.members[right]),
                })
                continue
            if uf.union(left, right):
                merges.append((pair[0], pair[1], "conservative_exact_title"))

    groups = []
    for root in sorted({uf.find(index) for index in range(len(records))}):
        indices = sorted(uf.members[root])
        members = [records[index] for index in indices]
        work_key = _canonical_key(members)
        paper, manifestations, provenance = _representative(members)
        titles = sorted({record["title"] for record in members})
        metadata_conflict = len(titles) > 1
        if metadata_conflict:
            audit.append({"kind": "metadata_conflict", "field": "title",
                          "work_key": work_key, "values": titles})
        member_indices = set(indices)
        groups.append({
            "work_key": work_key,
            "identity_status": ("resolved_with_metadata_conflict"
                                if metadata_conflict else "resolved"),
            "paper": paper.to_dict(), "manifestations": manifestations,
            "identity_keys": sorted(set().union(*(record["keys"] for record in members))),
            "match_bases": sorted({basis for left, right, basis in merges
                                   if left in member_indices and right in member_indices}),
            "occurrence_ids": [record["occurrence_id"] for record in members],
            "occurrence_count": len(members),
            "occurrences": [record["row"] for record in members],
            "channels": sorted({record["row"]["channel"] for record in members}),
            "seed_work_keys": sorted({record["row"]["seed_work_key"] for record in members
                                      if record["row"]["seed_work_key"]}),
            "field_provenance": provenance,
        })
    groups.sort(key=lambda group: (group["work_key"], group["occurrence_ids"]))
    unresolved.sort(key=lambda row: row["occurrence_id"])
    audit = [json.loads(key) for key in sorted({_dump(row) for row in audit})]

    expected = {item[0] for item in staged}
    resolved_ids = {oid for group in groups for oid in group["occurrence_ids"]}
    unresolved_ids = {row["occurrence_id"] for row in unresolved}
    if resolved_ids & unresolved_ids or resolved_ids | unresolved_ids != expected:
        raise AssertionError("every occurrence must be accounted for exactly once")
    return IdentityResolution(groups, unresolved, audit)
