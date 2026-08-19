"""Fresh, traced Elicit baseline for the focused workshop Scoper evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from common import load_gold, match_gold, normalise_arxiv, normalise_doi, title_key

import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import arxiv, openalex  # noqa: E402

ENDPOINT = "https://elicit.com/api/v1/search"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_key(env_file: Path | None = None) -> str:
    key = os.environ.get("ELICIT_API_KEY", "").strip()
    if not key and env_file and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ELICIT_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"\'')
                break
    if not key:
        raise SystemExit("ELICIT_API_KEY is unavailable")
    return key


def _arxiv(urls: list[str]) -> str:
    for url in urls:
        match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", url or "")
        if match:
            return match.group(1)
    return ""


def normalize(paper: dict) -> dict:
    urls = paper.get("urls") or []
    title = paper.get("title") or ""
    doi = normalise_doi(paper.get("doi"))
    arxiv = normalise_arxiv(_arxiv(urls))
    key = f"doi:{doi}" if doi else (f"arxiv:{arxiv}" if arxiv else
                                      "title:" + title_key(title))
    return {
        "key": key, "title": title, "doi": doi, "arxiv": arxiv,
        "year": paper.get("year"), "cited_by": paper.get("citedByCount"),
        "venue": paper.get("venue") or "", "elicit_id": paper.get("elicitId") or "",
        "urls": urls,
    }


def run(queries_file: Path, out: Path, *, env_file: Path | None,
        max_results: int, arm: str, whole_file_query: bool = False) -> None:
    raw_query_text = queries_file.read_text().strip()
    queries = ([raw_query_text] if whole_file_query else
               [line.strip() for line in raw_query_text.splitlines() if line.strip()])
    if arm == "plain":
        queries = queries[:1]
    key = load_key(env_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    with out.open("x") as handle:
        handle.write(json.dumps({
            "event": "manifest", "schema": "prior.elicit-workshop/1.0",
            "created_at": utc_now(), "arm": arm, "endpoint": ENDPOINT,
            "queries_file": str(queries_file),
            "queries_sha256": hashlib.sha256(queries_file.read_bytes()).hexdigest(),
            "queries": queries, "max_results_per_query": max_results,
            "whole_file_query": whole_file_query,
            "auth": "bearer credential present; value never recorded",
        }) + "\n")
        for query_index, query in enumerate(queries, 1):
            body = {"query": query, "maxResults": max_results}
            request_id = f"{arm}:q{query_index:03d}"
            handle.write(json.dumps({"event": "request", "request_id": request_id,
                                     "recorded_at": utc_now(), "body": body}) + "\n")
            handle.flush()
            response = requests.post(
                ENDPOINT, json=body, timeout=180,
                headers={"Authorization": "Bearer " + key,
                         "Content-Type": "application/json", "Accept": "application/json",
                         "User-Agent": "Prior-Scoper-workshop-evaluation/1.0"},
            )
            try:
                response.raise_for_status()
            except requests.HTTPError as error:
                # Never record the request object: it contains the Authorization header.
                handle.write(json.dumps({"event": "terminal", "request_id": request_id,
                                         "status": "failed", "http_status": response.status_code,
                                         "message": str(error).split(" for url:", 1)[0]}) + "\n")
                handle.flush()
                continue
            payload = response.json()
            raw_papers = payload.get("papers", payload) if isinstance(payload, dict) else payload
            for rank, raw in enumerate(raw_papers or [], 1):
                paper = normalize(raw)
                handle.write(json.dumps({
                    "event": "result", "request_id": request_id,
                    "query_index": query_index, "query": query, "rank": rank,
                    "first_observed": paper["key"] not in seen,
                    "paper": paper, "raw": raw,
                }, ensure_ascii=False) + "\n")
                seen.add(paper["key"])
            handle.write(json.dumps({"event": "terminal", "request_id": request_id,
                                     "status": "complete", "returned": len(raw_papers or []),
                                     "unique_cumulative": len(seen)}) + "\n")
            handle.flush()


def score(run_file: Path, gold_file: Path, out: Path) -> dict:
    events = [json.loads(line) for line in run_file.read_text().splitlines() if line]
    manifest = next(row for row in events if row.get("event") == "manifest")
    results = [row for row in events if row.get("event") == "result"]
    by_key = {}
    for row in results:
        by_key.setdefault(row["paper"]["key"], row)
    gold = load_gold(gold_file)
    target_rows = []
    for target in gold:
        hits = [(row, match_gold(target, row["paper"])) for row in results]
        row, similarity = max(hits, key=lambda item: item[1], default=(None, 0.0))
        target_rows.append({
            "gold_id": target.gold_id, "title": target.title, "found": similarity > 0,
            "match_score": similarity, "query_index": row.get("query_index") if row else None,
            "rank": row.get("rank") if row else None,
            "matched_title": row["paper"]["title"] if row else "",
        })
    recall_at = {}
    for cutoff in (10, 20, 50, 100, 300, 500):
        found = sum(any(match_gold(target, row["paper"]) and row["rank"] <= cutoff
                        for row in results) for target in gold)
        recall_at[str(cutoff)] = {"found": found, "recall": found / max(1, len(gold))}
    report = {
        "arm": manifest["arm"], "run_created_at": manifest["created_at"],
        "gold_n": len(gold), "result_records": len(results),
        "unique_candidates": len(by_key),
        "recovered": sum(row["found"] for row in target_rows),
        "recall": sum(row["found"] for row in target_rows) / max(1, len(gold)),
        "recall_at_per_query_rank": recall_at,
        "source_terminals": [row for row in events if row.get("event") == "terminal"],
        "targets": target_rows,
        "limitations": [
            "The 152-work target set is retrospective and Prior-derived, not independent gold.",
            "Elicit exposes ranked retrieval results but not its complete index/search trace.",
            "Retrieval recall does not establish relevance precision; screening is separate.",
        ],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _load_elicit_results(run_files: list[Path]) -> dict[str, dict]:
    """Union fresh Elicit arms, retaining every observed query/rank."""
    works: dict[str, dict] = {}
    for path in run_files:
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row.get("event") != "result":
                continue
            paper = row["paper"]
            record = works.setdefault(paper["key"], {
                "paper": paper, "observations": [], "raw": row.get("raw") or {},
            })
            record["observations"].append({
                "run": str(path), "request_id": row["request_id"],
                "query": row["query"], "rank": row["rank"],
            })
    return works


def _load_scoper_reference(path: Path) -> list[dict]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict):
        return payload.get("kept") or payload.get("papers") or []
    return payload


def _same_identity(elicit: dict, scoper_row: dict) -> bool:
    if elicit.get("doi") and normalise_doi(scoper_row.get("doi")) == elicit["doi"]:
        return True
    if elicit.get("arxiv") and normalise_arxiv(scoper_row.get("arxiv")) == elicit["arxiv"]:
        return True
    return bool(title_key(elicit.get("title")) and
                title_key(elicit.get("title")) == title_key(scoper_row.get("title")))


def _fallback_paper(record: dict) -> Paper:
    p = record["paper"]
    raw = record.get("raw") or {}
    return Paper(
        id="elicit:" + (p.get("elicit_id") or hashlib.sha1(
            p["key"].encode()).hexdigest()[:16]), source="elicit",
        title=p.get("title") or "", abstract=raw.get("abstract") or "",
        url=(p.get("urls") or [""])[0], year=p.get("year"),
        venue=p.get("venue") or None, doi=p.get("doi") or None,
        cited_by_count=p.get("cited_by") or 0,
    )


def resolve_external(run_files: list[Path], scoper_reference: Path,
                     out: Path, progress=print) -> None:
    """Resolve the work-level Elicit-only union to evidence-bearing records.

    Exact DOI and arXiv identifiers are preferred. Title search is only accepted
    when Prior's conservative same-work check agrees; unresolved records remain
    in the queue and will therefore screen as uncertain rather than excluded.
    """
    works = _load_elicit_results(run_files)
    reference = _load_scoper_reference(scoper_reference)
    external = [record for record in works.values()
                if not any(_same_identity(record["paper"], row) for row in reference)]
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"refusing to overwrite immutable ledger: {out}")
    with out.open("x") as handle:
        handle.write(json.dumps({
            "event": "manifest", "schema": "prior.elicit-resolution/1.0",
            "created_at": utc_now(), "run_files": [str(p) for p in run_files],
            "scoper_reference": str(scoper_reference), "elicit_union": len(works),
            "external_only": len(external),
            "policy": "exact DOI; exact arXiv; conservative OpenAlex title match; preserve unresolved",
        }) + "\n")
        for index, record in enumerate(external, 1):
            base = _fallback_paper(record)
            resolved = None
            channel = "unresolved"
            if record["paper"].get("doi"):
                resolved = openalex.fetch_doi(record["paper"]["doi"])
                channel = "openalex_doi" if resolved else channel
            if not resolved and record["paper"].get("arxiv"):
                resolved = arxiv.fetch_abs(record["paper"]["arxiv"])
                channel = "arxiv_id" if resolved else channel
            if not resolved and base.title:
                candidates = openalex.search(base.title, max_papers=5,
                                             require_abstract=False,
                                             exclude_reviews=False)
                resolved = next((candidate for candidate in candidates
                                 if scoper._same_work(base, candidate)), None)
                channel = "openalex_title" if resolved else channel
            paper = resolved or base
            handle.write(json.dumps({
                "event": "resolved_work", "elicit_key": record["paper"]["key"],
                "resolution_channel": channel, "paper": paper.to_dict(),
                "observations": record["observations"],
            }, ensure_ascii=False) + "\n")
            handle.flush()
            if index % 25 == 0:
                progress(f"resolved {index}/{len(external)} Elicit-only works")


def screen_external(resolution_file: Path, topic_file: Path, out_dir: Path,
                    *, model: str | None = None, progress=print) -> None:
    rows = [json.loads(line) for line in resolution_file.read_text().splitlines()
            if line]
    papers = [Paper.from_dict(row["paper"]) for row in rows
              if row.get("event") == "resolved_work"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = out_dir / "scope-cache.jsonl"
    roles = scoper.scope_exhaustive(
        topic_file.read_text(), papers, model=model, cache_path=cache,
        progress=progress)
    for role, items in roles.items():
        path = out_dir / f"{role}.jsonl"
        path.write_text("".join(json.dumps({
            "paper": paper.to_dict(), "decision": decision,
        }, ensure_ascii=False) + "\n" for paper, decision in items))
    (out_dir / "status.json").write_text(json.dumps({
        "stage": "elicit_external_screened", "created_at": utc_now(),
        "scope_file": str(topic_file), "scope_sha256": hashlib.sha256(
            topic_file.read_bytes()).hexdigest(), "screening_protocol": "scope-exhaustive/1.1",
        "records": len(papers),
        "roles": {role: len(items) for role, items in roles.items()},
        "missing_abstract": sum(not paper.abstract for paper in papers),
    }, indent=2) + "\n")


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    run_ap = sub.add_parser("run")
    run_ap.add_argument("--queries", required=True, type=Path)
    run_ap.add_argument("--out", required=True, type=Path)
    run_ap.add_argument("--env-file", type=Path)
    run_ap.add_argument("--arm", choices=("plain", "multiquery"), required=True)
    run_ap.add_argument("--max-results", type=int, default=100)
    run_ap.add_argument("--whole-file-query", action="store_true",
                        help="Send the complete file as one natural-language query")
    score_ap = sub.add_parser("score")
    score_ap.add_argument("--run", required=True, type=Path)
    score_ap.add_argument("--gold", required=True, type=Path)
    score_ap.add_argument("--out", required=True, type=Path)
    resolve_ap = sub.add_parser("resolve-external")
    resolve_ap.add_argument("--run", action="append", required=True, type=Path)
    resolve_ap.add_argument("--scoper-reference", required=True, type=Path)
    resolve_ap.add_argument("--out", required=True, type=Path)
    screen_ap = sub.add_parser("screen-external")
    screen_ap.add_argument("--resolution", required=True, type=Path)
    screen_ap.add_argument("--topic", required=True, type=Path)
    screen_ap.add_argument("--out-dir", required=True, type=Path)
    screen_ap.add_argument("--model")
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    if args.command == "run":
        run(args.queries, args.out, env_file=args.env_file,
            max_results=args.max_results, arm=args.arm,
            whole_file_query=args.whole_file_query)
    elif args.command == "score":
        print(json.dumps(score(args.run, args.gold, args.out), indent=2))
    elif args.command == "resolve-external":
        resolve_external(args.run, args.scoper_reference, args.out)
    else:
        screen_external(args.resolution, args.topic, args.out_dir, model=args.model)
