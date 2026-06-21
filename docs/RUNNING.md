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
cd /vols/bitbucket/stat0531/workspace/prior
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

**This box (tarball):**
```bash
/vols/bitbucket/stat0531/opt/neo4j/bin/neo4j start
# HTTP http://localhost:7474 · Bolt bolt://localhost:7687 · user neo4j / pass priorpass123
/vols/bitbucket/stat0531/opt/neo4j/bin/neo4j status     # check
/vols/bitbucket/stat0531/opt/neo4j/bin/neo4j stop       # stop
```

**Where containers work instead:**
```bash
docker compose up -d        # docker-compose.yml in the repo root
```

Connection is configurable via `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`.

### First-time setup (new person / fresh Neo4j)

You do **not** create the schema by hand — `prior build`/`daemon` call
`graph.setup_schema()` on first run, which creates the uniqueness constraints and
the vector index automatically. So first-time setup is just:

1. **Code + deps:** `pip install -e ".[graph,web]"`.
2. **A Neo4j to write to** — either:
   - *reuse the shared instance on ziz4* (already running, already populated) — just
     leave `NEO4J_*` at their defaults (`bolt://localhost:7687`, pwd in §2); your
     `build` MERGEs into the same graph (idempotent, dedups by id); **or**
   - *your own* — install the Neo4j 5 tarball, set its initial password once
     (`bin/neo4j-admin dbms set-initial-password <pw>`), `bin/neo4j start`, then
     point Prior at it via `NEO4J_URI/USER/PASSWORD`.
3. **A model backend:** `export PRIOR_LLM_BACKEND=claude-cli` (your own Claude Code
   login) or `ANTHROPIC_API_KEY=…` with `PRIOR_LLM_BACKEND=api`.
4. **Ingest** (next section). On the first call the local embedding model downloads
   once (~640 MB, cached); `PRIOR_EMBED_DIM` (1024) must match the index — leave
   the default and it just works.

> Heads-up: a colleague who only wants to *view* the running app doesn't ingest at
> all — that's the tunnel flow in [ACCESS.md](ACCESS.md). Ingestion is only for
> growing the graph.

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
