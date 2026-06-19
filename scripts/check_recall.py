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


def _field(entry: str, name: str):
    """Extract a bibtex field value, brace-balanced so nested {} in titles work.
    Handles both one-entry-per-line files and standard multi-line exports."""
    m = re.search(name + r"\s*=\s*", entry, re.I)
    if not m:
        return None
    i = m.end()
    if i < len(entry) and entry[i] == "{":
        depth = 0
        for j in range(i, len(entry)):
            if entry[j] == "{":
                depth += 1
            elif entry[j] == "}":
                depth -= 1
                if depth == 0:
                    return entry[i + 1:j]
        return None
    mq = re.match(r'"([^"]*)"|([\w.\-/:]+)', entry[i:])      # quoted or bare (year)
    return (mq.group(1) or mq.group(2)) if mq else None


def parse_bib(path: Path):
    """Parse a .bib into [{title, year, arxiv, doi}] — tolerant of single-line
    and multi-line entries, nested braces, and Zotero exports."""
    out = []
    for entry in re.split(r"\n@", "\n" + Path(path).read_text()):
        if "{" not in entry:
            continue
        title = _field(entry, "title")
        if not title:
            continue
        title = " ".join(re.sub(r"[{}]", "", title).split())
        yr = _field(entry, "year")
        doi = _field(entry, "doi")
        ma = (re.search(r"arXiv:(\d{4}\.\d{4,5})", entry, re.I)
              or re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", entry, re.I))
        # an arXiv DOI (10.48550/arXiv.XXXX) is just the arXiv id, not a journal DOI
        if doi and doi.lower().startswith("10.48550/arxiv."):
            ma = ma or re.search(r"(\d{4}\.\d{4,5})", doi)
            doi = None
        out.append({"title": title,
                    "year": int(yr) if (yr and yr.isdigit()) else None,
                    "arxiv": ma.group(1) if ma else None,
                    "doi": doi})
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
