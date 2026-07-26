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

Resumable: verdicts are checkpointed per claim-site after every batch, so re-running
picks up where it left off. Use ``--fresh`` to ignore the checkpoint and start over.

Usage (from repo root, with the prior venv active):
    python experiments/edge_quality/type_citations.py                # full 525
    python experiments/edge_quality/type_citations.py --limit 20     # first 20 edges
    python experiments/edge_quality/type_citations.py --fresh        # ignore checkpoint
    python experiments/edge_quality/type_citations.py --batch 40     # checkpoint every 40 sites
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]          # …/prior
OUT = REPO / "experiments" / "edge_quality" / "out"

# RefWarden: prefer the installed package (the SHA-pinned dep); fall back to the
# sibling source checkout if it isn't installed in this interpreter.
try:
    from citation_verifier.config import load_settings, apply_auth
    from citation_verifier.backends.relevance_judge import build_relevance_judge
except ImportError:
    src = REPO.parent / "citation_verification" / "src"
    if src.is_dir():
        sys.path.insert(0, str(src))
    from citation_verifier.config import load_settings, apply_auth
    from citation_verifier.backends.relevance_judge import build_relevance_judge

# Rank for choosing an edge-level support verdict from its per-site verdicts.
_SUPPORT_RANK = {"supports": 4, "partial": 3, "does_not": 2, "inconclusive": 1, "skipped": 0}


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
    ap.add_argument("--out", default=str(OUT / "citations_typed.json"))
    ap.add_argument("--checkpoint", default=str(OUT / "citations_typed.ckpt.json"))
    ap.add_argument("--fresh", action="store_true", help="ignore any existing checkpoint")
    args = ap.parse_args()

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
    print(f"[data]  {n_edges} edges · {len(sites)} claim-sites to judge")

    ckpt_path = Path(args.checkpoint)
    done: dict[str, dict] = {}
    if ckpt_path.exists() and not args.fresh:
        done = json.load(open(ckpt_path, encoding="utf-8"))
        print(f"[resume] {len(done)} sites already in checkpoint → {ckpt_path.name}")
    todo = [s for s in sites if s["site_key"] not in done]
    print(f"[run]   {len(todo)} sites remaining\n")

    judge = build_relevance_judge(settings)
    if judge is None:
        print("ABORT: no relevance judge available (Claude Agent SDK missing?).", file=sys.stderr)
        return 2
    # Judge model comes from the MODEL_JUDGE env var (RefWarden default: claude-opus-4-8).
    # On a Pro subscription, set MODEL_JUDGE=claude-sonnet-5 to stay within usage limits.
    print(f"[model] judge = {judge.model}\n")

    t0 = time.time()
    for start in range(0, len(todo), args.batch):
        chunk = todo[start:start + args.batch]
        verdicts = judge.judge_batch([s["judge_item"] for s in chunk])
        for s, v in zip(chunk, verdicts):
            done[s["site_key"]] = {
                "citing_id": s["citing_id"], "cited_id": s["cited_id"], "cite_key": s["cite_key"],
                "supports_claim": v.supports_claim.value,
                "priority": v.priority.value if v.priority else None,
                "confidence": v.confidence,
                "justification": v.justification,
                "claim": s["judge_item"]["claim"][:400],
            }
        json.dump(done, open(ckpt_path, "w", encoding="utf-8"), indent=1)  # checkpoint

        n = len(done)
        sc = Counter(r["supports_claim"] for r in done.values())
        pr = Counter(r["priority"] for r in done.values())
        rate = (n - len(sites) + len(todo)) / max(time.time() - t0, 1e-9)  # sites/s this run
        eta = (len(todo) - (start + len(chunk))) / max(rate, 1e-9)
        print(f"[{n:4}/{len(sites)}] +{len(chunk):2}  "
              f"support:{dict(sc)}  priority:{dict(pr)}  "
              f"| {judge.calls} LLM calls | {time.time()-t0:5.0f}s  ETA {eta:4.0f}s", flush=True)

    # ── aggregate per-site verdicts up to edge level ──────────────────────────
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

    out = {
        "edges": list(edges.values()),
        "meta": {
            "n_edges": len(edges), "n_sites": len(done),
            "edge_support_distribution": dict(Counter(e["support"] for e in edges.values())),
            "edge_priority_distribution": dict(Counter(e["priority"] for e in edges.values())),
            "site_support_distribution": dict(Counter(r["supports_claim"] for r in done.values())),
            "edges_with_a_does_not_site": sum(e["any_does_not"] for e in edges.values()),
            "model": judge.model, "evidence": "abstract-only (L0)", "seconds": round(time.time() - t0, 1),
        },
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=1)
    m = out["meta"]
    print(f"\n[done] {m['n_edges']} edges / {m['n_sites']} sites in {m['seconds']}s")
    print(f"  edge support : {m['edge_support_distribution']}")
    print(f"  edge priority: {m['edge_priority_distribution']}")
    print(f"  edges with a does_not site: {m['edges_with_a_does_not_site']}")
    print(f"  → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
