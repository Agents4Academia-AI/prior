#!/usr/bin/env python3
"""Overlay v12 citation-context corrections on the enriched legacy graph."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from integrate_legacy_enriched_graph import HARD, graph, metrics, pair_key

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "data/prior-core-v0.2"
OUT = Path(__file__).parent / "out"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    previous_rows = jsonl(OUT / "legacy_fulltext_citation_enriched_predictions.jsonl")
    previous = {row["candidate_id"]: row for row in previous_rows}
    corrected_rows = jsonl(OUT / "legacy_incoming_v12_context_predictions.jsonl")
    corrected = {row["candidate_id"]: row for row in corrected_rows}
    manifest = json.loads((OUT / "legacy_incoming_v12_context_candidates.json").read_text())
    expected = {row["candidate_id"] for row in manifest["candidates"]}
    if len(previous) != 989 or len(corrected) != 34 or set(corrected) != expected:
        raise RuntimeError({"previous": len(previous), "corrected": len(corrected),
                            "expected": len(expected),
                            "missing": sorted(expected - set(corrected))})

    merged = []
    normalized = Counter()
    for key in sorted(previous):
        row = dict(corrected.get(key, previous[key]))
        if key in corrected:
            row["relabel_source"] = "incoming_v12_new_citation_context"
        if row["relation"] in {"related", "none", "unclear"} and row["direction"] != "none":
            row["raw_direction"] = row["direction"]
            row["direction"] = "none"
            normalized[f"{row['relation']}_direction_to_none"] += 1
        merged.append(row)

    prediction_path = OUT / "legacy_fulltext_citation_enriched_v12_predictions.jsonl"
    prediction_path.write_text("".join(json.dumps(row) + "\n" for row in merged))
    contributions_obj = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = (contributions_obj["contributions"] if isinstance(contributions_obj, dict)
                     else contributions_obj)
    nodes = {row["id"] for row in contributions}
    edges = [{
        "src": row["a"] if row["direction"] != "b_to_a" else row["b"],
        "dst": row["b"] if row["direction"] != "b_to_a" else row["a"],
        "relation": row["relation"], "direction": row["direction"],
        "existence_confidence": row["existence_confidence"],
        "type_confidence": row["type_confidence"],
        "evidence_ids": row["evidence_ids"], "reason": row["reason"],
        "citation_directions": row.get("citation_directions", []),
        "relabel_source": row.get("relabel_source"),
    } for row in merged]
    graph_path = OUT / "canonical_semantic_candidates_enriched_evidence_v12.json"
    graph_path.write_text(json.dumps({
        "_meta": {"generated_utc": datetime.now(timezone.utc).isoformat(),
                  "artifact_id": "canonical_semantic_candidates_enriched_evidence_v12",
                  "status": "canonical",
                  "candidate_policy": "same 989 contribution pairs retained by legacy graph",
                  "evidence_policy": "quotes + retrieved full text + all currently localized parent-paper citation passages",
                  "incoming_v12_corrected_pairs": 34,
                  "intent_policy": "site-level intent retained separately; no rollup used",
                  "normalization": dict(normalized)},
        "contributions": contributions, "edges": edges,
    }, indent=2))

    old_rel = Counter(row["relation"] for row in previous_rows)
    new_rel = Counter(row["relation"] for row in merged)
    transitions = Counter((previous[key]["relation"], corrected[key]["relation"])
                          for key in corrected)
    changed = [{"candidate_id": key,
                "before": previous[key]["relation"],
                "after": corrected[key]["relation"],
                "citation_evidence_used": any(e.startswith("CIT:")
                                                for e in corrected[key].get("evidence_ids", [])),
                "reason": corrected[key]["reason"]}
               for key in sorted(corrected)
               if previous[key]["relation"] != corrected[key]["relation"]]
    legacy_obj = json.loads((BUNDLE / "contributions_core_consensus.json").read_text())
    legacy = legacy_obj["edges"] if isinstance(legacy_obj, dict) else legacy_obj
    previous_sub = [r for r in previous_rows if r["relation"] not in {"none", "unclear"}]
    current_sub = [r for r in merged if r["relation"] not in {"none", "unclear"}]
    report = {
        "validation": {"previous_pairs": len(previous), "merged_pairs": len(merged),
                       "corrected_pairs": len(corrected),
                       "duplicates": len(merged) - len({r["candidate_id"] for r in merged}),
                       "invalid_evidence": sum(bool(r.get("invalid_evidence_ids")) for r in corrected.values()),
                       "corrected_with_citation_passage": sum(r.get("n_citation_passages", 0) > 0 for r in corrected.values()),
                       "corrected_using_citation_evidence": sum(any(e.startswith("CIT:") for e in r.get("evidence_ids", [])) for r in corrected.values()),
                       "normalization": dict(normalized)},
        "relations": {"previous_enriched": dict(old_rel), "incoming_v12": dict(new_rel),
                      "affected_transitions": {f"{a} -> {b}": n for (a, b), n in sorted(transitions.items())},
                      "affected_exact_agreement": sum(a == b for a, b in transitions.elements()),
                      "affected_changed": len(changed)},
        "changed_pairs": changed,
        "topology": {
            "legacy": metrics(graph(nodes, [(r["src"], r["dst"]) for r in legacy])),
            "previous_enriched_substantive": metrics(graph(nodes, [(r["a"], r["b"]) for r in previous_sub])),
            "incoming_v12_substantive": metrics(graph(nodes, [(r["a"], r["b"]) for r in current_sub])),
            "incoming_v12_hard": metrics(graph(nodes, [(r["a"], r["b"]) for r in merged if r["relation"] in HARD])),
        },
    }
    report_path = OUT / "legacy_fulltext_citation_enriched_v12_comparison.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print("->", prediction_path, graph_path, report_path)


if __name__ == "__main__":
    main()
