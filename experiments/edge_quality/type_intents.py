#!/usr/bin/env python3
"""Assign the INTENT axis (the primary type `t`) to every intra-corpus citation edge.

For each claim-site in ``out/citation_map.json`` (525 edges, 809 sites), classify WHY
the citing paper cites the target work:

    intent : background | uses_extends | compares_contrasts   (+ confidence, justification)

This is the M2 deliverable's primary axis. It is INTENT-ONLY — it does NOT recompute
`supports_claim`/`priority` (those live in ``citations_typed.json`` and we keep them).
The output is a SEPARATE file (``citations_intent.json``) to merge with the verification
axes later.

DESIGN (vs the localized re-judge — deliberately different):
  • NO localization. We send FULL claim window verbatim — the surrounding
    sentences carry real signal about the citation's role. The rubric tells the model
    that ``[CITED:TARGET]`` marks the ONE citation to classify and that any other
    ``[CITED]`` markers are neighbouring citations present only for context.
  • Evidence = the cited paper's abstract (L0). Intent leans on the citing passage more
    than the abstract, but the abstract disambiguates uses_extends vs background, so we
    pass it when available (empty is fine — a site with no abstract is still classifiable).

RUBRIC SWAP, SAME TRANSPORT. RefWarden's public ``judge_batch`` hardcodes the support
rubric and returns support/priority, so we can't use it for intent. Instead we take the
correctly-configured judge from ``build_relevance_judge(settings)`` and drive its
transport (``_run_messages``/``_run_query`` — both accept an arbitrary system prompt) with
our own intent prompt + parser. Same subscription path, same usage accounting.

All the safety features of ``type_citations.py``: subscription-only cost guard;
resumable, self-healing checkpoint (never persists a failure verdict); manual ``STOP``
pause file; Ctrl-C safe; single model (default ``claude-sonnet-5``); ≤ ``--max-claims``
claims per LLM call (output cap + anti-rubber-stamp).

Usage (repo root, prior venv):
    python experiments/edge_quality/type_intents.py                 # all 809, sonnet-5
    python experiments/edge_quality/type_intents.py --limit 20      # first 20 edges
    python experiments/edge_quality/type_intents.py --fresh         # ignore checkpoint
"""
from __future__ import annotations

import argparse
import asyncio
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

_INTENTS = ("background", "uses_extends", "compares_contrasts")
# Edge-level rollup: the strongest relation present defines the edge (contrast is the
# highest-value, rarest signal; then builds-on; background is the weak default).
_INTENT_RANK = {"compares_contrasts": 3, "uses_extends": 2, "background": 1, "unknown": 0}
# Normalize model spellings to the taxonomy classes.
_INTENT_ALIASES = {
    "uses": "uses_extends", "extends": "uses_extends", "use_extend": "uses_extends",
    "method": "uses_extends", "builds_on": "uses_extends", "builds-on": "uses_extends",
    "uses/extends": "uses_extends",
    "contrast": "compares_contrasts", "contrasts": "compares_contrasts",
    "compare": "compares_contrasts", "compares": "compares_contrasts",
    "compare_contrast": "compares_contrasts", "comparison": "compares_contrasts",
    "critique": "compares_contrasts", "compares/contrasts": "compares_contrasts",
    "mention": "background", "context": "background", "motivation": "background",
    "future_work": "background",
}

_FAILED_JUSTIFS = {"batch judge returned no verdict", "no verdict"}


def edge_id(citing: str, cited: str) -> str:
    return f"{citing}->{cited}"


