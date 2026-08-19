# Frozen workshop inputs

Frozen 2026-08-19 for the AI for Meta-Science workshop RQ1 evaluation.

- `scope-v1.txt`: operational inclusion/exclusion boundary.
- `frozen-queries-v1.txt`: ten initial query formulations generated before this
  evaluation and already used in the July Elicit pilot. Reusing them prevents
  post-hoc tuning to the 152 recovery targets.
- `elicit-plain-query.txt`: single-query commercial-baseline arm.

The recovery target is
`artifacts/scoper-core-policy-replay-2026-08-15/gold-current-core.jsonl`
(SHA-256 `8adc8ff1e31422cb142d444137b08fb524cdc48d44e81b4a0edec968fd472019`).
It contains the 152 works in Prior core v0.2, generated 2026-06-24. It is a
retrospective expert-curated seed/recovery set, not an independent or complete
gold standard. Some records entered the historical construction through private
bibliography/grant anchors, and four have shown strict-boundary disagreements.
No target titles or identifiers may be passed to query generation or retrieval.
