"""Scoper agent: turn a topic into a CLEAN, relevant corpus.

Relevance search over a topic pulls in highly-cited but off-topic papers (tools
that merely contain "automated", adjacent subfields, etc.). The Scoper works in
two stages — recall then precision:

  1. propose_queries  — LLM turns a one-line topic definition into search queries
  2. gather_candidates — multi-seed OpenAlex/arXiv → candidate pool
  3. scope            — LLM judges each candidate against the topic's include /
                        exclude criteria, keeping only in-scope primary papers

A precise topic definition (what's IN and what's OUT) is the key input — that's
what lets the filter reject "ChatGPT in the classroom" when the topic is "agents
that do research tasks".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import config, dates, llm, repair
from .models import Paper
from .sources import arxiv, openalex, semanticscholar

# ── stage 1: propose search queries ──────────────────────────────────────────
_Q_SYSTEM = """You design literature-search queries. Given a research topic with
its scope, output 6–10 diverse OpenAlex/arXiv keyword queries that together give
broad recall over the topic — vary the phrasing, name key methods/subareas, and
avoid queries so generic they'd pull in unrelated highly-cited tools."""

_Q_SCHEMA = {
    "type": "object",
    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["queries"],
}


def propose_queries(topic_def: str, *, model: str | None = None) -> list[str]:
    out = llm.structured(
        model=model or config.READER_MODEL, system=_Q_SYSTEM,
        user=f"TOPIC:\n{topic_def}", schema=_Q_SCHEMA, tool_name="emit_queries")
    return [q.strip() for q in out.get("queries", []) if q.strip()]


_FOLLOWUP_SYSTEM = """You expand a literature search to improve RECALL. Given the
topic + its scope, the titles already found IN-SCOPE, and a few that were dropped,
find sub-areas, methods, named systems, or terminology that are under-represented
or missing, and output 4–8 NEW OpenAlex/arXiv keyword queries targeting those gaps.
Go after what's THIN — don't repeat angles already well covered, and avoid queries
so generic they'd pull in unrelated highly-cited tools."""


def followup_queries(topic_def: str, kept: list[Paper],
                     dropped: list[tuple[Paper, str]] | None = None, *,
                     model: str | None = None, max_titles: int = 60) -> list[str]:
    """Reformulate the search from what's been found so far: propose NEW queries
    aimed at gaps in the in-scope set (the query-axis complement to the citation
    snowball). Reacting to results is what lifts recall beyond a one-shot expansion."""
    found = "\n".join(f"- {p.title}" for p in kept[:max_titles])
    user = f"TOPIC:\n{topic_def}\n\nIN-SCOPE SO FAR ({len(kept)}):\n{found}"
    if dropped:
        drp = "\n".join(f"- {p.title}" for p, _ in dropped[:15])
        user += f"\n\nDROPPED (out of scope — don't re-surface):\n{drp}"
    out = llm.structured(model=model or config.READER_MODEL, system=_FOLLOWUP_SYSTEM,
                         user=user, schema=_Q_SCHEMA, tool_name="emit_queries")
    return [q.strip() for q in out.get("queries", []) if q.strip()]


# ── stage 2: gather candidates (recall) ──────────────────────────────────────
def _dedup_cross_source(papers: list[Paper]) -> list[Paper]:
    """Collapse the same paper arriving from different sources (OpenAlex / arXiv /
    S2) by canonical key (Paper.key), preferring OpenAlex (it carries the citation
    graph the snowball needs), then arXiv, then S2."""
    rank = {"openalex": 0, "arxiv": 1, "semanticscholar": 2}
    best: dict[str, Paper] = {}
    variants: dict[str, list[Paper]] = {}
    for p in papers:
        k = p.key()
        variants.setdefault(k, []).append(p)
        cur = best.get(k)
        if cur is None or rank.get(p.source, 9) < rank.get(cur.source, 9):
            best[k] = p
    # preprint precedence: the kept record adopts the EARLIEST real date across its
    # source variants, so an OpenAlex venue date never overrides an arXiv <published>.
    for k, rec in best.items():
        e = dates.earliest(variants[k])
        if e and (not rec.date or e[0][:7] < rec.date[:7]):
            rec.date, rec.date_precision, rec.date_source = e
    return list(best.values())


