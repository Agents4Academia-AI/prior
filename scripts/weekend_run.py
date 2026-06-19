"""Resumable end-to-end build of the scoped corpus + contributions graph.

Designed to run unattended for as long as it needs (the claude-code backend is
slow but free). Every stage is idempotent and checkpointed, so if it crashes or
hangs you just relaunch and it picks up where it left off:

  [0] base scope      → scope decisions cached (scope_cache.jsonl); skipped if
                        papers.jsonl + scope.json already exist
  [1] citation snowball→ forward cited-by + backward refs, re-scoped (same cache),
                        merged with NO capping; skipped if already recorded
  [2] contributions   → per-paper, flushed to contributions.partial.jsonl;
                        a restart skips papers already processed
  [3] relate          → one-shot cross-contribution relations → contributions.json

Run:
    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon \
        PYTHONPATH=src python3 scripts/weekend_run.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
sys.path.insert(0, str(HERE))

from prior import config, pipeline, scoper        # noqa: E402
from prior.atlas import Atlas                      # noqa: E402
from prior.models import Paper                     # noqa: E402
from prior.sources import arxiv                    # noqa: E402
from build_scoped import TOPIC, SEEDS              # noqa: E402
from check_recall import parse_bib, best_match     # noqa: E402


def _log(m):
    print(m, flush=True)


def _gold_anchors():
    """Resolve the gold set (grant bib) to Papers we GUARANTEE in the corpus:
    OpenAlex title-match where it indexes the paper, direct arXiv-id fetch for
    the recent preprints it doesn't. These bypass the relevance filter (they are
    declared-relevant) and seed the snowball."""
    bib = config.DATA / "gold.bib"
    if not bib.exists():
        return []
    anchors: dict[str, Paper] = {}
    need_arxiv: list[str] = []
    for g in parse_bib(bib):
        p, j = best_match(g["title"])
        if p and j >= 0.6:
            anchors[p.id] = p
        elif g["arxiv"]:
            need_arxiv.append(g["arxiv"])
    for pid, p in arxiv.fetch_ids(need_arxiv).items():
        anchors.setdefault(pid, p)
    return list(anchors.values())


def _write_corpus(papers, dropped=None):
    with (config.RAW / "papers.jsonl").open("w") as f:
        for p in papers:
            f.write(json.dumps(p.to_dict()) + "\n")
    a = Atlas(); a.topic = "agents for the scientific process"
    for p in papers:
        a.add_paper(p)
    a.link_citations(); a.save()
    sc_path = config.ATLAS / "scope.json"
    sc = json.loads(sc_path.read_text()) if sc_path.exists() else {"topic": TOPIC}
    sc["kept"] = [{"id": p.id, "cite": p.short_cite(), "year": p.year,
                   "cited_by": p.cited_by_count, "title": p.title} for p in papers]
    if dropped is not None:
        sc["dropped"] = [{"id": p.id, "reason": r} for p, r in dropped]
    sc_path.write_text(json.dumps(sc, indent=2))


def _load_corpus():
    return [Paper.from_dict(json.loads(l))
            for l in (config.RAW / "papers.jsonl").read_text().splitlines() if l]


def main():
    config.ensure_dirs()
    cache = str(config.ATLAS / "scope_cache.jsonl")
    scope_json = config.ATLAS / "scope.json"
    papers_path = config.RAW / "papers.jsonl"
    _log(f"data dir: {config.DATA}")

    # ── [0] base scope ───────────────────────────────────────────────────────
    if papers_path.exists() and scope_json.exists():
        papers = _load_corpus()
        _log(f"[0] base corpus exists: {len(papers)} papers (skip scope)")
    else:
        _log("[0] base scope — proposing queries ...")
        queries = list(dict.fromkeys(SEEDS + scoper.propose_queries(TOPIC)))
        _log(f"    {len(queries)} seed queries; gathering candidates ...")
        cands = scoper.gather_candidates(queries, per_query=20, progress=lambda m: None)
        _log(f"    {len(cands)} candidates; scoping ...")
        kept, dropped = scoper.scope(TOPIC, cands, cache_path=cache, progress=_log)
        papers = [p for p, _ in kept]
        _write_corpus(papers, dropped)
        _log(f"    base corpus: {len(papers)} kept / {len(dropped)} dropped")

    # ── [1] citation snowball (no caps) ──────────────────────────────────────
    sc = json.loads(scope_json.read_text())
    if "snowball_added" not in sc:
        anchors = _gold_anchors()
        if anchors:
            before = len(papers)
            cur = {p.id: p for p in papers}
            for p in anchors:
                cur.setdefault(p.id, p)
            papers = list(cur.values())
            _log(f"    folded {len(anchors)} gold anchors (+{len(papers) - before} "
                 f"new) → corpus {len(papers)}")
        _log("[1] snowball (forward cited-by + backward refs) ...")
        cands = scoper.snowball(papers, progress=lambda m: _log("    " + m))
        _log(f"    {len(cands)} new candidates; scoping (cache-aware) ...")
        kept, _ = scoper.scope(TOPIC, cands, cache_path=cache, progress=_log)
        new = [p for p, _ in kept]
        merged = {p.id: p for p in papers}
        for p in new:
            merged.setdefault(p.id, p)
        papers = list(merged.values())
        _write_corpus(papers)
        sc = json.loads(scope_json.read_text()); sc["snowball_added"] = len(new)
        scope_json.write_text(json.dumps(sc, indent=2))
        _log(f"    snowball added {len(new)} → corpus {len(papers)}")
    else:
        _log(f"[1] snowball already done (+{sc['snowball_added']}); "
             f"corpus {len(papers)}")

    yr = Counter(p.year for p in papers if p.year)
    _log("    by year: " + " ".join(f"{y}:{yr[y]}" for y in sorted(yr)))

    # ── [2] contributions (resumable, no caps) ───────────────────────────────
    _log(f"[2] contributions over all {len(papers)} papers (resumable) ...")
    pipeline.extract_contributions(papers, relate=False, progress=lambda m: _log("    " + m))

    # ── [3] relate ───────────────────────────────────────────────────────────
    _log("[3] relating contributions across papers ...")
    pipeline.relate_contributions_fast(progress=lambda m: _log("    " + m))
    _log("DONE.")


if __name__ == "__main__":
    main()
