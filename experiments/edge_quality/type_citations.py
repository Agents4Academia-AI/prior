#!/usr/bin/env python3
"""Type/verify the intra-corpus citation edges with RefWarden (Milestone 2, Stage 1).

For every citation edge in ``out/citation_map.json`` (the 525 resolved pairs), and
for every claim-site where the citing paper cites the target, ask RefWarden's
relevance judge: does the cited paper's abstract SUPPORT the claim, and how
NECESSARY is the citation there? Emits, per edge, RefWarden's axes:

    supports_claim : supports | partial | does_not | inconclusive | skipped
    priority       : obligatory | helpful

Evidence is the cited paper's abstract only (from the bundle) — ``resolved=None``,
so there are NO network fetches. The LLM runs on the Claude Code SUBSCRIPTION; the
script ABORTS if RefWarden's auth would resolve to a metered API key.

USAGE-EXHAUSTION SAFETY (learned the hard way):
    When the Claude subscription usage runs out mid-run, RefWarden's judge does NOT
    raise — it silently degrades every remaining site to a FAILURE verdict
    (``supports_claim=inconclusive``, ``priority=None``, justification
    "batch judge returned no verdict"). A naive loop checkpoints those dead rows and
    writes a "finished" file that is mostly junk. This script:
      • never checkpoints a failure verdict,
      • retries the failed sites once (rides out a transient blip),
      • if they still fail, STOPS CLEANLY — every good verdict is already saved,
      • self-heals an already-polluted checkpoint by purging dead rows on load,
    so re-running always resumes from the true last-good site, never redoing work.

Resumable: good verdicts are checkpointed per claim-site after every batch. Re-run to
continue. ``--fresh`` ignores the checkpoint and starts over.

Manual pause: create an empty file ``out/STOP`` (e.g. ``touch out/STOP``) and the run
finishes the current batch, flushes, and exits. Delete it and re-run to continue.
Ctrl-C also exits cleanly (the current in-flight batch is discarded, not corrupted).

Model: defaults to ``claude-sonnet-5`` (Pro-friendly). Override with ``--model``.

Usage (from repo root, with the prior venv active):
    python experiments/edge_quality/type_citations.py                    # all, sonnet-5
    python experiments/edge_quality/type_citations.py --model claude-opus-4-8
    python experiments/edge_quality/type_citations.py --limit 20         # first 20 edges
    python experiments/edge_quality/type_citations.py --fresh            # ignore checkpoint
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

try:  # Windows consoles default to cp1252 and choke on non-ASCII (incl. --help text).
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[2]          # …/prior
OUT = REPO / "experiments" / "edge_quality" / "out"

# Rank for choosing an edge-level support verdict from its per-site verdicts.
_SUPPORT_RANK = {"supports": 4, "partial": 3, "does_not": 2, "inconclusive": 1, "skipped": 0}

# Justifications RefWarden emits when a chunk FAILED (no model output) — NOT a real
# verdict. These mean "transient failure / usage exhausted", so we never persist them.
# (A legit empty-evidence abstain says "no abstract or introduction to judge from" and
# IS permanent — but we pre-filter empty abstracts, so it never reaches the judge here.)
_FAILED_JUSTIFS = {"batch judge returned no verdict", "no verdict"}


def _verdict_failed(v) -> bool:
    """True if a RelevanceVerdict is RefWarden's degrade-on-failure placeholder."""
    return (getattr(v, "justification", None) or "") in _FAILED_JUSTIFS


def _row_failed(r: dict) -> bool:
    """True if a checkpoint row is a persisted failure placeholder (self-heal)."""
    return (r.get("justification") or "") in _FAILED_JUSTIFS


def edge_id(citing: str, cited: str) -> str:
    return f"{citing}->{cited}"


def load_inputs():
    cm = json.load(open(OUT / "citation_map.json", encoding="utf-8"))
    papers = {}
    for line in open(REPO / "data" / "prior-core-v0.2" / "papers_core.jsonl", encoding="utf-8"):
        if line.strip():
            p = json.loads(line)
            papers[p["id"]] = p
    return cm, papers


