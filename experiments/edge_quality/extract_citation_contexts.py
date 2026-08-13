#!/usr/bin/env python3
"""Citation CONTEXTS: the text surrounding each intra-corpus in-text citation.

The sentence around a citation is highly informative about relation type
("we build on [Q]" / "unlike [Q]" / "consistent with [Q]") — scite.ai's
supporting/contrasting idea. From the cached e-print sources (out/eprints/):

  1. in citer P's .bbl/.bib, find the entry matching corpus paper Q
     (arXiv id or normalized title) -> its \\bibitem/@entry KEY;
  2. find \\cite*{...key...} occurrences in P's .tex body;
  3. extract a ±window of de-TeXed text around each -> contexts.

The citation that resolves to the destination Q is tagged ``[CITED:TARGET]``
(others stay ``[CITED]``) so a consumer can tell, in a multi-cite sentence,
which citation is this edge's destination.

Writes:
  out/citation_contexts.json: {"P->Q": ["...context...", ...]}  (back-compat)
  out/citation_map.json:      [{citing_id, cited_id, cite_key, bibtex,
                                contexts:[{text, target_offset}]}, ...]
    -- the join map from OpenAlex/arXiv edge endpoints to the citing paper's
       raw \\cite key / BibTeX entry (RefWarden's join key).

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


CITE_RE = r"\\cite[a-z]*\*?(?:\[[^\]]*\])?\{[^}]*\}"


def detex(s: str) -> str:
    s = re.sub(CITE_RE, "[CITED]", s)
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", s)
    s = re.sub(r"[{}$~%]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def detex_marked(window: str, target_start: int) -> str:
    """De-TeX ``window``, tagging the citation whose match begins at
    ``target_start`` (offset within ``window``) as ``[CITED:TARGET]`` and every
    other in-text citation as ``[CITED]``. Lets a consumer disambiguate which
    citation in a multi-cite sentence is the edge's destination."""
    def repl(mm: "re.Match[str]") -> str:
        return "[CITED:TARGET]" if mm.start() == target_start else "[CITED]"
    s = re.sub(CITE_RE, repl, window)          # match offsets are vs. the original window
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

    contexts: dict[str, list[str]] = {}          # back-compat: {"P->Q": ["...text..."]}
    records: list[dict] = []                      # join map: one record per cited pair
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
            key = bib_body = None
            for k, body in entries:
                if (s["arx"] and s["arx"] in body) or (s["title"] and s["title"] in norm(body)):
                    key = k.strip()
                    bib_body = re.sub(r"\s+", " ", body).strip()   # the citing paper's raw \bibitem/@entry
                    break
            if not key:
                continue
            ctxs = []
            for m in re.finditer(r"\\cite[a-z]*\*?(?:\[[^\]]*\])?\{([^}]*)\}", texs):
                if key in [x.strip() for x in m.group(1).split(",")]:
                    a, b = max(0, m.start() - WINDOW), min(len(texs), m.end() + WINDOW)
                    text = detex_marked(texs[a:b], m.start() - a)
                    ctxs.append({"text": text, "target_offset": text.find("[CITED:TARGET]")})
                if len(ctxs) >= 2:
                    break
            if ctxs:
                contexts[f'{p["id"]}->{q["id"]}'] = [c["text"] for c in ctxs]
                records.append({
                    "citing_id": p["id"],     # OpenAlex/arXiv id of the citing paper (edge src)
                    "cited_id": q["id"],      # OpenAlex/arXiv id of the cited paper  (edge dst)
                    "cite_key": key,          # the \cite key / BibTeX entry key in the citing paper
                    "bibtex": bib_body,       # raw bibliography entry body for that key
                    "contexts": ctxs,         # [{text (with [CITED:TARGET]), target_offset}]
                })
                n_pairs += 1
    (OUT / "citation_contexts.json").write_text(json.dumps(contexts, indent=1))
    (OUT / "citation_map.json").write_text(json.dumps(records, indent=1))
    print(f"contexts for {n_pairs} citation pairs -> {OUT/'citation_contexts.json'}", flush=True)
    print(f"join map ({len(records)} records) -> {OUT/'citation_map.json'}", flush=True)


if __name__ == "__main__":
    main()
