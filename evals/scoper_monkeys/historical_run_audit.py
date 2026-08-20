"""Audit a completed historical anchored Scoper run against the frozen 152 core.

This is an offline evaluation: the frozen target set is loaded only after the
search snapshot exists.  It resolves manifestations at work level, attributes
the first broad-eligible stage, and separates retrieval misses from screening
exclusions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from common import normalise_arxiv, normalise_doi, title_key, title_similarity
from coverage_subareas import classify


STAGES = (
    ("construction", "00-construction/snapshot/eligible.jsonl"),
    ("adaptive_query_1", "query-01/snapshot/eligible.jsonl"),
    ("adaptive_query_2", "query-02/snapshot/eligible.jsonl"),
    ("citation_1", "citation-01/snapshot/eligible.jsonl"),
    ("citation_2", "citation-02/snapshot/eligible.jsonl"),
    ("citation_3", "citation-03/snapshot/eligible.jsonl"),
)

SCREEN_FILES = (
    ("initial_screen", "00-construction/initial-screen/eligible.jsonl", True),
    ("initial_screen", "00-construction/initial-screen/excluded.jsonl", False),
    ("anchor_screen", "00-construction/anchor-screen/eligible.jsonl", True),
    ("anchor_screen", "00-construction/anchor-screen/excluded.jsonl", False),
    ("adaptive_query_1", "query-01/query-screen/eligible.jsonl", True),
    ("adaptive_query_1", "query-01/query-screen/excluded.jsonl", False),
    ("adaptive_query_2", "query-02/query-screen/eligible.jsonl", True),
    ("adaptive_query_2", "query-02/query-screen/excluded.jsonl", False),
    ("citation_1", "citation-01/citation-screen/eligible.jsonl", True),
    ("citation_1", "citation-01/citation-screen/excluded.jsonl", False),
)


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def paper(row: dict) -> dict:
    return row.get("paper", row)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def aliases(value: dict) -> set[str]:
    value = paper(value)
    out: set[str] = set()
    pid = str(value.get("id") or "").lower().strip()
    if pid:
        out.add("id:" + re.sub(r"v\d+$", "", pid))
    doi = normalise_doi(value.get("doi"))
    if doi:
        out.add("doi:" + doi)
        match = re.fullmatch(r"10\.48550/arxiv\.(\d{4}\.\d{4,5})", doi, re.I)
        if match:
            out.add("arxiv:" + match.group(1).lower())
    aid = normalise_arxiv(value.get("arxiv"))
    if not aid and pid.startswith("arxiv:"):
        aid = normalise_arxiv(pid.split(":", 1)[1])
    if aid:
        out.add("arxiv:" + aid)
    work_id = str(value.get("work_id") or "").lower().strip()
    if work_id:
        out.add(work_id)
    for alias in value.get("work_aliases") or []:
        alias = str(alias).lower().strip()
        if alias.startswith("arxiv:"):
            alias = "arxiv:" + normalise_arxiv(alias)
        elif alias.startswith("doi:"):
            alias = "doi:" + normalise_doi(alias[4:])
        if alias:
            out.add(alias)
    for manifestation in value.get("manifestations") or []:
        out.update(aliases(manifestation))
    title = title_key(value.get("title"))
    if title:
        out.add("title:" + title)
    return out


def match(target: dict, candidates: list[dict]) -> tuple[int | None, float, str]:
    target_aliases = aliases(target)
    for index, candidate in enumerate(candidates):
        overlap = target_aliases & aliases(candidate)
        strong = {item for item in overlap if not item.startswith("title:")}
        if strong:
            return index, 1.0, "strong_identifier"
    target_title = paper(target).get("title") or ""
    exact = "title:" + title_key(target_title)
    for index, candidate in enumerate(candidates):
        if exact in aliases(candidate):
            return index, 1.0, "exact_title"
    best_index, best_score = None, 0.0
    for index, candidate in enumerate(candidates):
        score = title_similarity(target_title, paper(candidate).get("title"))
        if score >= 0.82 and score > best_score:
            best_index, best_score = index, score
    return best_index, best_score, "title_jaccard" if best_index is not None else ""


def unique(rows_: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows_:
        row_aliases = aliases(row)
        if not row_aliases & seen:
            out.append(row)
            seen.update(row_aliases)
    return out


def exact_alias_union(rows_: list[dict]) -> set[str]:
    return {alias for row in rows_ for alias in aliases(row)}


def write_jsonl(path: Path, values: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in values))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument("--membership", type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    gold = rows(args.gold)
    membership = rows(args.membership) if args.membership else []
    membership_by_title = {
        title_key(paper(row).get("title")): row for row in membership
    }
    final = unique(rows(args.run_dir / "strict-screen/eligible.jsonl"))
    strict_excluded = unique(rows(args.run_dir / "strict-screen/excluded.jsonl"))

    cumulative: list[dict] = []
    cumulative_aliases: set[str] = set()
    final_aliases = exact_alias_union(final)
    final_seen_aliases: set[str] = set()
    stage_table = []
    stage_first: dict[str, str] = {}
    previous_n = 0
    for stage, relative in STAGES:
        snapshot = unique(rows(args.run_dir / relative))
        added = [row for row in snapshot if not (aliases(row) & cumulative_aliases)]
        cumulative = unique(cumulative + added)
        cumulative_aliases.update(exact_alias_union(added))
        surviving = [row for row in added if aliases(row) & final_aliases]
        surviving_new = [row for row in surviving if not (aliases(row) & final_seen_aliases)]
        final_seen_aliases.update(exact_alias_union(surviving_new))
        for row in added:
            stage_first.setdefault(title_key(paper(row).get("title")), stage)
        stage_table.append({
            "stage": stage,
            "snapshot_unique_broad": len(snapshot),
            "marginal_broad": len(added),
            "marginal_strict_survivors": len(surviving_new),
            "broad_growth_rate": len(added) / max(1, previous_n),
        })
        previous_n = len(snapshot)

    screen_events = []
    for channel, relative, kept in SCREEN_FILES:
        for row in rows(args.run_dir / relative):
            screen_events.append({"channel": channel, "kept": kept, "row": row})

    target_audit = []
    recovered_gold_indexes = set()
    for target_index, target in enumerate(gold):
        final_index, score, basis = match(target, final)
        status, channel, reason, matched = "recovered_final", "", "", None
        if final_index is not None:
            recovered_gold_indexes.add(target_index)
            matched = final[final_index]
            channel = stage_first.get(title_key(paper(matched).get("title")), "")
        else:
            excluded_index, score, basis = match(target, strict_excluded)
            if excluded_index is not None:
                status = "strict_screen_exclusion"
                matched = strict_excluded[excluded_index]
                reason = matched.get("decision", {}).get("reason", "")
                channel = stage_first.get(title_key(paper(matched).get("title")), "")
            else:
                broad_exclusion = None
                for event in screen_events:
                    event_index, event_score, event_basis = match(target, [event["row"]])
                    if event_index is not None:
                        broad_exclusion = (event, event_score, event_basis)
                        if event["kept"]:
                            continue
                        break
                if broad_exclusion is not None:
                    event, score, basis = broad_exclusion
                    matched = event["row"]
                    channel = event["channel"]
                    reason = matched.get("decision", {}).get("reason", "")
                    status = "broad_screen_exclusion" if not event["kept"] else "identity_or_pipeline_loss"
                else:
                    status = "retrieval_miss"
        target_audit.append({
            "gold_id": paper(target).get("id", ""),
            "gold_title": paper(target).get("title", ""),
            "status": status,
            "first_recovery_channel": channel,
            "match_basis": basis,
            "match_score": score,
            "matched_id": paper(matched).get("id", "") if matched else "",
            "matched_title": paper(matched).get("title", "") if matched else "",
            "screen_reason": reason,
            "is_reconstructed_anchor": bool(
                membership_by_title.get(title_key(paper(target).get("title")), {}).get(
                    "is_reconstructed_anchor", False
                )
            ),
            "subarea": classify(
                paper(membership_by_title.get(title_key(paper(target).get("title")), target))
            )[0],
        })

    new_final = []
    for row in final:
        gold_index, score, basis = match(row, gold)
        if gold_index is None:
            new_final.append({
                "paper": paper(row),
                "decision": row.get("decision", {}),
                "first_recovery_channel": stage_first.get(title_key(paper(row).get("title")), ""),
            })

    counts = {}
    for row in target_audit:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    recovered = counts.get("recovered_final", 0)
    anchors = [row for row in target_audit if row["is_reconstructed_anchor"]]
    nonanchors = [row for row in target_audit if not row["is_reconstructed_anchor"]]
    recovery_channels: dict[str, int] = {}
    miss_subareas: dict[str, int] = {}
    for row in target_audit:
        if row["status"] == "recovered_final":
            channel = row["first_recovery_channel"]
            recovery_channels[channel] = recovery_channels.get(channel, 0) + 1
        else:
            area = row["subarea"]
            miss_subareas[area] = miss_subareas.get(area, 0) + 1
    report = {
        "method": {
            "evaluation": "offline after frozen run",
            "identity": "stable identifiers/aliases, exact normalized title, then title-token Jaccard >= 0.82",
            "gold_sha256": sha256(args.gold),
            "run_summary_sha256": sha256(args.run_dir / "summary.json"),
        },
        "historical_core": {
            "targets": len(gold),
            "recovered_final": recovered,
            "recall": recovered / max(1, len(gold)),
            "misses": len(gold) - recovered,
            "miss_categories": counts,
            "recovery_by_first_channel": recovery_channels,
            "reconstructed_anchors": {
                "targets": len(anchors),
                "recovered_final": sum(row["status"] == "recovered_final" for row in anchors),
            },
            "non_anchor_recovery_targets": {
                "targets": len(nonanchors),
                "recovered_broad": sum(row["status"] != "retrieval_miss" for row in nonanchors),
                "recovered_final": sum(row["status"] == "recovered_final" for row in nonanchors),
            },
            "unrecovered_or_excluded_by_subarea": miss_subareas,
        },
        "final_strict": {
            "works": len(final),
            "historical_core_works": recovered,
            "genuinely_new_vs_historical_core": len(new_final),
        },
        "stage_yield": stage_table,
        "caveats": [
            "The 152-work corpus is retrospective and Prior-derived, not an independent gold standard.",
            "Screening failures are model decisions from title plus the first 320 abstract characters.",
            "Citation hops 2 and 3 repeated the same candidate pool; their marginal yield is therefore zero.",
            "Fuzzy title matches require manual review if used in headline recovery counts.",
        ],
    }
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    write_jsonl(args.out_dir / "historical-152-audit.jsonl", target_audit)
    write_jsonl(args.out_dir / "new-strict-eligible.jsonl", new_final)
    failures = [row for row in target_audit if row["status"] != "recovered_final"]
    write_jsonl(args.out_dir / "misses-and-screening-failures.jsonl", failures)
    with (args.out_dir / "stage-yield.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(stage_table[0]))
        writer.writeheader()
        writer.writerows(stage_table)
    markdown = [
        "# Historical anchored Scoper audit", "",
        f"- Final strict corpus: **{len(final)}** works.",
        f"- Historical 152 recovered: **{recovered}/152 ({recovered / 152:.1%})**.",
        f"- Reconstructed anchors recovered: **{sum(r['status'] == 'recovered_final' for r in anchors)}/{len(anchors)}**.",
        f"- Non-anchor works recovered before strict screening: **{sum(r['status'] != 'retrieval_miss' for r in nonanchors)}/{len(nonanchors)}**.",
        f"- Non-anchor works retained after strict screening: **{sum(r['status'] == 'recovered_final' for r in nonanchors)}/{len(nonanchors)}**.",
        f"- Strict eligible works absent from the historical 152: **{len(new_final)}** (model-screened; not yet human-validated).",
        "", "## Marginal yield", "",
        "| Stage | Broad snapshot | Marginal broad | Marginal strict survivors |",
        "|---|---:|---:|---:|",
    ]
    markdown.extend(
        f"| {row['stage']} | {row['snapshot_unique_broad']} | {row['marginal_broad']} | {row['marginal_strict_survivors']} |"
        for row in stage_table
    )
    markdown.extend(["", "## Historical misses and boundary disagreements", ""])
    markdown.extend(
        f"- **{row['status']} — {row['gold_title']}**"
        + (f": {row['screen_reason']}" if row['screen_reason'] else "")
        for row in failures
    )
    markdown.extend(["", "## Caveats", ""] + [f"- {item}" for item in report["caveats"]])
    (args.out_dir / "REPORT.md").write_text("\n".join(markdown) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
