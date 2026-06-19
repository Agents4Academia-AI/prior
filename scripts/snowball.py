"""Expand the scoped corpus by citation snowballing, then re-scope the new
candidates and merge. Run AFTER build_scoped.py has produced data/.../papers.jsonl.

  load scoped corpus → snowball (forward cited-by + backward refs)
        → LLM relevance filter on the new candidates → merge → rewrite corpus.

No capping: every relevant paper is kept.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon \
        PYTHONPATH=src python3 scripts/snowball.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
sys.path.insert(0, str(HERE))

from prior import config, scoper          # noqa: E402
from prior.atlas import Atlas             # noqa: E402
from prior.models import Paper            # noqa: E402
from build_scoped import TOPIC            # noqa: E402  (reuse the topic definition)


def main():
    seeds = [Paper.from_dict(json.loads(line))
             for line in (config.RAW / "papers.jsonl").read_text().splitlines() if line]
    print(f"seed corpus: {len(seeds)} papers", flush=True)

    print("[1/3] snowballing (forward cited-by + backward refs) ...", flush=True)
    cands = scoper.snowball(seeds, progress=lambda m: print("   " + m, flush=True))
    print(f"      {len(cands)} new candidates", flush=True)

    print("[2/3] scoping new candidates ...", flush=True)
    kept, dropped = scoper.scope(TOPIC, cands,
                                 progress=lambda m: print("   " + m, flush=True))
    new_relevant = [p for p, _ in kept]
    print(f"      +{len(new_relevant)} relevant (of {len(cands)} new)", flush=True)

    # merge — no capping
    merged = {p.id: p for p in seeds}
    for p in new_relevant:
        merged.setdefault(p.id, p)
    papers = list(merged.values())

    print("[3/3] rewriting corpus ...", flush=True)
    with (config.RAW / "papers.jsonl").open("w") as f:
        for p in papers:
            f.write(json.dumps(p.to_dict()) + "\n")
    a = Atlas(); a.topic = "agents for the scientific process"
    for p in papers:
        a.add_paper(p)
    a.link_citations(); a.save()
    sc = json.loads((config.ATLAS / "scope.json").read_text())
    sc["kept"] = [{"id": p.id, "cite": p.short_cite(), "year": p.year,
                   "cited_by": p.cited_by_count, "title": p.title} for p in papers]
    sc["snowball_added"] = len(new_relevant)
    (config.ATLAS / "scope.json").write_text(json.dumps(sc, indent=2))

    yr = Counter(p.year for p in papers if p.year)
    print(f"\n=== CORPUS after snowball: {len(papers)} papers "
          f"(+{len(new_relevant)} from snowball) ===", flush=True)
    print("by year: " + " ".join(f"{y}:{yr[y]}" for y in sorted(yr)), flush=True)


if __name__ == "__main__":
    main()
