#!/usr/bin/env python3
"""Audit all site-level citation intents against the final enriched graph."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "out"
DEFAULT_OLD = Path(
    "/Users/kk1918_1/projects/Otto/worktrees/prior-citation-substrate/"
    "experiments/edge_quality/out/citations_intent.json"
)
HARD = {"supports", "builds_on", "refines", "contradicts"}


def paper_id(contribution_id: str) -> str:
    return contribution_id.split("::")[0]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def old_sites(path: Path) -> list[dict]:
    rows = []
    for edge in load(path)["edges"]:
        for index, site in enumerate(edge.get("sites", [])):
            rows.append({
                "site_key": f"{edge['citing_id']}->{edge['cited_id']}#{index}",
                "citing_id": edge["citing_id"], "cited_id": edge["cited_id"],
                "intent": site["intent"], "confidence": site.get("confidence"),
                "justification": site.get("justification"), "claim": site.get("claim"),
                "intent_source": "callum_complete_809",
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-intents", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--new-intents", type=Path,
                        default=OUT / "citations_intent_incoming_v12_new.json")
    parser.add_argument("--graph", type=Path,
                        default=OUT / "legacy_fulltext_citation_enriched_v12_graph.json")
    parser.add_argument("--summary", type=Path,
                        default=OUT / "full_intent_graph_audit.json")
    parser.add_argument("--queue", type=Path,
                        default=OUT / "full_intent_graph_audit_queue.jsonl")
    parser.add_argument("--pair-queue", type=Path,
                        default=OUT / "full_intent_graph_audit_pair_queue.json")
    parser.add_argument("--markdown", type=Path,
                        default=OUT / "full_intent_graph_audit.md")
    args = parser.parse_args()

    sites = old_sites(args.original_intents)
    for site in load(args.new_intents)["sites"]:
        sites.append({**site, "intent_source": "incoming_v12_scaled_294"})
    if len(sites) != 1103 or len({s["site_key"] for s in sites}) != 1103:
        raise RuntimeError("expected 1,103 unique citation sites")

    graph_obj = load(args.graph)
    graph_edges = graph_obj["edges"]
    by_paper_pair: dict[frozenset[str], list[dict]] = defaultdict(list)
    for index, edge in enumerate(graph_edges):
        edge = {**edge, "graph_edge_index": index,
                "pair_id": "|".join(sorted((edge["src"], edge["dst"])))}
        by_paper_pair[frozenset((paper_id(edge["src"]), paper_id(edge["dst"])))].append(edge)

    observations = []
    matched_sites = set()
    for site in sites:
        pair = frozenset((site["citing_id"], site["cited_id"]))
        for edge in by_paper_pair.get(pair, []):
            matched_sites.add(site["site_key"])
            site_index = int(site["site_key"].rsplit("#", 1)[1]) + 1
            evidence_id = f"CIT:{site['citing_id']}->{site['cited_id']}:{site_index}"
            observations.append({
                **site,
                "contribution_pair": edge["pair_id"],
                "graph_src": edge["src"], "graph_dst": edge["dst"],
                "relation": edge["relation"], "direction": edge["direction"],
                "graph_reason": edge.get("reason"),
                "expected_evidence_id": evidence_id,
                "site_cited_as_evidence": evidence_id in edge.get("evidence_ids", []),
            })

    def subset(intent: str) -> list[dict]:
        return [r for r in observations if r["intent"] == intent]

    uses = subset("uses_extends")
    background = subset("background")
    comparisons = subset("compares_contrasts")
    uses_builds = [r for r in uses if r["relation"] == "builds_on"]
    direction_good = [r for r in uses_builds
                      if paper_id(r["graph_src"]) == r["citing_id"]
                      and paper_id(r["graph_dst"]) == r["cited_id"]]
    background_hard = [r for r in background if r["relation"] in HARD]
    background_evidence = [r for r in background_hard if r["site_cited_as_evidence"]]
    comparison_contradictions = [r for r in comparisons if r["relation"] == "contradicts"]

    def unique_pairs(rows: list[dict]) -> int:
        return len({r["contribution_pair"] for r in rows})

    relation_by_intent = {
        intent: dict(Counter(r["relation"] for r in subset(intent)))
        for intent in ("uses_extends", "background", "compares_contrasts")
    }
    queue = []
    for row in observations:
        reason = None
        if row["intent"] == "uses_extends" and row["relation"] != "builds_on":
            reason = "uses_extends_not_builds_on"
        elif (row["intent"] == "uses_extends" and row["relation"] == "builds_on"
              and not (paper_id(row["graph_src"]) == row["citing_id"]
                       and paper_id(row["graph_dst"]) == row["cited_id"])):
            reason = "builds_on_direction_mismatch"
        elif (row["intent"] == "background" and row["relation"] in HARD
              and row["site_cited_as_evidence"]):
            reason = "background_passage_supports_hard_relation"
        elif row["intent"] == "compares_contrasts" and row["relation"] == "contradicts":
            reason = "comparison_promoted_to_contradiction"
        if reason:
            queue.append({"audit_reason": reason, **row})

    summary = {
        "coverage": {
            "graph_contribution_pairs": len(graph_edges),
            "citation_sites": len(sites),
            "paper_citation_edges": len({(s["citing_id"], s["cited_id"]) for s in sites}),
            "matched_citation_sites": len(matched_sites),
            "matched_contribution_pairs": unique_pairs(observations),
            "site_pair_observations": len(observations),
            "unmatched_citation_sites": len(sites) - len(matched_sites),
        },
        "relation_by_site_intent": relation_by_intent,
        "four_point_audit": {
            "uses_extends": {
                "observations": len(uses), "unique_pairs": unique_pairs(uses),
                "builds_on_observations": len(uses_builds),
                "builds_on_unique_pairs": unique_pairs(uses_builds),
            },
            "direction": {
                "builds_on_observations": len(uses_builds),
                "agreeing_observations": len(direction_good),
                "mismatching_observations": len(uses_builds) - len(direction_good),
                "mismatching_unique_pairs": unique_pairs(
                    [r for r in uses_builds if r not in direction_good]),
            },
            "background": {
                "observations": len(background), "unique_pairs": unique_pairs(background),
                "hard_relation_observations": len(background_hard),
                "hard_relation_unique_pairs": unique_pairs(background_hard),
                "hard_using_exact_site_observations": len(background_evidence),
                "hard_using_exact_site_unique_pairs": unique_pairs(background_evidence),
            },
            "compares_contrasts": {
                "observations": len(comparisons), "unique_pairs": unique_pairs(comparisons),
                "contradiction_observations": len(comparison_contradictions),
                "contradiction_unique_pairs": unique_pairs(comparison_contradictions),
            },
        },
        "review_queue": {
            "observations": len(queue), "unique_pairs": unique_pairs(queue),
            "by_reason_observations": dict(Counter(r["audit_reason"] for r in queue)),
            "by_reason_unique_pairs": {
                reason: unique_pairs([r for r in queue if r["audit_reason"] == reason])
                for reason in sorted({r["audit_reason"] for r in queue})
            },
        },
        "method": {
            "unit": "citation-site x retained contribution-pair observation",
            "rollup": "none; mixed-intent paper edges may contribute to multiple intent categories",
            "hard_relations": sorted(HARD),
        },
    }
    args.summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.queue.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in queue),
                          encoding="utf-8")
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in queue:
        grouped[(row["audit_reason"], row["contribution_pair"])].append(row)
    reason_rank = {"comparison_promoted_to_contradiction": 0,
                   "background_passage_supports_hard_relation": 1,
                   "uses_extends_not_builds_on": 2}
    relation_rank = {"contradicts": 0, "refines": 1, "builds_on": 2,
                     "supports": 3, "related": 4}
    pair_queue = []
    for (audit_reason, contribution_pair), rows in grouped.items():
        first = rows[0]
        pair_queue.append({
            "audit_reason": audit_reason, "contribution_pair": contribution_pair,
            "relation": first["relation"], "graph_src": first["graph_src"],
            "graph_dst": first["graph_dst"], "graph_reason": first["graph_reason"],
            "n_flagged_sites": len(rows),
            "intents": sorted({r["intent"] for r in rows}),
            "intent_sources": sorted({r["intent_source"] for r in rows}),
            "sites": [{k: r.get(k) for k in
                       ("site_key", "citing_id", "cited_id", "intent", "confidence",
                        "justification", "claim", "site_cited_as_evidence")}
                      for r in rows],
        })
    pair_queue.sort(key=lambda r: (reason_rank[r["audit_reason"]],
                                   relation_rank.get(r["relation"], 9),
                                   r["contribution_pair"]))
    args.pair_queue.write_text(json.dumps({
        "meta": {"n_unique_pair_reasons": len(pair_queue),
                 "n_unique_pairs": len({r["contribution_pair"] for r in pair_queue}),
                 "ordering": "comparison contradictions; background hard relations ordered contradiction/refine/build/support; uses exceptions"},
        "queue": pair_queue,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    audit = summary["four_point_audit"]
    tier_one = [r for r in pair_queue
                if r["audit_reason"] == "comparison_promoted_to_contradiction"]
    tier_two = [r for r in pair_queue
                if r["audit_reason"] == "background_passage_supports_hard_relation"
                and r["relation"] in {"contradicts", "refines"}]
    tier_three = [r for r in pair_queue
                  if r["audit_reason"] == "uses_extends_not_builds_on"]

    def pointers(rows: list[dict]) -> str:
        return "\n".join(f"- `{r['contribution_pair']}` -> `{r['relation']}`"
                         for r in rows) or "- None"

    markdown = f"""# Full citation-intent audit of the enriched v12 graph

