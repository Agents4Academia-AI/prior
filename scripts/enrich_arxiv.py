"""Exploration enrichment — attach OPEN arXiv twins to corpus records that came in
closed (e.g. OpenAlex canonicalised a paper to a publisher/repository deposit with
no arXiv locator). Persists to papers.jsonl so the full-text stage then uses the
open edition. Polite to the arXiv API (1s between queries).

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/enrich_arxiv.py --select missing
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, pipeline                 # noqa: E402
from prior.models import Paper                       # noqa: E402


def _log(m):
    print(m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--select", choices=["all", "core", "missing", "skip", "preprints"],
                    default="missing")
    args = ap.parse_args()
    config.ensure_dirs()

    pp = config.RAW / "papers.jsonl"
    corpus = [Paper.from_dict(json.loads(l)) for l in pp.read_text().splitlines() if l]
    byid = {p.id: p for p in corpus}
    sel = [byid[p.id] for p in pipeline.select_papers(args.select) if p.id in byid]
    _log(f"enriching {len(sel)} papers (--select {args.select})")
    n = pipeline.enrich_arxiv_twins(sel, progress=_log)        # mutates the corpus objects
    if n:
        pp.write_text("\n".join(json.dumps(p.to_dict()) for p in corpus) + "\n")
        _log(f"persisted {n} arXiv twins to papers.jsonl — now run get_fulltext.py")


if __name__ == "__main__":
    main()
