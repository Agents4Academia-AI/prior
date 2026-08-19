# Scoper workshop RQ1 handoff — 2026-08-19

This is the coordination note for the AI for Meta-Science workshop paper.
It distinguishes completed results from work still running.

## Evaluation language

The 152 works are the **frozen Prior v0.2 reference set**, not an independent
expert gold standard. It is a retrospective recovery/regression benchmark and
must not be used to claim absolute field recall or superiority over Elicit.

The original Scoper comparison corpus contains 255 papers. Fresh Elicit-only
screening defines external-only at the work/manifestation level relative to
that 255-paper corpus, using DOI, arXiv identifier, then normalized title.

## Completed fresh Elicit retrieval

Artifacts live under:

`/Users/kk1918_1/projects/Otto/artifacts/scoper-workshop-rq1-2026-08-19/elicit/`

| arm | result records | unique candidates | Prior-v0.2 reference recovered | recall |
|---|---:|---:|---:|---:|
| Elicit plain | 300 | 300 | 32/152 | 21.05% |
| Elicit multi-query | 800 | 714 | 51/152 | 33.55% |

For multi-query Elicit, reference-set recall is 7/152 at rank 10 per query,
15/152 at 20, 36/152 at 50, and 51/152 at 100.

Inputs are frozen in `evals/scoper_monkeys/workshop_inputs/`. The ten-query file
reuses the July experiment's queries rather than tuning against known misses.

## Elicit-only common screening

`evals/scoper_monkeys/elicit_workshop.py` provides:

- `resolve-external`: unions fresh Elicit arms, removes original-Scoper overlap,
  and resolves full bibliographic evidence through exact DOI, exact arXiv, then
  conservative OpenAlex title matching;
- `screen-external`: applies Prior's existing `scope-exhaustive/1.1` four-way
  rubric, yielding `eligible`, `retrieval_only`, `uncertain`, and `excluded`.

The resolution ledger is being written to:

`artifacts/scoper-workshop-rq1-2026-08-19/elicit/external-resolution.jsonl`

Do not quote screening counts until
`artifacts/scoper-workshop-rq1-2026-08-19/elicit/external-screen/status.json`
exists. Missing evidence is retained as uncertain, never silently excluded.

## Paper-facing analysis plan

Use two distinct tables/analyses:

1. A controlled component comparison: one-shot query generation, iterative
   recovery, citation snowballing, and full Scoper under matched budgets.
2. A heuristic-repair analysis comparing the historical configuration with
   deeper retrieval, repaired evidence, removal of hard lexical gating, and
   broader citation traversal.

The expanded corpus is a system output. The 152-work set is only an evaluation
instrument. The full 120,894-work citation discovery pool has not been screened
and must not be described as an eligible corpus.

## Required caveats

- The reference set is Prior-derived and therefore not independent.
- Elicit is a retrieval baseline; accepted-relevance numbers require the common
  post-retrieval screen described above.
- Elicit does not expose a complete internal search trace.
- Search channels are dependent; capture-recapture is diagnostic only.
- Neither the evaluation nor Prior establishes exhaustive field coverage.
