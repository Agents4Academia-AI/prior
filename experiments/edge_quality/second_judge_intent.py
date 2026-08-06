#!/usr/bin/env python3
"""Second-annotator check on the INTENT axis: re-judge a stratified sample of our
already-labelled claim-sites with a DIFFERENT, stronger model (Opus 5) and measure
agreement with our production labels (Sonnet-5 in ``citations_intent.ckpt.json``).

WHY / DESIGN — this is a reliability + independent-validation probe, not a re-run:
  • SAME EVIDENCE. Each site is fed the *exact* marked claim window our judge saw
    (pulled verbatim from the intent checkpoint) plus the same L0 abstract. Byte-for-byte
    identical input — the only things that change are the model and the rubric.
  • DIFFERENT MODEL. Opus 5 (`claude-opus-5`), a different family/size than Sonnet-5, so
    the two annotators' errors are less correlated.
  • CLEAN-ROOM RUBRIC. We deliberately DO NOT replay ``type_intents.INTENT_SYSTEM``. That
    rubric carries our tie-breakers/grouping/baseline patches — the very place biases like
    concurrent-work over-firing live. Handing Opus the same patches would make it inherit
    our biases and agree for the wrong reason. Instead Opus gets a lean, faithful definition
    of the SAME three classes (same meaning, no procedural scaffolding), so a genuine
    disagreement surfaces instead of being laundered into false agreement.
  • BLIND. Opus never sees our label.
  • STRATIFIED. A random sample is ~82% background; we stratify by our label (~balanced
    across the 3 classes) for usable per-class estimates, then REWEIGHT the headline
    agreement back to the true 82/11/7 site distribution so the overall number is honest.

Reads  : out/citations_intent.ckpt.json   (our per-site labels + the claim text)
         data/prior-core-v0.2/papers_core.jsonl  (abstracts = evidence)
Writes : out/second_judge_intent.json      (report: metrics + full row-by-row + disagreements)
         out/second_judge_intent.ckpt.json  (resumable: site_key -> opus verdict)

Transport is REUSED from type_intents (subscription-only guard, same _run_messages/_run_query
path, same JSON parser) — no metered API, key-free, resumable.

Usage (repo root, prior venv):
    python experiments/edge_quality/second_judge_intent.py               # ~100 sites, opus 5
    python experiments/edge_quality/second_judge_intent.py --n 120
    python experiments/edge_quality/second_judge_intent.py --fresh
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "experiments" / "edge_quality" / "out"
sys.path.insert(0, str(Path(__file__).resolve().parent))  # for `import type_intents`
import prior.type_intents as ti  # reuse parse_intent, class list, edge_id

_INTENTS = list(ti._INTENTS)  # ("background", "uses_extends", "compares_contrasts")


# Lean, clean-room definitions of the SAME three classes — faithful meaning, none of our
# tie-breakers/grouping/baseline patches. Same output schema so ti.parse_intent works.
SECOND_SYSTEM = (
    "You label WHY one paper cites another. You receive a JSON array of CITATIONS. Each has a "
    "`cite_key`, an `evidence` field (the cited paper's abstract; may be empty), and a list of "
    "`claims` — passages taken from the CITING paper. In each passage, `[CITED:TARGET]` marks the "
    "SINGLE citation to label; any other `[CITED]` markers are different citations shown only for "
    "context — ignore them. For each claim, choose EXACTLY ONE label for how the citing paper "
    "relates to the `[CITED:TARGET]` work:\n"
    "- 'background': the target is cited for context, motivation, or as an example of prior/related "
    "work. The citing paper neither reuses the target nor positions its own contribution against it. "
    "(Noting that the target is concurrent or related work, described neutrally, is background.)\n"
    "- 'uses_extends': the citing paper actually reuses or builds on the target — its method, "
    "dataset, model, benchmark, protocol, code, or theoretical framework.\n"
    "- 'compares_contrasts': the citing paper sets its OWN approach or results specifically against "
    "the target — comparing performance against it, stating how it differs from the target, or "
    "critiquing a limitation of the target.\n"
    "Decide only from the passage and the evidence, never outside knowledge. If a passage mixes "
    "relations, pick the one that dominates for the target. Return ONE JSON array, exactly one "
    "object per input CITATION, echoing its `cite_key`, with one verdict per claim_id: "
    '[{"cite_key":"...","claims":[{"claim_id":"...",'
    '"intent":"background|uses_extends|compares_contrasts","confidence":0.0-1.0,'
    '"justification":"one short sentence naming the cue"}]}]. Output JSON only, no prose.'
)


def load_ours():
    """Our per-site labels straight from the intent checkpoint (has the claim text verbatim)."""
    ckpt = json.load(open(OUT / "citations_intent.ckpt.json", encoding="utf-8"))
    papers = {}
    for line in open(REPO / "data" / "prior-core-v0.2" / "papers_core.jsonl", encoding="utf-8"):
        if line.strip():
            p = json.loads(line)
            papers[p["id"]] = p
    sites = []
    for site_key, v in ckpt.items():
        if not v.get("intent") or v["intent"] == "unknown":
            continue
        abstract = (papers.get(v["cited_id"], {}) or {}).get("abstract") or ""
        sites.append({
            "site_key": site_key, "citing_id": v["citing_id"], "cited_id": v["cited_id"],
            "cite_key": v["cite_key"], "claim": v["claim"], "abstract": abstract,
            "ours": v["intent"], "ours_conf": v.get("confidence"),
            "ours_just": v.get("justification"),
        })
    return sites


def stratified_sample(sites, n, seed):
    """~balanced across our 3 classes, capped by availability, remainder to background."""
    by_class = defaultdict(list)
    for s in sites:
        by_class[s["ours"]].append(s)
    rng = random.Random(seed)
    per = max(1, n // 3)
    targets = {
        "uses_extends": min(per, len(by_class["uses_extends"])),
        "compares_contrasts": min(per, len(by_class["compares_contrasts"])),
    }
    targets["background"] = min(n - targets["uses_extends"] - targets["compares_contrasts"],
                                len(by_class["background"]))
    picked = []
    for cls in _INTENTS:
        pool = sorted(by_class[cls], key=lambda s: s["site_key"])  # deterministic
        picked += rng.sample(pool, targets.get(cls, 0))
    rng.shuffle(picked)
    return picked, targets


def run_chunk(judge, settings, apply_auth, chunk):
    """One LLM call over `chunk` sites (grouped by cited paper), using SECOND_SYSTEM.
    Mirrors type_intents.run_chunk but with our clean-room prompt. -> {site_key: verdict}."""
    groups: dict[str, dict] = {}
    for s in chunk:
        g = groups.setdefault(s["cited_id"], {"evidence": s["abstract"], "members": []})
        g["members"].append(s)
    payload = [
        {"cite_key": ck, "evidence": g["evidence"],
         "claims": [{"claim_id": s["site_key"], "claim": s["claim"]} for s in g["members"]]}
        for ck, g in groups.items()
    ]
    user = ("Label the intent of the [CITED:TARGET] citation in each claim, using ONLY that "
            "citation's evidence and the claim passage.\n" + json.dumps(payload, ensure_ascii=False))
    n_claims = len(chunk)
    if judge.mode == "messages":
        text = judge._run_messages(SECOND_SYSTEM, user, min(8192, max(512, 96 * n_claims)))
    else:
        import claude_agent_sdk as sdk
        apply_auth(settings)
        text = asyncio.run(judge._run_query(sdk, SECOND_SYSTEM, user))
    result = {}
    for per in ti.parse_intent(text).values():
        for site_key, v in per.items():
            result[site_key] = v
    return result


# ── metrics ───────────────────────────────────────────────────────────────
def cohen_kappa(rows, labels):
    """rows: list of (a, b). Standard Cohen's kappa over the given label set."""
    n = len(rows)
    if not n:
        return None
    po = sum(a == b for a, b in rows) / n
    ca = Counter(a for a, _ in rows)
    cb = Counter(b for _, b in rows)
    pe = sum((ca.get(l, 0) / n) * (cb.get(l, 0) / n) for l in labels)
    return None if pe == 1 else (po - pe) / (1 - pe)


