"""Collapse cross-namespace duplicates in a corpus.

OpenAlex (W-ids), arXiv (arxiv:…), and Semantic Scholar (s2:…) key the SAME paper
differently, so a snowball that mixes sources can add a paper twice. This dedups
by normalised title, preferring OpenAlex (it carries the citation graph), then
rebuilds the atlas and contributions (resumable — dropped dupes fall out, nothing
is re-extracted).

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/dedup_corpus.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
sys.path.insert(0, str(HERE))

from prior import config, pipeline, scoper       # noqa: E402
from prior.atlas import Atlas                     # noqa: E402
from prior.models import Paper                    # noqa: E402

# the OpenAlex capture-recapture estimate is the reliable completeness basis;
# the S2 hop couldn't add overlap (cross-namespace ids), so we carry it forward.
_EST_TOTAL, _EST_CI, _OVERLAP = 4105.4, [3322.3, 4888.5], 76


def main():
    pp = config.RAW / "papers.jsonl"
    corpus = [Paper.from_dict(json.loads(l))
              for l in pp.read_text().splitlines() if l]
    before = len(corpus)
    corpus = scoper._dedup_cross_source(corpus)
    print(f"dedup: {before} → {len(corpus)} papers (−{before - len(corpus)} dupes)",
          flush=True)

    with pp.open("w") as f:
        for p in corpus:
            f.write(json.dumps(p.to_dict()) + "\n")
    sc = config.ATLAS / "scope.json"
    o = json.loads(sc.read_text())
    a = Atlas(); a.topic = o.get("topic", "")
    for p in corpus:
        a.add_paper(p)
    a.link_citations(); a.save()

    pipeline.extract_contributions(corpus, relate=False,
                                   progress=lambda m: print("  " + m, flush=True))
    pipeline.relate_contributions_fast(progress=lambda m: print("  " + m, flush=True))

    o["completeness"] = {
        "observed": len(corpus), "estimate_total": _EST_TOTAL,
        "estimate_ci95": _EST_CI, "recall": round(len(corpus) / _EST_TOTAL, 3),
        "overlap": _OVERLAP,
        "note": ("estimate from the OpenAlex capture-recapture hop; the S2 hop "
                 "added recent papers but cross-namespace ids prevented a fresh "
                 "overlap measurement"),
    }
    sc.write_text(json.dumps(o, indent=2))
    print(f"DONE dedup | corpus {len(corpus)} | recall "
          f"≈ {o['completeness']['recall']}", flush=True)


if __name__ == "__main__":
    main()
