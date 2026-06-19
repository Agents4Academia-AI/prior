# AGENTS.md — what Claude Code reads at session start

Prior turns primary literature into a **two-level knowledge graph**, stored live
in **Neo4j**: a GLOBAL graph of *contributions* across papers (builds_on/refines/
contradicts…) and a LOCAL graph of *claims* within each paper (entails/contradicts/
supports/depends_on), joined by bridge edges. Agents: **Reader** (paper →
contributions + claims + local edges), **Cartographer** (→ global graph),
**Navigator/agent** (grounded Q&A + "has this been solved?"). Ingestion runs
**continuously** (`prior daemon`), MERGE-ing each paper into the graph. A FastAPI +
React app visualizes both levels and answers questions. See `docs/design.md`
(data model), `docs/architecture.md` (full pipeline), `docs/landscape.md` (prior art).

## How to run

- Install: `pip install -e ".[graph,web]"`   (core + Neo4j/embeddings + web API)
- Neo4j:   `docker compose up -d`  — or, where containers can't run, the Neo4j 5
           tarball on Java 21 (see docs/architecture.md). Bolt: `bolt://localhost:7687`.
- Backend: `export PRIOR_LLM_BACKEND=claude-cli`  (credit-free; see Credits)
- Build:   `prior build "<topic>"`      (ingest → read → map → sink to Neo4j)
- Stream:  `prior daemon --topic "<t>" [--watch]`   (continuous ingestion)
- Query:   `prior ask "<q>"` / `prior solved "<problem>"` / `prior info`
- Serve:   `prior serve`   then `cd frontend && npm install && npm run dev`  (web UI)
- Test:    `pytest -q`   (whole suite runs without an API key / Neo4j — 31 tests, mocked)
- Eval:    `python evals/graph_eval.py groundedness`  (key-free) ; `... abstention|novelty` (LLM)

Embeddings are local + free (fastembed, `mxbai-embed-large-v1`, 1024-dim); the
Neo4j vector index dimension (`PRIOR_EMBED_DIM`) must match the embedder.

## Credits

- `prior.llm` has three backends via `PRIOR_LLM_BACKEND`: `api` (metered),
  `claude-code` (Agent SDK), and `claude-cli`. IMPORTANT: `-p/--print` and the
  Agent SDK now meter API credits even on a Max plan — only `claude-cli` (drives
  the *interactive* Claude TUI through a PTY, see `claude_cli.py`) is truly
  credit-free. Set `PRIOR_LLM_BACKEND=claude-cli` for free runs on the
  subscription. Use `--mock` / mocked `ask_fn` to develop evals for free.

## Architecture (one line each)

- `sources/openalex.py` — search + citation edges (`referenced_works`); no key needed
- `sources/arxiv.py` — abstracts for recent preprints; Atom XML via stdlib
- `reader.py` — forces JSON via a single tool; atomic, typed, evidence-bearing claims
- `cartographer.py` — BM25 proposes candidate claim pairs; LLM labels only those (avoids O(n²))
- `navigator.py` — `ask` (forward: verdict + supporting/contradicting/open) and `origin` (backward)
- `atlas.py` — the graph + JSON persistence; `atlas.json` is the hand-off API
- `llm.py` — `structured()` (forced tool-call JSON) and `text()`; retries on rate limits

## Conventions

- Python 3.11+. Functions short; type-hint module boundaries.
- snake_case functions, PascalCase classes, ALL_CAPS constants.
- All LLM calls go through `llm.py` — don't call `anthropic` directly elsewhere.
- New structured outputs: define a JSON-Schema and use `llm.structured(...)`.
- Claim ids: `"<paper_id>::cNN"`. Paper ids: `"openalex:W…"` / `"arxiv:…"`.

## What's off-limits

- Do not commit `data/raw/` or `data/atlas/` (regenerable; gitignored), nor any
  `.env*`, `*.key`, or `secrets/`.
- Do not push directly to `main` — open a PR.
- Don't bypass `structured()` to hand-parse JSON out of prose responses.

## Operating principles

1. *Ground everything* — every Navigator statement cites a claim/paper id. No outside knowledge.
2. *Be a graceful "no"* — when the atlas doesn't cover a question, say so + name the gap.
3. *Cheap by default* — Sonnet for extraction/mapping, Opus only for the user-facing answer.
4. *Stages cache* — re-run `read`/`map` without re-`ingest`-ing.
