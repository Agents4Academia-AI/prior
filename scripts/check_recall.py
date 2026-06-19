"""Recall gauge: can our sources even FIND a known-relevant gold set?

Reads a .bib of papers we KNOW belong in the corpus (e.g. a grant proposal's
references) and, for each, asks OpenAlex by title. This separates two failure
modes the Scoper must not conflate:

  - SOURCE gap : OpenAlex doesn't have the paper at all (often very recent arXiv
                 preprints) -> need arXiv/Semantic Scholar direct, not better queries
  - QUERY gap  : OpenAlex has it but our keyword seeds never surface it
                 -> the snowball / query reformulation is what fixes this

"Avoid caps due to human limitations" starts here: measure recall against a gold
set instead of trusting a top-k relevance cut.

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src \
        python3 scripts/check_recall.py data_hackathon/gold.bib
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from prior.sources import openalex          # noqa: E402


def norm(s: str) -> set:
    return set(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def parse_bib(path: Path):
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line.startswith("@"):
            continue
        mt = re.search(r"title=\{(.+?)\}", line)
        if not mt:
            continue
        title = mt.group(1)
        my = re.search(r"year=\{(\d{4})\}", line)
        ma = re.search(r"arXiv:(\d{4}\.\d{4,5})", line)
        out.append({"title": title, "year": int(my.group(1)) if my else None,
                    "arxiv": ma.group(1) if ma else None})
    return out


def best_match(title: str):
    """Return (paper, jaccard) for the closest OpenAlex hit, or (None, 0)."""
    want = norm(title)
    best, score = None, 0.0
    try:
        hits = openalex.search(title, max_papers=5, require_abstract=False,
                               exclude_reviews=False)
    except Exception:
        hits = []
    for p in hits:
        got = norm(p.title)
        j = len(want & got) / max(1, len(want | got))
        if j > score:
            best, score = p, j
    return best, score


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data_hackathon/gold.bib")
    gold = parse_bib(path)
    print(f"gold set: {len(gold)} papers\n")
    found, source_gap, query_only = [], [], []
    for g in gold:
        p, j = best_match(g["title"])
        if p and j >= 0.6:
            found.append((g, p, j))
            tag = "FOUND "
            extra = f"{p.year} c{p.cited_by_count}"
        else:
            recent = (g["year"] or 0) >= 2025 or (g["arxiv"] and g["arxiv"] >= "2412")
            (source_gap if recent else query_only).append(g)
            tag = "MISS* " if recent else "MISS  "
            extra = "(recent → likely source/index lag)" if recent else "(in scope, not findable)"
        print(f"  {tag} j={j:.2f}  {g['title'][:62]:62}  {extra}")
    n = len(gold)
    print(f"\n=== recall: {len(found)}/{n} = {len(found)/n:.0%} findable in OpenAlex by title")
    print(f"    misses: {len(source_gap)} recent (source/index lag), "
          f"{len(query_only)} older (genuine)")
    print("    → recent misses argue for an arXiv-id / Semantic Scholar fetch path;")
    print("    → all gold papers should be added as snowball SEED ANCHORS regardless.")


if __name__ == "__main__":
    main()
