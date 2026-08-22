#!/usr/bin/env python3
"""Adjudicate the judge's fabrication flags against the corpus. (zero cost, no LLM)

WHY THIS EXISTS
---------------
The judge is sealed — no browser, no tools — and scores correctness "from your own
knowledge". That is the right design for reproducibility, but it has a hard limit:
**32% of the 152-paper corpus is dated 2026, and eight papers are dated after the
judge's knowledge cutoff.** A paper the judge has never heard of looks exactly like
a paper that does not exist.

That is not hypothetical. On q04 the judge set `fabricated` on the graph arm for
"DN Hypo Pipeline", writing that it "does not appear to be a real system/paper".
It is `arxiv:2606.08532`, *DN-Hypo-Pipeline: An AI-Driven Workflow for Hypothesis
Generation via Large Language Models and Scientific Explanations*, Lin, Wang, Zhou,
Wang & Wang, 2026 — in the corpus, and dated after the judge could have seen it.

The asymmetry matters: the graph arm is the arm that names obscure corpus papers,
so it is the arm most exposed to this. Left uncorrected, the fabrication metric
penalises it for being right about recent work.

WHAT THIS DOES
--------------
For every judge fabrication flag, resolve the titles the judge named (from
`fabrication_notes` and from that answer's `papers_named`) against the 152 papers.

  • resolves to a corpus paper  → **judge false positive**, reported and excluded
  • does not resolve            → the flag stands (for graph, `verify_named.py`
                                  already proves it is outside the corpus)

For web/null a non-resolving title is genuinely unverifiable here — the judge
remains the authority and the flag stands, which is stated rather than hidden.

  python check_fabrication.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDEATION = HERE.parent / "graph_vs_web_ideation"
sys.path.insert(0, str(IDEATION))
from graph_tools import GraphAtlas                                    # noqa: E402

ARMS = ("graph", "web", "null")
_WORD = re.compile(r"[a-z0-9]+")


def _norm(t: str) -> frozenset[str]:
    return frozenset(_WORD.findall((t or "").lower()))


def resolve(title: str, index: list[tuple[frozenset[str], str, str]]) -> tuple[str, str] | None:
    """Match a loosely-written title against the corpus. Tolerant of the mangling
    a retry-degraded answer introduces (hyphens dropped: 'DN Hypo Pipeline')."""
    q = _norm(title)
    if not q:
        return None
    # Coverage of the QUERY: every word the answer wrote must appear in the real
    # title. Ties broken by FEWEST extra words, so 'Hypothesis Generation with
    # Large Language Models' resolves to that paper and not to 'Automating
    # psychological hypothesis generation with AI: when large language models
    # meet causal graph', which also contains all six words.
    best, best_key = None, None
    for toks, pid, real in index:
        if not toks:
            continue
        coverage = len(q & toks) / len(q)
        if coverage < 0.85:
            continue
        key = (-coverage, len(toks - q))
        if best_key is None or key < best_key:
            best, best_key = (pid, real), key
    return best


def main() -> None:
    # this file prints box-drawing and check marks; Windows consoles default
    # to cp1252 and would raise UnicodeEncodeError on the first heading
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default="out/answers.jsonl")
    ap.add_argument("--judgements", default="out/qa_judgements.jsonl")
    args = ap.parse_args()

    atlas = GraphAtlas()
    index = [(_norm(p.get("title", "")), pid, p.get("title", ""))
             for pid, p in atlas.papers.items()]

    apath, jpath = HERE / args.answers, HERE / args.judgements
    if not jpath.exists():
        sys.exit(f"no judgements at {jpath} — run qa_judge.py first.")
    answers: dict[tuple[str, str], dict] = {}
    for line in apath.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            answers[(r["question_id"], r["arm"])] = r
    judgements = [json.loads(l) for l in
                  jpath.read_text(encoding="utf-8").splitlines() if l.strip()]

    # quantify the exposure once, up front
    n2026 = sum(1 for p in atlas.papers.values() if (p.get("year") or 0) >= 2026)
    post = [pid for pid in atlas.papers
            if re.match(r"arxiv:(2[6-9])(0[6-9]|1[0-2])", pid)]
    print(f"corpus: {len(atlas.papers)} papers, {n2026} dated 2026+ "
          f"({100 * n2026 / len(atlas.papers):.0f}%), {len(post)} provably after the "
          f"judge's cutoff\n")

    flags = upheld = overturned = 0
    for j in judgements:
        for arm in ARMS:
            if not j.get(f"{arm}_fabricated"):
                continue
            flags += 1
            qid = j["question_id"]
            row = answers.get((qid, arm)) or {}
            ans = row.get("answer") or {}
            named = list(ans.get("papers_named") or [])
            notes = j.get("fabrication_notes") or ""
            # candidate titles the judge may have meant: quoted spans in the notes,
            # plus everything the answer committed to
            quoted = re.findall(r'"([^"]{6,140})"', notes)
            cands = list(dict.fromkeys(quoted + named))

            print(f"── {qid} [{arm}] fabricated=True "
                  f"(G{j[f'{arm}_groundedness']}/C{j[f'{arm}_correctness']}"
                  f"/U{j[f'{arm}_usefulness']})")
            if row.get("n_submits", 1) > 1 or row.get("is_error"):
                print(f"   ⚠️  row is suspect independently of the flag: "
                      f"n_submits={row.get('n_submits')} is_error={row.get('is_error')} "
                      f"answer={len(str(ans.get('answer','')))} chars, "
                      f"{len(named)} papers named")
            hits = []
            for c in cands:
                m = resolve(c, index)
                if m:
                    hits.append((c, *m))
            for c, pid, real in hits:
                print(f"   ✅ OVERTURNED — {c!r}")
                print(f"      resolves to {pid}: {real}")
            if hits:
                overturned += 1
            else:
                upheld += 1
                print(f"   ❌ UPHELD — nothing the judge named resolves to the corpus")
            print(f"   judge wrote: {notes[:200]}")
            print()

    # ── unrecognised titles (judge v2) ──────────────────────────────────────
    # Not a penalty — the judge sets this when it simply cannot place a paper.
    # Resolving them against the corpus is the whole point of the split: it turns
    # "I don't know this" into either "confirmed real" or "genuinely unverifiable
    # here", without ever asking the judge to guess.
    seen_any = False
    for j in judgements:
        for arm in ARMS:
            titles = [t.strip() for t in
                      re.split(r"[;\n]", str(j.get(f"{arm}_unrecognised_titles") or ""))
                      if t.strip() and t.strip().lower() != "none"]
            if not titles:
                continue
            if not seen_any:
                print("\n" + "=" * 70)
                print("UNRECOGNISED TITLES — adjudicated against the corpus\n")
                seen_any = True
            print(f"── {j['question_id']} [{arm}]")
            for t in titles:
                m = resolve(t, index)
                if m:
                    print(f"   ✅ REAL (in corpus) — {t!r}\n      {m[0]}: {m[1]}")
                else:
                    print(f"   ·  outside the corpus — {t!r}")
                    print(f"      unverifiable here; not evidence either way")
            print()

    print(f"{flags} fabrication flag(s): {overturned} overturned, {upheld} upheld.")
    if overturned:
        print("\nAn OVERTURNED flag means the judge called a real corpus paper "
              "invented.\nReport the corrected count as the headline and the raw "
              "judge count beside it —\nnot the other way round, and never only one "
              "of them.")


if __name__ == "__main__":
    main()
