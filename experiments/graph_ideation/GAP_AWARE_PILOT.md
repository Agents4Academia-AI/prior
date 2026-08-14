# Gap-aware ideation pilot (2026-08-14)

## Question

Does explicit traversal of Prior's typed contribution graph yield more useful,
cumulative research ideas than (a) a closed-box LLM, (b) flat retrieval, or (c) a
cross-community semantic heuristic?

The experiment used 20 fixed seed contributions. Each arm generated three ideas per
seed (60 per arm, 240 total). The gap-aware arm traversed one/two-hop neighborhoods,
selected a three-contribution evidence packet, classified a missing-evidence motif,
and generated studies intended to resolve it.

## Mechanical checks

- 20/20 gap packets and 60/60 ideas were structurally complete.
- Every gap-aware idea cited all S1/S2/S3 packet contributions.
- 16/20 packets contained at least one hard typed relation; 21 hard pairs total.
- Gap selection was imbalanced: 14 benchmark reconciliation, 3 missing feedback
  loop, and 3 contradiction resolution packets.
- 17/20 packets used three distinct papers. Three used two distinct contributions
  from the same paper; these were retained and flagged rather than removed after
  seeing results. The next sampler enforces distinct papers by default.
- A provider/tool-output failure initially created 18 empty idea payloads. The raw
  checkpoint is preserved. Local payload validation and a larger output-token
  ceiling repaired the run. Local enum/range validation was subsequently added to
  all judges after one invalid enum value passed through the provider tool schema.

## Results

### Blinded idea-quality judge (means, 1–5)

| Arm | Grounding | Coherence | Feasibility | Corpus nonredundancy |
|---|---:|---:|---:|---:|
| Gap-aware | 4.45 | 4.62 | 3.62 | 4.28 |
| Flat | 4.13 | 4.08 | 3.50 | 3.60 |
| Cross-community | 4.03 | 3.83 | 3.20 | 3.63 |
| Closed-box | 3.20 | 3.88 | 3.43 | 3.35 |

### Frozen-corpus antecedent audit (60 ideas per arm)

| Arm | Not found | Partly covered | Fully covered |
|---|---:|---:|---:|
| Gap-aware | 11 | 49 | 0 |
| Flat | 6 | 49 | 5 |
| Cross-community | 7 | 51 | 2 |
| Closed-box | 18 | 42 | 0 |

`not_found` is not itself a success criterion: closed-box produces more such ideas
while being substantially less grounded.

### Blinded cumulative-value judge (means, 1–5)

| Arm | Uncertainty | Validation | Connective | Downstream | Actionability | Flashiness | Field value |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gap-aware | 4.17 | 4.37 | 4.32 | 4.07 | 3.97 | 2.18 | 4.37 |
| Flat | 3.10 | 3.20 | 3.45 | 3.27 | 3.53 | 2.38 | 3.02 |
| Cross-community | 3.18 | 3.15 | 3.42 | 3.28 | 3.40 | 2.60 | 3.05 |
| Closed-box | 3.28 | 3.13 | 2.47 | 3.43 | 3.55 | 2.80 | 2.97 |

The gap-aware arm was preferred for 17/20 seeds. Its judge marked 57/60 ideas as
high-field-value, actionable, and not fully covered, and 59/60 as useful work with
an incentive mismatch.

### Portfolio structure (local TF–IDF/SVD embeddings)

Gap-aware ideas were least similar to an existing corpus contribution (mean nearest
similarity 0.497) but had lower portfolio dispersion (0.765) than closed-box (0.808),
flat (0.839), and cross-community (0.827). Within each packet its three ideas were
also the least diverse. The benchmark-reconciliation motif dominance is the most
likely explanation and motivates motif-balanced sampling.

## External construct calibration

The same intrinsic field-value rubric was applied to 98 independently human-rated
AI-Researcher proposals (49 Human, 49 AI). Spearman correlations were modest:

- actionability vs expert feasibility: 0.293;
- field value vs expert overall: 0.289;
- field value vs expert effectiveness: 0.161;
- flashiness vs expert excitement: 0.136;
- flashiness vs expert novelty: 0.120.

For the 43 subsequently executed projects, proposal-stage field value correlated
0.183 with post-execution soundness, 0.158 with effectiveness, and 0.036 with
overall score. The original expert proposal overall score correlated -0.065 with
post-execution overall score. Proposal-stage judgement—human or LLM—therefore does
not substitute for execution.

## Interpretation and limits

The result supports a narrow claim: explicit, auditable graph-gap traversal changes
idea selection toward grounded, non-covered, cumulative studies more effectively
than the tested retrieval baselines. It does not show that the ideas are globally
novel, will execute successfully, or have real-world value.

The unusually large field-value advantage may partly reflect rubric alignment: the
gap-aware generator and judge share the language of validation, reconciliation, and
cumulative value, even though arm labels were hidden. Required next checks are
human blinded review, motif-balanced sampling, prompt/style controls, distinct-work
sampling, and a leakage-audited temporal future-gap-closure experiment.
