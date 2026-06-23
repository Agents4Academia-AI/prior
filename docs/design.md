# Design: two-level graph + the edge model

> Working design for Prior's knowledge base. Status: draft, 2026-06-18.
> Companion to [landscape.md](landscape.md) (prior art) and the architecture in the README.

## Two levels, one store

- **Local graph** (per paper): nodes = claims/assertions extracted from one paper;
  edges = entail / contradict / support between them. Measures internal coherence and
  represents the paper's "story." **Necessarily text-extracted** — no citations exist
  between sentences of the same paper.
- **Global graph** (cross-paper): nodes = research *contributions* (ORKG-style
  problem+method+result); edges = builds-on / refines / contradicts / contrast between
  contributions across papers.
- **Bridge:** a local claim/contribution node links up to its global contribution node;
  inter-paper argument edges (à la Sci-Arg 2025) connect a local component to another
  paper's claim.

Schemas adopted (don't reinvent): contribution node ≈ **ORKG ResearchContribution**;
local claim graph ≈ **SciClaim**; edge polarity types ≈ **GoAI/scite**; relation labels
+ free eval ≈ **SciNLI**.

## Global edges: both sources, citations as scaffold

Decision: **use both citation-derived and text-extracted edges** — they have
anti-correlated errors, so they're complementary, not competing.

- Citation-derived: high recall, cheap, but coarse (paper→paper), mostly neutral
  "mentions", and **cannot capture uncited parallel work**.
- Text-extracted: correct endpoints (contribution→contribution), real polarity, finds
  uncited links — but O(n²) and prone to hallucinated edges.

**Pipeline — "citations propose, text disposes":**

1. **Backbone (cheap, key-free):** paper-level citation graph from OpenAlex
   `referenced_works`. Candidate generator + fallback edge set. *(Already in repo.)*
2. **Candidate generation:** for each contribution, candidates =
   `{papers it cites} ∪ {embedding/BM25 near-neighbours}`. The union fixes both
   citations-miss-uncited-work and text-extraction's O(n²). *(SPECTER-style embeddings
   beat BM25 here.)*
3. **Typed labeling (LLM):** for each candidate pair, read **citation context + both
   contribution texts** → emit a typed edge between **contribution nodes**.
4. **Provenance stamp:** every edge carries `source ∈ {citation, text, both}`.
   `both` = highest confidence; `text`-only = most novel *and* most hallucination-prone
   → route to the Auditor for verification.

This captures uncited parallel work — something pure-citation systems (scite, GoAI)
structurally cannot — which is part of Prior's novelty.

## Edge schema (global)

```jsonc
{
  "src": "<contribution_id>",       // e.g. "openalex:W123::contrib0"
  "dst": "<contribution_id>",
  "type": "builds_on | refines | contradicts | contrast | supports | mentions",
  "source": "citation | text | both",
  "confidence": 0.0,                 // 0..1
  "evidence": "<span or citation-context sentence>",
  "evidence_loc": "<paper_id + offset, optional>"
}
```

## Edge schema (local)

```jsonc
{
  "src": "<claim_id>",              // "<paper_id>::cNN"
  "dst": "<claim_id>",             // same paper
  "type": "entails | contradicts | supports | neutral",
  "confidence": 0.0,
  "evidence": "<span>"
}
```

## Node schema (contribution, global)

```jsonc
{
  "id": "<paper_id>::contribN",
  "paper_id": "openalex:W… | arxiv:…",
  "problem": "…",                   // ORKG ResearchContribution triple
  "method": "…",
  "result": "…",
  "claims": ["<claim_id>", …]       // local claims that support this contribution
}
```

## Build-vs-reuse summary

- **Reuse schemas:** ORKG contributions, SciClaim claims, GoAI/scite edge types, SciNLI labels.
- **Reuse data/APIs:** OpenAlex, arXiv, Semantic Scholar; SciNLI/SciClaim as free evals.
- **Build fresh (the edge):** the two-level integration, the local↔global bridge, the
  agent-callable serving layer.

## Open decisions

1. Verify whether scite already covers the inter-paper typed-edge layer at scale before
   claiming that part novel.
2. Is the **local "story" graph load-bearing** for novelty/gap-finding, or a nice-to-have?
   (OpenNovelty gets results with no local graph — need a crisp justification.)
3. Streaming vs. batch processing (incremental graph merge as papers arrive vs. the
   current cached pipeline).
4. Embedding model for candidate generation (SPECTER vs. newer) and the neighbour budget.
