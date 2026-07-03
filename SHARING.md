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
APIs** → generic `citation_pdf_url`. All free/open or publisher-sanctioned; clean
text via pymupdf, cached so nothing is re-fetched.

- **No keys needed** for the free channels (arXiv, OA, Unpaywall, preprints,
  `citation_pdf_url`, arXiv-twin). They cover arXiv-heavy ML work well.
- **Publisher TDM APIs** (Elsevier/Springer/Wiley) are opt-in — bring your own keys
  in `.env` (`ELSEVIER_API_KEY`, `SPRINGER_API_KEY`, `WILEY_API_KEY`, …) if you're
  entitled. Paywalled papers with no open copy are cited, not fetched.
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

**Don't ship the full-text cache.** For **closed-access papers**, publisher usage
agreements (Elsevier / Springer / Wiley TDM terms) let us *mine* the text but **not
redistribute** it — so we can't include those full texts here, much as we'd like to.
Instead we **cite** every such paper (metadata + DOI), and wherever an open **arXiv**
copy exists we use that. Some paywalled papers with no open copy simply can't be
retrieved at scale and may need to be **added manually**. If paywalls frustrate you as
much as they do us, the fix is upstream — not in this repo.

Ship the **pipeline** instead — full text is fetched only from **free/open channels**
(arXiv, OpenAlex OA, Unpaywall, preprint servers) and the **publishers' own text-mining
APIs** (Elsevier / Springer / Wiley — bring your own keys if entitled) via
`get_fulltext.py`. That's the license-clean way to "share" full text.

## Getting the graph data

The shareable artifact is the **graph** — papers metadata + contributions + relations.
A sample atlas ships in `data/atlas/`; the full 152-paper AI-scientist graph is built and
exportable as a JSON bundle or Neo4j dump (a Zenodo DOI for a citable snapshot is planned).

## Reproducing the corpus

```bash
# 1. explore a topic (or bring your own papers.jsonl)
PRIOR_LLM_BACKEND=claude-code PYTHONPATH=src python scripts/explore.py --topic "$(cat topic.txt)"

# 2. fetch full text (free channels need no keys; add your .env for publisher APIs)
PYTHONPATH=src python scripts/get_fulltext.py --select all

# 3. extract into the graph
PRIOR_LLM_BACKEND=claude-code PYTHONPATH=src python scripts/extract.py --select all
```
