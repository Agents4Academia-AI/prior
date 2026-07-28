# Scoper monkey experiments

Small, falsifiable checks for the Scoper before a full benchmark:

1. recover known included studies;
2. attribute each recovery to one-shot, multi-query, adaptive, or citation search;
3. classify misses by pipeline stage;
4. compare stopping signals with retrospective gold recall.

The collector uses real search sources and the configured Prior LLM backend. The
scorer is offline and key-free.

## Input

The topic file is a plain-text scope with explicit IN/OUT criteria. Gold may be:

- BibTeX;
- JSONL with `title` and optional `doi`, `arxiv`, `year`, `id`;
- CSV with the same columns.

Never pass the original review title, DOI, authors, query, or included bibliography
to the Scoper.

## Run

```bash
export PRIOR_LLM_BACKEND=claude-cli

python evals/scoper_monkeys/run.py \
  --case nbs \
  --topic-file local/nbs_scope.txt \
  --gold local/nbs_included.bib \
  --cutoff-year 2018 \
  --out local/scoper-monkeys/nbs.jsonl \
  --recover-rounds 2 \
  --hops 2

python evals/scoper_monkeys/score.py \
  --run local/scoper-monkeys/nbs.jsonl \
  --gold local/nbs_included.bib \
  --out-dir local/scoper-monkeys/nbs-report
```

Use `--queries-file` to freeze generated queries across ablations. Use
`--no-prefilter`, `--recover-rounds 0`, or `--hops 0` for ablations.

Outputs:

- `report.json`: machine-readable metrics;
- `report.md`: recall/stopping tables;
- `misses.csv`: gold misses with automatic stage diagnosis and a blank
  `manual_category` column.

Raw runs and gold data should remain local unless their licenses permit release.