def build_sites(cm, papers, limit):
    """One work-item per (edge, claim-site). Stable ``site_key`` for checkpointing."""
    sites = []
    for rec in cm[: limit or None]:
        citing, cited = rec["citing_id"], rec["cited_id"]
        abstract = (papers.get(cited, {}) or {}).get("abstract") or ""
        for i, ctx in enumerate(rec.get("contexts") or []):
            claim = (ctx.get("text") or "").strip()
            if not claim or not abstract:
                continue
            sites.append({
                "site_key": f"{edge_id(citing, cited)}#{i}",
                "citing_id": citing, "cited_id": cited, "cite_key": rec["cite_key"],
                # cite_key passed to the judge is the EDGE id, so it groups sites of the
                # SAME edge (one abstract sent once) and never collides across edges.
                "judge_item": {"cite_key": edge_id(citing, cited), "claim_id": f"{edge_id(citing, cited)}#{i}",
                               "claim": claim, "abstract": abstract, "resolved": None},
            })
    return sites


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="cap number of EDGES (0 = all 525)")
    ap.add_argument("--batch", type=int, default=40, help="claim-sites per checkpoint flush (default 40)")
    ap.add_argument("--model", default="claude-sonnet-5",
                    help="judge model (sets MODEL_JUDGE). Default claude-sonnet-5 (Pro-friendly).")
    ap.add_argument("--out", default=str(OUT / "citations_typed.json"))
    ap.add_argument("--checkpoint", default=str(OUT / "citations_typed.ckpt.json"))
    ap.add_argument("--fresh", action="store_true", help="ignore any existing checkpoint")
    args = ap.parse_args()

    # Model must be set BEFORE load_settings() so it flows into settings.model_judge.
    os.environ["MODEL_JUDGE"] = args.model

    # RefWarden: prefer the installed package; fall back to the sibling source checkout.
    try:
        from citation_verifier.config import load_settings, apply_auth
        from citation_verifier.backends.relevance_judge import build_relevance_judge
    except ImportError:
        src = REPO.parent / "citation_verification" / "src"
        if src.is_dir():
            sys.path.insert(0, str(src))
        from citation_verifier.config import load_settings, apply_auth
        from citation_verifier.backends.relevance_judge import build_relevance_judge

    # ── HARD COST GUARD ───────────────────────────────────────────────────────
    settings = load_settings()
    auth = apply_auth(settings)
    if auth != "subscription":
        print(f"ABORT: RefWarden auth resolves to '{auth}', not 'subscription'. "
              f"Unset ANTHROPIC_API_KEY (and any .env key) to use the subscription.", file=sys.stderr)
        return 2
    print(f"[guard] auth = {auth} (safe, no metered API)")

    cm, papers = load_inputs()
    sites = build_sites(cm, papers, args.limit)
    n_edges = len({s["site_key"].split("#")[0] for s in sites})
    print(f"[data]  {n_edges} edges | {len(sites)} claim-sites to judge")

    ckpt_path = Path(args.checkpoint)
    stop_path = OUT / "STOP"
    done: dict[str, dict] = {}
    if ckpt_path.exists() and not args.fresh:
        raw = json.load(open(ckpt_path, encoding="utf-8"))
        purged = {k: v for k, v in raw.items() if _row_failed(v)}
        done = {k: v for k, v in raw.items() if not _row_failed(v)}
        msg = f"[resume] {len(done)} good sites in checkpoint"
        if purged:
            msg += f" | purged {len(purged)} dead 'no verdict' rows (usage-exhaustion junk)"
            json.dump(done, open(ckpt_path, "w", encoding="utf-8"), indent=1)  # persist the heal
        print(msg + f" -> {ckpt_path.name}")
    todo = [s for s in sites if s["site_key"] not in done]
    print(f"[run]   {len(todo)} sites remaining\n")
    if not todo:
        print("[run]   nothing to do — all sites already judged.")

    judge = build_relevance_judge(settings)
    if judge is None:
        print("ABORT: no relevance judge available (Claude Agent SDK missing?).", file=sys.stderr)
        return 2
    print(f"[model] judge = {judge.model}\n")

    def record(chunk, verdicts) -> int:
        """Persist only GOOD verdicts; return count of still-failed sites in this chunk."""
        failed = 0
        for s, v in zip(chunk, verdicts):
            if _verdict_failed(v):
                failed += 1
                continue
            done[s["site_key"]] = {
                "citing_id": s["citing_id"], "cited_id": s["cited_id"], "cite_key": s["cite_key"],
                "supports_claim": v.supports_claim.value,
                "priority": v.priority.value if v.priority else None,
                "confidence": v.confidence,
                "justification": v.justification,
                "model": judge.model,
                "claim": s["judge_item"]["claim"][:400],
            }
        return failed

    t0 = time.time()
    stopped = None  # reason string if we halt early
    try:
        for start in range(0, len(todo), args.batch):
            if stop_path.exists():
                stopped = f"manual STOP file present ({stop_path})"
                break

            chunk = todo[start:start + args.batch]
            verdicts = judge.judge_batch([s["judge_item"] for s in chunk])

            # One retry of just the failed sites — rides out a transient hiccup.
            fail_ix = [i for i, v in enumerate(verdicts) if _verdict_failed(v)]
            if fail_ix:
                retry = judge.judge_batch([chunk[i]["judge_item"] for i in fail_ix])
                for j, i in enumerate(fail_ix):
                    verdicts[i] = retry[j]

            failed = record(chunk, verdicts)
            json.dump(done, open(ckpt_path, "w", encoding="utf-8"), indent=1)  # checkpoint good rows

            n = len(done)
            sc = Counter(r["supports_claim"] for r in done.values())
            pr = Counter(r["priority"] for r in done.values())
            elapsed = time.time() - t0
            print(f"[{n:4}/{len(sites)}] +{len(chunk) - failed:2}  "
                  f"support:{dict(sc)}  priority:{dict(pr)}  "
                  f"| {judge.calls} calls | {elapsed:5.0f}s", flush=True)

            if failed:
                stopped = (f"{failed}/{len(chunk)} sites still failed after retry — "
                           f"subscription usage is almost certainly exhausted")
                break
    except KeyboardInterrupt:
        stopped = "KeyboardInterrupt (Ctrl-C) — current batch discarded, saved rows intact"

    # ── aggregate the GOOD per-site verdicts up to edge level ──────────────────
    edges: dict[str, dict] = {}
    for r in done.values():
        eid = edge_id(r["citing_id"], r["cited_id"])
        e = edges.setdefault(eid, {"citing_id": r["citing_id"], "cited_id": r["cited_id"],
                                   "cite_key": r["cite_key"], "sites": []})
        e["sites"].append({k: r[k] for k in ("supports_claim", "priority", "confidence", "justification", "claim")})
    for e in edges.values():
        sup = [s["supports_claim"] for s in e["sites"]]
        prios = [s["priority"] for s in e["sites"] if s["priority"]]
        e["support"] = max(sup, key=lambda x: _SUPPORT_RANK.get(x, 0))   # strongest across sites
        e["any_does_not"] = "does_not" in sup                             # misuse flag
        e["priority"] = "obligatory" if "obligatory" in prios else ("helpful" if prios else None)
        e["n_sites"] = len(e["sites"])

    complete = stopped is None and len(done) >= len(sites)
    out = {
        "edges": list(edges.values()),
        "meta": {
            "complete": complete,
            "n_expected_sites": len(sites), "n_judged_sites": len(done), "n_edges": len(edges),
            "models": sorted({r.get("model") for r in done.values() if r.get("model")}),
            "edge_support_distribution": dict(Counter(e["support"] for e in edges.values())),
            "edge_priority_distribution": dict(Counter(e["priority"] for e in edges.values())),
            "site_support_distribution": dict(Counter(r["supports_claim"] for r in done.values())),
            "edges_with_a_does_not_site": sum(e["any_does_not"] for e in edges.values()),
            "evidence": "abstract-only (L0)", "seconds": round(time.time() - t0, 1),
            "stopped_reason": stopped,
        },
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=1)
    m = out["meta"]
    banner = "COMPLETE" if complete else "STOPPED EARLY — RE-RUN TO CONTINUE"
    print(f"\n[{banner}] {m['n_judged_sites']}/{m['n_expected_sites']} sites | "
          f"{m['n_edges']} edges | models={m['models']} | {m['seconds']}s")
    if stopped:
        print(f"  reason: {stopped}")
        if "usage" in stopped:
            print("  -> wait for your usage to reset, then re-run the same command; it resumes here.")
    print(f"  edge support : {m['edge_support_distribution']}")
    print(f"  edge priority: {m['edge_priority_distribution']}")
    print(f"  edges with a does_not site: {m['edges_with_a_does_not_site']}")
    print(f"  -> {args.out}")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
