"""Cheap, bounded recovery: fold the gold-bib anchors into an existing corpus and
extract contributions for ONLY the newly-added papers — no snowball, no rescore.

Use after a base build is done, to guarantee curated gold papers are present
without the cost of another snowball hop.

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/fold_anchors.py
    PRIOR_TOPIC=topic_search PRIOR_DATA_DIR=data_search PYTHONPATH=src python3 scripts/fold_anchors.py
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
sys.path.insert(0, str(HERE))

from prior import config, pipeline               # noqa: E402
from prior.atlas import Atlas                     # noqa: E402
from prior.models import Paper                    # noqa: E402
from weekend_run import _gold_anchors             # noqa: E402


def main():
    pp = config.RAW / "papers.jsonl"
    papers = [Paper.from_dict(json.loads(l))
              for l in pp.read_text().splitlines() if l]
    have = {p.id for p in papers}

    anchors = _gold_anchors()
    new = [p for p in anchors if p.id not in have]
    print(f"corpus {len(papers)} | anchors resolved {len(anchors)} | "
          f"new to fold {len(new)}", flush=True)
    for p in new:
        papers.append(p)

    with pp.open("w") as f:
        for p in papers:
            f.write(json.dumps(p.to_dict()) + "\n")
    sc = config.ATLAS / "scope.json"
    topic = json.loads(sc.read_text()).get("topic", "") if sc.exists() else ""
    a = Atlas(); a.topic = topic
    for p in papers:
        a.add_paper(p)
    a.link_citations(); a.save()

    # resumable: skips the papers already in contributions.partial.jsonl,
    # so only the newly-folded anchors are extracted
    print(f"extracting contributions over {len(papers)} papers "
          f"(resumes; only ~{len(new)} new) ...", flush=True)
    pipeline.extract_contributions(papers, relate=False,
                                   progress=lambda m: print("  " + m, flush=True))
    pipeline.relate_contributions_fast(progress=lambda m: print("  " + m, flush=True))
    print("DONE fold", flush=True)


if __name__ == "__main__":
    main()
