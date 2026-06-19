# Project progress log

> Each session, append a new entry below. Most-recent at the top.

---

## 2026-06-19 — session 3: two-level graph + full text + web app

**Goal:** Reshape Prior into a two-level knowledge graph, run it credit-free on a
Claude Code subscription, ingest full text, and ship an interactive web UI.

**Done (verified):**
- **Credit-free `claude-cli` backend** (`claude_cli.py` + `llm.py`): the headless
  `-p` path / Agent SDK now meter API credits, so we drive the *interactive* TUI
  through a PTY with a file-in/file-out protocol (model writes JSON to a file we
  read; `--ax-screen-reader` + fence-tolerant `extract_json`). Runs on the Max
  plan, no credits. `anthropic` import made lazy. `PRIOR_LLM_BACKEND=claude-cli`.
- **Two-level graph** (`models.py`, `reader.py`, `cartographer.py`, `atlas.py`):
  Reader now emits *contributions* (ORKG-style problem/method/result, global
  nodes) + *claims* (local nodes) + *local edges* (entails/contradicts/supports/
  depends_on). Cartographer builds global contribution→contribution edges via the
  hybrid (citations propose ∪ BM25 neighbours; LLM labels; `source`=both|text).
  Every edge carries an explicit `level` (local|global|meta) so same-named
  relations across levels never conflate. See `docs/design.md`.
- **Full-text ingestion** (`sources/fulltext.py`): arXiv HTML (arxiv.org/html →
  ar5iv) directly or via title match for OpenAlex papers; head+tail window
  (`FULLTEXT_CHARS`). Reader reads full text when present, else abstract.
- **Web app**: FastAPI backend (`web/api.py`, `prior serve`) serving the
  two-level graph + `/ask` + `/origin`; React UI (`frontend/`, Vite + React Flow)
  visualizing global/local graphs with a question box.
- `docs/landscape.md`: prior-art scan (ORKG/scite/GoAI/OpenNovelty/…) — the
  whitespace is the integrated two-level graph + agent-callable serving.

**Verified by:**
- `pytest -q` → 25 passed (no API key needed).
- Live two-level build via `claude-cli`: 7 papers → 15 contributions, 47 claims,
  global graph with provenance-tagged edges. Full-text read yields body-only
  concepts the abstract lacked.
- API + Vite dev server both serving live (`:8077` / `:5173`), data flows.

**Not done / next:**
- Throughput: each LLM call spawns a fresh `claude` PTY (~30s). 100 papers ≈ 2.5h
  serially — parallelize PTY sessions (file-in/out is already isolated).
- Reader on full text is single-call (head+tail window); add real chunking.
- Navigator/Auditor not yet upgraded to reason over contributions/global edges.
- Browser-verify the UI visually (stack is up; not yet eyeballed in a browser).

## 2026-06-17 — session 2: SciFact harness + credit-saving backend

**Goal:** Add the headline Navigator eval (SciFact) and a way to run the pipeline
without burning the hackathon's metered API credits.

**Done (verified):**
- Pluggable LLM backend in `llm.py` (`PRIOR_LLM_BACKEND`): `api` (forced-tool
  JSON, metered) and `claude-code` (Agent SDK → Claude Code login / Max plan, no
  API credits; JSON parsed from text via `extract_json`). All agents inherit it.
- SciFact harness (`evals/scifact/`): `dataset.py` (load/download, gold-label
  derivation), `harness.py` (BM25 corpus retrieval → per-claim atlas → Navigator
  → verdict→label mapping → accuracy/macro-F1/abstention + confusion matrix),
  `run.py` (`--mock`/`--limit`/`--backend`/`--model`/`--cache`/`--download`).
- Credit thrift: `--mock` runs the entire harness with no model; `ask_fn` is
  injectable; predictions cache to JSONL and reruns resume.
- Backward/origin eval (`evals/origin_check.py`, key-free): citation-graph
  ancestor check — a traced origin is "grounded" if it's an ancestor of/within
  the matched frontier; plus a no-LLM `structural_origin` baseline. Completes the
  per-agent eval story (Reader/Cartographer/Navigator-fwd/Navigator-bwd).
