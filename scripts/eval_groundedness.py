#!/usr/bin/env python3
"""EVAL 1 — Groundedness (node-level, Reader fidelity). Key-free.

For each contribution: is its `quote` actually in the paper's source text? Exact
substring undercounts (whitespace/OCR), so use (a) whitespace/case-normalized
substring, and (b) content-token recall of the quote in the source. Reports
coverage + grounded rates. (statement-vs-quote faithfulness is semantic → needs
an LLM; flagged, not scored here.)

Usage: python3 scripts/eval_groundedness.py
"""
from __future__ import annotations
import os
import json, re, statistics
from pathlib import Path

ATLAS = Path(os.environ.get("PRIOR_DATA_DIR", "data") + "/atlas")
FT = Path(os.environ.get("PRIOR_DATA_DIR", "data") + "/fulltext")
STOP = set("the a an of for to in on and or but with without via using use is are be as that this these "
           "those by from at into over under can we our their its it they not no only".split())

norm = lambda s: re.sub(r"\s+", " ", (s or "").lower()).strip()
content = lambda s: [w for w in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()
                     if len(w) > 2 and w not in STOP]

cons = json.loads((ATLAS / "contributions_core.json").read_text())["contributions"]
src_cache = {}


def source(pid):
    if pid not in src_cache:
        f = FT / (pid.replace(":", "_") + ".txt")
        src_cache[pid] = f.read_text(errors="ignore") if f.exists() else None
    return src_cache[pid]


covered, missing = [], 0
sub_hits = 0
recalls = []
for c in cons:
    txt = source(c["paper_id"])
    if txt is None:
        missing += 1
        continue
    covered.append(c)
    nsrc = norm(txt)
    q = c.get("quote", "")
    if norm(q) and norm(q) in nsrc:
        sub_hits += 1
    qc = content(q)
    if qc:
        sset = set(content(txt))
        recalls.append(sum(1 for t in qc if t in sset) / len(qc))

N = len(covered)
print(f"=== EVAL 1: GROUNDEDNESS (node-level) ===")
print(f"contributions: {len(cons)} | with cached source: {N} ({N/len(cons):.0%}) | missing source: {missing}")
print(f"\nquote → source match (of the {N} covered):")
print(f"  normalized verbatim substring : {sub_hits} ({sub_hits/N:.0%})")
if recalls:
    for thr in (0.95, 0.9, 0.8, 0.6):
        print(f"  content-token recall ≥ {thr:.2f}    : {sum(r>=thr for r in recalls)} ({sum(r>=thr for r in recalls)/len(recalls):.0%})")
    print(f"  median token recall           : {statistics.median(recalls):.2f}")
print("\n(verbatim is low by design — quotes get whitespace/OCR-mangled; token recall is the")
print(" fair groundedness signal. statement-vs-quote faithfulness is semantic → LLM, not scored here.)")
