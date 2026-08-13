# External citation benchmarks

These adapters reuse existing human labels before commissioning Prior-specific
annotation. External data is downloaded to a user-supplied directory and is not
vendored in this repository.

## What each benchmark validates

| Pipeline stage | Dataset | Human supervision reused | Remaining Prior-specific audit |
|---|---|---|---|
| citation-context intent | SciCite | 11,020 contexts labelled `background`, `method`, or `result` | crosswalk to `background`, `uses_extends`, `compares_contrasts`, `mixed`, `unclear` |
| evidence-span localization | CORWA | 7,793 character-level citation spans, including dominant/reference type | bibliography-to-work resolution and non-related-work sections |
| bibliography resolution | none suitable end-to-end | identifier metadata where available | corpus-specific resolved/unresolved sample |
| citation-to-contribution alignment | none | — | stratified human audit |
| semantic relation existence/type/direction | none equivalent | — | stratified human audit |

SciCite's native labels and Prior's labels are not equivalent. Report native
three-class performance first. Any crosswalk result is secondary and must retain
the disagreement set rather than treating the mapping as ground truth.

CORWA evaluates the current fixed-window context extractor as a localization
baseline. It does not validate Prior's bibliography parsing because cited-paper
identities are already annotated.

## Reproducible acquisition

```bash
python experiments/citation_benchmarks/fetch.py --output /private/tmp/prior-citation-benchmarks
python experiments/citation_benchmarks/evaluate_corwa.py \
  --data /private/tmp/prior-citation-benchmarks/CORWA/data/CORWA_test.jsonl
```

Sources:

- SciCite: Cohan et al. (NAACL 2019), Apache-2.0 code repository.
- CORWA: Li et al. (NAACL 2022), repository commit pinned by `fetch.py`.

CORWA's repository does not declare a machine-readable license. Do not redistribute
its files in Prior; cite the paper and obtain clarification before redistributing
derived examples.

