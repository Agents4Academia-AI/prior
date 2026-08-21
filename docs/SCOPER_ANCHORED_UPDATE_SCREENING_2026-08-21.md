# Scoper anchored-update screening handoff (2026-08-21)

## Claim boundary

This is the explicitly seed-assisted living-update arm. It expands from the 152 papers already in the June Prior graph through one bounded OpenAlex/Semantic Scholar citation-and-recommendation hop. It is not a natural-language/no-seed run, it does not establish exhaustive coverage, and its priority cohort is not a probability sample.

The current graph was not modified.

## Corrected retrieval substrate

The immutable retrieval ledgers were reconciled at work/manifestation level after removing invalid identifiers such as `s2:None` from identity matching.

- 13,980 raw retrieval-result occurrences.
- 7,177 resolved work groups.
- 7,062 works novel relative to the 152 seeds.
- 6,991 identity-clean candidates eligible for downstream screening.
- 71 identity-conflict groups quarantined.
- 819 unresolved identity occurrences retained outside the work-level union.
- 24 of 37 external recovery targets joined after the candidate snapshot was frozen (64.9%; diagnostic only).

The authoritative local artifacts are under:

`/Users/kk1918_1/projects/Otto/artifacts/scoper-anchored-expansion-2026-08-21-v2/`

## Frozen 600-record screening cohort

The cohort contains 300 candidates first published after 2026-06-24, 252 on or before that reporting boundary, and 48 with unresolved dates. Within each date stratum, candidates are ordered by:

1. descending number of independent retrieval channels;
2. descending number of distinct seed-paper paths;
3. descending retrieval occurrences;
4. deterministic title, evidence-hash, and source-ID ties.

The screening order interleaves six 100-record waves, each with 50 after-boundary, 42 historical, and 8 date-uncertain records.

Screening used `scope-v1.txt`, `scope-exhaustive/1.4`, `claude-sonnet-4-6` through the API, and complete stored titles and abstracts. Earlier broad-scope labels were not imported. Evidence spans are exact excerpts selected by index from the model input. Transport/parser failures are not cached as scientific uncertainty.

## Final screening results

| Wave | Eligible | Retrieval only | Uncertain | Excluded | Missing evidence |
|---:|---:|---:|---:|---:|---:|
| 1 | 60 | 21 | 4 | 15 | 1 |
| 2 | 52 | 13 | 2 | 33 | 1 |
| 3 | 39 | 15 | 9 | 37 | 3 |
| 4 | 30 | 11 | 9 | 50 | 1 |
| 5 | 52 | 13 | 4 | 31 | 2 |
| 6 | 24 | 10 | 8 | 58 | 1 |
| **Total** | **257** | **83** | **36** | **224** | **9** |

There are 600 terminal decisions: 591 model-screened and 9 quarantined as uncertain because their stored abstracts were non-substantive. There are no pending or invalid decisions.

The first 300 yielded 151 eligible papers (50.3%); the last 300 yielded 106 (35.3%). The frozen cohort cap was reached before the proposed operational saturation rule: wave 6 still yielded 24 eligible and 10 retrieval-only papers. Describe this as a budget cap, not a stopping/completeness result.

Wave 5's rebound is real and is driven mainly by S2-forward-only candidates (28/32 eligible). Distinct seed-path count was more predictive than channel count in this cohort; this is useful diagnostic evidence for a future search-policy paper, not a general ranking claim.

## Boundary audit

All 340 retained (`eligible` plus `retrieval_only`) records were checked against full abstracts. No actual review/survey was marked eligible, and no evidence hash, verbatim-span, or missing-abstract defect was found. Seven eligible records remain in an explicit re-adjudication queue because they may be vision/position, non-scientific analog, or non-primary items:

- `arxiv:2608.18312`
- `openalex:W4406458040`
- `openalex:W4399803256`
- `arxiv:2607.12252`
- `openalex:W4410221857`
- `openalex:W7160957265`
- `s2:d5ec90ec0e8aa23108c559785b3977614c2c4f72`

Do not silently relabel them; preserve an adjudication trace.

## Usage and validation

- 118 Claude API responses, including correction retries.
- 424,514 input tokens and 109,048 output tokens.
- Full test suite: 192 passed, 6 skipped.

Exact results and caveats: `screening-v5/README.md` and `screening-v5/priority-summary.json` in the local artifact tree above.
