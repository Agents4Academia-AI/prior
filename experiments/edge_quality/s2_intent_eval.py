#!/usr/bin/env python3
"""Grade our INTENT axis against Semantic Scholar's citation-intent labels (a SILVER
standard — see MILESTONE_2_QUICKSTART.md §6). S2 attaches to each citation edge:

    intents        : subset of {background, methodology, result}   (SciCite classifier)
    isInfluential  : bool                                          (a weak influence hint)

S2 has NO contrast class, and only a minority of our 2025–26 frontier edges are parsed by
S2 at all, so this is a partial cross-check, not the source of truth. What it buys us:
agreement on the ~overlap where a label exists, and a sanity read that our `uses_extends`
lines up with S2 `methodology` and our high-value edges skew `isInfluential`.

NOT an LLM job — pure Semantic Scholar REST, no subscription, no metered API, key-free
(optional free S2 key raises the rate limit). We fetch ONE `/references` page per distinct
citing paper (84 of them) and match each reference back to our cited papers locally, so the
whole eval is ~84 requests.

Mapping S2 -> our taxonomy:
    background   -> background
    methodology  -> uses_extends
    result       -> (no clean map; recorded, excluded from agreement)
    (none)       -> S2 has the edge but no intent label (counts toward 'unlabelled overlap')
Our `compares_contrasts` has no S2 counterpart; we report where S2 saw those edges as
background/methodology instead (expected — S2 can't express contrast).

Usage (repo root):
    export S2_API_KEY=...            # optional; without it S2 rate-limits harder
    python experiments/edge_quality/s2_intent_eval.py
    python experiments/edge_quality/s2_intent_eval.py --fresh
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "experiments" / "edge_quality" / "out"
S2 = "https://api.semanticscholar.org/graph/v1"

# S2 intent value -> our class (result has no clean map; kept as None)
S2_TO_OURS = {"background": "background", "methodology": "uses_extends"}


def http_json(url: str, *, api_key: str | None, tries: int = 6, base_sleep: float = 2.0):
    headers = {"User-Agent": "prior-edge-quality-exp"}
    if api_key:
        headers["x-api-key"] = api_key
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503):
                time.sleep(base_sleep * (2 ** i))
                continue
            raise
        except Exception:
            time.sleep(base_sleep * (2 ** i))
    return None


def arxiv_id_of(p: dict) -> str | None:
    for f in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:./]|abs/|pdf/)(\d{4}\.\d{4,5})", str(p.get(f) or ""), re.I)
        if m:
            return m.group(1)
    return None


def norm_doi(d: str | None) -> str | None:
    if not d:
        return None
    return d.lower().removeprefix("https://doi.org/").strip() or None


def s2_ref_key(p: dict) -> str | None:
    """The external id we hand S2 to look a paper up by (arXiv preferred, then DOI)."""
    if (a := arxiv_id_of(p)):
        return f"ARXIV:{a}"
    if (d := norm_doi(p.get("doi"))):
        return f"DOI:{d}"
    return None


def match_cited(ext: dict, arx_idx: dict, doi_idx: dict) -> str | None:
    """S2 citedPaper.externalIds -> our cited paper_id (via arXiv or DOI), else None."""
    ext = ext or {}
    a = str(ext.get("ArXiv") or "").lower()
    if a and a in arx_idx:
        return arx_idx[a]
    d = norm_doi(ext.get("DOI"))
    if d and d in doi_idx:
        return doi_idx[d]
    return None


def load():
    papers = {}
    for l in open(REPO / "data" / "prior-core-v0.2" / "papers_core.jsonl", encoding="utf-8"):
        if l.strip():
            p = json.loads(l)
            papers[p["id"]] = p
    intent = json.load(open(OUT / "citations_intent.json", encoding="utf-8"))
    # edge-level our-label: {citing->cited: intent}
    ours = {f"{e['citing_id']}->{e['cited_id']}": e["intent"] for e in intent["edges"]}
    return papers, ours


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT / "s2_intent_eval.json"))
    ap.add_argument("--checkpoint", default=str(OUT / "s2_intent_eval.ckpt.json"))
    ap.add_argument("--api-key", default=os.environ.get("S2_API_KEY"))
    ap.add_argument("--sleep", type=float, default=1.1, help="seconds between S2 calls")
    ap.add_argument("--fresh", action="store_true")
    args = ap.parse_args()

    papers, ours = load()
    arx_idx = {a.lower(): pid for pid, p in papers.items() if (a := arxiv_id_of(p))}
    doi_idx = {d: pid for pid, p in papers.items() if (d := norm_doi(p.get("doi")))}

    # our edges grouped by citing paper (one S2 fetch per citing paper)
    by_citing: dict[str, list[str]] = defaultdict(list)
    for edge in ours:
        citing = edge.split("->")[0]
        by_citing[citing].append(edge)
    print(f"[data] {len(ours)} typed edges | {len(by_citing)} distinct citing papers to query S2")

    ckpt_path = Path(args.checkpoint)
    fetched: dict[str, dict] = {}  # edge -> {s2_intents, isInfluential} for edges S2 knows
    if ckpt_path.exists() and not args.fresh:
        fetched = json.load(open(ckpt_path, encoding="utf-8"))
        print(f"[resume] {len(fetched)} edges already looked up in S2")

    done_citing = {e.split("->")[0] for e in fetched}
    todo = [c for c in by_citing if c not in done_citing]
    print(f"[run] {len(todo)} citing papers remaining\n")

    for i, citing in enumerate(todo):
        key = s2_ref_key(papers.get(citing, {}))
        if not key:
            fetched[f"__nokey__{citing}"] = {"skipped": "no arXiv/DOI"}
            continue
        # paginate references (limit 1000 usually covers a single paper's ref list)
        offset, seen_any = 0, False
        while True:
            url = (f"{S2}/paper/{urllib.parse.quote(key, safe=':')}/references"
                   f"?fields=intents,isInfluential,citedPaper.externalIds,citedPaper.title"
                   f"&limit=1000&offset={offset}")
            j = http_json(url, api_key=args.api_key)
            time.sleep(args.sleep)
            if not j or not j.get("data"):
                break
            seen_any = True
            for row in j["data"]:
                cp = row.get("citedPaper") or {}
                cid = match_cited(cp.get("externalIds"), arx_idx, doi_idx)
                if not cid:
                    continue
                edge = f"{citing}->{cid}"
                if edge in ours:
                    fetched[edge] = {
                        "s2_intents": row.get("intents") or [],
                        "isInfluential": bool(row.get("isInfluential")),
                        "s2_title": cp.get("title"),
                    }
            nxt = j.get("next")
            if nxt is None or len(j["data"]) < 1000:
                break
            offset = nxt
        # mark this citing paper handled even if S2 didn't know it (avoid re-querying)
        fetched.setdefault(f"__done__{citing}", {"in_s2": seen_any})
        json.dump(fetched, open(ckpt_path, "w", encoding="utf-8"), indent=1)
        print(f"[{i+1}/{len(todo)}] {citing} ({key}) -> "
              f"{sum(1 for e in fetched if e.startswith(citing+'->') )} of our edges matched", flush=True)

    # ── analysis ────────────────────────────────────────────────────────────
    real = {e: v for e, v in fetched.items() if e in ours}          # edges S2 returned
    labelled = {e: v for e, v in real.items() if v["s2_intents"]}   # ... and carried an intent
    n_edges = len(ours)
    print(f"\n== OVERLAP ==")
    print(f"our typed edges           : {n_edges}")
    print(f"present in S2's ref graph : {len(real)} ({100*len(real)/n_edges:.0f}%)")
    print(f"...carrying an intent tag : {len(labelled)} ({100*len(labelled)/n_edges:.0f}%)")
    print(f"...flagged isInfluential  : {sum(v['isInfluential'] for v in real.values())}")

    # our-intent vs mapped-S2-intent, on the labelled overlap
    def map_s2(intents: list[str]) -> str | None:
        # prefer methodology (uses_extends) if present, else background; result -> None
        for want in ("methodology", "background"):
            if want in intents:
                return S2_TO_OURS[want]
        return None

    grid = defaultdict(Counter)
    agree = total = 0
    for e, v in labelled.items():
        oursi = ours[e]
        s2i = map_s2(v["s2_intents"])
        grid[oursi][s2i or "result/other"] += 1
        if s2i is not None:
            total += 1
            agree += int(oursi == s2i)  # only background & uses_extends are comparable
    print(f"\n== our intent  ×  S2 intent (mapped), labelled overlap n={len(labelled)} ==")
    cols = ["background", "uses_extends", "result/other"]
    print(f"{'ours \\ s2':22}" + "".join(f"{c:>15}" for c in cols))
    for oi in ("background", "uses_extends", "compares_contrasts"):
        r = grid[oi]
        print(f"{oi:22}" + "".join(f"{r.get(c,0):15}" for c in cols))
    if total:
        print(f"\nagreement on comparable classes (background/uses_extends): "
              f"{agree}/{total} = {100*agree/total:.0f}%")

    # isInfluential vs our intent
    infl = defaultdict(lambda: [0, 0])
    for e, v in real.items():
        infl[ours[e]][int(v["isInfluential"])] += 1
    print(f"\n== isInfluential rate by our intent (edges in S2, n={len(real)}) ==")
    for oi in ("background", "uses_extends", "compares_contrasts"):
        no, yes = infl[oi]
        tot = no + yes
        if tot:
            print(f"{oi:22} {yes:3}/{tot:3} influential = {100*yes/tot:.0f}%")

    report = {
        "meta": {
            "n_our_edges": n_edges, "n_in_s2": len(real), "n_labelled": len(labelled),
            "n_influential": sum(v["isInfluential"] for v in real.values()),
            "mapping": S2_TO_OURS, "note": "S2 has no contrast class; silver standard only",
        },
        "cross": {oi: dict(grid[oi]) for oi in grid},
        "agreement_comparable": {"agree": agree, "total": total},
        "influential_by_intent": {oi: infl[oi] for oi in infl},
        "edges": {e: {**v, "our_intent": ours[e]} for e, v in real.items()},
    }
    json.dump(report, open(args.out, "w", encoding="utf-8"), indent=1)
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
