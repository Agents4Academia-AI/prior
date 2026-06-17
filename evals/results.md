# Eval results

> Template — paste numbers in after a real run. Each table says exactly which
> command produced it so results are reproducible. Record the atlas topic, paper
> count, backend, and model with every run.

**Run context**

| | |
|---|---|
| Date | _YYYY-MM-DD_ |
| Atlas topic | _"…"_ |
| Papers / claims | _…_ / _…_ |
| Backend | `api` / `claude-code` |
| Models | reader=… cartographer=… navigator=… |

---

## Reader — groundedness (`python evals/groundedness.py`)

| Metric | Value |
|--------|-------|
| Groundedness rate (evidence span found in source) | _…%_ |
| Mean evidence overlap | _…%_ |
| Claims / paper | _…_ |
| Mean confidence | _…_ |
| Type distribution | _…_ |

## Cartographer — graph stats (`python evals/graph_stats.py`)

| Metric | Value |
|--------|-------|
| Citation edges | _…_ |
| Semantic relations (supports/contradicts/refines/extends) | _…_ |
| Contradiction rate | _…%_ |
| Linked-claim rate | _…%_ |

## Navigator (forward) — SciFact (`python evals/scifact/run.py --data data/scifact`)

| Metric | Value |
|--------|-------|
| Claims scored | _…_ |
| Accuracy (3-way) | _…%_ |
| Macro-F1 | _…_ |
| NOINFO recall (abstention) | _…_ |
| NOINFO precision | _…_ |

_Confusion matrix:_ paste the `render()` block here.

## Navigator (backward) — origin grounding (`python evals/origin_check.py "<concept>" --navigator`)

| Concept | Structural origin | Navigator origin | Grounded in citation graph? | Agrees w/ baseline? |
|---------|-------------------|------------------|-----------------------------|---------------------|
| _…_ | _…_ | _…_ | _yes/no_ | _yes/no_ |

---

## Notes / caveats for the slide

- Reader/Cartographer numbers come from the demo atlas, not a held-out gold set —
  groundedness is a faithfulness proxy, not extraction recall.
- SciFact scores Navigator + retrieval (the given claim bypasses Reader).
- Origin grounding is a self-consistency check against our own citation edges,
  not an external benchmark — report as illustrative.
