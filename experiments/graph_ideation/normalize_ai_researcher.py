#!/usr/bin/env python3
"""Join AI-Researcher ideation reviews to the released proposal texts."""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean


SCORES = ("novelty_score", "feasibility_score", "effectiveness_score",
          "excitement_score", "overall_score", "confidence_score")


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower().replace(".json", "").replace(".txt", ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--external", type=Path, required=True)
    args = parser.parse_args()
    root = args.external

    raw = json.loads((root / "human_reviews_ideation.json").read_text())
    reviews = [dict(zip(raw, (raw[k][i] for k in raw)))
               for i in range(len(raw["idea_id"]))]
    mapping_rows = list(csv.DictReader((root / "id_title_mapping.csv").open()))
    id_title = {x["ID"].replace(" ", ""): x["Title / Filename"].strip()
                for x in mapping_rows}
    files = list((root / "proposals").rglob("*.txt"))
    by_stem = defaultdict(list)
    by_title = defaultdict(list)
    for path in files:
        by_stem[norm(path.stem)].append(path)
        first = path.read_text(errors="replace").splitlines()[0]
        first = re.sub(r"^\s*Title\s*:\s*", "", first, flags=re.I)
        by_title[norm(first)].append(path)

    def proposal_path(idea_id: str, title: str) -> Path:
        condition = "AI_Rerank" if idea_id.endswith("_AI_Rerank") else (
            "AI" if idea_id.endswith("_AI") else "Human")
        directory = {"AI": "AI_AI_Ideas_Processed",
                     "AI_Rerank": "AI_Human_Ideas_Txt",
                     "Human": "Human_Ideas_Txt_Processed"}[condition]
        candidates = [p for p in by_stem[norm(title)] + by_title[norm(title)]
                      if p.parent.name == directory]
        unique = list(dict.fromkeys(candidates))
        if len(unique) != 1:
            raise ValueError(f"proposal join for {idea_id}: {title!r} -> {unique}")
        return unique[0]

    grouped = defaultdict(list)
    for review in reviews:
        grouped[review["idea_id"].replace(" ", "")].append(review)
    out = []
    unmapped = []
    for idea_id, rows in sorted(grouped.items()):
        if idea_id not in id_title:
            unmapped.append(idea_id)
            continue
        title = id_title[idea_id]
        path = proposal_path(idea_id, title)
        item = {"idea_id": idea_id, "condition": rows[0]["condition"],
                "topic": rows[0]["topic"], "title": title,
                "proposal_path": str(path.relative_to(root)),
                "proposal_text": path.read_text(errors="replace"),
                "n_reviews": len(rows)}
        for score in SCORES:
            item[score] = mean(float(x[score]) for x in rows)
        out.append(item)

    target = root / "normalized_idea_ratings.jsonl"
    target.write_text("".join(json.dumps(x) + "\n" for x in out))
    summary = {"reviews": len(reviews), "reviewed_ideas": len(grouped),
               "ideas_joined": len(out), "unmapped_idea_ids": unmapped,
               "proposals_joined": sum(bool(x["proposal_text"]) for x in out),
               "conditions": {c: sum(x["condition"] == c for x in out)
                              for c in ("Human", "AI", "AI_Rerank")}}
    (root / "normalization_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
