"""Freeze eligible external-only works and audit improved-Scoper recovery."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from common import normalise_arxiv, normalise_doi, title_key  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import arxiv, openalex  # noqa: E402

CUTOFF = date(2026, 6, 24)


def aliases(row: dict) -> set[str]:
    out = set()
    title = title_key(row.get("title"))
    doi = normalise_doi(row.get("doi"))
    aid = normalise_arxiv(row.get("arxiv"))
    if title: out.add("title:" + title)
    if doi:
        out.add("doi:" + doi)
        m = re.fullmatch(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", doi, re.I)
        if m: out.add("arxiv:" + m.group(1).lower())
    if aid: out.add("arxiv:" + aid)
    for value in row.get("work_aliases") or []:
        out.add(value.lower())
    return out


def read_screen(path: Path, product: str) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        item = json.loads(line); paper = item["paper"]
        rows.append({"paper": paper, "decision": item["decision"], "product": product})
    return rows


def richer_date(paper: dict) -> dict:
    if paper.get("date"):
        return paper
    p = Paper.from_dict(paper); candidate = None
    doi = normalise_doi(paper.get("doi"))
    aid = next((a.split(":", 1)[1] for a in aliases(paper) if a.startswith("arxiv:")), "")
    if doi: candidate = openalex.fetch_doi(doi)
    if not candidate and aid: candidate = arxiv.fetch_abs(aid)
    if candidate:
        for key in ("date", "date_precision", "date_source", "year", "doi"):
            if getattr(candidate, key, None): paper[key] = getattr(candidate, key)
    return paper


def freeze(elicit: Path, undermind: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    combined = read_screen(elicit, "elicit") + read_screen(undermind, "undermind")
    groups = []
    for item in combined:
        match = next((g for g in groups if aliases(g["paper"]) & aliases(item["paper"])), None)
        if match:
            match["products"].append(item["product"])
        else:
            groups.append({"paper": dict(item["paper"]), "decision": item["decision"],
                           "products": [item["product"]]})
    partitions = defaultdict(list)
    for index, item in enumerate(groups, 1):
        paper = item["paper"]
        if paper.get("year") == 2026 and not paper.get("date"):
            paper = richer_date(paper); item["paper"] = paper
        raw_date = paper.get("date") or ""
        if raw_date and re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
            bucket = "post_cutoff" if date.fromisoformat(raw_date) > CUTOFF else "hidden_pre_cutoff"
        elif paper.get("year") and paper["year"] < 2026:
            bucket = "hidden_pre_cutoff"
        elif paper.get("year") and paper["year"] > 2026:
            bucket = "post_cutoff"
        else:
            bucket = "cutoff_uncertain"
        item["target_id"] = "external:" + str(index).zfill(4)
        item["products"] = sorted(set(item["products"])); item["cutoff_bucket"] = bucket
        partitions[bucket].append(item)
    for bucket, rows in partitions.items():
        (out_dir / f"{bucket}.jsonl").write_text("".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    (out_dir / "status.json").write_text(json.dumps({
        "cutoff": CUTOFF.isoformat(), "eligible_product_records": len(combined),
        "canonical_eligible_works": len(groups),
        "partitions": {key: len(rows) for key, rows in partitions.items()},
        "hidden_target_policy": "eligible, external-only, publication date on/before cutoff",
    }, indent=2) + "\n")


def iter_candidates(path: Path):
    for line in path.read_text().splitlines():
        row = json.loads(line)
        paper = row.get("paper", row)
        yield paper, row


def recovery(targets: Path, channels: list[str], out: Path) -> None:
    target_rows = [json.loads(line) for line in targets.read_text().splitlines() if line]
    channel_indexes = []
    for spec in channels:
        name, raw_path = spec.split("=", 1); path = Path(raw_path)
        index = {}
        for paper, raw in iter_candidates(path):
            for alias in aliases(paper):
                index.setdefault(alias, (paper, raw))
        channel_indexes.append((name, index))
    results = []
    for target in target_rows:
        hits = []
        target_aliases = aliases(target["paper"])
        for name, index in channel_indexes:
            match = next((index[a] for a in target_aliases if a in index), None)
            if match:
                paper, raw = match
                hits.append({"channel": name, "candidate": paper,
                             "branch": raw.get("branch_id") or raw.get("direction") or ""})
        results.append({**target, "recovered": bool(hits), "hits": hits})
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results))
    status = {"targets": len(results), "recovered": sum(r["recovered"] for r in results),
              "channels": [name for name, _ in channel_indexes]}
    out.with_suffix(".status.json").write_text(json.dumps(status, indent=2) + "\n")


def parser():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze"); f.add_argument("--elicit", type=Path, required=True)
    f.add_argument("--undermind", type=Path, required=True); f.add_argument("--out-dir", type=Path, required=True)
    r = sub.add_parser("recovery"); r.add_argument("--targets", type=Path, required=True)
    r.add_argument("--channel", action="append", required=True); r.add_argument("--out", type=Path, required=True)
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    if args.command == "freeze": freeze(args.elicit, args.undermind, args.out_dir)
    else: recovery(args.targets, args.channel, args.out)
