# Scoper workshop RQ1 handoff — 2026-08-19

This is the coordination note for the AI for Meta-Science workshop paper.
It distinguishes completed results from work still running.

## Evaluation language

The 152 works are the **frozen Prior v0.2 reference set**, not an independent
expert gold standard. It is a retrospective recovery/regression benchmark and
must not be used to claim absolute field recall or superiority over Elicit.

The original Scoper comparison corpus contains 255 papers. The controlled
retrospective product comparison below defines external-only relative to the
152-work Prior v0.2 reference set, using DOI, arXiv identifier, then normalized
title. Do not conflate this with a comparison against the 255-paper export.

## Completed fresh Elicit retrieval

Artifacts live under:

`/Users/kk1918_1/projects/Otto/artifacts/scoper-workshop-rq1-2026-08-19/elicit/`

| arm | result records | unique candidates | Prior-v0.2 reference recovered | recall |
|---|---:|---:|---:|---:|
| Elicit plain | 300 | 300 | 32/152 | 21.05% |
| Elicit multi-query | 800 | 714 | 51/152 | 33.55% |

For multi-query Elicit, reference-set recall is 7/152 at rank 10 per query,
15/152 at 20, 36/152 at 50, and 51/152 at 100.

### Corrected matched-input baseline

The original Scoper user input was the full natural-language protocol recorded
in `broad-scope.txt`, not the short Elicit pilot query. Its byte-identical frozen
copy is `evals/scoper_monkeys/workshop_inputs/scoper-original-input-v1.txt`.

Elicit was rerun with that complete protocol as one request:

| arm | unique candidates | Prior-v0.2 reference recovered | recall |
|---|---:|---:|---:|
| Elicit, exact Scoper input | 500 | 51/152 | 33.55% |

The short-query Elicit and Undermind runs are pilots and must not be used as the
headline matched-input comparison. The matched Undermind deep search completed
with 157 stored results and recovered 36/152 (23.68%). Undermind exposes no
pagination beyond that completed deep-search result set and no depth/budget knob.
Elicit's tested plan ceiling is 500; requests for 750 return an explicit
`maxResults must be at most 500 for your plan tier` error.

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

Using the historical binary screen (not the later broad four-way screen), the
product-only pools relative to the 152-work reference produced:

| product | external-only records | eligible | excluded |
|---|---:|---:|---:|
| Elicit | 447 | 169 | 278 |
| Undermind | 120 | 71 | 49 |

After work-level deduplication and a 2026-06-24 retrospective cutoff, these form
192 distinct eligible pre-cutoff hidden targets. Four eligible works are
post-cutoff and 14 have unresolved cutoff status; neither group is counted in
retrospective recovery.

The already-completed deep retrieval and citation expansion recover 84/192
hidden targets (43.75%): deep retrieval finds 70 and citation expansion adds 14
unique works. This is an intermediate component result, not the final full-Scoper
number. The target titles were joined only after candidate collection and branch
outputs had been frozen.

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
