# Project progress log

> Each session, append a new entry below. Most-recent at the top.

---

## 2026-06-18 — session 3: Friday MVP shipped (live run, web view, baseline, skill)

**Goal:** Ship the Friday demo deliverables — a real end-to-end run, a web view,
a vanilla baseline, and real numbers. Use case (a). No refactors.

**Done (verified):**
- **Live build on real data** via the `claude-code` backend (Max login, no API
  credits): "retrieval augmented generation reduces hallucination" → 19 papers,
  111 claims, 191 relations (107 supports / 49 extends / 29 refines / 6
  contradicts), 11 citations.
- **Forward** (`ask`): grounded, cited "EMERGING" verdict on the RAG/hallucination
  question. **Graceful "no"**: protein-structure-prediction question → NOT_FOUND
  with closest + gap, no fabrication. **Backward** (`origin`): traces in-atlas and
  flags it misses the true (Lewis 2020) origin.
- **Web view**: `prior view` / `src/prior/render_html.py` → self-contained
  interactive HTML graph (vis-network), claims/papers nodes, typed edges,
  click-to-detail. → data/atlas/view.html.
- **Baseline**: `evals/baseline_vanilla.py` → `evals/baseline_comparison.md` —
  vanilla Claude answers confidently / invents citations; Prior is calibrated,
  grounded, and abstains honestly.
- **Agent artifact**: `.claude/skills/prior/SKILL.md` (Prior as a Claude Code
  skill driving the CLI tools).
- **Real numbers** pasted into `evals/results.md`. `WEEK_2.md` holds deferred work.
- Fixed `claude-code` backend for open prompts: `setting_sources=[]` (don't load
  project skills → bare baseline) + salvage text on SDK "max turns".

**Verified by:**
- `pytest -q` → 30 passed.
- `evals/groundedness.py` → 100% groundedness; `evals/graph_stats.py` → 191 relations.
- `evals/baseline_comparison.md` + `evals/results.md` written from the real run.

**Not done / blocked:**
- SciFact not run (dataset not downloaded) — no held-out accuracy number tonight.
- Built at --max-papers 15 (not 25) to fit the Max-plan time budget.
- Web view shows the single-layer atlas; local/global split is README-only.

**Next session — start here (Friday AM demo prep):**
1. Open `data/atlas/view.html` in a browser; rehearse the click-through.
2. Dry-run the three queries from the cached atlas (forward / graceful-no /
   origin) — do NOT live-build on stage.
3. Pull `evals/results.md` numbers + the baseline contrast onto the slide.

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
