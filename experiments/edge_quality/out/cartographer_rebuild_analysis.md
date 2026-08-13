# Legacy versus evidence-enriched Cartographer

## Mechanical validation

- 2188/2188 candidate records present; 0 duplicates.
- 0 records cite nonexistent evidence IDs.
- 1197 raw direction-schema mismatches; 1197 non-directional labels canonicalized in the derived graph.

## Contribution-edge comparison

- Shared legacy candidates: 989; newly citation-routed candidates: 1199.
- Exact relation-type agreement: 248/989 (25.1%).
- Legacy hard relations downgraded to related/none/unclear: 669/989 (67.6%).

## Paper-graph consequences

| policy | pairs | weighted edges | components | isolates | bridges | communities | modularity |
|---|---:|---:|---:|---:|---:|---:|---:|
| legacy_hard | 653 | 989 | 1 | 0 | 4 | 6 | 0.5243 |
| relabelled_legacy_all_substantive | 652 | 988 | 1 | 0 | 4 | 6 | 0.5251 |
| relabelled_legacy_hard | 230 | 320 | 30 | 22 | 38 | 38 | 0.6746 |
| enriched_union_all_substantive | 1160 | 2176 | 1 | 0 | 3 | 5 | 0.3622 |
| enriched_union_hard | 417 | 641 | 16 | 13 | 20 | 23 | 0.5416 |
| enriched_union_hard_high_confidence | 197 | 306 | 41 | 37 | 39 | 51 | 0.6555 |

Community stability uses adjusted Rand index over all 152 papers:

- `legacy_hard__vs__relabelled_legacy_all_substantive`: 1.0
- `legacy_hard__vs__relabelled_legacy_hard`: 0.304
- `relabelled_legacy_all_substantive__vs__relabelled_legacy_hard`: 0.304
- `enriched_union_all_substantive__vs__legacy_hard`: 0.4369
- `enriched_union_all_substantive__vs__relabelled_legacy_all_substantive`: 0.4369
- `enriched_union_all_substantive__vs__relabelled_legacy_hard`: 0.2734
- `enriched_union_all_substantive__vs__enriched_union_hard`: 0.3955
- `enriched_union_all_substantive__vs__enriched_union_hard_high_confidence`: 0.1613
- `enriched_union_hard__vs__legacy_hard`: 0.4239
- `enriched_union_hard__vs__relabelled_legacy_all_substantive`: 0.4239
- `enriched_union_hard__vs__relabelled_legacy_hard`: 0.5808
- `enriched_union_hard__vs__enriched_union_hard_high_confidence`: 0.3671
- `enriched_union_hard_high_confidence__vs__legacy_hard`: 0.1818
- `enriched_union_hard_high_confidence__vs__relabelled_legacy_all_substantive`: 0.1818
- `enriched_union_hard_high_confidence__vs__relabelled_legacy_hard`: 0.2935