def gather_candidates(queries: list[str], *, per_query: int = 25,
                      use_arxiv: bool = True, use_s2: bool = True,
                      progress=print) -> list[Paper]:
    """Resilient multi-source recall: OpenAlex + arXiv + Semantic Scholar. A
    source that errors (rate-limit, timeout) on one query is skipped, not fatal;
    arXiv and S2 are paced to respect their public limits. Cross-source
    duplicates are collapsed by title at the end."""
    import time
    papers: dict[str, Paper] = {}
    for q in queries:
        try:
            for p in openalex.search(q, max_papers=per_query):
                papers.setdefault(p.id, p)
        except Exception as e:  # noqa: BLE001
            progress(f"  openalex error on '{q[:40]}': {e}")
        if use_arxiv:
            try:
                for p in arxiv.search(q, max_papers=max(4, per_query // 5)):
                    papers.setdefault(p.id, p)
                time.sleep(1.0)   # be polite to arXiv
            except Exception as e:  # noqa: BLE001
                progress(f"  arxiv skip '{q[:40]}': {e}")
        if use_s2:
            try:
                for p in semanticscholar.search(q, max_papers=max(6, per_query // 2)):
                    papers.setdefault(p.id, p)
                time.sleep(1.1)   # S2 public pool is throttled
            except Exception as e:  # noqa: BLE001
                progress(f"  s2 skip '{q[:40]}': {e}")
        progress(f"  query '{q[:50]}' → pool now {len(papers)}")
    return _dedup_cross_source(list(papers.values()))


# ── stage 2b: citation snowball (recall, the high-leverage step) ─────────────
def snowball(seeds: list[Paper], *, corpus: list[Paper] | None = None,
             anchor_k: int = 25, per_paper: int = 40,
             progress=print) -> tuple[list[Paper], set[str]]:
    """One-hop citation expansion of a seed set (OpenAlex): backward references
    of all seeds + forward cited-by of the most-cited anchors. Finds the
    connected cluster that keyword search misses.

    `corpus` (default = seeds) is what we already have: membership and the
    capture-recapture overlap are tested by canonical key (Paper.key), so a paper
    we already hold under a different source's id is recognised — not re-added or
    miscounted. Returns (new_candidates, reached_keys), reached_keys being the
    canonical keys of corpus papers the citation channel re-reached."""
    corpus = corpus if corpus is not None else seeds
    known_ids = {p.id for p in corpus}                       # for OpenAlex-id refs
    id_to_key = {p.id: p.key() for p in corpus}
    known_keys = {p.key() for p in corpus}                   # cross-source identity
    new: dict[str, Paper] = {}                                # keyed by canonical key
    reached: set[str] = set()

    # backward — references are OpenAlex ids; match them against corpus ids
    all_refs = list(dict.fromkeys(
        r for p in seeds for r in p.referenced_works if r.startswith("openalex:")))
    reached |= {id_to_key[r] for r in all_refs if r in known_ids}   # ref → corpus paper
    for _pid, p in openalex.fetch_many([r for r in all_refs if r not in known_ids]).items():
        k = p.key()
        if k in known_keys:
            reached.add(k)
        elif k not in new:
            new[k] = p
    progress(f"  backward: {len(all_refs)} refs → +{len(new)} new")

    # forward — cited-by of the most-cited anchors (catches newer connected work)
    anchors = sorted((p for p in seeds if p.id.startswith("openalex:")),
                     key=lambda p: -p.cited_by_count)[:anchor_k]
    for p in anchors:
        for cp in openalex.cited_by(p.id, max_results=per_paper):
            k = cp.key()
            if k in known_keys:
                reached.add(k)
            elif k not in new:
                new[k] = cp
        progress(f"  forward cited-by {p.short_cite()} → pool {len(new)}")
    return list(new.values()), reached


def _s2_id(p: Paper) -> str | None:
    """A Semantic-Scholar-resolvable id for a Paper, preferring arXiv/DOI."""
    if p.id.startswith("arxiv:"):
        return "ARXIV:" + p.id.split(":", 1)[1].split("v")[0]
    if p.id.startswith("s2:"):
        return p.id.split(":", 1)[1]
    if p.doi:
        return "DOI:" + p.doi.rsplit("doi.org/", 1)[-1]
    return None


def snowball_s2(seeds: list[Paper], *, corpus: list[Paper] | None = None,
                anchor_k: int = 40, per_paper: int = 40,
                recent_year: int = 2024, progress=print
                ) -> tuple[list[Paper], set[str]]:
    """Citation snowball via Semantic Scholar — the path for the RECENT frontier,
    where OpenAlex has no citation edges yet. Anchors on recent / arXiv-keyed
    seeds and pulls S2 backward references + forward citations. Membership and
    overlap are tested by canonical key (S2 returns arXiv-keyed papers that match
    OpenAlex corpus papers by title). Returns (new_candidates, reached_keys)."""
    corpus = corpus if corpus is not None else seeds
    known_keys = {p.key() for p in corpus}
    new: dict[str, Paper] = {}
    reached: set[str] = set()
    anchors = [p for p in seeds
               if (p.year or 0) >= recent_year or p.id.startswith(("arxiv:", "s2:"))]
    anchors = sorted(anchors, key=lambda p: -(p.year or 0))[:anchor_k]
    for p in anchors:
        sid = _s2_id(p)
        if not sid:
            continue
        neighbours = (semanticscholar.references(sid, max_results=per_paper)
                      + semanticscholar.citations(sid, max_results=per_paper))
        for cp in neighbours:
            k = cp.key()
            if k in known_keys:
                reached.add(k)
            elif k not in new:
                new[k] = cp
        progress(f"  s2 cites {p.short_cite()} → pool {len(new)}")
    return list(new.values()), reached


def high_yield_seeds(papers: list[Paper], *, top_cited: int = 40,
                     recent_year: int = 2024, recent_k: int = 60) -> list[Paper]:
    """A small, high-yield seed set for a BOUNDED snowball: the most-cited papers
    (deep, well-connected) plus the recent frontier. Snowballing from ~100 chosen
    seeds keeps the candidate pool tractable, unlike snowballing from the whole
    corpus (which explodes into tens of thousands)."""
    by_cite = sorted(papers, key=lambda p: -p.cited_by_count)[:top_cited]
    recent = sorted((p for p in papers if (p.year or 0) >= recent_year),
                    key=lambda p: -(p.year or 0))[:recent_k]
    out, seen = [], set()
    for p in by_cite + recent:
        if p.id not in seen:
            seen.add(p.id)
            out.append(p)
    return out


# ── stage 2c: cheap TF-IDF pre-filter (spare the LLM the obvious noise) ───────
def _split_scope(topic_def: str) -> tuple[str, str]:
    """Split a topic definition into its IN-scope and OUT-of-scope text."""
    oi = topic_def.lower().find("out of scope")
    if oi == -1:
        return topic_def, ""
    return topic_def[:oi], topic_def[oi:]


def _bm25(cand_counts, doc_len, avgdl, idf, q_idx, *, k1=1.5, b=0.75):
    """BM25 score of every candidate against a query term-index set."""
    import numpy as np
    if len(q_idx) == 0:
        return np.zeros(cand_counts.shape[0])
    tf = cand_counts[:, q_idx].toarray().astype(float)        # (n × |Q|)
    denom = tf + k1 * (1 - b + b * doc_len.reshape(-1, 1) / avgdl)
    contrib = idf[q_idx] * (tf * (k1 + 1)) / np.where(denom == 0, 1.0, denom)
    return contrib.sum(axis=1)


def prefilter(topic_def: str, candidates: list[Paper], *, keep_frac: float = 0.30,
              progress=print) -> tuple[list[Paper], list[Paper]]:
    """Recall-preserving coarse gate, BM25. Scores each candidate's title+abstract
    against the IN-scope vocabulary and (separately) the OUT-of-scope vocabulary,
    and gates out the clear off-topic tail so the slow LLM filter only judges
    plausible candidates. BM25's term saturation + length normalisation make it a
    better lexical ranker than plain TF-IDF cosine for ranking abstracts.

    Recall-safe: any candidate whose in-scope score is at least its out-scope
    score is ALWAYS kept (we never gate an in-scope-dominant paper), plus the
    strongest in-scope matches overall. Only out-of-scope-dominant weak matches
    (recipes, classroom/education, software libraries…) get gated. The LLM still
    makes the precise call on every survivor."""
    if not candidates:
        return [], []
    import numpy as np
    from sklearn.feature_extraction.text import CountVectorizer
    inc, exc = _split_scope(topic_def)
    docs = [inc, exc or inc] + [f"{p.title} {p.abstract}" for p in candidates]
    X = CountVectorizer(stop_words="english", ngram_range=(1, 2),
                        max_features=40000).fit_transform(docs)
    in_q, out_q = X[0].indices, X[1].indices
    cand = X[2:]
    doc_len = np.asarray(cand.sum(axis=1)).ravel().astype(float)
    avgdl = max(doc_len.mean(), 1.0)
    df = np.asarray((cand > 0).sum(axis=0)).ravel().astype(float)
    idf = np.log(1 + (cand.shape[0] - df + 0.5) / (df + 0.5))
    bm_in = _bm25(cand, doc_len, avgdl, idf, in_q)
    bm_out = _bm25(cand, doc_len, avgdl, idf, out_q)
    n = len(candidates)
    k = max(1, int(n * keep_frac))
    keep = set(np.flatnonzero(bm_in >= bm_out).tolist())        # in-dominant: always keep
    keep |= set(np.argsort(bm_in)[::-1][:k].tolist())           # + strongest in-scope
    survivors = [p for i, p in enumerate(candidates) if i in keep]
    gated = [p for i, p in enumerate(candidates) if i not in keep]
    progress(f"  pre-filter (BM25): {len(survivors)} kept for LLM / {len(gated)} "
             f"gated (of {n})")
    return survivors, gated


# ── stage 3: relevance filter (precision) ────────────────────────────────────
_S_SYSTEM = """You are the Scoper. Decide whether each candidate paper is IN SCOPE
for the given topic, judging only from its title + abstract. Honour the topic's
inclusion and exclusion criteria exactly. Be strict: a paper that is merely
adjacent — same buzzwords, neighbouring subfield, a tool that just mentions the
terms — is OUT of scope.

PRIMARY SOURCES ONLY. Reject papers whose own framing is a perspective, position,
opinion, survey, review, roadmap, or viewpoint — judge this by CONTENT, not by
metadata or article-type flags. Out-of-scope tells (from the title/abstract's own
words): "this perspective / this position paper", "we argue", "we advocate", "we
call for", "a survey of", "systematic review", "a review of", "roadmap". Keep
primary empirical/methodological work that introduces a method, system, dataset,
benchmark, or finding. CRUCIAL: a paper whose *topic* is peer review (e.g. an agent
that reviews papers, a peer-review benchmark) is still PRIMARY — do not confuse
"about reviewing" with "a review article".

For each candidate return in_scope (true/false) and a one-line reason."""

_S_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "in_scope": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": ["index", "in_scope", "reason"],
            },
        }
    },
    "required": ["decisions"],
}


