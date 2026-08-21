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
import hashlib
import re
import time
import unicodedata
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
def _same_work(a: Paper, b: Paper) -> bool:
    """Conservative work-level match across source-specific manifestations."""
    aliases_a, aliases_b = set(a.identity_aliases()), set(b.identity_aliases())
    if aliases_a & aliases_b:
        return True
    # Two different values in the same strong namespace are evidence against a
    # merge, even when generic titles collide.
    for prefix in ("doi:", "arxiv:"):
        left = {value for value in aliases_a if value.startswith(prefix)}
        right = {value for value in aliases_b if value.startswith(prefix)}
        if left and right and left.isdisjoint(right):
            return False
    if a.key() == b.key():
        return True
    ta = set(a.key().removeprefix("title:").split())
    tb = set(b.key().removeprefix("title:").split())
    if not ta or not tb or min(len(ta), len(tb)) < 6:
        return False
    containment = len(ta & tb) / min(len(ta), len(tb))
    if containment < 0.88:
        return False
    aa = {name.split()[-1].lower() for name in a.authors if name.split()}
    ab = {name.split()[-1].lower() for name in b.authors if name.split()}
    return bool(aa & ab) and (not a.year or not b.year or abs(a.year - b.year) <= 2)


def _dedup_cross_source(papers: list[Paper]) -> list[Paper]:
    """Collapse the same paper arriving from different sources (OpenAlex / arXiv /
    S2) by canonical key (Paper.key), preferring OpenAlex (it carries the citation
    graph the snowball needs), then arXiv, then S2."""
    rank = {"openalex": 0, "arxiv": 1, "semanticscholar": 2}
    best: dict[str, Paper] = {}
    variants: dict[str, list[Paper]] = {}
    for p in papers:
        k = next((key for key, group in variants.items()
                  if _same_work(p, group[0])), p.key())
        variants.setdefault(k, []).append(p)
        cur = best.get(k)
        if cur is None or rank.get(p.source, 9) < rank.get(cur.source, 9):
            best[k] = p
    # preprint precedence: the kept record adopts the EARLIEST real date across its
    # source variants, so an OpenAlex venue date never overrides an arXiv <published>.
    for k, rec in best.items():
        merged, seen = [], set()
        for variant in variants[k]:
            for item in variant.all_manifestations():
                signature = (item.get("id", ""), item.get("url", ""),
                             item.get("pdf_url", ""), item.get("doi", ""))
                if signature not in seen and item.get("id") != rec.id:
                    seen.add(signature)
                    merged.append(item)
        rec.manifestations = merged
        e = dates.earliest(variants[k])
        if e and (not rec.date or e[0][:7] < rec.date[:7]):
            rec.date, rec.date_precision, rec.date_source = e
    return list(best.values())


def resolve_manifestations(papers: list[Paper], *, progress=print) -> list[Paper]:
    """Attach verified cross-source versions before retrieval and citation joins."""
    enriched = 0
    for i, paper in enumerate(papers, 1):
        before = len(paper.manifestations)
        variants = [paper]
        doi = (paper.doi or "").replace("https://doi.org/", "").replace("doi:", "")
        if doi:
            candidate = semanticscholar.fetch(f"DOI:{doi}")
            if candidate and _same_work(paper, candidate):
                variants.append(candidate)
        known_arxiv = any(str(item.get("id") or "").startswith("arxiv:")
                          for item in paper.all_manifestations())
        if not known_arxiv:
            aid = arxiv.find_id_by_title(paper.title)
            if aid:
                found = arxiv.fetch_ids([aid])
                candidate = next(iter(found.values()), None)
                if candidate and _same_work(paper, candidate):
                    variants.append(candidate)
        merged = _dedup_cross_source(variants)[0]
        paper.manifestations = merged.manifestations
        if len(paper.manifestations) > before:
            enriched += 1
        if i % 25 == 0:
            progress(f"  manifestations: resolved {i}/{len(papers)} works")
    progress(f"  manifestations: enriched {enriched}/{len(papers)} canonical works")
    return papers


