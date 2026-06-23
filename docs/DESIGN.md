# Prior — design & workflow (detailed)

> The authoritative design note for the Neo4j / continuous-ingestion line of work
> (branch `cli-backend-twolevel`). Companion runbook: [RUNNING.md](RUNNING.md).
> Shorter views: [architecture.md](architecture.md), edge model in [design.md](design.md),
> prior art in [landscape.md](landscape.md).

---

## 1. What Prior is

Prior turns primary scientific literature into a **living, two-level knowledge
graph** and reasons over it. Unlike "research assistants" that Google + summarize,
Prior builds a transparent graph of *claims* and *contributions* extracted from
primary sources, each carrying provenance, and answers questions by exploring that
graph — grounded, with citations, and an honest "not found" when the literature
doesn't cover something.

The graph lives in **Neo4j** (not a one-shot JSON file) and grows **continuously**
as new papers are ingested.

---

## 2. The two-level graph (data model)

Three node types, stacked:

```
Paper ──HAS_CONTRIBUTION──▶ Contribution  (GLOBAL node)
                                  ▲
                            SUPPORTS_CONTRIB   (bridge)
                                  │
                               Claim          (LOCAL node) ──STATED_IN──▶ Paper
```

**Nodes**
- **Paper** — a primary source. `id` = `openalex:W…` / `arxiv:…` / `s2:…`; carries
  title, year, authors, venue, doi, url, cited_by, abstract, full_text.
- **Contribution** (global) — one research contribution, ORKG-style: `problem` /
  `method` / `result`. A paper has 1–3. Carries a vector `embedding`.
- **Claim** (local) — an atomic, verifiable assertion with an `evidence` span and a
  `claim_type` (empirical / theoretical / methodological / definitional /
  background). Carries a vector `embedding`.

**Edges** — the relationship *type* is the relation; the **level is implicit in the
node labels** (a `SUPPORTS` between two Claims is local; between two Contributions is
global), so shared names never conflate.

| Level | Edge types | Meaning |
|-------|-----------|---------|
| bridge / meta | `STATED_IN`, `HAS_CONTRIBUTION`, `SUPPORTS_CONTRIB`, `CITES` | provenance + local↔global link + citation graph |
| **local** (Claim↔Claim, same paper) | `ENTAILS`, `CONTRADICTS`, `SUPPORTS`, `DEPENDS_ON` | the paper's internal coherence / "story" |
| **global** (Contribution↔Contribution, cross-paper) | `BUILDS_ON`, `REFINES`, `CONTRADICTS`, `CONTRAST`, `SUPPORTS`, `MENTIONS` | cross-paper lineage |