def _ask_scope(topic_def: str, items: list[Paper], model: str | None) -> dict[int, dict]:
    """One LLM scope call over `items`; returns {local_index: decision}."""
    listing = "\n".join(
        f"[{j}] {p.title}\n    {p.abstract[:320]}" for j, p in enumerate(items))
    out = llm.structured(
        model=model or config.READER_MODEL, system=_S_SYSTEM,
        user=f"TOPIC:\n{topic_def}\n\nCANDIDATES:\n{listing}",
        schema=_S_SCHEMA, tool_name="emit_scope", max_tokens=2000)
    return {d["index"]: d for d in out.get("decisions", [])
            if isinstance(d.get("index"), int)}


def scope(topic_def: str, candidates: list[Paper], *, model: str | None = None,
          batch: int = 12, cache_path: str | Path | None = None,
          use_prefilter: bool = False,
          progress=print) -> tuple[list[tuple[Paper, str]], list[tuple[Paper, str]]]:
    """Return (kept, dropped), each a list of (paper, reason).

    If cache_path is given, each decision is recorded (keyed by paper id) and a
    restart skips already-judged candidates — so re-scoping after a snowball, or
    resuming a crashed run, never re-spends LLM calls on papers already seen.

    If use_prefilter, a cheap TF-IDF gate drops the clear off-topic tail before
    the LLM sees anything — the lever that makes a broad snowball affordable."""
    gated: list[Paper] = []
    if use_prefilter:
        candidates, gated = prefilter(topic_def, candidates, progress=progress)
    cache: dict[str, dict] = {}
    cp = Path(cache_path) if cache_path else None
    if cp and cp.exists():
        for line in cp.read_text().splitlines():
            if not line:
                continue
            try:                                   # tolerate a torn final line
                d = json.loads(line)
                cache[d["id"]] = d
            except (ValueError, KeyError):
                continue

    kept: list[tuple[Paper, str]] = []
    dropped: list[tuple[Paper, str]] = []
    pending: list[Paper] = []
    for p in candidates:                           # replay cached decisions first
        d = cache.get(p.id)
        if d is None:
            pending.append(p)
        else:
            (kept if d["in_scope"] else dropped).append((p, d.get("reason", "")))
    if cache:
        progress(f"  {len(cache)} cached decisions reused — {len(pending)} to score")

    fh = cp.open("a") if cp else None
    try:
        for i in range(0, len(pending), batch):
            chunk = pending[i:i + batch]
            try:
                dec = _ask_scope(topic_def, chunk, model)
            except Exception as e:  # noqa: BLE001 — skip; uncached batch retries on resume
                progress(f"  scope batch error (will retry on resume): {e}")
                continue
            # A batch that omits an index must NOT silently drop that paper — re-ask
            # the omitted ones once, then treat anything still undecided as recall-safe
            # KEEP (flagged), never a default drop.
            missing = [j for j in range(len(chunk)) if j not in dec]
            if missing:
                try:
                    redec = _ask_scope(topic_def, [chunk[j] for j in missing], model)
                    for local, j in enumerate(missing):
                        if local in redec:
                            dec[j] = redec[local]
                except Exception as e:  # noqa: BLE001
                    progress(f"  scope re-ask error: {e}")
                still = [j for j in range(len(chunk)) if j not in dec]
                if still:
                    progress(f"  {len(still)} undecided after re-ask — kept for review")
            for j, p in enumerate(chunk):
                d = dec.get(j)
                if d is None:                      # undecided → keep (recall-safe)
                    in_scope, reason = True, "undecided — kept for review"
                else:
                    in_scope, reason = bool(d.get("in_scope")), d.get("reason", "")
                (kept if in_scope else dropped).append((p, reason))
                if fh:
                    fh.write(json.dumps(
                        {"id": p.id, "in_scope": in_scope, "reason": reason}) + "\n")
                    fh.flush()
            progress(f"  scored {min(i + batch, len(pending))}/{len(pending)} "
                     f"— kept {len(kept)}")
    finally:
        if fh:
            fh.close()
    for p in gated:                                # gated never reach the LLM
        dropped.append((p, "pre-filtered: low topic similarity"))
    return kept, dropped


