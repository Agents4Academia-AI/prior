#!/usr/bin/env python3
"""Do the papers each answer names actually exist? (zero cost, no LLM, no network)

Prior's pitch is grounded, verifiable answers — so fabrication is the metric that
matters most here, and for the GRAPH arm we can check it without spending anything:
every title in `papers_named` must resolve to one of the 152 corpus papers, or it
was invented.

Honest asymmetry, stated rather than hidden: the WEB and NULL arms may legitimately
name real papers that are outside the corpus, so a non-match there is NOT proof of
fabrication — it only means "unverifiable by this script", and the judge is the
authority for those. What this script does give, for every arm, is:
  • how many papers each answer commits to (the specificity floor), and
  • for the graph arm, a hard fabrication count.

  python verify_named.py                  # reads out/answers.jsonl
  python verify_named.py --file X.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

IDEATION = Path(__file__).resolve().parents[1] / "graph_vs_web_ideation"
sys.path.insert(0, str(IDEATION))
from graph_tools import GraphAtlas                                  # noqa: E402

HERE = Path(__file__).resolve().parent
_WORD = re.compile(r"[a-z0-9]+")


def norm(s: str) -> str:
    return " ".join(_WORD.findall((s or "").lower()))


def match(title: str, corpus: dict[str, str]) -> str | None:
    """Resolve a named title to a corpus paper: exact-normalised, then containment
    either way (titles get truncated or subtitled in prose), then a strong token
    overlap for the remainder."""
    n = norm(title)
    if not n:
        return None
    if n in corpus:
        return corpus[n]
    for cn, cid in corpus.items():
        if len(n) > 12 and (n in cn or cn.startswith(n)):
            return cid
    toks = set(n.split())
    best, best_score = None, 0.0
    for cn, cid in corpus.items():
        ct = set(cn.split())
        if not ct:
            continue
        score = len(toks & ct) / max(len(toks), 1)
        if score > best_score:
            best, best_score = cid, score
    return best if best_score >= 0.75 else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(HERE / "out" / "answers.jsonl"))
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        sys.exit(f"no answers at {path} — run qa_gen.py first.")

    atlas = GraphAtlas()
    corpus = {norm(p.get("title", "")): pid for pid, p in atlas.papers.items()}
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]

    per_arm = defaultdict(lambda: {"answers": 0, "named": 0, "resolved": 0, "unresolved": 0})
    print(f"{'qid':5} {'arm':6} {'named':>5} {'in-corpus':>9}  unresolved titles")
    for r in sorted(rows, key=lambda r: (r["question_id"], r["arm"])):
        ans = r.get("answer") or {}
        names = ans.get("papers_named") or []
        hits = [match(t, corpus) for t in names]
        miss = [t for t, h in zip(names, hits) if h is None]
        a = per_arm[r["arm"]]
        a["answers"] += 1
        a["named"] += len(names)
        a["resolved"] += sum(h is not None for h in hits)
        a["unresolved"] += len(miss)
        note = "; ".join(t[:44] for t in miss[:3]) if miss else ""
        print(f"{r['question_id']:5} {r['arm']:6} {len(names):5} "
              f"{len(names) - len(miss):9}  {note}")

    print(f"\n{'arm':6} {'answers':>7} {'papers/answer':>13} {'in-corpus':>10} {'unresolved':>11}")
    for arm, a in sorted(per_arm.items()):
        per = a["named"] / a["answers"] if a["answers"] else 0
        print(f"{arm:6} {a['answers']:7} {per:13.1f} {a['resolved']:10} {a['unresolved']:11}")

    g = per_arm.get("graph")
    if g:
        print(f"\nGRAPH arm fabrication check: {g['unresolved']}/{g['named']} named papers "
              f"do not resolve to the corpus.")
        print("  (For graph, an unresolved title IS a fabrication — it can only have seen "
              "the 152.\n   For web/null it just means 'outside the corpus' — unverifiable "
              "here, judge decides.)")
        print("  EXCEPT on c01/c02: naming an out-of-corpus paper there may be the graph arm "
              "correctly\n   reporting general knowledge — read those two rows before "
              "counting them as fabrications.")


if __name__ == "__main__":
    main()
