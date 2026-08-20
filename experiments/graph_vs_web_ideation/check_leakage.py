#!/usr/bin/env python3
"""Scan generated ideas for provenance leakage that would break blind judging.

Both arms must read as ordinary self-contained proposals. This flags any idea
whose text reveals HOW it was produced — internal IDs, "the graph", tool names,
"web search", etc. Run before judging; regenerate (or lightly scrub) flagged rows.

  python check_leakage.py                 # scan out/generations.jsonl
  python check_leakage.py --file X.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Markers that betray provenance. Internal IDs and structure words are the worst
# (they identify the graph arm); process words betray either arm.
PATTERNS = {
    "internal_id": re.compile(r"\b(?:arxiv:\d|openalex:W\d|::k\d)", re.I),
    "graph_structure": re.compile(r"\b(the graph|the corpus|contribution node|"
                                  r"graph contribution|typed edge|no edge|an edge\b)", re.I),
    "tool_name": re.compile(r"\b(get_neighbors|get_edges|get_contribution|get_paper|"
                            r"search_contributions|overview|WebSearch|WebFetch|"
                            r"mcp__)", re.I),
    "process": re.compile(r"\b(web[- ]?search|this session|my search(?:es)?|I searched|"
                          r"the database|knowledge base)\b", re.I),
}
FIELDS = ("title", "gap", "proposed_study", "expected_result", "grounding")


def scan(text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for name, pat in PATTERNS.items():
        found = sorted({m.group(0) for m in pat.finditer(text or "")})
        if found:
            hits[name] = found
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "out" / "generations.jsonl"))
    args = ap.parse_args()
    rows = [json.loads(l) for l in Path(args.file).read_text(encoding="utf-8").splitlines()
            if l.strip()]
    n_flag = 0
    by_arm = {"graph": [0, 0], "web": [0, 0]}   # [flagged, total]
    for r in rows:
        idea = r.get("idea") or {}
        text = " ".join(str(idea.get(f, "")) for f in FIELDS)
        hits = scan(text)
        arm = r.get("arm", "?")
        if arm in by_arm:
            by_arm[arm][1] += 1
            by_arm[arm][0] += bool(hits)
        if hits:
            n_flag += 1
            print(f"LEAK  {r.get('seed_id')} [{arm}]: "
                  + "; ".join(f"{k}={v}" for k, v in hits.items()))
    print(f"\n{n_flag}/{len(rows)} ideas leak provenance.")
    for arm, (f, t) in by_arm.items():
        print(f"  {arm}: {f}/{t} flagged")
    if n_flag:
        print("→ regenerate the flagged rows with the updated prompt before judging.")


if __name__ == "__main__":
    main()
