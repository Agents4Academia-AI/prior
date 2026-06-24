"""LLM self-evaluation — Claude audits its own extraction.

For a collection, the judge labels contributions, edges, and claims as
correct / incorrect / unsure, grounded in the stored quote / evidence. Verdicts
are written into the SAME annotation store under the annotator name `claude`, so
the eval scorecard gets three views for free:
  - self-eval     = annotations by `claude`
  - human-only    = annotations by real users (sparse)
  - aggregated    = per item, the human label if present, else `claude`'s

First-class: `prior selfeval --collection <name> [--kind ...] [--sample N]`.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from . import config, graph, llm

JUDGE = "claude"

_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["correct", "incorrect", "unsure"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict"],
}

_SYS = {
    "contribution": (
        "You audit automatically-extracted research contributions. Given a STATEMENT "
        "extracted as a paper's contribution and a verbatim QUOTE from that paper, judge "
        "whether the statement is a faithful, accurate representation grounded in the text. "
        "correct = faithful and supported; incorrect = misstates / overclaims / unsupported; "
        "unsure = genuinely cannot tell from the quote."),
    "edge": (
        "You audit cross-paper relations. Two research contributions A (source) and B "
        "(target) are linked by RELATION ∈ {supports, builds_on, refines, contradicts}. "
        "Judge whether that relation genuinely holds, in that direction. correct = it holds; "
        "incorrect = wrong type, wrong direction, or no real relation; unsure = cannot tell."),
    "claim": (
        "You audit extracted scientific claims. Given a CLAIM and the EVIDENCE span it was "
        "extracted from, judge whether the evidence actually supports the claim. correct = "
        "supported and faithful; incorrect = unsupported / distorted; unsure = cannot tell."),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sample(collection: str, kind: str, n: int) -> list[dict]:
    lim = "" if n <= 0 else f"ORDER BY rand() LIMIT {int(n)}"
    with graph.session() as s:
        if kind == "contribution":
            return [dict(r) for r in s.run(
                f"MATCH (k:Contribution {{collection:$c}}) "
                f"RETURN k.id AS key, k.statement AS statement, k.quote AS quote {lim}", c=collection)]
        if kind == "claim":
            return [dict(r) for r in s.run(
                f"MATCH (c:Claim {{collection:$c}}) "
                f"RETURN c.id AS key, c.text AS text, c.evidence AS evidence {lim}", c=collection)]
        if kind == "edge":
            return [dict(r) for r in s.run(
                f"MATCH (a:Contribution {{collection:$c}})-[r]->(b:Contribution {{collection:$c}}) "
                f"WHERE type(r) IN ['SUPPORTS','BUILDS_ON','REFINES','CONTRADICTS'] "
                f"RETURN a.id AS src, b.id AS dst, type(r) AS rel, "
                f"a.statement AS a_stmt, b.statement AS b_stmt {lim}", c=collection)]
    return []


def _prompt(kind: str, it: dict) -> tuple[str, str]:
    if kind == "contribution":
        return it["key"], f"STATEMENT:\n{it.get('statement','')}\n\nQUOTE:\n{it.get('quote','') or '(none provided)'}"
    if kind == "claim":
        return it["key"], f"CLAIM:\n{it.get('text','')}\n\nEVIDENCE:\n{it.get('evidence','') or '(none provided)'}"
    # edge
    key = f"{it['src']}|{it['rel']}|{it['dst']}"
    rel = it["rel"].lower()
    return key, (f"A (source): {it.get('a_stmt','')}\n\nB (target): {it.get('b_stmt','')}\n\n"
                 f"RELATION: A {rel} B")


def _judge_one(kind: str, it: dict, model: str) -> tuple[str, bool]:
    key, user = _prompt(kind, it)
    out = llm.structured(model=model, system=_SYS[kind], user=user,
                         schema=_SCHEMA, tool_name="judge")
    verdict = out.get("verdict", "unsure")
    if verdict not in ("correct", "incorrect", "unsure"):
        verdict = "unsure"
    graph.upsert_annotation(JUDGE, kind, key, faithful=verdict, issues=[],
                            soundness="", note=(out.get("reason") or "")[:300], created_at=_now())
    return key, True


def run(collection: str, *, kinds: list[str] | None = None, sample: int = 40,
        workers: int | None = None, model: str | None = None, progress=print) -> dict:
    """Judge a sample of each kind and store verdicts as `claude` annotations."""
    graph.setup_schema()
    kinds = kinds or ["contribution", "edge", "claim"]
    model = model or config.READER_MODEL
    workers = workers or int(os.environ.get("PRIOR_WORKERS", "6"))
    done = {}
    for kind in kinds:
        items = _sample(collection, kind, sample)
        progress(f"{kind}: judging {len(items)} items")
        n = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_judge_one, kind, it, model) for it in items]
            for i, f in enumerate(as_completed(futs), 1):
                try:
                    f.result(); n += 1
                    if i % 10 == 0:
                        progress(f"  {kind}: {i}/{len(items)}")
                except Exception as e:  # noqa: BLE001
                    progress(f"  {kind}: ERROR {e}")
        done[kind] = n
    progress(f"self-eval done: {done}")
    return done