INTENT_SYSTEM = (
    "You are a citation INTENT classifier. You receive a JSON array of CITATIONS. Each has a "
    "`cite_key`, the `evidence` text (the cited work's abstract, possibly empty), and a list of "
    "`claims`. Each claim is a passage taken from the CITING paper. Inside a passage, `[CITED:TARGET]` "
    "marks THE ONE citation you must classify; any other `[CITED]` markers are NEIGHBOURING citations "
    "included only for context — do NOT classify those. Using the passage (how/why the citing authors "
    "invoke the target there) together with the evidence (what the cited work actually is), classify "
    "the citing paper's intent toward the `[CITED:TARGET]` work into EXACTLY ONE of:\n"
    "- 'background': the target is cited as general context, prior art, motivation, or a passing "
    "mention. CRITICALLY, if the target is grouped with other papers to describe a general limitation "
    "of the field (e.g., 'current systems [CITED:TARGET] struggle with X', 'unlike these prior works', "
    "'while these studies show Y, they lack Z'), it is 'background'. The citing work neither builds "
    "on it nor singles it out for specific critique.\n"
    "- 'uses_extends': the citing work EXPLICITLY USES, ADOPTS, or BUILDS ON the target. The text must "
    "show active adoption (e.g., 'we use the dataset from [CITED:TARGET]', 'following the mathematical "
    "framework of [CITED:TARGET]'). Mere detailed description of the target's mechanics is not enough.\n"
    "- 'compares_contrasts': the citing work sets ITS OWN approach or results AGAINST the target "
    "SPECIFICALLY. It distinguishes its work from the target alone, critiques a limitation OF THE "
    "TARGET specifically, or reports a differing/contradicting result (e.g. 'unlike [CITED:TARGET]', "
    "'our work differs from [CITED:TARGET]', 'we outperform [CITED:TARGET]').\n"
    "IMPORTANT CLARIFICATIONS & TIE-BREAKERS:\n"
    "- Note on baselines: If the target is cited primarily as a competing method to outperform or "
    "compare results against, classify as 'compares_contrasts'. If the target is cited because the "
    "authors adopted their experimental protocol, dataset, or code infrastructure to run those tests, "
    "classify as 'uses_extends'.\n"
    "- THE GROUPING RULE: If the target is listed alongside other citations and the contrastive cue "
    "(e.g., 'However,', 'In contrast') applies to the ENTIRE GROUP or the 'current state-of-the-art', "
    "you MUST classify it as 'background'. The contrast must single out THE TARGET specifically.\n"
    "- Tie-breaker (background vs. compares_contrasts): When genuinely unsure, choose 'background' "
    "unless there is an explicit contrastive cue tied to the target alone.\n"
    "- Tie-breaker (background vs. uses_extends): When unsure whether a citation is merely describing "
    "prior work ('background') or actively adopting it, check if the citing authors' own methodology "
    "relies on that work to function. If yes, choose 'uses_extends'.\n"
    "Judge ONLY the target, from the passage and evidence — never prior knowledge. If a passage "
    "contains multiple intents, choose the relation that DOMINATES at this site. If the passage is too "
    "garbled or generic to tell, use 'background' with low confidence. Return ONE JSON array, "
    "exactly one object per input CITATION, echoing its `cite_key`, with one verdict per claim_id: "
    '[{"cite_key":"...","claims":[{"claim_id":"...",'
    '"intent":"background|uses_extends|compares_contrasts","confidence":0.0-1.0,'
    '"justification":"one short sentence naming the cue"}]}]. Output JSON only, no prose.'
)

def load_inputs():
    cm = json.load(open(OUT / "citation_map.json", encoding="utf-8"))
    papers = {}
    for line in open(REPO / "data" / "prior-core-v0.2" / "papers_core.jsonl", encoding="utf-8"):
        if line.strip():
            p = json.loads(line)
            papers[p["id"]] = p
    return cm, papers


def build_sites(cm, papers, limit):
    """One work-item per (edge, claim-site). Full claim window kept verbatim (NOT localized)."""
    sites = []
    for rec in cm[: limit or None]:
        citing, cited = rec["citing_id"], rec["cited_id"]
        abstract = (papers.get(cited, {}) or {}).get("abstract") or ""
        for i, ctx in enumerate(rec.get("contexts") or []):
            claim = (ctx.get("text") or "").strip()
            if not claim:  # intent needs a passage; abstract MAY be empty (still classifiable)
                continue
            sites.append({
                "site_key": f"{edge_id(citing, cited)}#{i}",
                "citing_id": citing, "cited_id": cited, "cite_key": rec["cite_key"],
                "claim": claim, "abstract": abstract,
            })
    return sites


# ── parsing (own JSON extractor; fail-soft) ───────────────────────────────
def _first_array(text: str) -> str | None:
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, flags=re.DOTALL)
    cand = fence.group(1) if fence else text
    s, e = cand.find("["), cand.rfind("]")
    return cand[s : e + 1] if s != -1 and e > s else None


def _coerce_intent(v) -> str:
    raw = str(v or "").strip().lower().replace(" ", "_").replace("-", "_")
    if raw in _INTENTS:
        return raw
    return _INTENT_ALIASES.get(raw, "unknown")


