"""Reconcile the gold-bib anchors with the corpus THROUGH the relevance filter.

The gold set is a recall gauge + snowball seeds — NOT an auto-include list. A
grant reference can be off-topic for this corpus (e.g. general-agent benchmarks
in an eval-of-AI-scientists grant). So we scope every anchor and let the filter
decide membership:

  - relevant gold not yet present  -> added (the recall guarantee that matters)
  - off-topic gold force-included earlier -> removed
  - search/snowball papers (already filter-passed, cached) -> untouched

Contributions are rebuilt from the final corpus (resumable), so removed papers
drop out automatically and only newly-added papers get extracted.

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/fold_anchors.py
    PRIOR_TOPIC=topic_search PRIOR_DATA_DIR=data_search PYTHONPATH=src python3 scripts/fold_anchors.py
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
from weekend_run import TOPIC, _gold_anchors      # noqa: E402


def main():
    pp = config.RAW / "papers.jsonl"
    cache = str(config.ATLAS / "scope_cache.jsonl")
    corpus = [Paper.from_dict(json.loads(l))
              for l in pp.read_text().splitlines() if l]

    anchors = _gold_anchors()
    print(f"resolved {len(anchors)} gold anchors; scoping (cache-aware) ...", flush=True)
    kept, dropped = scoper.scope(TOPIC, anchors, cache_path=cache,
                                 progress=lambda m: print("  " + m, flush=True))
    dropped_keys = {p.key() for p, _ in dropped}

    before = len(corpus)
    corpus = [p for p in corpus if p.key() not in dropped_keys]  # drop off-topic gold
    removed = before - len(corpus)
    have = {p.key() for p in corpus}
    added = 0
    for p, _ in kept:                                          # add relevant gold
        if p.key() not in have:
            corpus.append(p); have.add(p.key()); added += 1

    print(f"\ngold filter: {len(kept)} relevant, {len(dropped)} off-topic | "
          f"corpus {before} → {len(corpus)} (removed {removed} off-topic, "
          f"added {added} relevant)", flush=True)
    print("dropped as off-topic for this corpus:", flush=True)
    for p, r in dropped:
        print(f"   - {p.title[:58]}  ({r[:48]})", flush=True)

    with pp.open("w") as f:
        for p in corpus:
            f.write(json.dumps(p.to_dict()) + "\n")
    sc = config.ATLAS / "scope.json"
    topic = json.loads(sc.read_text()).get("topic", "") if sc.exists() else ""
    a = Atlas(); a.topic = topic
    for p in corpus:
        a.add_paper(p)
    a.link_citations(); a.save()

    print("rebuilding contributions over the reconciled corpus (resumable) ...", flush=True)
    pipeline.extract_contributions(corpus, relate=False,
                                   progress=lambda m: print("  " + m, flush=True))
    pipeline.relate_contributions_fast(progress=lambda m: print("  " + m, flush=True))
    print("DONE scoped-fold", flush=True)


if __name__ == "__main__":
    main()