def build_scoped_corpus(topic_def: str, *, per_query: int = 25,
                        model: str | None = None, repair_abstracts: bool = True,
                        progress=print
                        ) -> tuple[list[Paper], list[tuple[Paper, str]]]:
    """Full Scoper run: topic → queries → candidates → scoped corpus.
    Returns (kept_papers, dropped_with_reasons)."""
    progress("[1/3] proposing queries ...")
    queries = propose_queries(topic_def, model=model)
    progress(f"      {len(queries)} queries")
    progress("[2/3] gathering candidates ...")
    candidates = gather_candidates(queries, per_query=per_query, progress=progress)
    progress(f"      {len(candidates)} candidates")
    if repair_abstracts:                           # fix corrupted abstracts before judging
        repair.backfill_abstracts(candidates, progress=progress)
    progress("[3/3] scoping (relevance filter) ...")
    kept, dropped = scope(topic_def, candidates, model=model, progress=progress)
    progress(f"      kept {len(kept)} / dropped {len(dropped)}")
    return [p for p, _ in kept], dropped


def explore(topic_def: str, *, hops: int = 3, per_query: int = 25,
            use_prefilter: bool = True, epsilon: float = 0.03,
            repair_abstracts: bool = True, recover_rounds: int = 2,
            model: str | None = None, progress=print):
    """The full exploration pipeline as one call — Stage 1, the agentic stage:

      1. recall-then-precision : LLM query variations over OpenAlex+arXiv+S2, then
                                 an LLM relevance filter (the *search* channel)
      2. citation snowball      : backward refs + forward cited-by from high-yield
                                 seeds, OpenAlex + Semantic Scholar (the *snowball* channel)
      3. BM25 pre-filter        : a cheap recall-safe gate before the LLM filter
      4. saturation stopping    : stop when new-relevant-per-hop < epsilon, and
                                 report a capture-recapture completeness estimate

    Returns (corpus, dropped, stats={curve, completeness, n}). For a fresh corpus,
    point PRIOR_DATA_DIR at a new dir."""
    from . import completeness

    # 1 + 3: recall-then-precision with query RECOVERY (search channel). A one-shot
    # query expansion misses facets; reacting to the results and reformulating
    # toward gaps lifts recall — the query-axis complement to the citation snowball.
    progress("[explore 1/3] search: queries -> candidates -> scope (+ recovery)")
    queries = propose_queries(topic_def, model=model)
    asked = {q.lower() for q in queries}
    corpus: list[Paper] = []
    corpus_keys: set[str] = set()
    search_keys: set[str] = set()
    dropped: list[tuple[Paper, str]] = []
    for rnd in range(recover_rounds + 1):
        cand = [c for c in gather_candidates(queries, per_query=per_query, progress=progress)
                if c.key() not in corpus_keys]
        search_keys |= {c.key() for c in cand}
        if repair_abstracts and cand:              # repair before the prefilter/LLM judge
            repair.backfill_abstracts(cand, progress=progress)
        if use_prefilter and cand:
            cand, _ = prefilter(topic_def, cand, progress=progress)
        kept, drp = (scope(topic_def, cand, model=model, progress=progress)
                     if cand else ([], []))
        for p, _ in kept:
            corpus.append(p)
            corpus_keys.add(p.key())
        dropped += drp
        progress(f"  search round {rnd}: +{len(kept)} relevant of {len(cand)} candidates")
        # stop on the last round, or when a recovery round stops paying off (saturation)
        if rnd == recover_rounds or (rnd and len(kept) / max(1, len(cand)) < epsilon):
            break
        queries = [q for q in followup_queries(topic_def, corpus, dropped, model=model)
                   if q.lower() not in asked]
        asked |= {q.lower() for q in queries}
        if not queries:
            break
        progress(f"  recovery: +{len(queries)} follow-up queries targeting gaps")
    curve = [len(corpus)]
    progress(f"  search channel: {len(corpus)} relevant")

    # 2 + 4: citation snowball to saturation (snowball channel)
    progress("[explore 2/3] snowball to saturation")
    snow_keys: set[str] = set()
    for hop in range(1, hops + 1):
        seeds = high_yield_seeds(corpus)
        new_oa, reached_oa = snowball(seeds, corpus=corpus, progress=progress)
        new_s2, reached_s2 = snowball_s2(seeds, corpus=corpus, progress=progress)
        snow_keys |= reached_oa | reached_s2
        uniq: dict[str, Paper] = {}
        for c in new_oa + new_s2:
            if c.key() not in corpus_keys:
                uniq.setdefault(c.key(), c)
        cand = list(uniq.values())
        if repair_abstracts and cand:              # repair snowballed candidates too
            repair.backfill_abstracts(cand, progress=progress)
        if use_prefilter and cand:
            cand, _ = prefilter(topic_def, cand, progress=progress)
        hkept, hdrop = (scope(topic_def, cand, model=model, progress=progress)
                        if cand else ([], []))
        new_rel = [p for p, _ in hkept]
        for p in new_rel:
            corpus.append(p)
            corpus_keys.add(p.key())
        dropped += hdrop
        curve.append(len(new_rel))
        progress(f"  hop {hop}: +{len(new_rel)} relevant of {len(cand)} candidates "
                 f"(curve {curve})")
        if not new_rel or len(new_rel) / max(1, len(cand)) < epsilon:
            progress("  saturated — stopping.")
            break

    # completeness between the two independent channels
    progress("[explore 3/3] completeness")
    overlap = len(search_keys & snow_keys)
    est = completeness.capture_recapture(len(search_keys), len(snow_keys), overlap)
    progress(f"  completeness: {est}")
    return corpus, dropped, {"curve": curve, "completeness": est, "n": len(corpus)}
