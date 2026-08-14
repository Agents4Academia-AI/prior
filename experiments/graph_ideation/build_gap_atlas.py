#!/usr/bin/env python3
"""Turn gap predictions into auditable, human-reviewable gap cards.

This is deliberately a presentation/export step: it does not promote an LLM's
gap proposal into an atlas fact.  The supporting contributions and graph edge
are evidence; the gap, missing evidence, and proposed study remain hypotheses.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "data" / "prior-core-v0.2"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_papers(path: Path) -> dict[str, dict]:
    return {row["id"]: row for row in read_jsonl(path)}


def build_cards(manifest: dict, predictions: list[dict], contributions: dict[str, dict],
                papers: dict[str, dict]) -> list[dict]:
    prediction_by_packet = {row["packet_id"]: row for row in predictions}
    cards = []
    for packet in manifest["packets"]:
        prediction = prediction_by_packet.get(packet["packet_id"])
        if not prediction:
            continue
        sources = []
        for source in packet["sources"]:
            contribution = contributions[source["contribution_id"]]
            paper = papers.get(contribution["paper_id"], {})
            sources.append({
                "source_id": source["id"],
                "paper_id": contribution["paper_id"],
                "paper_title": paper.get("title", ""),
                "paper_year": paper.get("year"),
                "paper_url": paper.get("url", ""),
                "contribution_id": contribution["id"],
                "contribution": contribution["statement"],
                "supporting_quote": contribution.get("quote_verbatim") or contribution.get("quote", ""),
                "quote_offsets": contribution.get("quote_offsets", []),
                "grounding": contribution.get("grounding"),
            })
        edge = packet.get("edge_evidence", {})
        cards.append({
            "id": f"gap:{packet['packet_id']}",
            "gap_type": prediction["gap_type"],
            "status": "draft_unverified",
            "gap_hypothesis": prediction["gap_statement"],
            "missing_evidence": prediction["missing_evidence"],
            "smallest_resolving_study": prediction["minimal_study"],
            "model_rationale": prediction["reason"],
            "evidence": {
                "sources": sources,
                "graph_relation": edge.get("relation"),
                "edge_reason": edge.get("reason", ""),
                "edge_existence_confidence": edge.get("existence_confidence"),
                "edge_type_confidence": edge.get("type_confidence"),
            },
            "provenance": {
                "packet_id": packet["packet_id"],
                "generator_model": prediction.get("model"),
                "generated_from": "motif-balanced, distinct-paper graph packet",
            },
            "review": {
                "gap_confirmed": None,
                "sources_sufficient": None,
                "study_actionable": None,
                "reviewer": None,
                "reviewed_at": None,
                "notes": "",
                "disputed_claims": [],
                "missing_papers": [],
            },
        })
    return cards


def markdown(snapshot: dict) -> str:
    lines = [
        "# Prior Research Gap Atlas — draft snapshot",
        "",
        f"Generated {snapshot['generated_at']}. {len(snapshot['cards'])} candidate gaps.",
        "",
        "> These are hypotheses for human review, not claims that the literature gaps are real. "
        "Supporting quotations and graph relations are the evidence substrate; each proposed gap "
        "and resolving study must still be checked against the literature.",
        "",
    ]
    for i, card in enumerate(snapshot["cards"], 1):
        lines += [
            f"## {i}. {card['gap_type'].replace('_', ' ').title()}",
            "",
            f"**Status:** `{card['status']}`  ",
            f"**Card:** `{card['id']}`",
            "",
            "### Candidate gap",
            "",
            card["gap_hypothesis"],
            "",
            "### Evidence substrate",
            "",
        ]
        for source in card["evidence"]["sources"]:
            title = source["paper_title"] or source["paper_id"]
            year = f" ({source['paper_year']})" if source["paper_year"] else ""
            lines += [
                f"- **{source['source_id']}: {title}{year}.** {source['contribution']}",
                f"  - Supporting quote: “{source['supporting_quote'].replace(chr(10), ' ')}”",
            ]
        relation = card["evidence"]["graph_relation"] or "open_wedge"
        lines += [
            "",
            f"Graph motif: `{relation}`. {card['evidence']['edge_reason']}",
            "",
            "### What is missing",
            "",
            card["missing_evidence"],
            "",
            "### Smallest resolving study",
            "",
            card["smallest_resolving_study"],
            "",
            "### Review checklist",
            "",
            "- [ ] Search for omitted or newer work that already addresses this gap.",
            "- [ ] Verify that each quotation supports its contribution summary.",
            "- [ ] Confirm that the graph relation is correctly typed.",
            "- [ ] Decide whether the proposed study is minimal and genuinely informative.",
            "- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True,
                        help="Directory containing manifest.json and gap_predictions.jsonl")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((args.input / "manifest.json").read_text())
    predictions = read_jsonl(args.input / "gap_predictions.jsonl")
    grounded = json.loads((args.bundle / "contributions_core_grounded.json").read_text())
    contributions = {row["id"]: row for row in grounded["contributions"]}
    papers = load_papers(args.bundle / "papers_core.jsonl")
    cards = build_cards(manifest, predictions, contributions, papers)
    snapshot = {
        "schema_version": "prior-gap-atlas/0.1",
        "generated_at": date.today().isoformat(),
        "topic": "AI agents for the scientific process",
        "status_policy": {
            "draft_unverified": "Model-proposed gap; source substrate attached but no human review.",
            "evidence_checked": "Quotes, contributions, and graph relation checked by a human.",
            "gap_confirmed": "A fresh search found no prior work that resolves the stated gap.",
            "disputed": "A reviewer identified a substantive problem or missing source.",
        },
        "summary": {
            "cards": len(cards),
            "by_type": dict(sorted(Counter(card["gap_type"] for card in cards).items())),
            "by_status": dict(sorted(Counter(card["status"] for card in cards).items())),
        },
        "cards": cards,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "gap_atlas.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    (args.out / "gap_atlas.md").write_text(markdown(snapshot) + "\n")
    print(json.dumps(snapshot["summary"], indent=2))


if __name__ == "__main__":
    main()
