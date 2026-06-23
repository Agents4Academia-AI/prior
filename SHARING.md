# Sharing Prior with other teams

Prior is three standalone stages — **explore → get full text → extract** — plus the
graph they produce. Here's how to reuse each, and what's safe to share.

## The three stages (each usable on its own)

### 1. Explore (agentic) — topic → scoped corpus
`scoper.explore(topic_def)` · `scripts/explore.py --topic "..." --hops 3`

The full recall pipeline in one call: LLM-proposed query variations over OpenAlex +
arXiv + Semantic Scholar → BM25 pre-filter → LLM relevance filter against an explicit
in-/out-of-scope definition → citation snowball (backward refs + forward cited-by) to
**saturation**, with a capture–recapture completeness estimate. Use `--hops 0` for a
search-only (top-k) run if that's enough.

### 2. Get full text (deterministic) — DOIs/arXiv ids → cached text
`fulltext.fetch_many(papers)` · `scripts/get_fulltext.py --ids dois.txt`

A multi-source cascade: arXiv (HTML/PDF + **title-search for arXiv twins**) →
open-access PDF → preprint servers → Unpaywall → **Elsevier/Springer/Wiley TDM
APIs** → generic `citation_pdf_url` → institutional cookies → Playwright. Clean text
via pymupdf, cached so nothing is re-fetched.

- **No keys needed** for the free channels (arXiv, OA, Unpaywall, preprints,
  `citation_pdf_url`, arXiv-twin). They cover arXiv-heavy ML work well.
- **Publisher APIs** (Elsevier/Springer/Wiley) and **Playwright** are opt-in via
  your own `.env` (`ELSEVIER_API_KEY`, `SPRINGER_API_KEY`, `WILEY_API_KEY`, …) and
  your own institutional entitlement.
- `--ids` takes a plain file of DOIs / arXiv ids — so any project can use this with
  just a list, no Prior corpus required.

### 3. Extract (LLM) — full text → graph
`scripts/extract.py --select all` → `pipeline.read_all` → contributions + claims +
local edges; `build` / `sink_to_neo4j` take it to the global graph DB.

## What's safe to share

| layer | redistribute? | why |
|---|---|---|
| **papers metadata** (`papers.jsonl`) | ✅ | open OpenAlex / arXiv metadata |
| **extractions + relations** (the graph) | ✅ | derived / transformative — our analysis, not source text |
| **raw full text** (the `fulltext/` cache) | ⚠️ **no** | publisher TDM licenses permit *mining*, not redistribution |

**Don't ship the full-text cache.** It's licensed for our text-mining, not
redistribution (per the Bodleian TDM guidance). Instead ship the **pipeline** —
anyone reproduces full text locally with *their own* entitlement via
`get_fulltext.py`. That's the license-clean way to "share" full text.

## Getting the graph data

The shareable artifact is the **graph** (papers metadata + contributions + relations),
to be released as a JSON export / Neo4j dump (and optionally a Zenodo DOI for a
citable reference). _Link TBD once extraction over the full corpus completes._

## Reproducing the corpus

```bash
# 1. explore a topic (or bring your own papers.jsonl)
PRIOR_LLM_BACKEND=claude-code PYTHONPATH=src python scripts/explore.py --topic "$(cat topic.txt)"

# 2. fetch full text (free channels need no keys; add your .env for publisher APIs)
PYTHONPATH=src python scripts/get_fulltext.py --select all

# 3. extract into the graph
PRIOR_LLM_BACKEND=claude-code PYTHONPATH=src python scripts/extract.py --select all
```
