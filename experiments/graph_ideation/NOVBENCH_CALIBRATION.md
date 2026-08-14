# NovBench novelty-recognition calibration (2026-08-14)

The contribution/novelty sentence recognizer was evaluated on all 993 released
NovBench sentence labels: 493 novelty/contribution sentences and 500 non-novelty
review sentences.

- precision: 0.8762
- recall: 0.8905
- F1: 0.8833
- accuracy: 0.8832
- confusion matrix: TP 439, FP 62, FN 54, TN 438

This supports the narrow claim that an LLM can identify sentences that state or
evaluate novelty with reasonably high recall. It does **not** test whether a paper's
novelty claim is true, whether Prior retrieved all relevant antecedents, or whether
the proposed per-section novelty score agrees with reviewers.

The run used 25 batched model calls and cost approximately $0.58.
