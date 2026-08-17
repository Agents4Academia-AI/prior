"""Offline hidden-target recovery after an immutable expansion snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from common import (load_gold, normalise_arxiv, normalise_doi, title_key,
                    title_tokens)
from adaptive_expansion import _receipt


def _papers(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line)["paper"] for line in path.read_text().splitlines() if line]


def score(gold_file: Path, sources: list[tuple[str, Path]], out_dir: Path,
          label: str) -> dict:
    candidates = []
    input_paths = []
    for channel, path in sources:
        input_paths.append(path)
        candidates.extend((channel, paper) for paper in _papers(path))
    doi_index, arxiv_index, token_index = {}, {}, defaultdict(set)
    prepared = []
    for index, (channel, paper) in enumerate(candidates):
        doi = normalise_doi(paper.get("doi"))
        pid = str(paper.get("id") or "")
        arxiv = normalise_arxiv(pid.split(":", 1)[1] if pid.startswith("arxiv:") else "")
        tokens = title_tokens(paper.get("title"))
        prepared.append((channel, paper, tokens))
        if doi:
            doi_index.setdefault(doi, index)
        if arxiv:
            arxiv_index.setdefault(arxiv, index)
        for token in tokens:
            token_index[token].add(index)
    rows = []
    for gold in load_gold(gold_file):
        hit, score_value, basis = None, 0.0, ""
        exact = doi_index.get(gold.doi) if gold.doi else None
        if exact is None and gold.arxiv:
            exact = arxiv_index.get(gold.arxiv)
        if exact is not None:
            hit, score_value, basis = prepared[exact], 1.0, "strong_identifier"
        else:
            gt = title_tokens(gold.title)
            plausible = set()
            for token in gt:
                plausible.update(token_index.get(token, ()))
            for index in plausible:
                candidate = prepared[index]
                ct = candidate[2]
                similarity = len(gt & ct) / max(1, len(gt | ct))
                if similarity >= 0.82 and similarity > score_value:
                    hit, score_value, basis = candidate, similarity, "title_jaccard"
        rows.append({"gold_id": gold.gold_id, "title": gold.title,
                     "recovered": hit is not None, "channel": hit[0] if hit else "",
                     "matched_title": hit[1].get("title", "") if hit else "",
                     "score": score_value, "basis": basis})
    recovered = sum(row["recovered"] for row in rows)
    report = {"label": label, "gold_n": len(rows), "recovered": recovered,
              "recovery": recovered / max(1, len(rows)),
              "candidate_records": len(candidates), "targets": rows}
    output = out_dir / f"recovery-{label}.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    _receipt(out_dir, f"recovery_{label}", [gold_file] + input_paths, [output],
             deterministic=True,
             parameters={"gold_join": "offline_after_snapshot_freeze",
                         "title_threshold": 0.82})
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--label", required=True)
    ap.add_argument("--source", action="append", required=True,
                    help="CHANNEL=JSONL")
    args = ap.parse_args()
    sources = []
    for value in args.source:
        channel, path = value.split("=", 1)
        sources.append((channel, Path(path)))
    report = score(args.gold, sources, args.out_dir, args.label)
    print(json.dumps({key: report[key] for key in
                      ("label", "gold_n", "recovered", "recovery", "candidate_records")}, indent=2))


if __name__ == "__main__":
    main()
