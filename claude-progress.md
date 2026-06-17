# Project progress log

> Each session, append a new entry below. Most-recent at the top.

---

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
