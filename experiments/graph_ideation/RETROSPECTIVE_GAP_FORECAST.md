# Retrospective gap forecasting (2025-01-01 cutoff)

## Question

Can a literature graph built only from earlier work independently identify
research needs that later papers materially address?

## Design

The cutoff was 2025-01-01. The prediction substrate contained 153 contributions
published before the cutoff; 428 contributions were held out as later work.
Twenty graph-eligible seed contributions were sampled across communities. Five
prompt-matched arms generated one gap per seed from three distinct early papers:

- typed one/two-hop graph traversal (`gap_aware`);
- flat semantic neighbours;
- cross-cluster semantic neighbours;
- highest-degree contributions;
- degree/community-matched random contributions.

The 100 forecasts were frozen before later-paper retrieval. Each forecast was
matched to five later contributions and judged blind as `closes`,
`partly_addresses`, or `unrelated`. Later manifestations of the seed work were
excluded using DOI, version-normalized arXiv identity, or normalized exact title.

## Results

| Arm | Later candidates at least partly addressing forecast | Nominal closes | Seed hit rate | MRR |
|---|---:|---:|---:|---:|
| Gap-aware | 50% | 1 | 100% | 0.817 |
| Flat | 43% | 0 | 90% | 0.650 |
| Cross-cluster | 43% | 2 | 75% | 0.596 |
| Centrality | 59% | 2 | 100% | 0.683 |
| Matched random | 51% | 0 | 95% | 0.775 |

On per-seed partial-address yield, gap-aware minus flat was +0.07 (paired
bootstrap 95% interval -0.04 to +0.19); minus cross-cluster +0.07 (-0.08 to
+0.22); minus centrality -0.09 (-0.21 to +0.03); and minus matched random -0.01
(-0.12 to +0.10). The sample does not establish a statistically reliable arm
advantage.

## Manual audit of nominal closures

None of the five nominal closures survives strict inspection as a complete
closure. The gap-aware closure was a citation-trustworthiness evaluation
framework (FACT) that supplies relevant measurement machinery but does not run
the requested evaluation of the AI Scientist retrieval/synthesis stage. The two
centrality closures validate an LLM judge in MLR-Bench but do not perform the
specified same-manuscript, same-system calibration. The two cross-cluster
closures provide related LLM-versus-expert evidence but do not validate the
named reward model and pipeline under the proposed controls. All five should be
relabeled `partly_addresses`.

## What was independently recovered

The useful result is not prediction of exact later papers. Before seeing the
held-out corpus, graph-conditioned packets repeatedly exposed research needs
that later papers worked on in narrower forms:

- transfer of benchmark rankings across literature QA and broader scientific
  tasks; later, STELLA reported one system across multiple biomedical benchmarks;
- calibration of automated peer review against expert review; later, MLR-Judge,
  ScholarPeer, and related review benchmarks supplied pieces of that evidence;
- robustness and blind-spot testing for automated reviewers; later perturbation
  and multimodal peer-review benchmarks operationalized parts of this need;
- citation accuracy and factual grounding of research agents; later
  DeepResearch Bench introduced explicit citation-trustworthiness measures.

This supports the restrained claim that Prior can reconstruct **field-relevant
questions that later research partially addresses**. It does not yet show that
the graph arm uniquely forecasts them, that the questions were globally novel at
the cutoff, or that later work fully resolved them.

## Interpretation and next validation step

Graph traversal improved yield and rank over flat retrieval in this run, but
uncertainty is wide and centrality generated broader gaps that were easier for
later papers to touch. The next test should distinguish specificity from generic
addressability: humans should rate whether each forecast was concrete and
falsifiable *before* seeing the later work, then adjudicate the best later match.
A high-recall external search should also challenge the claim that each gap was
open at the cutoff; the current test searches only the held-out Prior corpus.