def gather_candidates(queries: list[str], *, per_query: int = 25,
                      use_openalex: bool = True, use_arxiv: bool = True,
                      use_s2: bool = True,
                      progress=print, observe=None) -> list[Paper]:
    """Resilient multi-source recall: OpenAlex + arXiv + Semantic Scholar. A
    source that errors (rate-limit, timeout) on one query is skipped, not fatal;
    arXiv and S2 are paced to respect their public limits. Cross-source
    duplicates are collapsed by title at the end."""
    import time
    papers: dict[str, Paper] = {}
    observed: list[Paper] = []

    def search_source(source: str, query: str, limit: int, search_fn) -> None:
        request = {
            "kind": "retrieval_request", "source": source, "query": query,
            "parameters": {"max_papers": limit},
        }
        if observe:
            observe(request)
        try:
            results = search_fn(query, max_papers=limit)
            for rank, paper in enumerate(results, 1):
                observed.append(paper)
                papers.setdefault(paper.id, paper)
                if observe:
                    observe({
                        "kind": "retrieval_result", "source": source, "query": query,
                        "source_rank": rank, "paper": paper,
                    })
        except Exception as error:  # noqa: BLE001
            if observe:
                observe({
                    "kind": "source_failure", "source": source, "query": query,
                    "error_type": type(error).__name__, "message": str(error)[:500],
                    "retry_or_fallback": "continue_with_remaining_sources",
                })
            raise

    for q in queries:
        if use_openalex:
            try:
                search_source("openalex", q, per_query, openalex.search)
            except Exception as e:  # noqa: BLE001
                progress(f"  openalex error on '{q[:40]}': {e}")
        if use_arxiv:
            try:
                search_source("arxiv", q, max(4, per_query // 5), arxiv.search)
                time.sleep(1.0)   # be polite to arXiv
            except Exception as e:  # noqa: BLE001
                progress(f"  arxiv skip '{q[:40]}': {e}")
        if use_s2:
            try:
                search_source(
                    "semanticscholar", q, max(6, per_query // 2),
                    semanticscholar.search,
                )
            except Exception as e:  # noqa: BLE001
                progress(f"  s2 skip '{q[:40]}': {e}")
        progress(f"  query '{q[:50]}' → pool now {len(papers)}")
    deduped = _dedup_cross_source(list(papers.values()))
    if observe:
        variants: dict[str, list[Paper]] = {}
        for paper in observed:
            key = next((key for key, group in variants.items()
                        if _same_work(paper, group[0])), paper.key())
            variants.setdefault(key, []).append(paper)
        for key, copies in variants.items():
            unique_ids = list(dict.fromkeys(paper.id for paper in copies))
            if len(unique_ids) > 1:
                retained = next(paper for paper in deduped
                                if _same_work(paper, copies[0]))
                observe({
                    "kind": "deduplication", "work_key": key,
                    "retained_id": retained.id, "variant_ids": unique_ids,
                    "basis": "strong_identifier_or_conservative_work_match",
                })
    return deduped


# ── stage 2b: citation snowball (recall, the high-leverage step) ─────────────
def snowball(seeds: list[Paper], *, corpus: list[Paper] | None = None,
             anchor_k: int = 25, per_paper: int = 40,
             progress=print, observe=None, hop: int = 1) -> tuple[list[Paper], set[str]]:
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
    ref_seeds: dict[str, list[Paper]] = {}
    for seed in seeds:
        for ref in seed.referenced_works:
            if ref.startswith("openalex:"):
                ref_seeds.setdefault(ref, []).append(seed)
    all_refs = list(ref_seeds)
    reached |= {id_to_key[r] for r in all_refs if r in known_ids}   # ref → corpus paper
    for _pid, p in openalex.fetch_many([r for r in all_refs if r not in known_ids]).items():
        k = p.key()
        for seed in ref_seeds.get(p.id, []):
            if observe:
                observe({"source": "openalex", "hop": hop, "direction": "backward",
                         "seed": seed, "paper": p, "endpoint": "works/filter:ids.openalex"})
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
            if observe:
                observe({"source": "openalex", "hop": hop, "direction": "forward",
                         "seed": p, "paper": cp, "endpoint": "works/filter:cites"})
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
                recent_year: int = 2024, progress=print, observe=None, hop: int = 1
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
        neighbours = [
            ("backward", cp) for cp in semanticscholar.references(sid, max_results=per_paper)
        ] + [
            ("forward", cp) for cp in semanticscholar.citations(sid, max_results=per_paper)
        ]
        for direction, cp in neighbours:
            if observe:
                observe({"source": "semanticscholar", "hop": hop,
                         "direction": direction, "seed": p, "paper": cp,
                         "endpoint": f"paper/{{seed}}/{'references' if direction == 'backward' else 'citations'}"})
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
        f"[{j}] {p.title}\n    {p.abstract}" for j, p in enumerate(items))
    out = llm.structured(
        model=model or config.READER_MODEL, system=_S_SYSTEM,
        user=f"TOPIC:\n{topic_def}\n\nCANDIDATES:\n{listing}",
        schema=_S_SCHEMA, tool_name="emit_scope", max_tokens=2000)
    return {d["index"]: d for d in out.get("decisions", [])
            if isinstance(d.get("index"), int)}


_ACCEPT_CONTRADICTION = re.compile(
    r"(?:\bout of scope\b|\b(?:is|reads as) (?:a )?(?:survey|review article)\b|"
    r"\b(?:this paper )?(?:surveys|reviews) (?:the |existing )?(?:field|literature|methods|work)\b|"
    r"\b(?:position|perspective|opinion) paper\b|\bdoes not (?:fit|meet)\b)", re.I)
_EXCLUDE_CONTRADICTION = re.compile(
    r"(?:\bdirectly in scope\b|\bdirectly (?:fits|matches)\b|"
    r"\bsatisfies the (?:inclusion|in-scope) criteria\b)", re.I)


def _scope_decision_conflict(decision: dict) -> bool:
    """Detect an explicit contradiction between a label and its rationale."""
    reason = str(decision.get("reason") or "")
    if bool(decision.get("in_scope")):
        return bool(_ACCEPT_CONTRADICTION.search(reason))
    return bool(_EXCLUDE_CONTRADICTION.search(reason))


def scope(topic_def: str, candidates: list[Paper], *, model: str | None = None,
          batch: int = 12, cache_path: str | Path | None = None,
          use_prefilter: bool = False,
          request_delay: float = 0.0,
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
                # Old caches may contain the exact failure this guard prevents.
                # Treat contradictory entries as absent so they are re-judged.
                if not _scope_decision_conflict(d):
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
            # Structured output guarantees a boolean, but not that the boolean
            # agrees with its rationale. Re-judge contradictions individually and
            # refuse to cache a decision that remains internally inconsistent.
            conflicts = [j for j, decision in dec.items()
                         if j < len(chunk) and _scope_decision_conflict(decision)]
            for j in conflicts:
                progress(f"  contradictory scope decision for {chunk[j].id} — re-asking")
                revised = _ask_scope(topic_def, [chunk[j]], model).get(0)
                if revised is None or _scope_decision_conflict(revised):
                    raise RuntimeError(
                        "scope decision remained internally contradictory after re-ask: "
                        f"{chunk[j].id} | {json.dumps(revised or dec[j], ensure_ascii=False)}"
                    )
                dec[j] = revised
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
            if request_delay > 0 and i + batch < len(pending):
                time.sleep(request_delay)
    finally:
        if fh:
            fh.close()
    for p in gated:                                # gated never reach the LLM
        dropped.append((p, "pre-filtered: low topic similarity"))
    return kept, dropped


_EXHAUSTIVE_SCOPE_SYSTEM = """You screen records for an exhaustive scientific
literature search. Use the complete available title and abstract and apply the
provided scope criteria. Return one role for every record:

- eligible: satisfies the inclusion criteria as primary evidence;
- retrieval_only: not eligible for synthesis, but useful for discovering
  terminology, named systems, communities, authors, venues, or citations (reviews,
  surveys, perspectives, protocols, and adjacent bridge papers often belong here);
- uncertain: available evidence is insufficient or genuinely ambiguous;
- excluded: clearly outside scope and not useful as a discovery bridge.

Also classify publication_role as one of: primary_system_or_method,
primary_empirical_evaluation, benchmark_or_dataset, secondary_review_or_survey,
perspective_or_position, protocol_only, or unclear. Set
has_original_contribution=true only when the title/abstract supports a substantive
original system, method, benchmark, dataset, or empirical evaluation. A hybrid
review is eligible only when that separable original contribution satisfies the
scope. Papers *about peer review* can still be primary research.

The complete title and abstract are supplied as numbered evidence spans in their
original order. Read all spans. For every eligible, retrieval_only, or excluded
decision, choose one non-negative evidence_span_index that directly supports the
decision. Use -1 only for uncertain. The pipeline will copy the selected span
verbatim; do not reproduce the quote yourself. Do not infer exclusion from missing
evidence. An exclusion requires positive evidence; otherwise use uncertain. Return
exactly one decision for every record index."""

_EXHAUSTIVE_ROLES = ("eligible", "retrieval_only", "uncertain", "excluded")
_PUBLICATION_ROLES = (
    "primary_system_or_method", "primary_empirical_evaluation",
    "benchmark_or_dataset", "secondary_review_or_survey",
    "perspective_or_position", "protocol_only", "unclear",
)
_PRIMARY_PUBLICATION_ROLES = set(_PUBLICATION_ROLES[:3])
_EXHAUSTIVE_SCOPE_PROTOCOL = "scope-exhaustive/1.4"

_EXHAUSTIVE_SCOPE_SCHEMA = {
    "type": "object",
    "properties": {"decisions": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "index": {"type": "integer"},
            "role": {"type": "string", "enum": [
                "eligible", "retrieval_only", "uncertain", "excluded",
            ]},
            "criterion": {"type": "string"},
            "evidence_span_index": {"type": "integer", "minimum": -1},
            "reason": {"type": "string"},
            "publication_role": {"type": "string", "enum": list(_PUBLICATION_ROLES)},
            "has_original_contribution": {"type": "boolean"},
        },
        "required": ["index", "role", "criterion", "evidence_span_index", "reason",
                     "publication_role", "has_original_contribution"],
    }}},
    "required": ["decisions"],
}


