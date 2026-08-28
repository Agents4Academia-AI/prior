#!/usr/bin/env python3
"""How the two environments actually got mixed. FREE — no model call, ever.

This is the pilot's real deliverable. Three questions cannot separate two hybrids
on judge scores: the parent's judge moves an axis by about a point between runs
on identical answers, which is larger than any difference this n could detect.
The ROUTING is not noise-limited — it is a deterministic property of the logged
calls, and it answers the question that was actually asked: does an agent handed
both environments use them well, and does telling it how to change what it does?

WHAT IS MEASURED, per (question, arm)

  first_tool        which environment it reached for first.
  atlas_first       did any atlas call precede any web call.
  n_atlas / n_web   how the calls split.
  payload split     how the CHARACTERS split — a WebFetch dwarfs a find_paper,
                    so call counts alone overstate how much web there was.

  web call classification — each web call is put in one of three buckets by
  replaying the atlas calls that preceded it and seeing what the agent already
  had in hand when it searched:

    COVERAGE      the query mentions nothing the atlas had already surfaced.
                  Reaching outside for material the atlas does not hold — the
                  intended use.
    VERIFICATION  the query names a paper the atlas had ALREADY returned. The
                  agent is checking something it was told, which is trigger 3
                  of the routing policy and the behaviour q06 needed.
    OPENING       the call happened before any atlas call at all. The agent
                  never asked the atlas, so it cannot know whether it was
                  duplicating work.

  The classifier is a heuristic on a small n and it is reported as evidence to
  read, not as a statistic: every query string is printed verbatim underneath so
  the bucket can be checked by eye. That is the point of printing them.

REPLAY, NOT RECONSTRUCTION. The atlas is local and deterministic, so re-issuing
the logged `tool_args` returns exactly the bytes the agent saw. Nothing here is
inferred from what the answer says.

  python routing.py                      # the table + every web query
  python routing.py --questions q06      # one question
  python routing.py --compare            # against the parent's graph/web arms
  python routing.py --md > routing.md    # markdown, for the report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))
sys.path.insert(0, str(PARENT.parent / "graph_vs_web_ideation"))

from graph_tools import GraphAtlas                                   # noqa: E402

HYBRID_ANSWERS = HERE / "out" / "answers.jsonl"
PARENT_ANSWERS = PARENT / "out" / "answers.jsonl"                    # READ-ONLY
WEB_TOOLS = ("WebSearch", "WebFetch")
GRAPH_PREFIX = "mcp__graph__"

# a title has to be this long before a match means anything — "AIDE" or "MLE"
# would hit half the web queries by accident
_MIN_TITLE_WORDS = 3

# Matching a title against a query by SUBSTRING is far too strict, and it got the
# first batch's only web call wrong. The agent searched
#   AIDE "AI-Driven Exploration" Jiang Schmidt Weco machine learning engineering
# for a paper the atlas had already handed it as
#   AIDE: AI-Driven Exploration in the Space of Code
# — plainly the same paper, plainly a check of something it had already been
# told, but not a substring, so it was filed as COVERAGE when it is
# VERIFICATION. Overlap of content words is the right test: a query that carries
# most of a title's distinctive words is about that paper however it is phrased.
_MATCH_RATIO = 0.6
_STOP = {"a", "an", "and", "the", "of", "for", "in", "on", "to", "with", "from",
         "at", "by", "is", "are", "as", "via", "into", "over", "toward",
         "towards", "using", "use", "its", "it", "this", "that", "we", "can",
         "do", "does"}


def content_words(s: str) -> set[str]:
    return {w for w in norm(s).split() if w not in _STOP and len(w) > 2}


def mentions(title: str, query_norm: str) -> bool:
    """Does this query appear to be about this paper?"""
    if norm(title) and norm(title) in query_norm:
        return True
    tw = content_words(title)
    if len(tw) < _MIN_TITLE_WORDS:
        return False
    qw = set(query_norm.split())
    return len(tw & qw) / len(tw) >= _MATCH_RATIO


def _read(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def titles_in(obj) -> set[str]:
    """Every paper title anywhere in a tool result, however deeply nested."""
    found: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("title", "paper_title", "paper") and isinstance(v, str):
                    found.add(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            # paper_neighbourhood serialises edges as pipe-delimited lines:
            #   "<- builds_on | Some Paper Title | openalex:W...::k01"
            if "|" in o:
                for part in o.split("|")[1:]:
                    part = part.strip()
                    if len(part.split()) >= _MIN_TITLE_WORDS and "::" not in part:
                        found.add(part)

    walk(obj)
    return {t for t in found if len(t.split()) >= _MIN_TITLE_WORDS}


def replay(atlas: GraphAtlas, call: dict):
    """Re-issue one logged atlas call. Deterministic — same bytes the agent saw."""
    name = call["tool"].replace(GRAPH_PREFIX, "")
    fn = getattr(atlas, name, None)
    if fn is None:
        return None
    args = dict(call.get("args") or {})
    import inspect
    ok = set(inspect.signature(fn).parameters)
    try:
        return fn(**{k: v for k, v in args.items() if k in ok})
    except Exception as e:                       # a pilot script must not die here
        return {"_replay_error": f"{type(e).__name__}: {e}"}


def query_text(call: dict) -> str:
    a = call.get("args") or {}
    return str(a.get("query") or a.get("url") or a.get("prompt") or "")


def analyse(row: dict, atlas: GraphAtlas) -> dict:
    calls = row.get("tool_args") or []
    seen_titles: set[str] = set()
    n_atlas = n_web = 0
    atlas_chars = web_chars = 0
    web_calls: list[dict] = []

    for c in calls:
        tool = c["tool"]
        chars = c.get("result_chars") or 0
        if tool.startswith(GRAPH_PREFIX):
            n_atlas += 1
            atlas_chars += chars
            seen_titles |= titles_in(replay(atlas, c))
        elif tool in WEB_TOOLS:
            n_web += 1
            web_chars += chars
            q = query_text(c)
            qn = norm(q)
            hits = sorted(t for t in seen_titles if mentions(t, qn))
            if n_atlas == 0:
                bucket = "OPENING"
            elif hits:
                bucket = "VERIFICATION"
            else:
                bucket = "COVERAGE"
            web_calls.append({"tool": tool, "query": q, "bucket": bucket,
                              "matched": hits, "chars": chars,
                              "after_atlas_calls": n_atlas})

    seq = [c["tool"].replace(GRAPH_PREFIX, "") for c in calls]
    return {
        "question_id": row["question_id"], "arm": row["arm"],
        "sequence": seq, "first_tool": seq[0] if seq else None,
        "atlas_first": bool(seq) and seq[0] not in WEB_TOOLS,
        "n_atlas": n_atlas, "n_web": n_web,
        "atlas_chars": atlas_chars, "web_chars": web_chars,
        "payload_chars": row.get("payload_chars"),
        "web_calls": web_calls,
        "titles_surfaced": len(seen_titles),
        "cost_usd": row.get("total_cost_usd"), "seconds": row.get("seconds"),
        "papers_named": len((row.get("answer") or {}).get("papers_named") or []),
    }


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", help="comma-separated question_ids")
    ap.add_argument("--compare", action="store_true",
                    help="include the parent's graph and web arms for the same questions")
    ap.add_argument("--md", action="store_true", help="markdown output")
    ap.add_argument("--json", action="store_true", help="dump the analysis as JSON")
    args = ap.parse_args()

    rows = _read(HYBRID_ANSWERS)
    if not rows:
        sys.exit(f"no hybrid answers at {HYBRID_ANSWERS} — run hybrid_gen.py first.")
    qids = ({q.strip() for q in args.questions.split(",")} if args.questions
            else {r["question_id"] for r in rows})
    rows = [r for r in rows if r["question_id"] in qids and r.get("answer")]
    if args.compare:
        rows += [r for r in _read(PARENT_ANSWERS)
                 if r["question_id"] in qids and r["arm"] in ("graph", "web")
                 and r.get("answer")]
    rows.sort(key=lambda r: (r["question_id"], r["arm"]))

    atlas = GraphAtlas()
    res = [analyse(r, atlas) for r in rows]

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    B, EOL = ("**", "  ") if args.md else ("", "")
    if args.md:
        print("### Routing\n")
        print("| qid | arm | first | atlas | web | atlas chars | web chars | "
              "cover | verify | open |")
        print("|---|---|---|---|---:|---:|---:|---:|---:|---:|")
        for a in res:
            b = lambda k: sum(1 for w in a["web_calls"] if w["bucket"] == k)  # noqa: E731
            print(f"| {a['question_id']} | `{a['arm']}` | `{a['first_tool']}` | "
                  f"{a['n_atlas']} | {a['n_web']} | {a['atlas_chars']:,} | "
                  f"{a['web_chars']:,} | {b('COVERAGE')} | {b('VERIFICATION')} | "
                  f"{b('OPENING')} |")
        print()
    else:
        print(f"{'qid':5} {'arm':16} {'first':22} {'atlas':>5} {'web':>4} "
              f"{'atlas ch':>9} {'web ch':>8}  buckets")
        print("-" * 92)
        for a in res:
            b = {k: sum(1 for w in a["web_calls"] if w["bucket"] == k)
                 for k in ("COVERAGE", "VERIFICATION", "OPENING")}
            tag = " ".join(f"{k[:4].lower()}={v}" for k, v in b.items() if v)
            print(f"{a['question_id']:5} {a['arm']:16} {str(a['first_tool'])[:22]:22} "
                  f"{a['n_atlas']:>5} {a['n_web']:>4} {a['atlas_chars']:>9,} "
                  f"{a['web_chars']:>8,}  {tag or '(no web calls)'}")

    # the evidence, verbatim — the classifier above is a heuristic and this is
    # what lets a reader overrule it
    print(("\n#### Web queries, in order\n" if args.md else "\nWEB QUERIES, IN ORDER"))
    any_web = False
    for a in res:
        if not a["web_calls"]:
            continue
        any_web = True
        print(f"\n{B}{a['question_id']} · {a['arm']}{B}{EOL}")
        for w in a["web_calls"]:
            m = f"  [matched: {'; '.join(w['matched'])[:90]}]" if w["matched"] else ""
            print(f"  {w['bucket']:12} {w['tool']:10} after {w['after_atlas_calls']} "
                  f"atlas call(s), {w['chars']:,}ch{EOL}")
            print(f"      {w['query'][:160]}{m}{EOL}")
    if not any_web:
        print("  (none — no arm reached for the browser)")

    print(("\n#### Call sequences\n" if args.md else "\nCALL SEQUENCES"))
    for a in res:
        print(f"  {a['question_id']} {a['arm']:16} "
              f"{' -> '.join(a['sequence']) or '(none)'}{EOL}")


if __name__ == "__main__":
    main()
