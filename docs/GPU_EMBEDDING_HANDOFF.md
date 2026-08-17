# GPU handoff: Scoper semantic geometry

## Objective

Choose an embedding geometry for inducing Prior's evolving literature-search map.
The model is a scientific variable: select it on downstream discovery behaviour,
not cluster appearance or convenience.

## Code baseline

- branch: `codex/scoper-exhaustiveness-2026-08-15`
- minimum relevant commit: `cb150c6`
- decisions: `docs/SCOPER_EXHAUSTIVENESS_DECISIONS.md`, especially decision 14
- pipeline controller: `evals/scoper_monkeys/scoper_pipeline.py`
- bundle producer: `evals/scoper_monkeys/adaptive_expansion.py`

Do not edit or benchmark Cartographer's graph-retrieval embedding setting as a
substitute for this experiment. This experiment concerns Scoper discovery and
query-map induction.

## Inputs to transfer from the source machine

Artifact root:

`/Users/kk1918_1/projects/Otto/artifacts/scoper-adaptive-expansion-2026-08-17`

Required initial files:

- `semantic-corpus.jsonl` (about 6.7 MB): 2,050 useful works after evidence repair;
- `embedding-experiment.json`: frozen leakage-safe protocol;
- `stage-prepare_embedding.json`: hashes for verifying transfer;
- `screened-v2/status.json`: role counts and snapshot identity.

Later large-scale prioritisation input:

- `citation-new-candidates.jsonl` (about 328 MB at the first partial citation
  snapshot). Citation traversal is still progressing, so transfer this only after
  its desired snapshot is frozen and record the snapshot receipt/hash.

## Leakage boundary

Do not load `gold-current-core.jsonl`, recovery reports, or titles of the 152
hidden targets during model selection, clustering, query generation, or branch
revision. Hidden targets are joined only after the model and induced branches
have been frozen.

## Required comparison

At minimum compare:

1. a scientific-document embedding model;
2. a strong current general retrieval embedding model;
3. a lexical BM25 baseline.

Record exact model repository, immutable revision, trust-remote-code setting,
tokenizer revision, input prefix/instruction, maximum length, truncation,
pooling, normalization, precision, batch size, hardware, library versions, seed,
and elapsed time. Cache vectors under a configuration fingerprint.

Do not assume one embedding is appropriate for both document-community mapping
and query-to-document retrieval. Test separate document and query encodings where
the model specifies them.

## Evaluation before hidden-target join

- blinded nearest-neighbour coherence audit;
- neighbourhood and cluster stability across seeds/resolutions;
- preservation of small or interdisciplinary communities;
- role mixing/separation for eligible, retrieval-only, and uncertain works;
- robustness to title-only versus title+abstract evidence;
- duplicate/alternate-manifestation proximity;
- sensitivity of candidate priorities to model choice.

Use dimensionality reduction only for inspection. Do not select a model because
UMAP/t-SNE looks clean.

## Downstream evaluation after freezing

Freeze the selected configuration, community map, terminology proposals, and
new query branches before evaluating:

- unique eligible yield per induced branch;
- hidden-target recovery;
- boundary-disagreement rate under strict synthesis scope;
- stopping-curve sensitivity;
- minority-community coverage.

## Expected outputs

- `embedding-runs/<fingerprint>/manifest.json`
- memory-mappable embeddings keyed by canonical `work_key`
- nearest-neighbour audit sample with deterministic sampling seed
- stability metrics and community assignments
- proposed terminology/community map with record-level evidence
- model-comparison report and a clearly justified frozen selection
- query branches in a machine-readable file, each linked to motivating records

The output must remain resumable and deterministic outside the explicitly
agentic interpretation/query-naming step.