def _exhaustive_prompt_hash() -> str:
    return "sha256:" + hashlib.sha256(
        (_EXHAUSTIVE_SCOPE_SYSTEM + "\n" + json.dumps(
            _EXHAUSTIVE_SCOPE_SCHEMA, sort_keys=True)).encode()).hexdigest()


def exhaustive_scope_fingerprint(topic_def: str, paper: Paper, *,
                                 model: str | None = None,
                                 backend: str | None = None) -> str:
    """Stable cache identity for a complete title/abstract screening decision."""
    selected_model = model or config.READER_MODEL
    selected_backend = backend or llm.backend()
    payload = "\n".join((_EXHAUSTIVE_SCOPE_PROTOCOL, selected_backend,
                          selected_model, _exhaustive_prompt_hash(), topic_def,
                          paper.key(), paper.title, paper.abstract or ""))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def _exhaustive_decision_issues(paper: Paper, decision: dict) -> list[str]:
    """Mechanical contradictions that require individual re-adjudication."""
    issues = []
    role = decision.get("role")
    publication_role = decision.get("publication_role")
    original = decision.get("has_original_contribution")
    combined = " ".join(str(decision.get(field) or "")
                        for field in ("criterion", "reason"))
    evidence = str(decision.get("evidence") or "").strip()
    haystack = paper.title + "\n" + (paper.abstract or "")
    normalize = lambda value: " ".join(
        unicodedata.normalize("NFKC", str(value or "")).split()).casefold()
    if role not in _EXHAUSTIVE_ROLES:
        issues.append("invalid_role")
    if publication_role not in _PUBLICATION_ROLES:
        issues.append("invalid_publication_role")
    if not isinstance(original, bool):
        issues.append("missing_original_contribution_flag")
    if role != "uncertain" and (not evidence or normalize(evidence) not in normalize(haystack)):
        issues.append("evidence_not_verbatim")
    if role == "eligible" and (
            publication_role not in _PRIMARY_PUBLICATION_ROLES or original is not True):
        issues.append("eligible_without_primary_original_contribution")
    if role == "eligible" and _ACCEPT_CONTRADICTION.search(combined):
        issues.append("eligible_rationale_says_exclude")
    if role == "excluded" and _EXCLUDE_CONTRADICTION.search(combined):
        issues.append("excluded_rationale_says_include")
    if role == "retrieval_only" and publication_role in _PRIMARY_PUBLICATION_ROLES \
            and original is True and _EXCLUDE_CONTRADICTION.search(combined):
        issues.append("retrieval_only_rationale_says_include")
    if role == "excluded" and not paper.abstract and not evidence:
        issues.append("excluded_from_missing_evidence")
    return issues


