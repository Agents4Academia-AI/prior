#!/usr/bin/env python3
"""Export the 809 claim-sites to ONE CSV for the Google-Sheets gold-labelling app.

Writes out/gold_export/sheet.csv — a single tab holding everything: the gold columns the
app writes, the context the labeller reads (abstracts inlined, duplicated per site — the
redundancy is cheap and keeps it to one file), and the judge verdicts / quality gates /
second-judge fields, which the web app never sends to the browser.

Sampling (the `sample_type` column) — designed so accuracy is computable without bias:

  random_eval  uniform random sample of sites, in random order. ANY PREFIX of this block
               is still a uniform sample, so stopping early keeps the estimate valid.
  disagreement the second-judge disagreement sites not already drawn above
               (deliberately enriched hard cases -> EXCLUDE from accuracy).
  strat_topup  random top-up per predicted class so each class reaches --strat-per-class
               labelled sites; supports per-class F1 and a reweighted accuracy estimate.
  rest         everything else, queued after the above.

queue_rank orders the app: random_eval -> disagreement -> strat_topup -> rest.
Ordering is a hash of (seed, site_key), NOT a positional shuffle, so adding or dropping
sites upstream does not reshuffle the sites you have already labelled.

Usage:
    python experiments/edge_quality/gold/export_gold_sheet.py
    # refresh the data, keeping labels already made in the sheet:
    python experiments/edge_quality/gold/export_gold_sheet.py --merge-gold ~/Downloads/sheet.csv
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "experiments" / "edge_quality" / "out"
DATA = ROOT / "data" / "prior-core-v0.2"
CLASSES = ("background", "uses_extends", "compares_contrasts")

# One set of gold columns per labeller. "" is the primary (Callum); the others are the
# cross-check annotators, who work the random_eval block only. Keep in sync with
# LABELLERS in appsscript/Code.gs.
LABEL_PREFIXES = ("", "H_", "K_")
GOLD_FIELDS = ("gold_intent", "gold_support", "gold_priority", "gold_notes")
GOLD_COLS = [p + f for p in LABEL_PREFIXES for f in GOLD_FIELDS] + ["revision"]

# A cell starting with one of these is parsed as a formula by Sheets on import.
FORMULA_LEAD = ("=", "+", "@")


def guard(v) -> str:
    """Neutralise formula-leading text cells (a leading space is invisible in Sheets)."""
    s = "" if v is None else str(v)
    return " " + s if s[:1] in FORMULA_LEAD else s


def load_json(name: str):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def fmt_authors(v) -> str:
    """papers_core.jsonl stores authors as a Python-repr list string."""
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    s = (v or "").strip()
    if s.startswith("["):
        try:
            return ", ".join(str(x) for x in ast.literal_eval(s))
        except (ValueError, SyntaxError):
            return s
    return s


def ordkey(seed: int, site_key: str) -> str:
    return hashlib.md5(f"{seed}:{site_key}".encode()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-random", type=int, default=80,
                    help="size of the unbiased random_eval block")
    ap.add_argument("--strat-per-class", type=int, default=27,
                    help="target labelled sites per predicted class (earlier blocks count toward it)")
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--merge-gold", default=None,
                    help="a previously downloaded sheet CSV; its gold_* columns are carried over")
    ap.add_argument("--outdir", default=str(OUT / "gold_export"))
    args = ap.parse_args()

    cmap = load_json("citation_map.json")
    intent = {(e["citing_id"], e["cited_id"], e["cite_key"]): e
              for e in load_json("citations_intent.json")["edges"]}
    typed = {(e["citing_id"], e["cited_id"], e["cite_key"]): e
             for e in load_json("citations_typed.json")["edges"]}
    flags = {(f["citing_id"], f["cited_id"], f["cite_key"]): f
             for f in load_json("citation_map.bibtex_flags.json")}
    papers = {}
    for line in (DATA / "papers_core.jsonl").open(encoding="utf-8"):
        p = json.loads(line)
        papers[p["id"]] = p
    sj = {r["site_key"]: r for r in load_json("second_judge_intent.json")["rows"]}

    # ── previously-made labels ────────────────────────────────────────────
    prior = {}
    if args.merge_gold:
        for r in csv.DictReader(open(args.merge_gold, encoding="utf-8")):
            key = (r.get("site_key") or "").strip()
            if key and any((r.get(c) or "").strip() for c in GOLD_COLS):
                prior[key] = {c: (r.get(c) or "") for c in GOLD_COLS}
                prior[key]["_sample_type"] = (r.get("sample_type") or "").strip()
        print(f"merging {len(prior)} previously-labelled rows from {args.merge_gold}")

    # ── flatten to sites ──────────────────────────────────────────────────
    rows = []
    for rec in cmap:
        k = (rec["citing_id"], rec["cited_id"], rec["cite_key"])
        ed_i, ed_t, fl = intent[k], typed[k], flags[k]
        edge_key = f"{rec['citing_id']}->{rec['cited_id']}"
        n_sites = len(rec["contexts"])
        citing, cited = papers[rec["citing_id"]], papers[rec["cited_id"]]
        cited_abs = cited.get("abstract") or ""
        for i, ctx in enumerate(rec["contexts"]):
            si, st = ed_i["sites"][i], ed_t["sites"][i]
            site_key = f"{edge_key}#{i}"
            s = sj.get(site_key)
            claim = " ".join((ctx.get("text") or "").split())
            row = {
                "site_key": site_key,
                # ── the labeller's evidence ──
                "citing_title": citing.get("title", ""),
                "citing_year": citing.get("year", ""),
                "citing_authors": fmt_authors(citing.get("authors")),
                "citing_abstract": citing.get("abstract", ""),
                "cited_title": cited.get("title", ""),
                "cited_year": cited.get("year", ""),
                "cited_authors": fmt_authors(cited.get("authors")),
                "cited_abstract": cited_abs,
                # "…" wrap: the claim is a mid-sentence window, and it also makes a
                # formula-leading first character impossible.
                "claim": "…" + claim + "…",
                "claim_len": len(claim),
                "cite_key": rec["cite_key"],
                "site_idx": i,
                "n_sites_on_edge": n_sites,
                "edge_key": edge_key,
                "citing_id": rec["citing_id"],
                "cited_id": rec["cited_id"],
                # ── judge verdicts: exported, never shown in the app ──
                "judge_intent": si.get("intent", ""),
                "judge_intent_conf": si.get("confidence", ""),
                "judge_intent_just": si.get("justification", ""),
                "judge_support": st.get("supports_claim", ""),
                "judge_priority": st.get("priority", ""),
                "judge_sp_conf": st.get("confidence", ""),
                "judge_sp_just": st.get("justification", ""),
                "edge_intent": ed_i.get("intent", ""),
                "edge_support": ed_t.get("support", ""),
                "edge_priority": ed_t.get("priority", ""),
                # ── quality gates ──
                "bibtex_valid": fl.get("bibtex_valid", ""),
                "is_blob_edge": not fl.get("bibtex_valid", True),
                "bibtex_len": fl.get("bibtex_len", ""),
                "n_bibtex_entries": fl.get("n_bibtex_entries", ""),
                "ran_past_end": fl.get("ran_past_end", ""),
                "citee_abstract_len": len(cited_abs),
                "citee_abstract_ok": len(cited_abs) >= 250,
                # ── second-judge cross-check (100-site sample only) ──
                "sj_in_sample": bool(s),
                "sj_agree": (s or {}).get("agree", ""),
                "sj_opus": (s or {}).get("opus", ""),
                "sj_opus_conf": (s or {}).get("opus_conf", ""),
                "sj_opus_just": (s or {}).get("opus_just", ""),
                "sj_pair": (f"{s['ours']}->{s['opus']}" if s and not s["agree"] else ""),
            }
            row.update({c: prior.get(site_key, {}).get(c, "") for c in GOLD_COLS})
            rows.append(row)

    by_key = {r["site_key"]: r for r in rows}
    assert len(by_key) == len(rows), "site_key collision"
    print(f"sites: {len(rows)}  edges: {len(cmap)}  papers: {len(papers)}")

    # ── sampling blocks (hash order: stable across re-exports) ────────────
    all_keys = sorted(by_key, key=lambda k: ordkey(args.seed, k))

    block_random = all_keys[:min(args.n_random, len(all_keys))]
    taken = set(block_random)

    block_dis = sorted((k for k, v in sj.items() if not v["agree"] and k in by_key and k not in taken),
                       key=lambda k: ordkey(args.seed, k))
    taken |= set(block_dis)

    have = Counter(by_key[k]["judge_intent"] for k in taken)
    pool = defaultdict(list)
    for k in all_keys:
        if k not in taken:
            pool[by_key[k]["judge_intent"]].append(k)
    block_strat = []
    for c in CLASSES:
        block_strat += pool[c][:max(0, args.strat_per_class - have[c])]
    block_strat.sort(key=lambda k: ordkey(args.seed, k))
    taken |= set(block_strat)

    block_rest = [k for k in all_keys if k not in taken]

    order = ([("random_eval", k) for k in block_random]
             + [("disagreement", k) for k in block_dis]
             + [("strat_topup", k) for k in block_strat]
             + [("rest", k) for k in block_rest])

    for rank, (stype, k) in enumerate(order, start=1):
        by_key[k]["queue_rank"] = rank
        by_key[k]["sample_type"] = stype
        by_key[k]["random_ord"] = rank if stype == "random_eval" else ""

    blocks = [("random_eval", block_random), ("disagreement", block_dis),
              ("strat_topup", block_strat), ("rest", block_rest)]
    print("queue blocks: " + ", ".join(f"{n}={len(b)}" for n, b in blocks))
    target = sum(len(b) for n, b in blocks if n != "rest")
    print(f"gold target (first three blocks): {target} sites")
    per_class = Counter(by_key[k]["judge_intent"]
                        for n, b in blocks if n != "rest" for k in b)
    print("  predicted-class coverage in target: " + str({c: per_class[c] for c in CLASSES}))

    # a labelled site that changed block would silently corrupt the estimate
    moved = [k for k, p in prior.items()
             if p["_sample_type"] and k in by_key and by_key[k]["sample_type"] != p["_sample_type"]]
    if moved:
        print(f"⚠ {len(moved)} already-labelled sites changed sample_type "
              f"(e.g. {moved[0]}) — check before trusting the accuracy split")

    # ── write ─────────────────────────────────────────────────────────────
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    cols = (["site_key", "queue_rank", "sample_type", "random_ord"] + GOLD_COLS
            + ["citing_title", "citing_year", "citing_authors", "citing_abstract",
               "cited_title", "cited_year", "cited_authors", "cited_abstract",
               "claim", "claim_len", "cite_key", "site_idx", "n_sites_on_edge",
               "edge_key", "citing_id", "cited_id",
               "judge_intent", "judge_intent_conf", "judge_intent_just",
               "judge_support", "judge_priority", "judge_sp_conf", "judge_sp_just",
               "edge_intent", "edge_support", "edge_priority",
               "bibtex_valid", "is_blob_edge", "bibtex_len", "n_bibtex_entries", "ran_past_end",
               "citee_abstract_len", "citee_abstract_ok",
               "sj_in_sample", "sj_agree", "sj_opus", "sj_opus_conf", "sj_opus_just", "sj_pair"])

    path = outdir / "sheet.csv"
    ordered = sorted(rows, key=lambda r: r["queue_rank"])
    with path.open("w", encoding="utf-8", newline="") as fh:
        wtr = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        wtr.writeheader()
        for rec in ordered:
            wtr.writerow({c: guard(rec.get(c, "")) for c in cols})
    print(f"-> {path}  ({len(ordered)} rows, {len(cols)} cols, {path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
