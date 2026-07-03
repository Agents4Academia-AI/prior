"""Repair candidate metadata before scoping — chiefly abstracts.

The Scoper judges relevance from title + abstract, so a *corrupted* abstract on an
otherwise on-topic paper gets it (correctly, given the bad data) dropped. OpenAlex
reconstructs abstracts from an inverted index and occasionally returns one that
belongs to a DIFFERENT paper — observed on high-citation hub papers merged across
aggregators (e.g. DDPM `W3036167779`, whose abstract reconstructs to an unrelated
DNA-methylation paper). One poisoned record on a foundational paper is enough to
silently lose it from a survey.

Two repairs, cheapest/most-reliable first:

  1. arXiv backfill (robust, the actual fix). For any non-arXiv paper that
     ORIGINATES on arXiv — it carries an arXiv id, or its DOI is an arXiv DOI
     (10.48550/arXiv.<id>) — arXiv's abstract is authoritative, so we batch-fetch
     and overwrite. This fixes the DDPM class of bug deterministically.
  2. S2 fallback (best-effort) for the long tail: a non-arXiv paper whose abstract
     *contradicts* its title (shares almost none of its salient vocabulary) is
     refetched from Semantic Scholar by DOI. Gated by a conservative suspicion
     check so it costs a lookup only on the few genuinely broken records.
"""

from __future__ import annotations

import re

from .models import Paper
from .sources import arxiv, semanticscholar

_ARXIV_DOI = re.compile(r"arxiv\.(\d{4}\.\d{4,5})", re.I)   # 10.48550/arXiv.2006.11239
# very common words that say nothing about a paper's specific topic
_STOP = {
    "a", "an", "the", "of", "for", "and", "or", "to", "in", "on", "with", "via",
    "using", "based", "towards", "toward", "from", "by", "is", "are", "we", "our",
    "model", "models", "method", "methods", "approach", "approaches", "learning",
    "network", "networks", "deep", "neural", "data", "system", "systems", "study",
    "novel", "new", "framework", "analysis", "via",
}


def arxiv_id_of(p: Paper) -> str | None:
    """Base arXiv id (no version) if the paper originates on arXiv, else None."""
    if p.id.startswith("arxiv:"):
        return p.id.split(":", 1)[1].split("v")[0]
    m = _ARXIV_DOI.search(p.doi or "")
    return m.group(1) if m else None


def _s2_id(p: Paper) -> str | None:
    """An S2-resolvable id, preferring arXiv then DOI (mirrors scoper._s2_id)."""
    if p.id.startswith("arxiv:"):
        return "ARXIV:" + p.id.split(":", 1)[1].split("v")[0]
    if p.id.startswith("s2:"):
        return p.id.split(":", 1)[1]
    if p.doi:
        return "DOI:" + p.doi.rsplit("doi.org/", 1)[-1]
    return None


def _salient(text: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9]", " ", (text or "").lower()).split()
            if len(w) > 2 and w not in _STOP}


def abstract_suspect(title: str, abstract: str, *, threshold: float = 0.12) -> bool:
    """True if a non-empty abstract shares almost none of the title's distinctive
    vocabulary — a sign it belongs to a different paper. Conservative by design
    (we'd rather miss a borderline case than refetch healthy records); the title
    must have enough salient terms to make the ratio meaningful."""
    if not abstract or not abstract.strip():
        return False
    title_terms = _salient(title)
    if len(title_terms) < 4:                      # too short to judge reliably
        return False
    overlap = len(title_terms & _salient(abstract)) / len(title_terms)
    return overlap < threshold


def backfill_abstracts(papers: list[Paper], *, s2_fallback: bool = True,
                       progress=print) -> dict:
    """Repair abstracts in place. Returns {arxiv, s2, suspect_unrepaired} counts."""
    stats = {"arxiv": 0, "s2": 0, "suspect_unrepaired": 0}

    # 1. arXiv backfill — collect base ids, fetch once (batched), overwrite.
    want: dict[str, list[Paper]] = {}
    for p in papers:
        if p.source == "arxiv":                   # already carries the arXiv abstract
            continue
        aid = arxiv_id_of(p)
        if aid:
            want.setdefault(aid, []).append(p)
    if want:
        fetched = arxiv.fetch_ids(list(want))     # keyed 'arxiv:<id>v<n>' (versioned)
        by_base: dict[str, str] = {}
        for k, v in fetched.items():
            base = k.split(":", 1)[1].split("v")[0]
            if v.abstract:
                by_base[base] = v.abstract
        for aid, plist in want.items():
            ab = by_base.get(aid)
            if not ab:
                continue
            for p in plist:
                if (p.abstract or "").strip() != ab.strip():
                    p.abstract = ab
                    stats["arxiv"] += 1

    # 2. S2 fallback for remaining non-arXiv papers whose abstract contradicts title.
    if s2_fallback:
        for p in papers:
            if arxiv_id_of(p):                     # arXiv-origin already handled above
                continue
            if not abstract_suspect(p.title, p.abstract):
                continue
            sid = _s2_id(p)
            got = semanticscholar.fetch(sid) if sid else None
            if got and got.abstract and not abstract_suspect(p.title, got.abstract):
                p.abstract = got.abstract
                stats["s2"] += 1
            else:
                stats["suspect_unrepaired"] += 1

    progress(f"  abstract repair: +{stats['arxiv']} from arXiv, +{stats['s2']} from S2, "
             f"{stats['suspect_unrepaired']} suspect left as-is")
    return stats
