# Prior — architecture (Neo4j live graph + continuous ingestion)

How the system works end to end. Companion to `design.md` (data model / edge
hybrid) and `landscape.md` (prior art).

## One picture

```
DISCOVERY (prior daemon)            ENRICHMENT (worker pool)             LIVE STORE
 topic search ─┐                  fetch full text (HTML→ar5iv→PDF)        ┌────────────┐
 (OpenAlex,    ├─▶ dedup vs ─▶    Reader  → contributions+claims+local ─▶ │  Neo4j     │
  arXiv)       │   Neo4j          embed (mxbai, local, free)              │  two-level │
              new papers          Cartographer (incremental) → global     │  graph +   │
                                  edges vs vector-nearest existing  ─────▶ │  vectors   │
                                                                          └─────┬──────┘
                                                                                │
                                          FastAPI (graph tools + Q&A) ◀─────────┤
                                          React UI (global/local viz) ◀─────────┘
                                          agent.ask / has_been_solved
```

## Stages

1. **Ingest** — OpenAlex + arXiv search; primary-literature focus; full text
   (`sources/fulltext.py`, HTML-first). Each paper deduped by canonical id.
2. **Extract** (one LLM call/paper, parallel) — Reader emits the paper's
   *contributions* (problem/method/result, GLOBAL nodes), *claims* (LOCAL nodes,
   typed, evidence-bearing) and *local edges* (entails/contradicts/supports/
   depends_on). Claims bridge up to the contribution they support.
3. **Relate** (parallel / incremental) — Cartographer builds GLOBAL contribution↔
   contribution edges via "citations propose, text disposes": candidates =
   cited ∪ vector-nearest, LLM labels builds_on/refines/contradicts/contrast,
   each edge stamped `source = both|text`.
4. **Store** — everything MERGE-ed into **Neo4j** (`graph.py`). Node labels carry
   the level; native vector index over contribution/claim embeddings. The DB is
   the source of truth (no more `atlas.json`); writes are idempotent so continuous
   ingestion just keeps merging.
5. **Serve / reason** — `web/api.py` exposes the graph + the agent's tools; the
   React app in `frontend/` visualizes both levels. `agent.py` answers questions
   by vector-seeding the graph, expanding neighbourhoods, and judging — grounded
   in node ids, with honest abstention.

## Agents vs tools vs functions

- **Plain functions**: ingest, full-text fetch, embedding, candidate generation,
  graph upserts — deterministic, no autonomy.
- **One LLM call (function)**: Reader, Contribution extraction, edge labelling —
  fixed input→structured output, run in parallel.
- **Agent**: the Navigator/`agent.py` layer — it decides what to retrieve, expands
  the graph, and reasons. This is the only place autonomy pays off.

## Backends & cost

All model calls go through `llm.py`. `PRIOR_LLM_BACKEND=claude-cli` drives the
*interactive* Claude TUI via a PTY (`claude_cli.py`) — the only path that runs on
a Max subscription **without** metering API credits (`-p`/the Agent SDK now meter).
It is ~30s/call, so read/map run in thread pools. Embeddings are local + free.

## Why Neo4j

The agent's queries are vector-seeded, localized, iterative subgraph exploration:
k-NN seed → typed 1-hop expand → bounded `builds_on*` lineage → aggregate
consensus. Neo4j gives index-free-adjacency traversal + a native vector index in
one store; the agent reaches it only through the `graph.py` repository (never raw
Cypher). Swappable behind that layer if needed.

## Running it

See `AGENTS.md` "How to run". Tests (`pytest -q`) run with no Neo4j and no API key.
