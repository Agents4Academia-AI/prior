#!/usr/bin/env python3
"""Intra-corpus citations from arXiv LaTeX sources (.bbl/.bib) — source #3.

arXiv serves each paper's source at export.arxiv.org/e-print/<id> (tar.gz or a
single gzipped .tex). The bundled .bbl (or .bib) is the author's actual
bibliography — complete and structured, unlike PDF-extracted text. We fetch the
source for every arXiv paper in the corpus, pull all .bbl/.bib content, and
match entries against the other corpus papers by arXiv id and normalized title.

Polite: 1 request / 3s against the export mirror; cached under out/eprints/ so
re-runs are free. Sources are used for mining only (not redistributed).

Writes out/citations_bbl.json (same shape; merge with merge_citations.py).

Usage:
  python3 experiments/edge_quality/fetch_arxiv_bbl.py --papers ../prior-core-v0.2/papers_core.jsonl
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import tarfile
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "out"
CACHE = OUT / "eprints"


def arxiv_id_of(p: dict) -> str | None:
    for field in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5})(v\d+)?", str(p.get(field) or ""), re.I)
        if m:
            return m.group(1) + (m.group(2) or "")
    return None


def norm(s: str) -> str:
    s = re.sub(r"[{}\\~'\"`^]|\\[a-zA-Z]+", " ", s)      # strip TeX markup
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def fetch_source(aid: str) -> bytes | None:
    f = CACHE / f"{aid.replace('/', '_')}.bin"
    if f.exists():
        return f.read_bytes() or None
    url = f"https://arxiv.org/src/{aid}"
    import subprocess
    r = subprocess.run(["curl", "-sL", "-m", "60", url], capture_output=True)
    data = r.stdout if r.returncode == 0 else b""
    if not data:
        print(f"  {aid}: fetch failed (curl rc={r.returncode})", flush=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)
    time.sleep(3.0)                                       # arXiv politeness
    return data or None


def bib_texts(data: bytes) -> list[str]:
    """All .bbl/.bib contents from an e-print blob (tar.gz, gz-tex, or raw)."""
    out = []
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
            for m in tf.getmembers():
                if m.name.lower().endswith((".bbl", ".bib")):
                    fh = tf.extractfile(m)
                    if fh:
                        out.append(fh.read().decode("utf-8", errors="ignore"))
        return out
    except tarfile.TarError:
        pass
    try:                                                   # single gzipped file
        text = gzip.decompress(data).decode("utf-8", errors="ignore")
        if "\\bibitem" in text or "@article" in text.lower():
            out.append(text)
    except OSError:
        pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True)
    args = ap.parse_args()
    papers = [json.loads(l) for l in open(args.papers) if l.strip()]

    sig = {p["id"]: {"arx": (arxiv_id_of(p) or "").split("v")[0] or None,
                     "title": (t if len(t := norm(p.get("title") or "")) >= 25 else None)}
           for p in papers}

    edges: set[tuple[str, str]] = set()
    n_src = n_bib = 0
    for p in papers:
        aid = arxiv_id_of(p)
        if not aid:
            continue
        data = fetch_source(aid)
        if not data:
            continue
        n_src += 1
        texts = bib_texts(data)
        if not texts:
            continue
        n_bib += 1
        blob = "\n".join(texts)
        nblob = norm(blob)
        for q in papers:
            if q["id"] == p["id"]:
                continue
            s = sig[q["id"]]
            hit = False
            if s["arx"] and s["arx"] != sig[p["id"]]["arx"] and \
               re.search(rf"(?<![\d.]){re.escape(s['arx'])}(?![\d])", blob):
                hit = True
            if not hit and s["title"] and s["title"] != sig[p["id"]]["title"] and s["title"] in nblob:
                hit = True
            if hit:
                edges.add((p["id"], q["id"]))

    result = {"edges": sorted(edges),
              "coverage": {"papers": len(papers), "sources_fetched": n_src,
                           "with_bbl_or_bib": n_bib, "intra_corpus_edges": len(edges)},
              "method": "arXiv e-print .bbl/.bib matched on arXiv ids + normalized titles"}
    (OUT / "citations_bbl.json").write_text(json.dumps(result, indent=1))
    print(f"\nDONE: {n_src} sources, {n_bib} with .bbl/.bib -> {len(edges)} intra-corpus edges "
          f"-> {OUT/'citations_bbl.json'}", flush=True)


if __name__ == "__main__":
    main()
