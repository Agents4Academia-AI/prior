"""Freeze receipts and audit a corrected-policy run after search completion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

from historical_run_audit import aliases, match, paper, rows, unique, write_jsonl


PASSES = ("01-main", "02-high-yield", "03-s2-only", "04-supplied-anchors")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def publication_bucket(row: dict, last_search: date) -> str:
    value = paper(row)
    for field in ("publication_date", "published", "date"):
        raw = str(value.get(field) or "")[:10]
        try:
            return "post_previous_search" if date.fromisoformat(raw) > last_search else "older"
        except ValueError:
            pass
    year = value.get("year")
    if isinstance(year, int) and year > last_search.year:
        return "post_previous_search"
    if year == last_search.year:
        return "same_year_date_unresolved"
    return "older_or_date_unresolved"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--historical", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--last-search-date", default="2026-06-24")
    args = ap.parse_args()
    if not (args.run_dir / "summary.json").exists():
        raise SystemExit("refusing post-run audit: final summary/snapshot is not frozen")
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise SystemExit("audit output directory must be new and empty")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    final = unique(rows(args.run_dir / "snapshot/eligible.jsonl"))
    excluded = unique(rows(args.run_dir / "strict-screen/excluded.jsonl"))
    historical = unique(rows(args.historical))
    last_search = date.fromisoformat(args.last_search_date)

    target_audit = []
    recovered = set()
    for index, target in enumerate(historical):
        found, score, basis = match(target, final)
        status, matched = "retrieval_or_screen_miss", None
        if found is not None:
            status, matched = "recovered_strict", final[found]
            recovered.add(index)
        else:
            found, score, basis = match(target, excluded)
            if found is not None:
                status, matched = "strict_screen_exclusion", excluded[found]
        target_audit.append({
            "historical_id": paper(target).get("id"),
            "historical_title": paper(target).get("title"),
            "status": status,
            "match_basis": basis,
            "match_score": score,
            "matched_id": paper(matched).get("id") if matched else None,
            "screen_reason": matched.get("decision", {}).get("reason") if matched else None,
        })

    additions = []
    buckets = Counter()
    for row in final:
        found, _score, _basis = match(row, historical)
        if found is None:
            bucket = publication_bucket(row, last_search)
            buckets[bucket] += 1
            additions.append({"paper": paper(row), "decision": row.get("decision", {}),
                              "publication_bucket": bucket})

    yield_rows = []
    source_totals = Counter()
    trace_totals = Counter()
    for stage in PASSES:
        status_path = args.run_dir / stage / "status.json"
        if not status_path.exists():
            continue
        status = json.loads(status_path.read_text())
        provenance = rows(args.run_dir / stage / "candidate-provenance.jsonl")
        sources = Counter()
        for record in provenance:
            discoveries = record.get("discoveries", [])
            trace_totals["discoveries"] += len(discoveries)
            for discovery in discoveries:
                source = discovery.get("source") or "unknown"
                sources[source] += 1
                source_totals[source] += 1
                for field in ("source", "direction", "seed_id", "source_rank"):
                    if discovery.get(field) in (None, ""):
                        trace_totals[f"missing_{field}"] += 1
        yield_rows.append({
            "pass": stage,
            "candidate_works": status.get("records", 0),
            "openalex_candidates": status.get("source_candidates", {}).get("openalex", 0),
            "semanticscholar_candidates": status.get("source_candidates", {}).get("semanticscholar", 0),
            "marginal_unique_eligible": status.get("marginal_unique_eligible", 0),
            "corpus_after": status.get("corpus_after", 0),
            "repeated_frontier": status.get("repeated_frontier", False),
        })

    checksums = []
    for path in sorted(args.run_dir.rglob("*")):
        if path.is_file():
            checksums.append({"path": str(path.relative_to(args.run_dir)),
                              "bytes": path.stat().st_size, "sha256": digest(path)})
    write_jsonl(args.out_dir / "checksums.jsonl", checksums)
    write_jsonl(args.out_dir / "historical-152-audit.jsonl", target_audit)
    write_jsonl(args.out_dir / "new-strict-eligible.jsonl", additions)
    write_jsonl(args.out_dir / "misses-and-disagreements.jsonl",
                [row for row in target_audit if row["status"] != "recovered_strict"])
    with (args.out_dir / "pass-source-yield.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(yield_rows[0]))
        writer.writeheader(); writer.writerows(yield_rows)
    with (args.out_dir / "sankey.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("source", "target", "value"))
        writer.writeheader()
        for row in yield_rows:
            writer.writerow({"source": "OpenAlex", "target": row["pass"],
                             "value": row["openalex_candidates"]})
            writer.writerow({"source": "Semantic Scholar", "target": row["pass"],
                             "value": row["semanticscholar_candidates"]})
            writer.writerow({"source": row["pass"], "target": "broad eligible additions",
                             "value": row["marginal_unique_eligible"]})

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "evaluation": "offline after immutable corrected-policy snapshot",
        "run_summary_sha256": digest(args.run_dir / "summary.json"),
        "historical_target_sha256": digest(args.historical),
        "historical_targets": len(historical),
        "historical_recovered_strict": len(recovered),
        "historical_recall": len(recovered) / max(1, len(historical)),
        "final_strict_works": len(final),
        "strict_additions_vs_historical": len(additions),
        "addition_date_buckets": dict(buckets),
        "pass_yield": yield_rows,
        "trace_audit": dict(trace_totals),
        "caveats": [
            "The historical 152 are a retrospective Prior corpus, not an independent gold standard.",
            "Search-channel yields are field- and index-dependent and may not generalise.",
            "Publication year 2026 alone cannot distinguish pre- from post-search publication; unresolved cases require metadata review.",
            "New strict-eligible works are model-screened candidates pending human validation.",
        ],
    }
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    readme = ["# Corrected historical-policy audit", "",
              "Generated only after the search snapshot was frozen.", "",
              f"- Final strict corpus: **{len(final)}** works",
              f"- Historical 152 recovered: **{len(recovered)}/{len(historical)}**",
              f"- Strict additions: **{len(additions)}**", "", "## Pass yield", "",
              "| Pass | Candidates | OA | S2 | Marginal eligible | Repeated frontier |",
              "|---|---:|---:|---:|---:|:---:|"]
    readme += [f"| {r['pass']} | {r['candidate_works']} | {r['openalex_candidates']} | "
               f"{r['semanticscholar_candidates']} | {r['marginal_unique_eligible']} | "
               f"{r['repeated_frontier']} |" for r in yield_rows]
    readme += ["", "See `report.json` for caveats and `checksums.jsonl` for the immutable receipt."]
    (args.out_dir / "README.md").write_text("\n".join(readme) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
