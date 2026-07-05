#!/usr/bin/env python3
"""Arms B & C of the edge-quality experiment: decomposed pairwise relation
labeling, without (B) and with (C) citation signal.

Hypothesis (Prior roadmap, REL-motivated): batched labeling (1 call x ~6
candidates) drives relation correctness to 21-53%; low-arity decomposed calls
(pair-at-a-time: related? -> type) + citation context fix it.

Protocol per pair:
  stage 1  "are these related at all?"        (1 pair per call, yes/no + reason)
  stage 2  if related: "which relation type?" (1 pair per call, 6-way)
  stage 3  direction — deterministic, NO llm: citation (C only) > date > symmetric.

Candidate universe (identical for B and C, so C's delta is attributable):
  BM25 top-k statements from other papers          (mirrors the Cartographer)
  ∪ every pair asserted by Arm A                   (direct re-adjudication of A)
  C only adds: contribution pairs across citation-linked papers (from stage 0),
  and injects "PAPER CITATION: ..." context into the prompts of pairs whose
  papers are citation-linked. For pairs with no citation signal C reuses B's
  stage-1/2 verdicts (the prompts would be byte-identical).

Checkpointed to JSONL after every call; safe to kill and resume.

Usage:
  PRIOR_LLM_BACKEND=claude-cli python3 experiments/edge_quality/relate_decomposed.py \
      --bundle ../prior-core-v0.2 --arm B [--limit-pairs N] [--workers 6]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from prior import llm  # noqa: E402

from rank_bm25 import BM25Okapi  # noqa: E402

OUT = Path(__file__).parent / "out"
RELATIONS = ["builds_on", "refines", "contradicts", "contrast", "supports", "mentions"]
SYMMETRIC = {"contradicts", "contrast", "supports", "mentions"}
_WORD = re.compile(r"[a-z0-9]+")

# One low-arity call per PAIR (vs Arm A's one call per ~6 candidates): first
# decide relatedness strictly, then — only if related — the type. Single call
# keeps the overnight budget; the arity reduction (1 pair, not 6) is the
# hypothesis under test.
S_SYSTEM = """You are labelling the relation between TWO research contributions
(each with a supporting quote from its paper). Step 1 — decide whether a
genuine, defensible relation exists at all: one you could justify from the
texts alone. Same broad topic is NOT a relation; be strict — most pairs are NOT
related. If (and only if) related, step 2 — choose exactly one type:
  builds_on    — one is based on / extends / applies the other
  refines      — one qualifies or improves the other
  contradicts  — their results are incompatible; both cannot hold as stated.
                 NOT mere novelty framing ("unlike prior work...") — require a
                 genuine empirical or theoretical clash.
  contrast     — alternative approaches to the same problem, no incompatibility
  supports     — one's result corroborates the other's
  mentions     — related, but none of the above