def _evidence_spans(paper: Paper) -> list[str]:
    """Deterministic, ordered spans covering the complete title and abstract."""
    spans = [paper.title.strip()]
    abstract = (paper.abstract or "").strip()
    if abstract:
        spans.extend(part.strip() for part in re.split(
            r"(?<=[.!?])\s+(?=[A-Z0-9])|\n+", abstract) if part.strip())
    return spans


def _ask_scope_exhaustive(topic_def: str, items: list[Paper], *, model: str,
                          validation_feedback: str = "") \
        -> tuple[dict[int, dict], set[int]]:
    spans_by_index = [_evidence_spans(paper) for paper in items]
    records = []
    for index, (paper, spans) in enumerate(zip(items, spans_by_index)):
        listing = "\n".join(f"  <{span_index}> {span}"
                            for span_index, span in enumerate(spans))
        records.append(
            f"[{index}] METADATA: year={paper.year or 'unknown'}; "
            f"source={paper.source}; type={paper.type or 'unknown'}; "
            f"review_flag={paper.is_review}\nEVIDENCE SPANS:\n{listing}"
        )
    listing = "\n\n".join(records)
    correction = (
        "\n\nCORRECTION REQUIRED:\nThe previous decision failed mechanical "
        f"validation: {validation_feedback}. Return a corrected decision. For any "
        "non-uncertain role, select one valid non-negative evidence_span_index "
        "from the supplied record; use -1 only for uncertain."
        if validation_feedback else ""
    )
    response = llm.structured(
        model=model, system=_EXHAUSTIVE_SCOPE_SYSTEM,
        user=f"TOPIC:\n{topic_def}\n\nCANDIDATES:\n{listing}{correction}",
        schema=_EXHAUSTIVE_SCOPE_SCHEMA, tool_name="emit_scope_roles",
        max_tokens=5000,
    )
    decisions: dict[int, dict] = {}
    duplicates = set()
    for row in response.get("decisions", []):
        if not isinstance(row, dict):
            continue
        index = row.get("index")
        if not isinstance(index, int) or not 0 <= index < len(items):
            continue
        span_index = row.get("evidence_span_index")
        spans = spans_by_index[index]
        if isinstance(span_index, int) and 0 <= span_index < len(spans):
            row["evidence"] = spans[span_index]
        elif "evidence" not in row:
            row["evidence"] = ""
        if index in decisions:
            duplicates.add(index)
        decisions[index] = row
    return decisions, duplicates


