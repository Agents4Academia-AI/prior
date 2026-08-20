# Historical Scoper policy reconstruction

## What the released corpus was

The 152-paper Prior v0.2 graph was not the output of one zero-shot query run.
The recoverable June 2026 process was:

1. generate queries from a natural-language topic and combine them with fixed
   seed queries;
2. search OpenAlex, arXiv, and Semantic Scholar at shallow per-query depth;
3. screen candidates with a broad relevance prompt and cache decisions;
4. resolve every `*.bib` file in `data_hackathon/` as candidate anchors, screen
   those anchors, and fold accepted works into the corpus;
5. traverse backward and forward citations from the accumulated corpus;
6. run later bounded expansions from high-yield and gold-anchor seeds;
7. re-screen 1,128 accumulated candidates with a strict core scope, retaining
   255;
8. apply the primary-research filter and remove three residual non-primary
   works, yielding the released 152.

The released graph predates the query-recovery and bridge-seeding fixes committed
later on 24 June. Those improvements therefore describe the evolving software,
not the exact policy that generated v0.2.

## Recovered anchor inputs

Five bibliography files predate the released snapshot: `AI+Science.bib`,
`gold.bib`, `landscape_refs.bib`, `paperena_refs.bib`, and
`paperena_repo.bib`. Together they contain 133 entries and 122 unique candidate
anchors. Offline reconstruction resolves 106 against the preserved 1,128-paper
pool. Sixty-five anchor entries occur in the strict 255 and 58 entries occur in
the released 152. After work-level deduplication, those 58 entries represent 55
distinct released works; the remaining 97 released works are non-anchor targets.

The frozen reconstruction bundle contains exact bibliography copies, hashes,
entry-level provenance, and resolved paper records. Title-resolved records are
marked as approximations because the historical run queried live OpenAlex.

## Reconstructed executable policy

`bounded_expansion.py --anchor-papers ...` turns the recoverable behavior into a
staged policy:

```
natural-language scope + supplied papers
  -> autonomous probe search
  -> common strict screen
  -> combined evidence map
  -> one frozen adaptive query round
  -> common strict screen
  -> bounded backward/forward citation expansion from all accepted works
  -> common strict screen
  -> deduplicated snapshot + discovery ledger
```

This is a best-evidence reconstruction, not byte-for-byte replay. Semantic
Scholar currently rejects both anonymous and credentialed search, live indexes
have changed, the original generated query strings were not logged, and some
historical runs were launched interactively. These differences must remain in
the paper limitations.

## Workshop ablations

The main evaluation should use the anchored setting and hold scope, screen,
sources, and budgets fixed:

1. accepted anchors only;
2. one-shot autonomous search only;
3. anchors plus one-shot search;
4. add adaptive query recovery;
5. add citation expansion;
6. full traced policy.

Report recovery of the 97 released works that are not in the reconstructed
anchor set separately from recovery of all 152. A final work may have multiple
discovery routes; do not force first-observed attribution when reporting source
overlap.
