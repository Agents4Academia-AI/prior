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


def _key_of(kind: str, it: dict) -> str:
    return it["key"] if kind != "edge" else f"{it['src']}|{it['rel']}|{it['dst']}"


def _judged_keys(kind: str) -> set[str]:
    """Targets this judge has already labelled — so runs are incremental/resumable."""
    with graph.session() as s:
        return {r["k"] for r in s.run(
            "MATCH (a:Annotation {annotator:$j, target_kind:$kind}) RETURN a.target_key AS k",
            j=JUDGE, kind=kind)}


def _candidates(collection: str, kind: str) -> list[dict]:
    with graph.session() as s:
        if kind == "contribution":
            return [dict(r) for r in s.run(
                "MATCH (k:Contribution {collection:$c}) "
                "RETURN k.id AS key, k.statement AS statement, k.quote AS quote", c=collection)]
        if kind == "claim":
            return [dict(r) for r in s.run(
                "MATCH (c:Claim {collection:$c}) "
                "RETURN c.id AS key, c.text AS text, c.evidence AS evidence", c=collection)]
        if kind == "edge":
            return [dict(r) for r in s.run(
                "MATCH (a:Contribution {collection:$c})-[r]->(b:Contribution {collection:$c}) "
                "WHERE type(r) IN ['SUPPORTS','BUILDS_ON','REFINES','CONTRADICTS'] "
                "RETURN a.id AS src, b.id AS dst, type(r) AS rel, r.evidence AS evidence, "
                "a.statement AS a_stmt, b.statement AS b_stmt", c=collection)]
    return []


def _remaining(collection: str, kind: str, limit: int) -> list[dict]:
    """All not-yet-judged items of `kind` (optionally capped to `limit` for this run)."""
    skip = _judged_keys(kind)
    rem = [it for it in _candidates(collection, kind) if _key_of(kind, it) not in skip]
    return rem[:limit] if limit and limit > 0 else rem


def _prompt(kind: str, it: dict) -> tuple[str, str]:
    key = _key_of(kind, it)
    if kind == "contribution":
        return key, f"STATEMENT:\n{it.get('statement','')}\n\nQUOTE:\n{it.get('quote','') or '(none provided)'}"
    if kind == "claim":
        return key, f"CLAIM:\n{it.get('text','')}\n\nEVIDENCE:\n{it.get('evidence','') or '(none provided)'}"
    rel = it["rel"].lower()
    return key, (f"A (source): {it.get('a_stmt','')}\n\nB (target): {it.get('b_stmt','')}\n\n"
                 f"RELATION: A {rel} B\n\nWHY (extracted reasoning): {it.get('evidence','') or '(none)'}")


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


def run(collection: str, *, kinds: list[str] | None = None, limit: int = 0,
        workers: int | None = None, model: str | None = None, progress=print) -> dict:
    """Judge every not-yet-judged item of each kind (incremental/resumable), storing
    verdicts as `claude` annotations. `limit` > 0 caps how many to do this run."""
    graph.setup_schema()
    kinds = kinds or ["contribution", "edge", "claim"]
    model = model or config.READER_MODEL
    workers = workers or int(os.environ.get("PRIOR_WORKERS", "6"))
    done = {}
    for kind in kinds:
        items = _remaining(collection, kind, limit)
        already = len(_judged_keys(kind))
        progress(f"{kind}: {already} already judged · judging {len(items)} more")
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
