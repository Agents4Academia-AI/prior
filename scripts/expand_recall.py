"""Bounded recall expansion — push completeness up without the days-long grind.

  high-yield seeds (top-cited + recent) → bounded OpenAlex + S2 citation snowball
        → TF-IDF pre-filter (drop the obvious noise) → LLM relevance filter
        → merge (no cap) → recompute capture-recapture completeness.

The pre-filter is what makes this affordable: the snowball can be broad, but only
plausible candidates ever reach the (slow, claude-code) LLM filter.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon \
        PYTHONPATH=src python3 scripts/expand_recall.py
    PRIOR_TOPIC=topic_search PRIOR_DATA_DIR=data_search ... (for the search corpus)
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
sys.path.insert(0, str(HERE))

from prior import completeness, config, pipeline, scoper   # noqa: E402
from prior.atlas import Atlas                               # noqa: E402
from prior.models import Paper                              # noqa: E402
from weekend_run import TOPIC                                # noqa: E402


def _log(m):
    print(m, flush=True)


def main():
    pp = config.RAW / "papers.jsonl"
    cache = str(config.ATLAS / "scope_cache.jsonl")
    corpus = [Paper.from_dict(json.loads(l))
              for l in pp.read_text().splitlines() if l]
    corpus_keys = {p.key() for p in corpus}
    _log(f"corpus: {len(corpus)} papers")

    seeds = scoper.high_yield_seeds(corpus)
    s2_only = os.environ.get("EXPAND_S2_ONLY") == "1"
    _log(f"[1] bounded snowball from {len(seeds)} high-yield seeds "
         f"({'S2 only' if s2_only else 'OpenAlex + S2'}) ...")
    if s2_only:
        new_oa, reached_oa = [], set()
    else:
        new_oa, reached_oa = scoper.snowball(seeds, corpus=corpus, anchor_k=25,
                                             per_paper=40, progress=lambda m: _log("    " + m))
    new_s2, reached_s2 = scoper.snowball_s2(seeds, corpus=corpus, anchor_k=40,
                                            per_paper=40, progress=lambda m: _log("    " + m))
    cands = [p for p in scoper._dedup_cross_source(new_oa + new_s2)
             if p.key() not in corpus_keys]
    _log(f"    {len(cands)} new candidates ({len(new_oa)} OA + {len(new_s2)} S2)")

    _log("[2] scoping with pre-filter (cache-aware) ...")
    kept, _drop = scoper.scope(TOPIC, cands, cache_path=cache, use_prefilter=True,
                               progress=lambda m: _log("    " + m))
    new = [p for p, _ in kept]
    _log(f"    +{len(new)} relevant kept")

    merged = {p.key(): p for p in corpus}
    for p in new:
        merged.setdefault(p.key(), p)
    corpus = list(merged.values())

    with pp.open("w") as f:
        for p in corpus:
            f.write(json.dumps(p.to_dict()) + "\n")
    sc = config.ATLAS / "scope.json"
    o = json.loads(sc.read_text())
    a = Atlas(); a.topic = o.get("topic", "")
    for p in corpus:
        a.add_paper(p)
    a.link_citations(); a.save()

    overlap = len((reached_oa | reached_s2) & corpus_keys)
    comp = completeness.capture_recapture(len(corpus_keys), overlap + len(new), overlap)
    o["kept"] = [{"id": p.id, "cite": p.short_cite(), "year": p.year,
                  "cited_by": p.cited_by_count, "title": p.title} for p in corpus]
    o["completeness"] = comp
    o["recall_expansion"] = {"seeds": len(seeds), "new": len(new), "overlap": overlap}
    sc.write_text(json.dumps(o, indent=2))

    _log(f"[3] contributions over the expanded corpus (resumable) ...")
    pipeline.extract_contributions(corpus, relate=False, progress=lambda m: _log("    " + m))
    pipeline.relate_contributions_fast(progress=lambda m: _log("    " + m))

    yr = Counter(p.year for p in corpus if p.year)
    _log(f"\n=== corpus {len(corpus)} (+{len(new)}) | recall {comp.get('recall')} "
         f"(CI {comp.get('recall_ci95')}) est~{comp.get('estimate_total')} "
         f"overlap {overlap} ===")
    _log("by year: " + " ".join(f"{y}:{yr[y]}" for y in sorted(yr)))
    _log("DONE expand")


if __name__ == "__main__":
    main()