def analyze(judged):
    """judged: list of dicts with ours/opus etc. Prints + returns the metrics block."""
    rated = [r for r in judged if r["opus"] in _INTENTS]  # drop parse-failures/unknown
    conf = {oi: Counter() for oi in _INTENTS}  # ours -> opus
    for r in rated:
        conf[r["ours"]][r["opus"]] += 1

    per_class = {}
    for oi in _INTENTS:
        tot = sum(conf[oi].values())
        per_class[oi] = {"n": tot, "agree": conf[oi].get(oi, 0),
                         "rate": (conf[oi].get(oi, 0) / tot) if tot else None}

    raw_agree = sum(r["ours"] == r["opus"] for r in rated) / len(rated) if rated else None
    kappa = cohen_kappa([(r["ours"], r["opus"]) for r in rated], _INTENTS)

    # reweight to the TRUE 809-site distribution so the headline isn't skewed by stratification
    TRUE = {"background": 665, "uses_extends": 55, "compares_contrasts": 89}
    tot_true = sum(TRUE.values())
    weighted = None
    if all(per_class[oi]["rate"] is not None for oi in _INTENTS):
        weighted = sum((TRUE[oi] / tot_true) * per_class[oi]["rate"] for oi in _INTENTS)

    print(f"\n== SECOND-JUDGE AGREEMENT (Opus 5 vs our Sonnet-5), n={len(rated)} rated "
          f"({len(judged)-len(rated)} unrated) ==\n")
    hdr = "ours \\ opus".ljust(20) + "".join(c[:12].rjust(14) for c in _INTENTS) + "     row"
    print(hdr); print("-" * len(hdr))
    for oi in _INTENTS:
        row = oi.ljust(20) + "".join(str(conf[oi].get(c, 0)).rjust(14) for c in _INTENTS)
        print(row + str(sum(conf[oi].values())).rjust(8))
    print()
    for oi in _INTENTS:
        pc = per_class[oi]
        if pc["n"]:
            print(f"  agree | ours={oi:20} {pc['agree']:3}/{pc['n']:<3} = {100*pc['rate']:5.1f}%")
    print(f"\n  raw agreement (balanced sample) : {100*raw_agree:.1f}%" if raw_agree is not None else "")
    if weighted is not None:
        print(f"  reweighted to true 82/11/7 dist : {100*weighted:.1f}%   <- honest headline")
    if kappa is not None:
        strength = ("poor" if kappa < .2 else "fair" if kappa < .4 else "moderate"
                    if kappa < .6 else "substantial" if kappa < .8 else "almost perfect")
        print(f"  Cohen's kappa (on sample)       : {kappa:.3f} ({strength})")

    return {
        "n_rated": len(rated), "n_unrated": len(judged) - len(rated),
        "confusion_ours_x_opus": {oi: dict(conf[oi]) for oi in _INTENTS},
        "per_class_agreement": per_class,
        "raw_agreement_balanced": raw_agree,
        "reweighted_agreement_true_dist": weighted,
        "cohen_kappa": kappa,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=100, help="total sites to sample (stratified)")
    ap.add_argument("--seed", type=int, default=13, help="sampling seed (reproducible)")
    ap.add_argument("--model", default="claude-opus-5", help="second-annotator model")
    ap.add_argument("--max-claims", type=int, default=12, help="claims per LLM call / flush")
    ap.add_argument("--out", default=str(OUT / "second_judge_intent.json"))
    ap.add_argument("--checkpoint", default=str(OUT / "second_judge_intent.ckpt.json"))
    ap.add_argument("--fresh", action="store_true")
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

    sites = load_ours()
    sample, targets = stratified_sample(sites, args.n, args.seed)
    by_key = {s["site_key"]: s for s in sample}
    print(f"[data]  {len(sites)} labelled sites | sampling {len(sample)} "
          f"(seed={args.seed}) stratified {targets}")

    ckpt_path = Path(args.checkpoint)
    opus: dict[str, dict] = {}
    if ckpt_path.exists() and not args.fresh:
        opus = {k: v for k, v in json.load(open(ckpt_path, encoding="utf-8")).items()
                if k in by_key and v.get("intent")}
        print(f"[resume] {len(opus)} sites already judged by {args.model}")
    todo = [s for s in sample if s["site_key"] not in opus]
    print(f"[run]   {len(todo)} sites remaining | model={args.model} | <= {args.max_claims}/call\n")

    judge = build_relevance_judge(settings)
    if judge is None:
        print("ABORT: no relevance judge available (Claude Agent SDK missing?).", file=sys.stderr)
        return 2
    judge.escalate_full_text = False
    print(f"[model] judge = {judge.model} (mode={judge.mode})\n")

    stop_path = OUT / "STOP"
    t0 = time.time()
    stopped = None
    try:
        for start in range(0, len(todo), args.max_claims):
            if stop_path.exists():
                stopped = f"manual STOP file present ({stop_path})"; break
            chunk = todo[start:start + args.max_claims]
            got = run_chunk(judge, settings, apply_auth, chunk)
            missing = [s for s in chunk if s["site_key"] not in got]
            if missing:
                got.update(run_chunk(judge, settings, apply_auth, missing))
            failed = 0
            for s in chunk:
                v = got.get(s["site_key"])
                if not v or not v.get("intent"):
                    failed += 1; continue
                opus[s["site_key"]] = {"intent": v["intent"], "confidence": v.get("confidence"),
                                       "justification": v.get("justification"), "model": judge.model}
            json.dump(opus, open(ckpt_path, "w", encoding="utf-8"), indent=1)
            print(f"[{len(opus):4}/{len(sample)}] +{len(chunk)-failed:2} "
                  f"| {judge.calls} calls | {time.time()-t0:5.0f}s", flush=True)
            if failed == len(chunk) and chunk:
                stopped = (f"whole batch of {len(chunk)} returned no verdict — subscription "
                           f"usage is almost certainly exhausted"); break
    except KeyboardInterrupt:
        stopped = "KeyboardInterrupt (Ctrl-C) — current batch discarded, saved rows intact"

    # ── join + analyze ─────────────────────────────────────────────────────
    judged = []
    for s in sample:
        o = opus.get(s["site_key"])
        if not o:
            continue
        judged.append({
            "site_key": s["site_key"], "cite_key": s["cite_key"],
            "citing_id": s["citing_id"], "cited_id": s["cited_id"],
            "ours": s["ours"], "ours_conf": s["ours_conf"], "ours_just": s["ours_just"],
            "opus": o["intent"], "opus_conf": o.get("confidence"), "opus_just": o.get("justification"),
            "agree": s["ours"] == o["intent"],
            "claim": s["claim"],
        })
    metrics = analyze(judged) if judged else {}

    disagreements = sorted((r for r in judged if not r["agree"]),
                           key=lambda r: (r["ours"], r["opus"]))
    print(f"\n== DISAGREEMENTS: {len(disagreements)}/{len(judged)} ==")
    for r in disagreements:
        snip = " ".join(r["claim"].split())
        snip = (snip[:200] + "…") if len(snip) > 200 else snip
        print(f"\n  {r['site_key']}")
        print(f"    ours={r['ours']} ({r['ours_conf']})  opus={r['opus']} ({r['opus_conf']})")
        print(f"    opus: {r['opus_just']}")
        print(f"    claim: {snip}")

    report = {
        "meta": {
            "axis": "intent", "second_model": args.model, "our_model": "claude-sonnet-5",
            "n_sample": len(sample), "n_judged": len(judged), "seed": args.seed,
            "stratify_targets": targets, "stopped_reason": stopped,
            "note": ("SAME evidence/marker convention; clean-room rubric (not our tie-breakers); "
                     "blind; reweighted headline to true 82/11/7 site distribution."),
        },
        "metrics": metrics,
        "disagreements": disagreements,
        "rows": judged,
    }
    json.dump(report, open(args.out, "w", encoding="utf-8"), indent=1)
    if stopped:
        print(f"\n[stopped] {stopped}\n  -> re-run same command to resume.")
    print(f"\n-> {args.out}")
    return 0 if stopped is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
