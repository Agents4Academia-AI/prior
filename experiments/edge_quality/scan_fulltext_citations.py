#!/usr/bin/env python3
"""Intra-corpus citations by scanning cached FULL TEXT — no API, no LLM.

S2/OpenAlex reference lists are incomplete for this fresh-arXiv corpus, but we
only need *intra-corpus* edges (do any of these 152 papers cite each other?).
So: for each corpus paper with cached full text, search the text for every
OTHER corpus paper's (a) arXiv id — near-perfect precision — and (b) normalized
title (>= 25 chars, to avoid short-title false hits). A hit anywhere in the
text (references section or inline) counts: text-mentions-paper => citer edge.

Writes out/citations_fulltext.json in the same shape as citations_core.json;
merge_citations.py unions the sources.

Usage:
  python3 experiments/edge_quality/scan_fulltext_citations.py \
      --papers ../prior-core-v0.2/papers_core.jsonl \
      --fulltext ../prior/data_hackathon/fulltext
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

OUT = Path(__file__).parent / "out"


def arxiv_id_of(p: dict) -> str | None:
    for field in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5})", str(p.get(field) or ""), re.I)
        if m:
            return m.group(1)
    return None


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True)
    ap.add_argument("--fulltext", required=True)
    args = ap.parse_args()

    papers = [json.loads(l) for l in open(args.papers) if l.strip()]
    ft_dir = Path(args.fulltext)

    # map each corpus paper -> its cached fulltext file (by arXiv id in filename)
    files = {f.name: f for f in ft_dir.glob("*.txt")}
    def ft_of(p: dict) -> Path | None:
        a = arxiv_id_of(p)
        if not a:
            return None
        cands = [n for n in files if n.startswith(f"arxiv_{a}")]
        return files[sorted(cands)[0]] if cands else None

    # per-paper detection signatures
    sig = {}
    for p in papers:
        t = norm(p.get("title") or "")
        sig[p["id"]] = {"arx": arxiv_id_of(p), "title": t if len(t) >= 25 else None}

    edges: set[tuple[str, str]] = set()
    n_scanned = 0
    for p in papers:
        f = ft_of(p)
        if not f:
            continue
        n_scanned += 1
        try:
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        tnorm = norm(text)
        for q in papers:
            if q["id"] == p["id"]:
                continue
            s = sig[q["id"]]
            hit = False
            if s["arx"] and re.search(rf"(?<![\d.]){re.escape(s['arx'])}(?![\d])", text):
                # don't fire on the paper's own id appearing in its header
                hit = s["arx"] != sig[p["id"]]["arx"]
            if not hit and s["title"] and s["title"] in tnorm:
                # exclude self-title (it's obviously in its own text)
                hit = s["title"] != sig[p["id"]]["title"]
            if hit:
                edges.add((p["id"], q["id"]))          # p's text mentions q => p cites q

    result = {
        "edges": sorted(edges),
        "coverage": {"papers": len(papers), "fulltext_scanned": n_scanned,
                     "intra_corpus_edges": len(edges)},
        "method": "fulltext scan: other papers' arXiv ids + normalized titles (>=25 chars)",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "citations_fulltext.json").write_text(json.dumps(result, indent=1))
    print(f"scanned {n_scanned}/{len(papers)} fulltexts -> {len(edges)} intra-corpus "
          f"citation edges -> {OUT/'citations_fulltext.json'}", flush=True)


if __name__ == "__main__":
    main()
