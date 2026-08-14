# Temporal gap-closure pilot (2026-08-14)

## Design

Primary cutoff: 2025-07-01. The prediction substrate contained only 288
contributions from 77 pre-cutoff papers and 832 early–early graph edges. Twelve
seed contributions were selected across graph communities. Five evidence-selection
arms received the identical gap-formulation prompt:

- typed one/two-hop graph traversal (`gap_aware`);
- flat semantic neighbours;
- cross-cluster semantic neighbours;
- highest-degree contributions;
- degree/community-matched random contributions.

All packets used three distinct papers. The 60 gap predictions were frozen before
retrieving five candidate contributions from the 293 post-cutoff contributions.
A blinded judge labelled each pair `closes`, `partly_addresses`, or `unrelated`.

## Results

| Arm | At least partly addresses (top 5) | Nominal closes | Seed hit rate | MRR |
|---|---:|---:|---:|---:|
| Gap-aware | 45.0% | 2 | 83.3% | 0.729 |
| Flat | 43.3% | 1 | 100% | 0.694 |
| Cross-cluster | 31.7% | 0 | 83.3% | 0.614 |
| Centrality | 61.7% | 0 | 100% | 0.819 |
| Matched random | 35.0% | 0 | 83.3% | 0.556 |

Paired bootstrap differences in partial-address yield were uncertain (95% intervals
all include zero): gap-aware minus flat +0.017 [-0.167, 0.183]; cross-cluster +0.133
[-0.100, 0.350]; centrality -0.167 [-0.367, 0.033]; matched random +0.100
[-0.133, 0.300]. Only twelve seeds were tested.

All three nominal direct closures refer to the same later contribution about
LLM-judge/expert disagreement. Qualitative audit found that each leaves material
parts of the predicted study unresolved; the judge's own explanations acknowledge
this. They should be treated as partial addresses pending independent adjudication.
The defensible current result is therefore differential partial-address yield, not
demonstrated prediction of fully closed gaps.

## Interpretation

Prompt matching removes the very large advantage observed when the gap-aware arm
alone was explicitly asked for cumulative field needs. Under this stronger control,
gap-aware is only slightly above flat retrieval and below centrality on broad
partial-address yield. Centrality may identify genuinely consequential hubs, or it
may generate generic gaps that are easy for later work to touch; qualitative/human
review is required to distinguish these explanations.

## Leakage audit

The prediction code strictly removed post-cutoff nodes and edges before graph
construction and did not expose later contribution text until predictions were
frozen. Residual retrospective leakage remains:

- none of the 77 early paper records contains the original Scoper query/discovery
  provenance, so inclusion based on later search paths cannot be excluded;
- five early records point to arXiv v2/v3 manifestations;
- seven OpenAlex records use recovered arXiv abstracts;
- 14/77 dates have only month precision (63 have day precision);
- the early edge set was labelled during the present-day reconstruction, although
  each retained edge's evidence is restricted to its two early contributions.

An online manifestation-resolution audit was attempted through the standard Scoper
resolver, but arXiv title-search retries/backoff made completion impractical. It was
stopped without producing a partial artifact. Consequently this is an early-only
replay over a retrospectively assembled corpus, not a fully prospective experiment.

## Cost

The temporal run logged 140 model calls and approximately $4.13 at Sonnet 4.6
standard token pricing. Failed/omitted structured-output retries are included.