def scope_exhaustive(topic_def: str, candidates: list[Paper], *,
                     model: str | None = None, batch: int = 6,
                     cache_path: str | Path | None = None,
                     progress=print) -> dict[str, list[tuple[Paper, dict]]]:
    """Evidence-grounded four-way screening for exhaustive discovery.

    Unlike :func:`scope`, this never turns missing/ambiguous evidence into an
    exclusion and preserves navigation records separately from synthesis-eligible
    evidence. Cache keys include scope, protocol, paper identity, and evidence.
    """
    protocol = _EXHAUSTIVE_SCOPE_PROTOCOL
    selected_model = model or config.READER_MODEL
    selected_backend = llm.backend()
    prompt_hash = _exhaustive_prompt_hash()

    def fingerprint(paper: Paper) -> str:
        return exhaustive_scope_fingerprint(
            topic_def, paper, model=selected_model, backend=selected_backend)

    cp = Path(cache_path) if cache_path else None
    cache = {}
    if cp and cp.exists():
        for line in cp.read_text().splitlines():
            try:
                row = json.loads(line)
                if row.get("cacheable", True) and row.get("role") in _EXHAUSTIVE_ROLES:
                    cache[row["fingerprint"]] = row
            except (json.JSONDecodeError, KeyError):
                continue
    roles = {role: [] for role in _EXHAUSTIVE_ROLES}
    pending = []
    for paper in candidates:
        cached = cache.get(fingerprint(paper))
        if cached:
            roles[cached["role"]].append((paper, cached))
        else:
            pending.append(paper)
    handle = cp.open("a") if cp else None
    try:
        for start in range(0, len(pending), batch):
            chunk = pending[start:start + batch]
            try:
                decisions, duplicates = _ask_scope_exhaustive(
                    topic_def, chunk, model=selected_model)
            except Exception as error:  # noqa: BLE001
                # Transport/structured-output failures are operational failures,
                # not scientific uncertainty. Leave the batch uncached so a
                # resumable run retries it.
                progress(f"  exhaustive scope batch error (uncached): {error}")
                continue
            for index, paper in enumerate(chunk):
                decision = decisions.get(index)
                issues = (["duplicate_or_missing_index"] if
                          decision is None or index in duplicates else
                          _exhaustive_decision_issues(paper, decision))
                if issues:
                    progress(f"  invalid exhaustive decision for {paper.id} "
                             f"({', '.join(issues)}) — re-asking")
                    try:
                        revised, duplicate = _ask_scope_exhaustive(
                            topic_def, [paper], model=selected_model,
                            validation_feedback=", ".join(issues))
                        candidate = revised.get(0)
                        revised_issues = (["duplicate_or_missing_index"] if
                                          candidate is None or duplicate else
                                          _exhaustive_decision_issues(paper, candidate))
                    except Exception as error:  # noqa: BLE001
                        candidate, revised_issues = None, [
                            f"reask_error:{type(error).__name__}"]
                    if candidate is not None and not revised_issues:
                        decision, issues = candidate, []
                    else:
                        decision = {
                            "role": "uncertain", "criterion": "adjudication required",
                            "evidence": "", "reason": "screening decision failed validation",
                            "publication_role": "unclear",
                            "has_original_contribution": False,
                            "adjudication_required": True,
                            "validation_issues": issues + revised_issues,
                        }
                role = decision.get("role")
                if role not in roles:
                    role = "uncertain"
                    decision["role"] = role
                cacheable = not decision.get("adjudication_required", False)
                record = {
                    "fingerprint": fingerprint(paper), "protocol": protocol,
                    "work_key": paper.key(), "model": selected_model,
                    "backend": selected_backend, "prompt_hash": prompt_hash,
                    "cacheable": cacheable,
                    "evidence_sha256": "sha256:" + hashlib.sha256(
                        (paper.title + "\n" + (paper.abstract or "")).encode()).hexdigest(),
                    **decision,
                }
                roles[role].append((paper, record))
                if handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                    handle.flush()
            progress(f"  exhaustive scope {min(start + batch, len(pending))}/"
                     f"{len(pending)} — " + ", ".join(
                         f"{role}={len(items)}" for role, items in roles.items()
                     ))
    finally:
        if handle:
            handle.close()
    return roles


