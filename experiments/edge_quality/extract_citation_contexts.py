#!/usr/bin/env python3
"""Citation CONTEXTS: the text surrounding each intra-corpus in-text citation.

The sentence around a citation is highly informative about relation type
("we build on [Q]" / "unlike [Q]" / "consistent with [Q]") — scite.ai's
supporting/contrasting idea. From the cached e-print sources (out/eprints/):

  1. in citer P's .bbl/.bib, find the entry matching corpus paper Q
     (arXiv id or normalized title) -> its \\bibitem/@entry KEY;
  2. find \\cite*{...key...} occurrences in P's .tex body;
  3. extract a ±window of de-TeXed text around each -> contexts.

Writes out/citation_contexts.json: {"P->Q": ["...context...", ...]} for Arm C.

Usage: python3 experiments/edge_quality/extract_citation_contexts.py --papers ../prior-core-v0.2/papers_core.jsonl
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import tarfile
from pathlib import Path

OUT = Path(__file__).parent / "out"
WINDOW = 320          # chars either side of the \cite


def arxiv_id_of(p: dict) -> str | None:
    for f in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5})", str(p.get(f) or ""), re.I)
        if m:
            return m.group(1)
    return None


def norm(s: str) -> str:
    s = re.sub(r"[{}\\~'\"`^]|\\[a-zA-Z]+", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def detex(s: str) -> str:
    s = re.sub(r"\\cite[tp]?\*?(\[[^\]]*\])?\{[^}]*\}", "[CITED]", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", s)
    s = re.sub(r"[{}$~%]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def files_of(blob: bytes) -> dict[str, str]:
    out = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:*") as tf:
            for m in tf.getmembers():
                if m.name.lower().endswith((".tex", ".bbl", ".bib")):
                    fh = tf.extractfile(m)
                    if fh:
                        out[m.name] = fh.read().decode("utf-8", errors="ignore")
    except tarfile.TarError:
        try:
            out["main.tex"] = gzip.decompress(blob).decode("utf-8", errors="ignore")
        except OSError:
            pass
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", required=True)
    args = ap.parse_args()
    papers = [json.loads(l) for l in open(args.papers) if l.strip()]
    sig = {p["id"]: {"arx": arxiv_id_of(p),
                     "title": (t if len(t := norm(p.get("title") or "")) >= 25 else None)}
           for p in papers}

    contexts: dict[str, list[str]] = {}
    n_pairs = 0
    for p in papers:
        aid_v = None
        for f in ("id", "url", "doi", "pdf_url"):
            m = re.search(r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5}(?:v\d+)?)", str(p.get(f) or ""), re.I)
            if m:
                aid_v = m.group(1); break
        if not aid_v:
            continue
        cache = OUT / "eprints" / f"{aid_v.replace('/', '_')}.bin"
        if not cache.exists() or not cache.stat().st_size:
            continue
        fs = files_of(cache.read_bytes())
        bibs = "\n".join(v for k, v in fs.items() if k.lower().endswith((".bbl", ".bib")))
        texs = "\n".join(v for k, v in fs.items() if k.lower().endswith(".tex"))
        if not bibs or not texs:
            continue
        # split bibliography into entries with their keys
        entries = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}(.*?)(?=\\bibitem|\Z)", bibs, re.S) \
                + re.findall(r"@\w+\{([^,]+),(.*?)\n\}", bibs, re.S)
        for q in papers:
            if q["id"] == p["id"]:
                continue
            s = sig[q["id"]]
            key = None
            for k, body in entries:
                if (s["arx"] and s["arx"] in body) or (s["title"] and s["title"] in norm(body)):
                    key = k.strip(); break
            if not key:
                continue
            ctxs = []
            for m in re.finditer(r"\\cite[a-z]*\*?(?:\[[^\]]*\])?\{([^}]*)\}", texs):
                if key in [x.strip() for x in m.group(1).split(",")]:
                    a, b = max(0, m.start() - WINDOW), min(len(texs), m.end() + WINDOW)
                    ctxs.append(detex(texs[a:b]))
                if len(ctxs) >= 2:
                    break
            if ctxs:
                contexts[f'{p["id"]}->{q["id"]}'] = ctxs
                n_pairs += 1
    (OUT / "citation_contexts.json").write_text(json.dumps(contexts, indent=1))
    print(f"contexts for {n_pairs} citation pairs -> {OUT/'citation_contexts.json'}", flush=True)


if __name__ == "__main__":
    main()
