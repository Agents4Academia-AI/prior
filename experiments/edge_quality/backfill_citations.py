#!/usr/bin/env python3
"""Stage 0 of the edge-quality experiment: backfill reference lists for the core
corpus and emit the intra-corpus citation graph.

Why: only 33/152 core papers carry `referenced_works` (arXiv 0/34, S2 0/23), so
citation-aware relation labeling (Arm C) has nothing to eat, and the
citation-vs-relation overlap diagnostic is meaningless. This script:

  1. resolves every paper to an OpenAlex work (by W-id, then DOI — arXiv papers
     usually resolve via their 10.48550 DOI) and fetches `referenced_works`;
  2. falls back to Semantic Scholar (`/paper/{id}/references`) for the rest,
     with polite 429 backoff;
  3. matches references back into the corpus (OpenAlex id / DOI / arXiv id) and
     writes `out/citations_core.json`:
       { "edges": [[citer_paper_id, citee_paper_id], ...],   # directed
         "refs":  { paper_id: {"n_refs": int, "source": "openalex|s2|none"} },
         "coverage": {...} }

Deterministic, key-free, resumable (checkpoints after every paper).

Usage:
  python3 experiments/edge_quality/backfill_citations.py \
      --papers ../prior-core-v0.2/papers_core.jsonl \
      [--out experiments/edge_quality/out] [--mailto you@example.org]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OA = "https://api.openalex.org"
S2 = "https://api.semanticscholar.org/graph/v1"


def http_json(url: str, *, tries: int = 5, base_sleep: float = 2.0) -> dict | None:
    """GET url -> parsed json, with exponential backoff on 429/5xx."""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "prior-edge-quality-exp"})
            with urllib.request.urlopen(req, timeout=30) as r:
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
    """Pull a bare arXiv id (2401.12345) from id/url/doi/pdf_url if present."""
    for field in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:./]|abs/|pdf/)(\d{4}\.\d{4,5})", str(p.get(field) or ""), re.I)
        if m:
            return m.group(1)
    return None


def norm_doi(d: str | None) -> str | None:
    if not d:
        return None
    return d.lower().removeprefix("https://doi.org/").strip() or None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True)
    ap.add_argument("--out", default="experiments/edge_quality/out")
    ap.add_argument("--mailto", default="prior@example.org")  # OpenAlex polite pool
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    ckpt_f = out / "refs_checkpoint.json"
    papers = [json.loads(l) for l in open(args.papers) if l.strip()]

    # -- corpus indexes for matching references back in --------------------
    by_oa: dict[str, str] = {}    # W... -> paper_id
    by_doi: dict[str, str] = {}
    by_arx: dict[str, str] = {}
    for p in papers:
        pid = p["id"]
        if "openalex" in pid:
            by_oa[pid.split(":")[-1]] = pid
        if (d := norm_doi(p.get("doi"))):
            by_doi[d] = pid
        if (a := arxiv_id_of(p)):
            by_arx[a] = pid

    refs: dict[str, dict] = json.loads(ckpt_f.read_text()) if ckpt_f.exists() else {}

    def save() -> None:
        ckpt_f.write_text(json.dumps(refs))

    # -- pass 1: OpenAlex (native W-id, else DOI resolution) ---------------
    for i, p in enumerate(papers):
        pid = p["id"]
        if pid in refs:
            continue
        ref_ids: list[str] | None = None
        if p.get("referenced_works"):                       # already ingested
            ref_ids = [str(r).split("/")[-1].split(":")[-1] for r in p["referenced_works"]]
            refs[pid] = {"source": "ingest", "oa_refs": ref_ids, "ext": []}
            save(); continue
        wid = pid.split(":")[-1] if "openalex" in pid else None
        url = None
        if wid:
            url = f"{OA}/works/{wid}?select=referenced_works&mailto={args.mailto}"
        elif (d := norm_doi(p.get("doi"))):
            url = f"{OA}/works/doi:{urllib.parse.quote(d, safe='')}?select=referenced_works&mailto={args.mailto}"
        if url and (j := http_json(url)) is not None:
            ref_ids = [str(r).split("/")[-1].split(":")[-1] for r in (j.get("referenced_works") or [])]
            refs[pid] = {"source": "openalex", "oa_refs": ref_ids, "ext": []}
            save()
            print(f"[oa {i+1}/{len(papers)}] {pid}: {len(ref_ids)} refs", flush=True)
            time.sleep(0.15)                                # ~7/s, polite pool

    # -- pass 2: Semantic Scholar fallback ----------------------------------
    for i, p in enumerate(papers):
        pid = p["id"]
        if pid in refs:
            continue
        sid = None
        if (a := arxiv_id_of(p)):
            sid = f"arXiv:{a}"
        elif (d := norm_doi(p.get("doi"))):
            sid = f"DOI:{d}"
        if not sid:
            refs[pid] = {"source": "none", "oa_refs": [], "ext": []}
            save(); continue
        j = http_json(f"{S2}/paper/{urllib.parse.quote(sid)}/references"
                      f"?fields=externalIds&limit=1000", base_sleep=12.0)
        ext = []
        for r in (j or {}).get("data", []):
            e = (r.get("citedPaper") or {}).get("externalIds") or {}
            ext.append({"doi": norm_doi(e.get("DOI")), "arx": e.get("ArXiv")})
        refs[pid] = {"source": "s2" if j else "none", "oa_refs": [], "ext": ext}
        save()
        print(f"[s2 {i+1}/{len(papers)}] {pid}: {len(ext)} refs", flush=True)
        time.sleep(2.0)                                     # S2 unauthenticated limit

    # -- match references into the corpus -> directed citation edges --------
    edges: set[tuple[str, str]] = set()
    for pid, r in refs.items():
        for w in r.get("oa_refs", []):
            if w in by_oa and by_oa[w] != pid:
                edges.add((pid, by_oa[w]))
        for e in r.get("ext", []):
            tgt = by_doi.get(e.get("doi") or "") or by_arx.get(e.get("arx") or "")
            if tgt and tgt != pid:
                edges.add((pid, tgt))

    n_with = sum(1 for r in refs.values() if r["source"] != "none" and (r["oa_refs"] or r["ext"]))
    result = {
        "edges": sorted(edges),
        "refs": {pid: {"n_refs": len(r["oa_refs"]) + len(r["ext"]), "source": r["source"]}
                 for pid, r in refs.items()},
        "coverage": {"papers": len(papers), "with_refs": n_with,
                     "intra_corpus_edges": len(edges)},
    }
    (out / "citations_core.json").write_text(json.dumps(result, indent=1))
    print(f"\nDONE: {n_with}/{len(papers)} papers with refs · "
          f"{len(edges)} intra-corpus citation edges -> {out/'citations_core.json'}", flush=True)


if __name__ == "__main__":
    main()
