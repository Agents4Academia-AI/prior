# Eval results — Neo4j two-level graph

Numbers from the live graph (run via the credit-free `claude-cli` backend unless
noted). Reproduce with `evals/graph_eval.py`.

## Run context

| | |
|---|---|
| Atlas topic | continual learning / catastrophic forgetting |
| Papers / contributions / claims | 12 / 26 / 87 |
| Global / local edges | 98 / 49 |
| Backend | `claude-cli` (no API credits) |
| Embeddings | `mxbai-embed-large-v1` (1024-dim, local) |

## Reader — groundedness (`python evals/graph_eval.py groundedness`)

| Metric | Value |
|--------|-------|
| Claims | 87 |
| Grounded rate (evidence span ≥0.8 token overlap with source) | **1.000** |
| Mean evidence overlap | 0.997 |

Faithfulness guard: extracted claims' evidence spans are present in the source.

## Navigator/agent — abstention & headline (LLM)

| Check | Result |
|-------|--------|
| `ask` off-topic ("data-center energy") | `not_found` (graceful, no confabulation) |
| `has_been_solved` "regularization prevents forgetting?" | `open` — correctly notes it appears only in survey taxonomies; cites contributions; states the gap |

`python evals/graph_eval.py abstention` / `novelty` for the batch runs.

## Performance

| Stage (12 papers) | Time |
|-------------------|------|
| Map (global relations), 6 parallel workers | ~143 s |
| Neo4j sink (batched UNWIND) | ~37 s |
| Full build | ~3 min |

Before parallelism + batched writes: 30-min timeouts (serial calls; one-node-per-
transaction vector writes flushing the HNSW index each commit, ~5.7 s/node).

## Caveats

- Cartographer is conservative → global edges skew to `mentions`/`contrast`; tune
  the prompt for more `builds_on`/`refines`.
- Novelty eval is currently a recall proxy over the live graph; a full temporal
  holdout (rebuild from papers before year Y, ground truth from citations) is the
  next step.