Every global edge carries a **provenance** stamp: `source = both` (a citation links
the two papers *and* the text confirms the relation) or `text` (text-extracted, no
citation — i.e. **uncited parallel work**, which pure-citation tools can't surface).

Schemas are deliberately borrowed from prior art (see landscape.md): contribution ≈
ORKG ResearchContribution; claim graph ≈ SciClaim; edge polarity ≈ scite/GoAI;
relation labels ≈ SciNLI.

---

## 3. The agents (and what is *not* an agent)

Design rule: something is an **agent** only if it must *decide what to do next and
loop*. Fixed input→output is a function. Most of Prior is functions; autonomy lives
only in the query layer.

| Component | Kind | What it does |
|-----------|------|--------------|
| sources (`openalex`, `arxiv`, `fulltext`, …) | functions | fetch papers + body text |
| **Reader** (`reader.py`) | one LLM call / paper | paper → contributions + claims + local edges |
| **Cartographer** (`cartographer.py`) | functions + LLM labelling | contribution↔contribution global edges (hybrid) |
| embeddings (`embeddings.py`) | function | local vectors for the index |
| graph (`graph.py`) | function (repository) | the only Neo4j access layer |
| **Navigator / agent** (`agent.py`) | **agent** | explores the graph to answer questions |

The agent is the one place looping pays off: vector-seed → expand → judge → maybe
expand again.

---

## 4. The global-edge hybrid — "citations propose, text disposes"

Citation-derived and text-extracted edges have *anti-correlated* errors, so Prior
uses both:

1. **Backbone (cheap):** OpenAlex `referenced_works` → candidate edges (high recall,
   but coarse and mostly neutral).
2. **Candidate generation:** for each contribution, candidates = `{cited papers}` ∪
   `{vector-nearest contributions}`. The union fixes both citations-miss-uncited-work
   *and* text-extraction's O(n²) cost.
3. **Typed labelling (LLM):** read both contributions → emit a typed global edge.
4. **Provenance stamp:** `both` if a citation links the papers, else `text`.

This captures uncited parallel work — part of Prior's novelty over scite/GoAI.

---

## 5. Storage — Neo4j + native vectors

The DB is the **source of truth** (no `atlas.json`). One store does graph traversal
*and* vector search:
- Node labels carry the level; uniqueness constraints on `id` give idempotent
  `MERGE` (so continuous ingestion dedups for free).
- **Vector indexes** (cosine) on `Contribution.embedding` and `Claim.embedding`,
  `PRIOR_EMBED_DIM`-dimensional (must match the embedder).
- Writes go through `graph.bulk_load` (batched `UNWIND` in single transactions).
  *Why batched:* writing one embedding per transaction flushes the HNSW index on
  every commit (~5.7 s/node); batching → a 12-paper sink dropped 8 min → 37 s.

The agent reaches the graph **only** through `graph.py` (ann / neighbours / traverse
/ aggregate) — never raw Cypher — so the engine is swappable.

**Embeddings** are local and free: fastembed `mxbai-embed-large-v1` (1024-dim, CPU/
ONNX, no torch, no API).

---

## 6. Backends & cost

All model calls go through `llm.py`, selected by `PRIOR_LLM_BACKEND`:

| Backend | Runs on | Cost |
|---------|---------|------|
| `api` | Anthropic API | metered credits |
| `claude-code` | Agent SDK | **meters** (SDK = headless) |
| **`claude-cli`** | interactive Claude TUI via PTY (`claude_cli.py`) | **free** on a Max plan |

Important: `-p/--print` and the Agent SDK now meter even on a subscription — only the
*interactive* path is free. `claude_cli` drives it through a pseudo-terminal with a
**file-in / file-out** protocol (the model writes JSON to a file we read), dodging
TUI scraping. It is ~30 s/call, so read/map stages run in thread pools.

---

## 7. Workflow — batch build

`prior build "<topic>"`:

1. **Ingest** — OpenAlex + arXiv search (capped); full text fetched where available
   (`fulltext.py`: arXiv HTML → ar5iv → PDF), else abstract.
2. **Read** (parallel, `PRIOR_READ_WORKERS`) — Reader extracts contributions +
   claims + local edges per paper.
3. **Map** (parallel, `PRIOR_MAP_WORKERS`) — Cartographer builds global edges via the
   hybrid; per-call timeout + capped retries so one hung call can't stall the build.
4. **Sink** — embed all nodes, `graph.bulk_load` into Neo4j.

A 12-paper build is ~3 min on `claude-cli`.

---

## 8. Workflow — continuous ingestion (`prior daemon`)

The graph is never "done". `daemon.py`:

```
discover (topic search)  →  dedup vs Neo4j  →  worker pool:
                                                  fetch full text
                                                  Reader → contributions/claims/local
                                                  embed
                                                  graph.bulk_load (this paper)
                                                  incremental global relate:
                                                    each new contribution vs its
                                                    vector-nearest EXISTING ones → label → add
  →  repeat (── --watch loops forever, re-polling topics every interval)
```

Key property: **incremental merge** — a new paper is related to the existing graph
via vector-nearest neighbours; the global graph is never rebuilt. Idempotent `MERGE`
makes re-discovery a no-op. Validated: a round grew the graph 12 → 21 papers, adding
global edges per new paper.

**Planned front-end (Klara's `scoper` branch):** replace the daemon's naive topic
search with the **Scoper** — topic *definition* (include/exclude) → LLM queries →
multi-source gather (OpenAlex/arXiv/Semantic Scholar) → strict LLM relevance filter
→ clean, recall-checked corpus. Only the discovery step changes; the rest of the
daemon is unchanged. A capture–recapture + hypergeometric **completeness model**
gives a principled stopping criterion.

---

## 9. The exploration agent (`agent.py`)

Two entry points, both grounded in node ids with honest abstention:

- **`ask(question)`** — vector-seed claims → LLM verdict (established / contested /
  emerging / not_found) + supporting / contradicting / open, or a graceful "no"
  (closest + gap).
- **`has_been_solved(problem)`** — the headline novelty/gap question:
  1. vector-seed contributions about the problem,
  2. expand each with its global neighbours,
  3. `aggregate_relations` for consensus (supports vs contradicts counts),
  4. LLM verdict (solved / partially_solved / contested / open / not_addressed) +
     the contributions that address it + closest + gap.

The general query pattern is **vector-seeded, localized, iterative subgraph
exploration**: `ann` seed → typed 1-hop expand → bounded `BUILDS_ON*` lineage →
aggregate → answer.

---

## 10. Serving

- **`web/api.py`** (`prior serve`) — reads the live Neo4j graph (reflects continuous
  ingestion with no reload). Endpoints: `/api/summary`, `/api/papers`,
  `/api/graph/global`, `/api/graph/paper/{id}`, `/api/contribution/{id}`, plus the
  agent-callable tools `/api/search` (vector), `/api/neighbours`, `/api/traverse`,
  and `/api/ask`, `/api/solved`.
- **`frontend/`** — React + React Flow app: global contribution graph (edges dashed
  for `text` provenance, solid for `both`), drill into a paper's local claim graph,
  and an Ask panel.

---

## 11. Evaluation (`evals/graph_eval.py`)

Two tracks: cheap always-on guards + the headline task eval.

| Eval | Cost | Latest |
|------|------|--------|
| **groundedness** — evidence span present in source | key-free | 100% of 87 claims (overlap 0.997) |
| **abstention** — off-topic → not_found | LLM | 3/3 |
| **novelty (recall proxy)** — never falsely "not_addressed" when related work exists | LLM | 5/5 |

Next: full **temporal holdout** — build the graph from papers before year Y, ask
whether a known contribution's problem was solved, ground truth from chronology +
the paper's own citations.

---

## 12. Module map

```
src/prior/
  sources/openalex.py arxiv.py fulltext.py   # ingestion (+ semanticscholar.py planned)
  reader.py            # paper → contributions + claims + local edges (1 LLM call)
  cartographer.py      # global edges (hybrid, parallel)
  embeddings.py        # local fastembed vectors
  graph.py             # Neo4j repository (the only graph-access layer)
  agent.py             # graph-backed Navigator: ask / has_been_solved
  daemon.py            # continuous ingestion + incremental merge
  llm.py  claude_cli.py# model backends (claude-cli = credit-free PTY)
  pipeline.py          # batch build + sink_to_neo4j
  web/api.py           # FastAPI over the live graph
  models.py            # Paper / Contribution / Claim / Edge
frontend/              # React + React Flow UI
evals/graph_eval.py    # groundedness / abstention / novelty
```

---

## 13. Open items

- **Reconcile with `main`** — `main` diverged ~35 commits (its own contributions/
  full-text/views); this branch's unique pieces (credit-free backend, Neo4j+vectors,
  daemon, React app) should be ported onto current `main`, ideally with Klara's
  Scoper. Branch is pushed (`origin/cli-backend-twolevel`), no PR yet.
- **Cartographer is mentions-heavy** (conservative prompt) — tune for richer
  `builds_on`/`refines`.
- **Scoper integration** into the daemon (section 8).
- **Citation-frontier expansion** in the daemon (topics drive discovery for now).
- **Throughput** — `claude-cli` ~30 s/call; parallelized, but session-reuse would cut
  the per-call spawn overhead further.
