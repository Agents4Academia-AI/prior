"""Work-level, two-sided disagreement audit for Scoper, Elicit and Undermind."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from common import normalise_arxiv, normalise_doi, title_key  # noqa: E402
from prior import scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import arxiv, openalex  # noqa: E402


def identity(row: dict) -> set[str]:
    out = set()
    doi = normalise_doi(row.get("doi"))
    aid = normalise_arxiv(row.get("arxiv"))
    title = title_key(row.get("title"))
    if doi:
        out.add("doi:" + doi)
        match = re.fullmatch(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", doi, re.I)
        if match:
            out.add("arxiv:" + match.group(1).lower())
    if aid:
        out.add("arxiv:" + aid)
    if title:
        out.add("title:" + title)
    return out


def load_scoper(path: Path) -> list[dict]:
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in path.read_text().splitlines() if line]
    data = json.loads(path.read_text())
    return data.get("kept") or data.get("papers") or data


def load_elicit(path: Path) -> list[dict]:
    by_identity = {}
    for line in path.read_text().splitlines():
        event = json.loads(line)
        if event.get("event") != "result":
            continue
        p, raw = event["paper"], event.get("raw") or {}
        row = {**p, "abstract": raw.get("abstract") or "", "rank": event["rank"],
               "authors": raw.get("authors") or [], "source": "elicit"}
        key = p["key"]
        by_identity.setdefault(key, row)
    return list(by_identity.values())


def load_undermind(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 6 or not parts[0].isdigit():
            continue
        rank, cite_key, relevance, title, doi, aid = parts
        rows.append({"rank": int(rank), "cite_key": cite_key,
                     "relevance": float(relevance), "title": title,
                     "doi": "" if doi == "unavailable" else doi,
                     "arxiv": "" if aid == "unavailable" else aid,
                     "source": "undermind"})
    return rows


def overlaps(row: dict, others: list[dict]) -> bool:
    aliases = identity(row)
    return any(aliases & identity(other) for other in others)


def to_paper(row: dict) -> Paper:
    aid = normalise_arxiv(row.get("arxiv"))
    doi = normalise_doi(row.get("doi"))
    return Paper(id=("arxiv:" + aid if aid else
                     row.get("source", "product") + ":" +
                     re.sub(r"\W+", "-", row.get("title", "").lower()).strip("-")),
                 source=row.get("source", "product"), title=row.get("title") or "",
                 abstract=row.get("abstract") or "", url="", year=row.get("year"),
                 authors=row.get("authors") or [], venue=row.get("venue") or None,
                 doi=doi or None)


def repair_undermind(rows: list[dict]) -> list[Paper]:
    aids = [normalise_arxiv(row.get("arxiv")) for row in rows]
    arxiv_records = arxiv.fetch_ids([aid for aid in aids if aid])
    papers = []
    for index, row in enumerate(rows, 1):
        aid, doi = normalise_arxiv(row.get("arxiv")), normalise_doi(row.get("doi"))
        paper = arxiv_records.get("arxiv:" + aid) if aid else None
        if not paper and doi:
            paper = openalex.fetch_doi(doi)
        base = to_paper(row)
        if paper and scoper._same_work(base, paper):
            paper.manifestations.append({"id": base.id, "source": "undermind",
                                         "doi": doi, "title": base.title})
            papers.append(paper)
        else:
            papers.append(base)
        if index % 25 == 0:
            print(f"resolved Undermind evidence {index}/{len(rows)}", flush=True)
    return papers


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def prepare(scoper_path: Path, elicit_path: Path, undermind_path: Path,
            out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    s, e, u = load_scoper(scoper_path), load_elicit(elicit_path), load_undermind(undermind_path)
    groups = {
        "elicit_only": [row for row in e if not overlaps(row, s)],
        "undermind_only": [row for row in u if not overlaps(row, s)],
        "scoper_not_elicit": [row for row in s if not overlaps(row, e)],
        "scoper_not_undermind": [row for row in s if not overlaps(row, u)],
    }
    for name, rows in groups.items():
        write_jsonl(out_dir / f"{name}-raw.jsonl", rows)
    write_jsonl(out_dir / "elicit_only-papers.jsonl",
                (to_paper(row).to_dict() for row in groups["elicit_only"]))
    repaired = repair_undermind(groups["undermind_only"])
    write_jsonl(out_dir / "undermind_only-papers.jsonl", (p.to_dict() for p in repaired))
    write_jsonl(out_dir / "scoper_not_elicit-papers.jsonl",
                (to_paper(row).to_dict() for row in groups["scoper_not_elicit"]))
    write_jsonl(out_dir / "scoper_not_undermind-papers.jsonl",
                (to_paper(row).to_dict() for row in groups["scoper_not_undermind"]))
    (out_dir / "overlap-status.json").write_text(json.dumps({
        "scoper": len(s), "elicit": len(e), "undermind_records": len(u),
        "counts": {name: len(rows) for name, rows in groups.items()},
        "identity": "DOI or arXiv identifier or normalized exact title",
    }, indent=2) + "\n")


def _load_env(path: Path | None) -> None:
    if not path or not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def screen(input_path: Path, topic: Path, out_dir: Path, model: str | None,
           cache: Path | None = None, env_file: Path | None = None) -> None:
    _load_env(env_file)
    papers = [Paper.from_dict(json.loads(line)) for line in input_path.read_text().splitlines()]
    out_dir.mkdir(parents=True, exist_ok=True)
    roles = scoper.scope_exhaustive(topic.read_text(), papers, model=model,
                                    cache_path=cache or out_dir / "scope-cache.jsonl")
    for role, items in roles.items():
        write_jsonl(out_dir / f"{role}.jsonl",
                    ({"paper": p.to_dict(), "decision": d} for p, d in items))
    (out_dir / "status.json").write_text(json.dumps({
        "input": str(input_path), "records": len(papers),
        "roles": {role: len(items) for role, items in roles.items()},
        "protocol": "scope-exhaustive/1.1",
    }, indent=2) + "\n")


def screen_historical(input_path: Path, topic: Path, out_dir: Path,
                      model: str | None, cache: Path | None = None,
                      env_file: Path | None = None, request_delay: float = 0.0) -> None:
    """Reproduce the binary historical Scoper screen used for the 255 corpus."""
    _load_env(env_file)
    papers = [Paper.from_dict(json.loads(line)) for line in input_path.read_text().splitlines()]
    out_dir.mkdir(parents=True, exist_ok=True)
    kept, dropped = scoper.scope(topic.read_text(), papers, model=model, batch=20,
                                 cache_path=cache or out_dir / "scope-cache.jsonl",
                                 use_prefilter=False, request_delay=request_delay)
    write_jsonl(out_dir / "eligible.jsonl",
                ({"paper": p.to_dict(), "decision": {"in_scope": True, "reason": r}}
                 for p, r in kept))
    write_jsonl(out_dir / "excluded.jsonl",
                ({"paper": p.to_dict(), "decision": {"in_scope": False, "reason": r}}
                 for p, r in dropped))
    (out_dir / "status.json").write_text(json.dumps({
        "input": str(input_path), "records": len(papers), "eligible": len(kept),
        "excluded": len(dropped), "protocol": "historical-scoper-binary-v1",
        "evidence_window": "title plus first 320 abstract characters",
        "batch": 20, "prefilter": False,
        "request_delay_seconds": request_delay,
    }, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--scoper", type=Path, required=True)
    p.add_argument("--elicit", type=Path, required=True); p.add_argument("--undermind", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    s = sub.add_parser("screen"); s.add_argument("--input", type=Path, required=True)
    s.add_argument("--topic", type=Path, required=True); s.add_argument("--out-dir", type=Path, required=True)
    s.add_argument("--model")
    s.add_argument("--cache", type=Path)
    s.add_argument("--env-file", type=Path)
    h = sub.add_parser("screen-historical")
    h.add_argument("--input", type=Path, required=True); h.add_argument("--topic", type=Path, required=True)
    h.add_argument("--out-dir", type=Path, required=True); h.add_argument("--model")
    h.add_argument("--cache", type=Path); h.add_argument("--env-file", type=Path)
    h.add_argument("--request-delay", type=float, default=0.0)
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    if args.command == "prepare": prepare(args.scoper, args.elicit, args.undermind, args.out_dir)
    elif args.command == "screen":
        screen(args.input, args.topic, args.out_dir, args.model,
               cache=args.cache, env_file=args.env_file)
    else:
        screen_historical(args.input, args.topic, args.out_dir, args.model,
                          cache=args.cache, env_file=args.env_file,
                          request_delay=args.request_delay)
