"""Build the deduplicated screening queue for bounded CPU round two."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from freeze_external_targets import aliases


CUTOFF = date(2026, 6, 24)


def rows(path: Path):
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def eligible_date(paper: dict) -> bool:
    raw = paper.get("date") or ""
    if len(raw) == 10:
        return date.fromisoformat(raw) <= CUTOFF
    year = paper.get("year")
    return bool(year and year < 2026)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--search", type=Path, required=True)
    ap.add_argument("--citation-dir", type=Path, required=True)
    ap.add_argument("--existing", type=Path, action="append", default=[])
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)

    known = set()
    for path in args.existing:
        for row in rows(path):
            paper = row.get("paper") if row.get("event") == "result" else row.get("paper", row)
            if paper:
                known |= aliases(paper)

    groups = []
    def add(paper: dict, channel: str, trace: dict) -> None:
        paper_aliases = aliases(paper)
        group = next((item for item in groups if item["aliases"] & paper_aliases), None)
        if group is None:
            group = {"paper": paper, "aliases": set(paper_aliases), "traces": []}
            groups.append(group)
        else:
            group["aliases"] |= paper_aliases
            if len(paper.get("abstract") or "") > len(group["paper"].get("abstract") or ""):
                group["paper"] = paper
        group["traces"].append({"channel": channel, **trace})

    for row in rows(args.search):
        add(row["paper"], "adaptive_query", {"hits": row.get("hits", [])})
    back_seeds = {}
    for row in rows(args.citation_dir / "citation-backward-edges.jsonl"):
        if row.get("resolved"):
            back_seeds.setdefault(row["cited_id"], set()).add(row["seed_work_key"])
    for row in rows(args.citation_dir / "citation-backward-candidates.jsonl"):
        paper = row["paper"]
        add(paper, "citation_backward", {"seed_work_keys": sorted(back_seeds.get(paper.get("id"), ()))})
    for row in rows(args.citation_dir / "citation-forward-ledger.jsonl"):
        if row.get("event") == "result":
            add(row["paper"], "citation_forward", {"seed_work_keys": [row["seed_work_key"]],
                                                    "page_rank": row.get("page_rank")})

    queue, rediscovered, post_cutoff = [], [], []
    for group in groups:
        group["aliases"] = sorted(group["aliases"])
        group["channels"] = sorted({trace["channel"] for trace in group["traces"]})
        if set(group["aliases"]) & known:
            rediscovered.append(group)
        elif eligible_date(group["paper"]):
            queue.append(group)
        else:
            post_cutoff.append(group)
    queue.sort(key=lambda row: (min((hit.get("rank", 10**9) for trace in row["traces"]
                                    for hit in trace.get("hits", [])), default=10**9),
                                row["paper"].get("title", "")))
    for name, items in (("screening-queue-traced", queue),
                        ("rediscovered", rediscovered), ("post-cutoff-or-uncertain", post_cutoff)):
        (args.out_dir / f"{name}.jsonl").write_text("".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in items))
    (args.out_dir / "screening-papers.jsonl").write_text("".join(
        json.dumps(row["paper"], ensure_ascii=False) + "\n" for row in queue))
    status = {"cutoff": CUTOFF.isoformat(), "hidden_targets_loaded": False,
              "canonical_works_across_round_channels": len(groups),
              "screening_queue": len(queue), "rediscovered_prior_search": len(rediscovered),
              "post_cutoff_or_date_uncertain": len(post_cutoff),
              "query_and_citation_overlap": sum(len(row["channels"]) > 1 for row in groups)}
    (args.out_dir / "queue-status.json").write_text(json.dumps(status, indent=2) + "\n")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