Reason must be one line, grounded in the quoted texts; confidence in [0,1]."""

S_SCHEMA = {"type": "object", "properties": {
    "related": {"type": "boolean"},
    "relation": {"type": "string", "enum": RELATIONS},
    "reason": {"type": "string"},
    "confidence": {"type": "number"}}, "required": ["related", "reason"]}


def _tok(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def load_bundle(d: Path):
    papers = {p["id"]: p for p in (json.loads(l) for l in open(d / "papers_core.jsonl") if l.strip())}
    obj = json.load(open(d / "contributions_core_grounded.json"))
    contribs = obj["contributions"] if isinstance(obj, dict) else obj
    obj = json.load(open(d / "contributions_core_consensus.json"))
    a_edges = obj["edges"] if isinstance(obj, dict) else obj
    return papers, contribs, a_edges


def ctext(c: dict) -> str:
    q = c.get("quote_verbatim") or c.get("quote") or ""
    return f'{c["statement"]}\n  quote: "{q[:400]}"'


def build_pairs(contribs, a_edges, k: int) -> set[frozenset]:
    """BM25 top-k cross-paper pairs ∪ Arm-A asserted pairs."""
    ids = {c["id"] for c in contribs}
    corpus = [_tok(c["statement"]) for c in contribs]
    bm25 = BM25Okapi(corpus)
    pairs: set[frozenset] = set()
    for i, c in enumerate(contribs):
        scores = bm25.get_scores(corpus[i])
        ranked = sorted(range(len(contribs)), key=lambda j: scores[j], reverse=True)
        n = 0
        for j in ranked:
            if j == i or contribs[j]["paper_id"] == c["paper_id"]:
                continue
            pairs.add(frozenset({c["id"], contribs[j]["id"]}))
            n += 1
            if n >= k:
                break
    for e in a_edges:
        if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
            pairs.add(frozenset({e["src"], e["dst"]}))
    return pairs


def citation_pairs(contribs, cites: set[tuple[str, str]], per_paper_pair: int) -> set[frozenset]:
    """Cross pairs over citation-linked papers, capped by BM25 similarity."""
    by_paper: dict[str, list[dict]] = {}
    for c in contribs:
        by_paper.setdefault(c["paper_id"], []).append(c)
    corpus = [_tok(c["statement"]) for c in contribs]
    idx = {c["id"]: i for i, c in enumerate(contribs)}
    bm25 = BM25Okapi(corpus)
    out: set[frozenset] = set()
    for pa, pb in cites:
        ca, cb = by_paper.get(pa, []), by_paper.get(pb, [])
        scored = []
        for x in ca:
            s = bm25.get_scores(corpus[idx[x["id"]]])
            for y in cb:
                scored.append((s[idx[y["id"]]], x["id"], y["id"]))
        for _, xa, yb in sorted(scored, reverse=True)[:per_paper_pair]:
            out.add(frozenset({xa, yb}))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--arm", choices=["B", "C"], required=True)
    ap.add_argument("--model", default=os.environ.get("PRIOR_CARTOGRAPHER_MODEL", "claude-sonnet-4-6"))
    ap.add_argument("--k", type=int, default=4)   # 6 in Arm A; 4 fits the overnight budget
    ap.add_argument("--workers", type=int, default=int(os.environ.get("PRIOR_MAP_WORKERS", "8")))
    ap.add_argument("--limit-pairs", type=int, default=0, help="debug: cap pair count")
    ap.add_argument("--cite-pairs-cap", type=int, default=3, help="C: max contribution pairs per citation-linked paper pair")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    papers, contribs, a_edges = load_bundle(Path(args.bundle))
    by_id = {c["id"]: c for c in contribs}

    cites: set[tuple[str, str]] = set()
    cite_pairs_papers: set[frozenset] = set()
    cit_f = OUT / "citations_core.json"
    if args.arm == "C":
        cit = json.load(open(cit_f))          # stage 0 must have finished
        cites = {tuple(e) for e in cit["edges"]}
        cite_pairs_papers = {frozenset(e) for e in cites}
        print(f"[C] citation edges: {len(cites)}", flush=True)

    pairs = build_pairs(contribs, a_edges, args.k)
    print(f"pair universe (BM25 k={args.k} ∪ armA): {len(pairs)}", flush=True)
    if args.arm == "C":
        extra = citation_pairs(contribs, cites, args.cite_pairs_cap) - pairs
        print(f"[C] + citation-proposed pairs: {len(extra)}", flush=True)
        pairs |= extra

    def cited_ctx(pair: frozenset) -> str | None:
        a, b = sorted(pair)
        pa, pb = by_id[a]["paper_id"], by_id[b]["paper_id"]
        if (pa, pb) in cites:
            return f"PAPER CITATION: the paper of the first contribution CITES the paper of the second."
        if (pb, pa) in cites:
            return f"PAPER CITATION: the paper of the second contribution CITES the paper of the first."
        return None

    # ---- resume: load existing verdicts (B's file doubles as C's cache) ----
    def load_jsonl(f: Path) -> dict[str, dict]:
        out = {}
        if f.exists():
            for line in open(f):
                if line.strip():
                    r = json.loads(line)
                    out[r["pair"]] = r
        return out

    my_f = OUT / f"arm{args.arm}_verdicts.jsonl"
    mine = load_jsonl(my_f)
    cache = dict(load_jsonl(OUT / "armB_verdicts.jsonl")) if args.arm == "C" else {}

    todo = []
    for pair in sorted(pairs, key=lambda p: sorted(p)):
        key = "|".join(sorted(pair))
        if key in mine:
            continue
        ctx = cited_ctx(pair) if args.arm == "C" else None
        if args.arm == "C" and ctx is None and key in cache:
            # identical prompt to B — reuse instead of re-spending
            r = dict(cache[key]); r["reused_from_B"] = True
            with open(my_f, "a") as fh:
                fh.write(json.dumps(r) + "\n")
            mine[key] = r
            continue
        todo.append((key, pair, ctx))
    if args.limit_pairs:
        todo = todo[: args.limit_pairs]
    print(f"to label: {len(todo)} pairs (done: {len(mine)})", flush=True)

    lock = threading.Lock()
    timeout = int(os.environ.get("PRIOR_MAP_CALL_TIMEOUT", "120"))

    def label(key: str, pair: frozenset, ctx: str | None) -> dict:
        a, b = sorted(pair)
        ca, cb = by_id[a], by_id[b]
        header = (ctx + "\n\n") if ctx else ""
        body = (f"{header}CONTRIBUTION 1 ({ca['paper_id']}):\n  {ctext(ca)}\n\n"
                f"CONTRIBUTION 2 ({cb['paper_id']}):\n  {ctext(cb)}")
        for _attempt in range(3):
            try:
                s = llm.structured(model=args.model, system=S_SYSTEM, user=body,
                           schema=S_SCHEMA, tool_name="emit_relation",
                           max_tokens=400, timeout=timeout)
                break
            except Exception:
                if _attempt == 2:
                    raise
                import time as _t; _t.sleep(20 * (_attempt + 1))
        rec = {"pair": key, "a": a, "b": b, "cited": bool(ctx),
               "related": bool(s.get("related")), "s1_reason": s.get("reason", "")}
        if rec["related"] and s.get("relation"):
            rec.update(relation=s.get("relation"), reason=s.get("reason", ""),
                       confidence=float(s.get("confidence", 0.5)))
        return rec

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(label, *t): t[0] for t in todo}
        for f in as_completed(futs):
            done += 1
            try:
                rec = f.result()
            except Exception as e:  # noqa: BLE001
                print(f"  [{done}/{len(todo)}] ERROR {futs[f]}: {e}", flush=True)
                continue
            with lock, open(my_f, "a") as fh:
                fh.write(json.dumps(rec) + "\n")
            if done % 25 == 0 or done == len(todo):
                print(f"  [{done}/{len(todo)}] {rec['pair'][:60]} related={rec['related']}", flush=True)

    # ---- assemble edges: deterministic direction (stage 3) ----------------
    verdicts = load_jsonl(my_f)
    edges = []
    for r in verdicts.values():
        if not r.get("related") or not r.get("relation"):
            continue
        a, b = r["a"], r["b"]
        rel = r["relation"]
        da, db = by_id[a].get("date") or "", by_id[b].get("date") or ""
        pa, pb = by_id[a]["paper_id"], by_id[b]["paper_id"]
        src, dst, directed, prec = a, b, False, "symmetric"
        if rel in ("builds_on", "refines"):
            if args.arm == "C" and (pa, pb) in cites:
                src, dst, directed, prec = a, b, True, "by_citation"
            elif args.arm == "C" and (pb, pa) in cites:
                src, dst, directed, prec = b, a, True, "by_citation"
            elif da and db and da != db:                    # newer builds on older
                (src, dst) = (a, b) if da > db else (b, a)
                directed, prec = True, "by_date"
            else:
                directed, prec = False, "ambiguous"
        edges.append({"src": src, "dst": dst, "relation": rel, "directed": directed,
                      "precedence": prec, "evidence": r.get("reason", ""),
                      "confidence": r.get("confidence", 0.5), "cited": r.get("cited", False),
                      "arm": args.arm})
    ef = OUT / f"arm{args.arm}_edges.json"
    ef.write_text(json.dumps({"edges": edges, "n_pairs_labelled": len(verdicts)}, indent=1))
    from collections import Counter
    print(f"\nDONE arm {args.arm}: {len(edges)} edges from {len(verdicts)} pairs -> {ef}")
    print("  by type:", dict(Counter(e['relation'] for e in edges)), flush=True)


if __name__ == "__main__":
    main()
