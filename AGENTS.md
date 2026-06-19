# AGENTS.md — what Claude Code reads at session start

> ⚠️ **BRANCHING — `main` is the Friday-demo snapshot.** Do **not** commit to
> `main`. All subsequent work goes on a feature branch (`name/feature`, e.g.
> `harit/local-graph`, `klara/merge`), then opens a PR for a teammate to review
> and merge. One Claude Code session per branch.

Prior turns primary literature into a queryable atlas of claims via three core
agents: **Reader** (paper → claims), **Cartographer** (claims → graph),
**Navigator** (question → grounded answer, forward & backward). A fourth,
**Contribution agent** (`contributor.py`), extracts papers' *self-declared,
standalone* contributions from full text. Sources are filtered to primary
literature (reviews/surveys excluded). Read `README.md` for the why.

## How to run

- Install: `pip install -e .`  (or `pip install -r requirements.txt`)
- Env:     `export ANTHROPIC_API_KEY=...` ; optionally `PRIOR_CONTACT_EMAIL=...`
- Build:   `prior build "<topic>" [--cite-hops N]`  (ingest → read → map → `data/atlas/atlas.json`)
- Query:   `prior ask "<q>"` / `prior origin "<concept>"` / `prior info`
- Extras:  `prior contributions` (self-declared contributions, full text) · `prior view [--contributions]`
- Test:    `pytest -q`   (the whole suite runs without an API key — 20 tests, all backends mocked)
- Eval:    `python evals/scifact/run.py --data data/scifact --mock`  (SciFact, zero credits)

## Credits

- `prior.llm` has two backends via `PRIOR_LLM_BACKEND`: `api` (metered) and
  `claude-code` (Agent SDK → your Claude Code login, no API credits). The SciFact
  runner also takes `--backend`. Use `--mock` / mocked `ask_fn` to develop evals
  for free; spend credits only on the final run.

## Architecture (one line each)

- `sources/openalex.py` — search + citation edges + OA PDF urls; no key needed
- `sources/arxiv.py` — recent preprints; Atom XML via stdlib
- `sources/_filters.py` — `looks_like_review` (primary-lit only; reviews excluded)
- `reader.py` — forces JSON via a single tool; atomic, typed, evidence-bearing claims
- `cartographer.py` — BM25 proposes candidate claim pairs; LLM labels only those (avoids O(n²))
- `navigator.py` — `ask` (forward: verdict + supporting/contradicting/open) and `origin` (backward)
- `contributor.py` — Contribution agent; standalone self-declared contributions (full text)
- `fulltext.py` — HTML-first full text (arxiv html → ar5iv → real-PDF); skip, never abstract-fallback
- `atlas.py` — the graph + JSON persistence; `atlas.json` is the hand-off API
- `llm.py` — `structured()` (forced tool-call JSON) and `text()`; api / claude-code backends

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
