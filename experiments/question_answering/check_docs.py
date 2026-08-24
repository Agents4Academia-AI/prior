#!/usr/bin/env python3
"""Check that the prompts quoted in the docs still match the code. (free, no LLM)

ARMS.md and JUDGING.md quote every system prompt, task prompt and nudge verbatim.
Verbatim quotes rot: someone edits a prompt in `qa_arms.py`, the run changes, and
the write-up quietly describes an experiment that was never performed. This
catches that.

Comparison is on normalised text — case, punctuation and whitespace are stripped
from both sides — so the docs are free to add markdown emphasis, bullet markers
and blockquote arrows around the words, but not to change the words.

  python check_docs.py          # exits non-zero if a quote has drifted
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def main() -> int:
    sys.path.insert(0, str(HERE))
    import qa_arms
    import qa_judge

    head, tail = qa_arms.TASK.split(qa_arms._BLIND)

    checks: list[tuple[str, str, str]] = [
        ("ARMS.md", "TASK (before the blinding contract)", head),
        ("ARMS.md", "TASK (after the blinding contract)", tail),
        ("ARMS.md", "_BLIND (blinding contract)", qa_arms._BLIND),
        ("ARMS.md", "NUDGE", qa_arms.NUDGE),
        ("ARMS.md", "GRAPH_SYS", qa_arms.GRAPH_SYS),
        ("ARMS.md", "WEB_SYS", qa_arms.WEB_SYS),
        ("ARMS.md", "NULL_SYS", qa_arms.NULL_SYS),
        ("JUDGING.md", "JUDGE_SYS", qa_judge.JUDGE_SYS),
        ("JUDGING.md", "PROMPT", qa_judge.PROMPT),
    ]

    docs = {name: norm((HERE / name).read_text(encoding="utf-8"))
            for name in {c[0] for c in checks}}

    bad = 0
    for doc, label, code in checks:
        # `{question}` and the like normalise down to the bare word, which is
        # exactly what the doc shows, so no special-casing is needed
        want = norm(code)
        if want and want in docs[doc]:
            print(f"  ok    {doc:12} {label}")
        else:
            bad += 1
            print(f"  DRIFT {doc:12} {label}")
            # show where it diverges, so the fix is obvious
            words = want.split()
            lo, hi = 0, len(words)
            while lo < hi:                      # longest matching prefix
                mid = (lo + hi + 1) // 2
                if " ".join(words[:mid]) in docs[doc]:
                    lo = mid
                else:
                    hi = mid - 1
            print(f"        matches up to word {lo}/{len(words)}, then expected: "
                  f"...{' '.join(words[max(0, lo - 6):lo + 8])}...")

    # the graph arm's data files must still be where ARMS.md §3.1 says they are
    from graph_tools import CANONICAL, INTENTS_809, TYPED_809, INTENTS_294, PAPERS
    for f in (CANONICAL, INTENTS_809, TYPED_809, INTENTS_294, PAPERS):
        if f.exists():
            print(f"  ok    atlas source {f.name}")
        else:
            bad += 1
            print(f"  MISSING atlas source {f}")

    print(f"\n{'ALL QUOTES MATCH THE CODE' if not bad else f'{bad} PROBLEM(S)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
