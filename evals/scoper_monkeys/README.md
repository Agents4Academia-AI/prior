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

## Committed bounded expansion policy

`bounded_expansion.py` runs the workshop policy end to end from an existing,
versioned Scoper snapshot. It retains existing eligible works, induces lexical
communities, opens exactly one adaptive query round, screens novel candidates
against the supplied strict scope, performs one bounded citation hop from newly
eligible works, and writes the next snapshot. It never loads evaluation targets.

```bash
export PRIOR_LLM_BACKEND=api  # or another configured backend

python evals/scoper_monkeys/bounded_expansion.py \
  --screen-dir local/atlas-v1/screened \
  --scope local/strict-scope.txt \
  --out-dir local/atlas-v2-expansion
```

Workshop defaults are eight communities, two queries per community, depth 200
per query/source, one adaptive round, and one OpenAlex citation hop. The output
directory must be empty unless `--resume` is explicit. `manifest.json` freezes
inputs and parameters; `run-ledger.jsonl` records every stage command and
terminal status; `summary.json` and `snapshot/eligible.jsonl` are the handoff.
This is an auditable bounded policy, not a claim of exhaustive coverage.

Outputs:

- the raw `--out` JSONL is a `prior.scoper-ledger/1.0` ledger with a frozen scope,
  run/event identifiers, UTC timestamps, code and parameter provenance, explicit
  probe/reformulation events, candidates, decisions, and stopping snapshots;
- `report.json`: machine-readable metrics;
- `report.md`: recall/stopping tables;
- `misses.csv`: gold misses with automatic stage diagnosis and a blank
  `manual_category` column.

Raw runs and gold data should remain local unless their licenses permit release.
Validate a versioned ledger before analysis with
`ledger.load_and_validate(path)`; the scorer does this automatically. Older
unversioned traces remain readable for comparison but are not release-grade
ledgers.

Each query is a branch. `branch_snapshot` records its unique returns, first-observed
globally new records, rediscoveries, newly included papers, eligible yield, and
cumulative corpus size. First-observed attribution prevents overlap from inflating
growth; all retrieval-result events remain available for alternative attribution.

## Visualise a ledger

Serve this directory and open the read-only Three.js viewer:

```bash
python3 -m http.server 8000 --directory evals/scoper_monkeys
```

Then visit `http://localhost:8000/viewer.html` and choose a local ledger. The
browser does not upload the file. Query branches are blue; included, excluded,
undecided, and rediscovered papers/paths have distinct colours. Clicking any node
shows the exact ledger-derived provenance used to draw it. The viewer loads a
pinned Three.js version from jsDelivr; ledger data remains local.

Legacy snapshots can be visualised without pretending they contain native
provenance:

```bash
python evals/scoper_monkeys/reconstruct_legacy.py \
  --out evals/scoper_monkeys/reconstructed-ai-scientist.jsonl
```

Open `viewer.html?ledger=reconstructed-ai-scientist.jsonl`. The generated manifest
lists every unavailable field, and branch growth uses preserved snapshot deltas—not
inferred causal attribution.

## Seed Collection adapter

The MIT-licensed `ielab/sysrev-seed-collection` provides 40 review topics, real
seed studies, included studies, and snowballing candidates. Prepare a local case
without exporting the review's original Boolean query:

```bash
python evals/scoper_monkeys/seed_collection.py \
  --dataset-root data/raw/benchmarks/sysrev-seed-collection \
  --topic 40 \
  --out-dir local/scoper-monkeys/seed-40
```

The generated `scope.smoke.txt` is intentionally labelled as a weak automatic
scope. Have a domain expert revise it before treating results as benchmark
evidence. The adapter fails if an included record is absent from the bundled
corpus. Fill known omissions with `--supplement records.jsonl`;
`--allow-missing` is only for plumbing smoke tests.