- `evals/results.md` template for the Friday slide.

**Verified by:**
- `pytest -q` → 25 passed (added SciFact + origin-eval suites; `extract_json`),
  still no API key needed.
- End-to-end `python evals/scifact/run.py --data <synthetic> --mock` → full report
  + confusion matrix, zero API calls.

**Not done / blocked:**
- `claude-code` backend not live-tested here (no Agent SDK installed, no Claude
  Code session in this shell). Logic + lazy import are in; needs a real run.
- SciFact not downloaded yet; `--download` pulls the AllenAI tarball.

**Next session — start here:**
1. `pip install claude-agent-sdk`; `unset ANTHROPIC_API_KEY`;
   `PRIOR_LLM_BACKEND=claude-code` then a 5-claim `prior build` to confirm the
   subscription backend returns valid JSON.
2. `python evals/scifact/run.py --data data/scifact --download --limit 20
   --backend claude-code` and record numbers in `evals/results.md`.
3. If JSON parsing from the Agent SDK is flaky, tighten the JSON-only prompt /
   add a one-shot example in `_structured_claude_code`.

## 2026-06-17 — session 1: scaffold + end-to-end pipeline

**Goal:** Stand up Prior — sources + Reader/Cartographer/Navigator + CLI + evals
— as a runnable foundation for the Fri 19 Jun demo.

**Done (verified):**
- Repo scaffolded to starter-template conventions (`AGENTS.md`, this log, `src/`,
  `evals/`, `tests/`, `pyproject.toml` with a `prior` console script).
- Source adapters: `openalex.py` (search + citation edges, abstract-inverted-index
  reconstruction, no key) and `arxiv.py` (Atom XML via stdlib).
  *Verified live:* fetched real RAG papers with abstracts, refs, cited-by counts.
- Data model (`models.py`): `Paper` / `Claim` / `Edge`; `atlas.py` graph +
  JSON persistence (the hand-off API). *Verified:* citation linking only connects
  papers held in-atlas; save/load round-trips.
- Reader / Cartographer / Navigator agents wired through one `llm.structured()`
  forced-tool-call helper. Cartographer uses BM25 to propose candidate pairs then
  LLM-labels only those (avoids O(n²)). Navigator has forward (`ask`) and backward
  (`origin`) modes; forward emits a graceful `not_found` with closest+gap.
- `pipeline.py` orchestrates ingest→read→map with per-stage caching; `cli.py`
  exposes build/ingest/read/map/ask/origin/info.
- Evals: `groundedness.py` (Reader, key-free), `graph_stats.py` (Cartographer,
  key-free), `citation_check.py` (Navigator citation validity).

**Verified by:**
- `pytest -q` → 13 passed (models, atlas graph, citation linking, retrieval,
  origin ordering, source parsing, eval primitives) — runs with no API key.
- Live: `prior ingest "retrieval augmented generation" --max-papers 15` →
  19 papers cached, 5 intra-atlas citation edges, 11/19 with reference lists.

**Not done / blocked:**
- No `ANTHROPIC_API_KEY` in the dev shell, so Reader/Cartographer/Navigator and
  the on-disk evals were NOT run live yet. All non-LLM layers are tested.
- Citation graph is sparse at ~20 papers; densifies with more (or a 2-hop
  reference expansion — see next).

**Next session — start here:**
1. `export ANTHROPIC_API_KEY=...` then `prior build "retrieval augmented
   generation reduces hallucination" --max-papers 25`; eyeball claims + atlas.
2. Run the three evals on the built atlas; record per-agent numbers in a
   `evals/results.md` for the Friday slide.
3. Pick the demo topic we know best; script the forward / graceful-no / backward
   trio and one commercial-tool comparison (e.g. vs an Elicit/Perplexity answer).

## Conventions
- Append, don't rewrite. "Done" means verified by something runnable.
- Always end with "next session — start here": three numbered, atomic tasks.
