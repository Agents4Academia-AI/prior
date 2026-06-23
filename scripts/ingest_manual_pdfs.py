"""Ingest manually-downloaded PDFs — the bot-protected/SSO papers you grabbed in
your normal browser (the permitted human-readable route, and it sidesteps the bot
walls). Drop the PDFs (any filenames) into data_hackathon/manual_pdfs/. Each is
auto-matched to a corpus paper by the DOI printed on its first pages (fallback:
title), parsed with pymupdf, and cached as clean text — the extraction sweep then
turns them into contributions.

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/ingest_manual_pdfs.py
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, fulltext               # noqa: E402
from prior.models import Paper                     # noqa: E402


def _log(m):
    print(m, flush=True)


def _toks(t):
    return set(re.sub(r"[^a-z0-9]", " ", (t or "").lower()).split())


def main():
    import fitz
    config.ensure_dirs()
    pdir = config.DATA / "manual_pdfs"
    pdir.mkdir(parents=True, exist_ok=True)
    corpus = [Paper.from_dict(json.loads(l))
              for l in (config.RAW / "papers.jsonl").read_text().splitlines() if l]
    by_doi = {}
    for p in corpus:
        d = (p.doi or "").replace("https://doi.org/", "").lower()
        if d:
            by_doi[d] = p

    pdfs = sorted(pdir.glob("*.pdf"))
    _log(f"ingesting {len(pdfs)} PDFs from {pdir}")
    matched = 0
    for f in pdfs:
        try:
            doc = fitz.open(f)
            head = "\n".join(doc[i].get_text() for i in range(min(3, len(doc))))
        except Exception as e:  # noqa: BLE001
            _log(f"  {f.name}: cannot open ({e})")
            continue
        paper, how = None, ""
        m = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", head)
        if m and m.group(0).rstrip(".").lower() in by_doi:
            paper, how = by_doi[m.group(0).rstrip(".").lower()], "doi"
        if not paper:                                  # fall back to title overlap
            cand = _toks(" ".join(l for l in head.splitlines()[:8] if len(l.strip()) > 20))
            best, score = None, 0.0
            for p in corpus:
                tt = _toks(p.title)
                if tt and len(tt & cand) / len(tt) > score:
                    best, score = p, len(tt & cand) / len(tt)
            if score > 0.7:
                paper, how = best, f"title({score:.0%})"
        if not paper:
            _log(f"  {f.name}: NO MATCH — rename it to its DOI and re-run")
            continue
        text = "\n".join(doc[i].get_text() for i in range(min(14, len(doc))))
        text = text.replace("ﬁ", "fi").replace("ﬂ", "fl").replace("ﬀ", "ff")
        fulltext._cache_path(paper).write_text(text)
        matched += 1
        _log(f"  {f.name} → {paper.short_cite()} [{how}] ({len(text)} chars cached)")
    _log(f"DONE | matched+cached {matched}/{len(pdfs)} — run extract_cached.py to "
         f"turn them into contributions")


if __name__ == "__main__":
    main()