def build_scoped_corpus(topic_def: str, *, per_query: int = 25,
                        model: str | None = None, repair_abstracts: bool = True,
                        resolve_versions: bool = True,
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
    corpus = [p for p, _ in kept]
    if resolve_versions:
        progress("[post] resolving work manifestations ...")
        resolve_manifestations(corpus, progress=progress)
    return corpus, dropped


def source_preflight(progress=print) -> dict[str, str]:
    """Ping each source with a trivial query and report throttling BEFORE a run, so a
    degraded source surfaces upfront instead of mid-snowball — e.g. OpenAlex daily
    budget exhaustion (which otherwise silently empties the snowball) or an expired
    Semantic Scholar key. Non-fatal; just warns."""
    import requests

    def _probe(url, params, headers):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code == 200:
                return "ok"
            if r.status_code == 429:
                return "budget-exhausted" if "budget" in r.text.lower() else "rate-limited (429)"
            return f"http {r.status_code}"
        except Exception as e:  # noqa: BLE001
            return f"unreachable ({str(e)[:36]})"

    status = {
        "openalex": _probe(openalex.API, openalex._params() | {"per_page": 1, "select": "id"},
                           openalex._headers()),
        "arxiv": _probe(arxiv.API, {"search_query": "all:agent", "max_results": 1},
                        {"User-Agent": config.USER_AGENT}),
        "semanticscholar": _probe(semanticscholar.SEARCH,
                                  {"query": "agent", "limit": 1, "fields": "title"},
                                  semanticscholar._headers()),
    }
    for src, st in status.items():
        progress(f"  [preflight] {src:<16} {st}")
    bad = {s: st for s, st in status.items() if st != "ok"}
    if bad:
        progress("  [preflight] WARNING degraded: "
                 + ", ".join(f"{s} ({st})" for s, st in bad.items())
                 + " — recall reduced. Fixes: SEMANTIC_SCHOLAR_API_KEY in .env / CONTACT_EMAIL "
                 "(OpenAlex polite pool) / wait for OpenAlex's daily budget reset.")
    return status


def explore(topic_def: str, *, hops: int = 3, per_query: int = 25,
            use_prefilter: bool = True, epsilon: float = 0.03,
            repair_abstracts: bool = True, recover_rounds: int = 5,
            preflight: bool = True, resolve_versions: bool = True,
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

    if preflight:
        source_preflight(progress=progress)

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
    # Reformulation surfaces cross-cluster BRIDGE papers (moderately cited, so absent
    # from the top-cited seed set). Snowballing FROM them reaches clusters the citation
    # graph otherwise can't, so the FIRST hop seeds from the whole search/recovery set,
    # not just high-yield. (Validated: bridge-seeding +56 vs top-cited seeding +0.)
    bridge_seeds = list(corpus)[:200]
    snow_keys: set[str] = set()
    for hop in range(1, hops + 1):
        seeds = high_yield_seeds(corpus)
        if hop == 1:
            seeds = list({s.id: s for s in bridge_seeds + seeds}.values())
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
    if resolve_versions:
        progress("[post] resolving work manifestations")
        resolve_manifestations(corpus, progress=progress)
    return corpus, dropped, {"curve": curve, "completeness": est, "n": len(corpus)}
