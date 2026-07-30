#!/usr/bin/env python3
"""Stage 2.5 — claim LOCALIZATION + single-model re-judge of the distrust buckets.

WHY. 84% of citation contexts are multi-cite sentences/paragraphs; the L0 run judged
the cited paper's abstract against the WHOLE paragraph, so a citee often got scored on
a NEIGHBOUR's clause. That produced false `does_not` (91% of does_not were multi-cite)
and muddy `inconclusive`. Every context carries `target_offset` (the exact position of
the `[CITED:TARGET]` marker), so we can send the model just the TARGET's sentence with
the target citation kept as `[CITED]` and sibling citations stripped.

WHAT. Re-judge ONLY the distrust buckets from the completed L0 checkpoint
(default: does_not + inconclusive) with the localized claim, a SINGLE model
(claude-sonnet-5), abstract-only (L0), and a hard CAP on claims per LLM call
(rubber-stamping was observed when ~60 claims were crammed into one call). Writes a
NEW file with an old->new transition matrix; never overwrites citations_typed.json.

Validated finding this rests on (2026-07-29): full-text escalation changes ~0 verdicts
(0/6) because the stuck claims are MIS-LOCALIZED, not missing-evidence. Localization —
not more evidence — is the lever. See MILESTONE_2_QUICKSTART.md Stage 2.5 / 2.6.

Same cost guards as type_citations.py: aborts on a metered key; subscription only;
resumable checkpoint; manual STOP file; never persists a failure verdict.

Usage (repo root, prior venv):
    python experiments/edge_quality/localize_rejudge.py --dry-run   # localize only, no LLM
    python experiments/edge_quality/localize_rejudge.py             # re-judge does_not+inconclusive
    python experiments/edge_quality/localize_rejudge.py --buckets does_not
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "experiments" / "edge_quality" / "out"
_FAILED_JUSTIFS = {"batch judge returned no verdict", "no verdict"}
_TARGET = "[CITED:TARGET]"

# Abbreviations whose trailing '.' must NOT end a sentence.
_ABBREV = re.compile(r"(?:e\.g|i\.e|et al|cf|vs|fig|eq|sec|no|dr|mr|ms|prof|approx|resp|etc|al)\.\s*$", re.I)
# A sentence terminator followed by whitespace + a capital / opening bracket (or end).
_SENT_END = re.compile(r"[.?!][\"')\]]?(?=\s+[A-Z(\[]|\s*$)")


def edge_id(citing: str, cited: str) -> str:
    return f"{citing}->{cited}"


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENT_END.finditer(text):
        if _ABBREV.search(text[start : m.start() + 1]):
            continue
        spans.append((start, m.end()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def localize(text: str, target_offset: int) -> str:
    """Return the TARGET citation's sentence, target kept as [CITED], siblings stripped.

    Falls back to a ±120-char window if sentence detection can't bracket the target,
    and expands to include a neighbour sentence if the target's sentence is very short.
    """
    spans = _sentence_spans(text)
    hit = next((i for i, (s, e) in enumerate(spans) if s <= target_offset < e), None)
    if hit is None:
        s, e = max(0, target_offset - 120), min(len(text), target_offset + 120)
    else:
        s, e = spans[hit]
        if e - s < 40:  # too short — glue the following (else preceding) sentence
            if hit + 1 < len(spans):
                e = spans[hit + 1][1]
            elif hit - 1 >= 0:
                s = spans[hit - 1][0]
    seg = text[s:e]
    seg = seg.replace(_TARGET, "\x00").replace("[CITED]", "").replace("\x00", "[CITED]")
    return re.sub(r"\s+", " ", seg).strip()


def load_inputs():
    cm = json.load(open(OUT / "citation_map.json", encoding="utf-8"))
    papers = {}
    for line in open(REPO / "data" / "prior-core-v0.2" / "papers_core.jsonl", encoding="utf-8"):
        if line.strip():
            p = json.loads(line)
            papers[p["id"]] = p
    return cm, papers


def build_subset(cm, papers, old, buckets):
    """Rebuild sites exactly as the L0 run did; keep those whose OLD verdict is in `buckets`."""
    sites = []
    for rec in cm:
        citing, cited = rec["citing_id"], rec["cited_id"]
        abstract = (papers.get(cited, {}) or {}).get("abstract") or ""
        for i, ctx in enumerate(rec.get("contexts") or []):
            raw = (ctx.get("text") or "").strip()
            if not raw or not abstract:
                continue
            site_key = f"{edge_id(citing, cited)}#{i}"
            prev = old.get(site_key)
            if not prev or prev.get("supports_claim") not in buckets:
                continue
            loc = localize(ctx.get("text") or "", int(ctx.get("target_offset") or 0))
            sites.append({
                "site_key": site_key, "citing_id": citing, "cited_id": cited,
                "cite_key": rec["cite_key"],
                "old": prev, "loc_claim": loc, "raw_claim": raw,
                # UNIQUE cite_key per site => each is its own group => the --max-claims
                # cap on citations-per-chunk becomes a hard cap on CLAIMS per LLM call.
                "judge_item": {"cite_key": site_key, "claim_id": site_key,
                               "claim": loc, "abstract": abstract, "resolved": None},
            })
    return sites


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--buckets", default="does_not,inconclusive",
                    help="comma list of OLD supports_claim values to re-judge")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--max-claims", type=int, default=12, help="hard cap on claims per LLM call")
    ap.add_argument("--dry-run", action="store_true", help="localize + print samples, NO LLM calls")
    ap.add_argument("--source", default=str(OUT / "citations_typed.ckpt.json"),
                    help="the completed L0 checkpoint to read OLD verdicts from")
    ap.add_argument("--out", default=str(OUT / "citations_typed.localized.json"))
    ap.add_argument("--checkpoint", default=str(OUT / "citations_typed.localized.ckpt.json"))
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()
    buckets = {b.strip() for b in args.buckets.split(",") if b.strip()}

    cm, papers = load_inputs()
    old = json.load(open(args.source, encoding="utf-8"))
    sites = build_subset(cm, papers, old, buckets)
    n_multi = sum(s["raw_claim"].count("[CITED") >= 2 for s in sites)
    print(f"[data] buckets={sorted(buckets)} | {len(sites)} sites to re-judge "
          f"({n_multi} multi-cite, {100*n_multi//max(1,len(sites))}%)")

    if args.dry_run:
        print("\n[dry-run] localization samples (OLD verdict | raw -> localized):\n")
        for s in sites[:20]:
            print(f"  [{s['old']['supports_claim']}] raw: {s['raw_claim'][:150]}")
            print(f"        -> loc: {s['loc_claim'][:150]}\n")
        shrink = [1 - len(s["loc_claim"]) / max(1, len(s["raw_claim"])) for s in sites]
        print(f"[dry-run] mean length reduction: {100*sum(shrink)/len(shrink):.0f}%  "
              f"(no LLM calls made)")
        return 0

    os.environ["MODEL_JUDGE"] = args.model
    try:
        from citation_verifier.config import load_settings, apply_auth
        from citation_verifier.backends.relevance_judge import build_relevance_judge
    except ImportError:
        src = REPO.parent / "citation_verification" / "src"
        if src.is_dir():
            sys.path.insert(0, str(src))
        from citation_verifier.config import load_settings, apply_auth
        from citation_verifier.backends.relevance_judge import build_relevance_judge

    settings = load_settings()
    if apply_auth(settings) != "subscription":
        print("ABORT: auth is not 'subscription' (unset ANTHROPIC_API_KEY).", file=sys.stderr)
        return 2
    print("[guard] auth = subscription (safe, no metered API)")

    ckpt_path = Path(args.checkpoint)
    stop_path = OUT / "STOP"
    done: dict[str, dict] = {}
    if ckpt_path.exists() and not args.fresh:
        raw = json.load(open(ckpt_path, encoding="utf-8"))
        done = {k: v for k, v in raw.items() if (v.get("justification") or "") not in _FAILED_JUSTIFS}
        print(f"[resume] {len(done)} good sites already in checkpoint")
    todo = [s for s in sites if s["site_key"] not in done]
    print(f"[run] {len(todo)} sites remaining | model={args.model} | <= {args.max_claims} claims/call\n")

    judge = build_relevance_judge(settings)
    if judge is None:
        print("ABORT: no relevance judge available.", file=sys.stderr)
        return 2
    judge.batch_size = args.max_claims  # each site is its own group -> caps claims/call
    judge.escalate_full_text = False    # L0 only

    def failed(v) -> bool:
        return (getattr(v, "justification", None) or "") in _FAILED_JUSTIFS

    by_key = {s["site_key"]: s for s in sites}
    t0 = time.time()
    stopped = None
    try:
        for start in range(0, len(todo), args.max_claims):
            if stop_path.exists():
                stopped = f"manual STOP file present ({stop_path})"
                break
            chunk = todo[start : start + args.max_claims]
            verdicts = judge.judge_batch([s["judge_item"] for s in chunk])
            fail_ix = [i for i, v in enumerate(verdicts) if failed(v)]
            if fail_ix:
                retry = judge.judge_batch([chunk[i]["judge_item"] for i in fail_ix])
                for j, i in enumerate(fail_ix):
                    verdicts[i] = retry[j]
            nfail = 0
            for s, v in zip(chunk, verdicts):
                if failed(v):
                    nfail += 1
                    continue
                done[s["site_key"]] = {
                    "citing_id": s["citing_id"], "cited_id": s["cited_id"], "cite_key": s["cite_key"],
                    "old_supports_claim": s["old"]["supports_claim"],
                    "old_priority": s["old"].get("priority"),
                    "old_model": s["old"].get("model"),
                    "supports_claim": v.supports_claim.value,
                    "priority": v.priority.value if v.priority else None,
                    "confidence": v.confidence, "justification": v.justification,
                    "model": judge.model, "loc_claim": s["loc_claim"][:400],
                    "raw_claim": s["raw_claim"][:400],
                }
            json.dump(done, open(ckpt_path, "w", encoding="utf-8"), indent=1)
            elapsed = time.time() - t0
            print(f"[{len(done):4}/{len(sites)}] +{len(chunk)-nfail:2}  "
                  f"{judge.calls} calls | {elapsed:5.0f}s", flush=True)
            if nfail:
                stopped = f"{nfail}/{len(chunk)} still failed after retry — usage likely exhausted"
                break
    except KeyboardInterrupt:
        stopped = "KeyboardInterrupt — current batch discarded, saved rows intact"

    # transition matrix old -> new (only over sites we re-judged)
    trans: Counter = Counter()
    for r in done.values():
        trans[(r["old_supports_claim"], r["supports_claim"])] += 1
    changed = sum(n for (a, b), n in trans.items() if a != b)
    complete = stopped is None and len(done) >= len(sites)
    out = {
        "rejudged": list(done.values()),
        "meta": {
            "complete": complete, "buckets": sorted(buckets), "model": args.model,
            "n_sites": len(sites), "n_judged": len(done),
            "changed": changed, "unchanged": len(done) - changed,
            "old_distribution": dict(Counter(r["old_supports_claim"] for r in done.values())),
            "new_distribution": dict(Counter(r["supports_claim"] for r in done.values())),
            "transitions": {f"{a} -> {b}": n for (a, b), n in sorted(trans.items(), key=lambda kv: -kv[1])},
            "evidence": "abstract-only (L0), TARGET-sentence localized",
            "seconds": round(time.time() - t0, 1), "stopped_reason": stopped,
        },
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=1)
    m = out["meta"]
    print(f"\n[{'COMPLETE' if complete else 'STOPPED — RE-RUN TO CONTINUE'}] "
          f"{m['n_judged']}/{m['n_sites']} | changed {m['changed']}, unchanged {m['unchanged']}")
    if stopped:
        print(f"  reason: {stopped}")
    print(f"  old dist: {m['old_distribution']}")
    print(f"  new dist: {m['new_distribution']}")
    print(f"  transitions: {m['transitions']}")
    print(f"  -> {args.out}")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