This joins all 1,103 available site-level intent labels to the final 989-pair
contribution graph without an edge-level intent rollup. The analysis covers
{summary['coverage']['matched_citation_sites']} citation sites and
{summary['coverage']['matched_contribution_pairs']} contribution pairs, producing
{summary['coverage']['site_pair_observations']} site-pair observations.

## Four checks

1. `uses_extends` -> `builds_on`
   - {audit['uses_extends']['builds_on_observations']}/{audit['uses_extends']['observations']}
     site-pair observations are `builds_on`, spanning
     {audit['uses_extends']['builds_on_unique_pairs']}/{audit['uses_extends']['unique_pairs']}
     unique contribution pairs.
2. Direction
   - {audit['direction']['agreeing_observations']}/{audit['direction']['builds_on_observations']}
     `uses_extends` -> `builds_on` observations follow citing -> cited direction;
     {audit['direction']['mismatching_unique_pairs']} unique pairs mismatch.
3. Background overinterpretation
   - {audit['background']['hard_relation_observations']}/{audit['background']['observations']}
     background observations map to a hard relation, spanning
     {audit['background']['hard_relation_unique_pairs']} unique pairs.
   - {audit['background']['hard_using_exact_site_observations']} observations across
     {audit['background']['hard_using_exact_site_unique_pairs']} unique pairs explicitly
     use that exact background passage as graph evidence. These are the priority audit queue.
4. Comparison promoted to contradiction
   - {audit['compares_contrasts']['contradiction_observations']}/{audit['compares_contrasts']['observations']}
     comparison observations became `contradicts`, spanning
     {audit['compares_contrasts']['contradiction_unique_pairs']} unique pairs.

## Suggested review order for Callum

### Tier 1: comparison -> contradiction ({len(tier_one)} pairs)

{pointers(tier_one)}

### Tier 2: exact background evidence -> contradiction/refinement ({len(tier_two)} pair-reasons)

{pointers(tier_two)}

### Tier 3: `uses_extends` not represented as `builds_on` ({len(tier_three)} pair-reasons)

{pointers(tier_three)}

The pair-level JSON queue contains passages, confidence, intent justification,
graph rationale, direction, and exact contribution IDs. The remaining background
queue (mostly `builds_on` and `supports`) is lower priority and can be sampled.

## Interpretation caveat

Intent is site-level and graph relations are contribution-pair-level. Multiple
citation sites—and multiple intents—can map to the same contribution pair. Queue
membership is an audit pointer, not a claim that the graph edge is wrong.
"""
    args.markdown.write_text(markdown, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
