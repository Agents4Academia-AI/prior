# AGENTS.md — what Claude Code reads at session start

Prior turns primary literature into a queryable atlas of claims via three agents:
**Reader** (paper → claims), **Cartographer** (claims → graph), **Navigator**
(question → grounded answer, forward & backward). Read `README.md` for the why.

## How to run

- Install: `pip install -e .`  (or `pip install -r requirements.txt`)
- Env:     `export ANTHROPIC_API_KEY=...` ; optionally `PRIOR_CONTACT_EMAIL=...`
- Build:   `prior build "<topic>"`     (ingest → read → map → `data/atlas/atlas.json`)
- Query:   `prior ask "<q>"` / `prior origin "<concept>"` / `prior info`
- Test:    `pytest -q`   (the suite runs without an API key — source/graph layers only)

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
