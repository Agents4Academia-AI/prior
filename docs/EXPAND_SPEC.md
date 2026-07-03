# `expand()` — automatic, self-terminating graph expansion

One entry point that grows the corpus/graph from **seeds** (provided papers *or* a
search) to **saturation within a budget**, non-destructively and incrementally.
Replaces the hand-cranked gather → snowball → scope → fold → relate sequence.

## Entry point

```python
def expand(
    *,
    topic: str,                       # relevance rubric (IN / OUT scope text)
    seeds: list[Paper] | None = None, # provided-papers mode
    queries: list[str] | None = None, # search mode (else propose_queries(topic))
    budget_calls: int = 300,          # hard cap on LLM calls (throughput is the limit)
    epsilon: float = 0.03,            # stop when kept/candidates < epsilon for a hop
    max_hops: int = 4,                # backstop
    anchor_k: int = 25, per_paper: int = 40,
    view: str | None = None,          # also emit a filtered view of the result
    model: str | None = None,         # scope/filter model (cheap model = big unlock)
    progress=print,
) -> ExpandResult
```

Both inputs collapse to **`seeds + topic`**:
- `queries` → `scoper.gather_candidates(queries)` → relevance pass → seeds.
- `seeds` (Zotero / repo / DOIs) → resolve like `weekend_run._gold_anchors` (arXiv-id → DOI → title) → seeds.

## Algorithm

```
NORMALIZE
  corpus       = load papers.jsonl                 # the ever-growing substrate
  corpus_keys  = {p.key() for p in corpus}         # canonical cross-source identity
  seeds        = resolve(queries|papers); add seeds∉corpus  (additive)
  frontier     = seeds

EXPAND  (per hop)
  new_oa, reached_oa = scoper.snowball(frontier, corpus=corpus, anchor_k, per_paper)
  new_s2, reached_s2 = scoper.snowball_s2(frontier, corpus=corpus, anchor_k, per_paper)
  cands = [c for c in scoper._dedup_cross_source(new_oa+new_s2)
           if c.key() not in corpus_keys]
  survivors, gated = scoper.prefilter(topic, cands)              # BM25, cheap
  kept, dropped    = scoper.scope(topic, survivors,             # LLM, cache-aware,
                                  cache_path=…, model=model)     #   STRICTLY sequential
  new_kept = [p for p,_ in kept]
  add new_kept to corpus + papers.jsonl (additive); corpus_keys |= keys
  pipeline.append_contributions(new_kept)                        # only new papers
  yield_ratio = len(new_kept) / max(1, len(cands))
  spent += (scope + extract calls)
  frontier = new_kept

  STOP if   new_kept == 0 or yield_ratio < epsilon   # SATURATED  (primary)
       or   spent >= budget_calls                    # BUDGET
       or   hop  >= max_hops                          # backstop

RELATE  (incremental)
  relate only the NEW contributions: kNN them against the existing set,
  merge into contributions.json edges — never re-relate the whole graph.

VIEW  (optional)
  if view: pipeline.write_contribution_view(view, {core ids})
```

## Stopping rule (the actual automation)

| signal | source | role |
|---|---|---|
| **saturation** | `kept==0` or `kept/cands < epsilon` | primary stop (the 376→20→10→0 curve) |
| **budget** | cumulative LLM calls ≥ `budget_calls` | hard cap — throughput is the bottleneck |
| **hops** | `hop ≥ max_hops` | backstop |
| **completeness** | `completeness.capture_recapture(search, snowball, overlap)` | *reported*, and an optional recall target while channels stay independent |
| **gold recall** | provided seeds | papers-mode: don't stop until each seed's refs/cites are scoped |

## Why it's affordable (non-negotiable design choices)

- **Substrate is append-only.** `papers.jsonl` / `contributions.json` only grow; one-time `*_full` backup; views are derived. Nothing is ever deleted.
- **Caches everywhere.** `scope_cache.jsonl` (never re-judge a paper), `append_contributions` (never re-extract), incremental relate (never re-relate the graph).
- **Canonical `Paper.key()`** for dedup, membership, and capture-recapture overlap — across OpenAlex / arXiv / S2 id namespaces.
- **Strictly sequential LLM.** One process, no concurrency (it caused empty-response failures repeatedly). A lock-file in the data dir refuses a second concurrent `expand`.
- **Pre-filter before the LLM.** `scoper.prefilter` (BM25, recall-safe) gates obvious noise so a broad snowball is scopeable.

## Triggers (thin wrappers)

```python
on_input(papers|query)  → expand(...)                              # once, to saturation
on_new_paper(p)         → expand(seeds=[p], max_hops=1)            # snowball from it
scheduled_refresh()     → expand(seeds=high_yield_seeds(corpus),  # catch new citing work
                                 max_hops=1)  # forward cited-by only
```

## Views = slices on one substrate

`pipeline.write_contribution_view(name, keep_ids)` →
`contributions_<name>.json` + `view_<name>.html`, full graph untouched.
- **core** = `keep_ids` = papers passing a strict `topic`.
- **section / zoom** = a subtopic predicate, an embedding cluster, or one paper's
  citation neighbourhood. Expansion can target a view ("expand this section").

## Outputs

`ExpandResult = {added, kept, dropped, hops, calls_spent, stop_reason, recall_estimate}`.
Substrate files grow; derived `contributions_<view>.json` + `view_<view>.html`.

## Build order

1. `expand()` core loop + `ExpandResult` + the stopping rule (wraps existing
   `scoper.*` / `pipeline.*` — mostly orchestration).
2. **Incremental relate** (relate only new contributions vs. their neighbours) —
   the one genuinely new piece; today's relate redoes the whole set.
3. Data-dir lock-file (sequential guard).
4. Trigger wrappers (`on_new_paper`, `scheduled_refresh`).
5. **Cheap-filter option**: run `scope()` on Haiku (model param already exists) →
   ~10× candidates affordable; keep contributions/Navigator on the strong model.
   This is the single biggest throughput unlock.

## Pieces already in place

`scoper.{propose_queries, gather_candidates, prefilter, snowball, snowball_s2,
high_yield_seeds, scope, _dedup_cross_source}`, `Paper.key`, the three sources
(incl. `cited_by` / `references` / `citations` / `fetch_ids` / `fetch_doi`, S2
keyless-fallback), `completeness.capture_recapture`, `pipeline.{append_contributions,
write_contribution_view, relate_contributions_fast(path=)}`,
`render_contributions(data_path=)`, append-only + checkpointing.

**Full-text stage (implemented).** `fulltext.fetch_with_source` is the retrieval
cascade — arXiv (html / pdf / **title-search for arXiv twins**) → OA PDF → preprint
servers → Unpaywall → **Elsevier / Springer / Wiley TDM APIs** (bring your own keys)
→ generic `citation_pdf_url` — all free/open or publisher-sanctioned, with a raw-text cache
(`data/fulltext/`, pymupdf parsing) so nothing is re-fetched. `pipeline.fetch_fulltext`
runs it in PARALLEL (no LLM, so safe to fan out); `pipeline.expand` chains
full-text → `append_contributions` → `write_contribution_view`. One CLI:
`scripts/expand.py --select {all,core,missing,skip,preprints} [--fetch-only|--view]`.
Document-class + topical-scope filtering: `scripts/classify_core.py` (primary ×
llm_agent) layered with the OpenAlex `Paper.type` veto. Manual entitled PDFs:
`scripts/ingest_manual_pdfs.py`. Keys live in `.env` (Elsevier/Springer/Wiley/Unpaywall).
