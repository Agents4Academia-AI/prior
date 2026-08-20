#!/usr/bin/env python3
"""Scan answers for provenance leakage that would break blind judging. (zero cost)

All three arms must read as ordinary scholarly replies. This flags any answer whose
text betrays HOW it was produced. The dangerous one here is **schema vocabulary**:
the graph arm quoting its own classification labels ("background",
"compares_contrasts", "citation intent labels") identifies it to the judge
instantly. Caught on q01 in the first live batch — hence this gate.

Note the deliberate distinction: `background` used as ordinary English ("cited as
motivating background") is FINE and every arm does it. What is flagged is the label
used as a technical term — in quotes, with an underscore, or alongside "intent" /
"label" / "tag".

  python check_leakage.py                 # scan out/answers.jsonl
  python check_leakage.py --file X.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

PATTERNS = {
    # the schema words as TECHNICAL TERMS: underscored, or quoted, or next to
    # intent/label/tag/edge/relation. Bare English "background" is not flagged.
    "schema_label": re.compile(
        r"(\b(?:uses_extends|compares_contrasts|builds_on|type_confidence|"
        r"contribution_id|paper_id|n_sites)\b"
        r"|[\"'](?:background|uses[_ ]extends|compares[_ ]contrasts|builds[_ ]on|"
        r"contradicts|refines|supports)[\"']"
        r"|\b(?:citation|relation|edge)\s+(?:intent|type|label|tag)s?\b"
        r"|\b(?:intent|relation)\s+labels?\b)", re.I),
    # NB: "knowledge graph" is deliberately NOT here — it appears in real paper titles
    # in this corpus ("Interesting Scientific Idea Generation using Knowledge Graphs
    # and LLMs"), so flagging it produces false positives.
    "graph_words": re.compile(r"\b(the graph\b|the corpus\b|the atlas\b|a typed edge|"
                              r"in my graph|our graph|the graph structure)", re.I),
    "tool_name": re.compile(r"\b(get_edges|get_neighbors|get_contribution|get_paper|"
                            r"get_citations|citations_between|search_contributions|"
                            r"WebSearch|WebFetch|mcp__)", re.I),
    "process": re.compile(r"\b(web[- ]?search|I searched|my search(?:es)?|the database|"
                          r"knowledge base|my tools|the tools (?:I|available)|"
                          r"my training data|I have no access)\b", re.I),
}
FIELDS = ("answer", "limits")


def scan(text: str) -> dict[str, list[str]]:
    hits = {}
    for name, pat in PATTERNS.items():
        found = sorted({m.group(0).strip() for m in pat.finditer(text or "")})
        if found:
            hits[name] = found
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "out" / "answers.jsonl"))
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"no answers at {path} — run qa_gen.py first.")
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    n_flag = 0
    by_arm: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in sorted(rows, key=lambda r: (r["question_id"], r["arm"])):
        ans = r.get("answer") or {}
        text = " ".join(str(ans.get(f, "")) for f in FIELDS)
        hits = scan(text)
        arm = r.get("arm", "?")
        by_arm[arm][1] += 1
        by_arm[arm][0] += bool(hits)
        if hits:
            n_flag += 1
            print(f"LEAK  {r['question_id']} [{arm}]: "
                  + "; ".join(f"{k}={v[:4]}" for k, v in hits.items()))

    print(f"\n{n_flag}/{len(rows)} answers leak provenance.")
    for arm, (f, t) in sorted(by_arm.items()):
        print(f"  {arm:6}: {f}/{t} flagged")
    if n_flag:
        print("\n→ regenerate the flagged (question, arm) cells, then re-judge those "
              "questions:\n   python qa_gen.py --questions <qid> --arm <arm>\n"
              "   (delete the stale row from out/answers.jsonl first, and the "
              "question's row\n    from out/qa_judgements.jsonl so it re-judges)")


if __name__ == "__main__":
    main()