def parse_intent(text: str) -> dict[str, dict[str, dict]]:
    """{cite_key: {claim_id: {intent, confidence, justification}}}. Missing claims -> absent (failed)."""
    blob = _first_array(text)
    out: dict[str, dict[str, dict]] = {}
    if not blob:
        return out
    try:
        rows = json.loads(blob)
    except json.JSONDecodeError:
        return out
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("cite_key"), str):
            continue
        per: dict[str, dict] = {}
        for cl in row.get("claims") or []:
            if isinstance(cl, dict) and isinstance(cl.get("claim_id"), str):
                conf = cl.get("confidence")
                per[cl["claim_id"]] = {
                    "intent": _coerce_intent(cl.get("intent")),
                    "confidence": float(conf) if isinstance(conf, (int, float)) else None,
                    "justification": str(cl.get("justification") or "").strip(),
                }
        out[row["cite_key"]] = per
    return out


def run_chunk(judge, settings, apply_auth, chunk: list[dict]) -> dict[str, dict]:
    """One LLM call over ``chunk`` sites, grouped by cited paper (abstract sent once).
    Returns {site_key: verdict}; sites absent from the model output are omitted (=failed)."""
    groups: dict[str, dict] = {}
    for s in chunk:
        g = groups.setdefault(s["cited_id"], {"evidence": s["abstract"], "members": []})
        g["members"].append(s)
    payload = [
        {"cite_key": ck, "evidence": g["evidence"],
         "claims": [{"claim_id": s["site_key"], "claim": s["claim"]} for s in g["members"]]}
        for ck, g in groups.items()
    ]
    user = ("Classify the intent of the [CITED:TARGET] citation in each claim, using ONLY that "
            "citation's evidence and the claim passage.\n" + json.dumps(payload, ensure_ascii=False))
    n_claims = len(chunk)
    if judge.mode == "messages":
        text = judge._run_messages(INTENT_SYSTEM, user, min(8192, max(512, 96 * n_claims)))
    else:
        import claude_agent_sdk as sdk
        apply_auth(settings)  # API key if configured, else subscription
        text = asyncio.run(judge._run_query(sdk, INTENT_SYSTEM, user))
    parsed = parse_intent(text)
    result: dict[str, dict] = {}
    for per in parsed.values():
        for site_key, v in per.items():
            result[site_key] = v
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="cap number of EDGES (0 = all 525)")
    ap.add_argument("--max-claims", type=int, default=12, help="claims per LLM call / checkpoint flush")
    ap.add_argument("--model", default="claude-sonnet-5", help="judge model (sets MODEL_JUDGE)")
    ap.add_argument("--out", default=str(OUT / "citations_intent.json"))
    ap.add_argument("--checkpoint", default=str(OUT / "citations_intent.ckpt.json"))
    ap.add_argument("--fresh", action="store_true", help="ignore any existing checkpoint")
    args = ap.parse_args()

    os.environ["MODEL_JUDGE"] = args.model  # before load_settings()

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
    auth = apply_auth(settings)
    if auth != "subscription":
        print(f"ABORT: RefWarden auth resolves to '{auth}', not 'subscription'. "
              f"Unset ANTHROPIC_API_KEY (and any .env key).", file=sys.stderr)
        return 2
    print(f"[guard] auth = {auth} (safe, no metered API)")

    cm, papers = load_inputs()
    sites = build_sites(cm, papers, args.limit)
    n_edges = len({s["site_key"].split("#")[0] for s in sites})
    print(f"[data]  {n_edges} edges | {len(sites)} claim-sites (full window, NOT localized)")

    ckpt_path = Path(args.checkpoint)
    stop_path = OUT / "STOP"
    done: dict[str, dict] = {}
    if ckpt_path.exists() and not args.fresh:
        raw = json.load(open(ckpt_path, encoding="utf-8"))
        done = {k: v for k, v in raw.items() if (v.get("justification") or "") not in _FAILED_JUSTIFS
                and v.get("intent")}
        purged = len(raw) - len(done)
        msg = f"[resume] {len(done)} good sites in checkpoint"
        if purged:
            msg += f" | purged {purged} dead rows"
            json.dump(done, open(ckpt_path, "w", encoding="utf-8"), indent=1)
        print(msg + f" -> {ckpt_path.name}")
    todo = [s for s in sites if s["site_key"] not in done]
    print(f"[run]   {len(todo)} sites remaining | model={args.model} | <= {args.max_claims} claims/call\n")
    if not todo:
        print("[run]   nothing to do — all sites already classified.")

    judge = build_relevance_judge(settings)
    if judge is None:
        print("ABORT: no relevance judge available (Claude Agent SDK missing?).", file=sys.stderr)
        return 2
    judge.escalate_full_text = False
    print(f"[model] judge = {judge.model} (mode={judge.mode})\n")

    t0 = time.time()
    stopped = None
    try:
        for start in range(0, len(todo), args.max_claims):
            if stop_path.exists():
                stopped = f"manual STOP file present ({stop_path})"
                break
            chunk = todo[start : start + args.max_claims]
            got = run_chunk(judge, settings, apply_auth, chunk)
            # one retry of the sites that came back with no verdict (rides out a blip)
            missing = [s for s in chunk if s["site_key"] not in got]
            if missing:
                got2 = run_chunk(judge, settings, apply_auth, missing)
                got.update(got2)

            failed = 0
            for s in chunk:
                v = got.get(s["site_key"])
                if not v or not v.get("intent") or v["intent"] == "unknown" and v.get("confidence") is None:
                    failed += 1
                    continue
                done[s["site_key"]] = {
                    "citing_id": s["citing_id"], "cited_id": s["cited_id"], "cite_key": s["cite_key"],
                    "intent": v["intent"], "confidence": v.get("confidence"),
                    "justification": v.get("justification"), "model": judge.model,
                    "claim": s["claim"],  # full window as evaluated (not cropped)
                }
            json.dump(done, open(ckpt_path, "w", encoding="utf-8"), indent=1)

            n = len(done)
            it = Counter(r["intent"] for r in done.values())
            print(f"[{n:4}/{len(sites)}] +{len(chunk)-failed:2}  intent:{dict(it)}  "
                  f"| {judge.calls} calls | {time.time()-t0:5.0f}s", flush=True)
            if failed == len(chunk) and chunk:
                stopped = (f"whole batch of {len(chunk)} returned no verdict — "
                           f"subscription usage is almost certainly exhausted")
                break
    except KeyboardInterrupt:
        stopped = "KeyboardInterrupt (Ctrl-C) — current batch discarded, saved rows intact"

    # ── aggregate to edge level ────────────────────────────────────────────
    edges: dict[str, dict] = {}
    for r in done.values():
        eid = edge_id(r["citing_id"], r["cited_id"])
        e = edges.setdefault(eid, {"citing_id": r["citing_id"], "cited_id": r["cited_id"],
                                   "cite_key": r["cite_key"], "sites": []})
        e["sites"].append({k: r[k] for k in ("intent", "confidence", "justification", "claim")})
    for e in edges.values():
        intents = [s["intent"] for s in e["sites"]]
        e["intent"] = max(intents, key=lambda x: _INTENT_RANK.get(x, 0))  # strongest relation present
        e["intent_distribution"] = dict(Counter(intents))
        e["n_sites"] = len(e["sites"])

    complete = stopped is None and len(done) >= len(sites)
    out = {
        "edges": list(edges.values()),
        "meta": {
            "complete": complete,
            "axis": "intent", "classes": list(_INTENTS),
            "localized": False, "evidence": "abstract-only (L0), full claim window",
            "n_expected_sites": len(sites), "n_judged_sites": len(done), "n_edges": len(edges),
            "models": sorted({r.get("model") for r in done.values() if r.get("model")}),
            "site_intent_distribution": dict(Counter(r["intent"] for r in done.values())),
            "edge_intent_distribution": dict(Counter(e["intent"] for e in edges.values())),
            "edge_rollup_rule": "strongest relation present (compares_contrasts>uses_extends>background)",
            "seconds": round(time.time() - t0, 1), "stopped_reason": stopped,
        },
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), indent=1)
    m = out["meta"]
    banner = "COMPLETE" if complete else "STOPPED EARLY — RE-RUN TO CONTINUE"
    print(f"\n[{banner}] {m['n_judged_sites']}/{m['n_expected_sites']} sites | {m['n_edges']} edges | "
          f"models={m['models']} | {m['seconds']}s")
    if stopped:
        print(f"  reason: {stopped}")
        if "usage" in stopped:
            print("  -> wait for usage to reset, then re-run the same command; it resumes here.")
    print(f"  site intent : {m['site_intent_distribution']}")
    print(f"  edge intent : {m['edge_intent_distribution']}")
    print(f"  -> {args.out}")
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
