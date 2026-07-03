# Prior — how to run

Practical runbook for the Neo4j / continuous line (branch `cli-backend-twolevel`).
Design: [DESIGN.md](DESIGN.md).

---

## 0. Prerequisites

- **Python 3.11+**
- **Java 17/21** (for Neo4j) — `java -version`
- **Neo4j 5** — via Docker *or* the tarball (this dev box can't run rootless
  containers, so we run the tarball; see §2).
- **Node 18+** (for the React UI)
- No GPU / no torch needed — embeddings run on CPU via fastembed.

```bash
cd prior                          # the repo root
pip install -e ".[graph,web]"     # core + Neo4j/embeddings + web API
```

---

## 1. One-time: which model backend

```bash
export PRIOR_LLM_BACKEND=claude-cli     # credit-free; runs on your Claude Code (Max) login
# (alternative, metered:  export ANTHROPIC_API_KEY=sk-ant-...  && PRIOR_LLM_BACKEND=api)
```
`claude-cli` drives the interactive Claude TUI via a PTY — no API credits. It is
~30 s/call; the pipeline parallelizes around that.

---

## 2. Start Neo4j

**Recommended — Docker:**
```bash
docker compose up -d        # docker-compose.yml in the repo root
# HTTP http://localhost:7474 · Bolt bolt://localhost:7687
```

**No containers? Neo4j 5 tarball** (`$NEO4J_HOME` = wherever you unpacked it):
```bash
"$NEO4J_HOME"/bin/neo4j start
"$NEO4J_HOME"/bin/neo4j status     # check
"$NEO4J_HOME"/bin/neo4j stop       # stop
```
Credentials default to the values in `docker-compose.yml`; override with the
env vars below.

Connection is configurable via `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`.

---

## 3. Build a graph

```bash
export PYTHONPATH=src        # if not pip-installed
prior build "continual learning catastrophic forgetting" --max-papers 12
```
Ingest → full text → read → map → **sink into Neo4j**. ~3 min for 12 papers.
`prior info` prints the graph summary.

Tuning knobs (env): `PRIOR_READ_WORKERS`, `PRIOR_MAP_WORKERS` (default 6),
`PRIOR_MAX_PAPERS`, `PRIOR_FULLTEXT_CHARS`, `PRIOR_EMBED_DIM` (must match the
embedder — 1024 for mxbai-embed-large-v1).

---

## 4. Continuous ingestion (daemon)

```bash
prior daemon --topic "continual learning" --per-topic 15            # one round
prior daemon --topic "continual learning" --watch --interval 600    # loop forever
```
Discovers papers, dedups against Neo4j, enriches each, and **incrementally merges**
into the graph. Repeatable topics: `--topic A --topic B`.

---

## 5. Ask the graph

```bash
prior ask    "Do regularization methods prevent catastrophic forgetting?"
prior solved "continual learning without storing past data"     # novelty / gap
```
Answers are grounded in node ids; off-topic questions get an honest `not_found`.

---

## 6. Web app (API + UI)

```bash
# terminal 1 — API over the live graph
prior serve --port 8078                     # or: python -m prior.cli serve --port 8078

# terminal 2 — React UI
cd frontend
npm install                                 # first time only
VITE_API_BASE=http://127.0.0.1:8078 npx vite --port 5175
```
Open **http://localhost:5175**.

**Remote box?** The servers bind to `127.0.0.1`. From your laptop:
```bash
ssh -L 5175:127.0.0.1:5175 -L 8078:127.0.0.1:8078 <this-host>
```
then open `http://localhost:5175`.

---

## 7. Tests & evals

```bash
pytest -q                                          # 31 tests; no Neo4j / no API key needed
python evals/graph_eval.py groundedness            # key-free faithfulness check
python evals/graph_eval.py abstention              # LLM: off-topic → not_found
python evals/graph_eval.py novelty                 # LLM: recall proxy
```

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `ModuleNotFoundError: prior` | `export PYTHONPATH=src` (or `pip install -e .`) |
| Neo4j won't start | check `java -version` (need 17/21); `neo4j status`; logs in `…/neo4j/logs` |
| Containers fail with subuid error | this box can't run rootless containers — use the tarball (§2) |
| `torch` import error | not used — embeddings are fastembed (CPU/ONNX) |
| Builds feel slow | each LLM call is ~30 s on `claude-cli`; raise `PRIOR_*_WORKERS`, or use `api` backend (metered) for speed |
| Vector dim mismatch on write | `PRIOR_EMBED_DIM` must equal the embedder's dim; drop+recreate the vector index after changing models |
| API returns 503 / empty | Neo4j not running, or graph empty — start Neo4j and `prior build` |
| UI can't reach API | set `VITE_API_BASE`; forward both ports if remote (§6) |
