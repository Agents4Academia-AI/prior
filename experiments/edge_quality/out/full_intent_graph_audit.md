# Full citation-intent audit of the enriched v12 graph

This joins all 1,103 available site-level intent labels to the final 989-pair
contribution graph without an edge-level intent rollup. The analysis covers
271 citation sites and
259 contribution pairs, producing
474 site-pair observations.

## Four checks

1. `uses_extends` -> `builds_on`
   - 59/70
     site-pair observations are `builds_on`, spanning
     36/43
     unique contribution pairs.
2. Direction
   - 59/59
     `uses_extends` -> `builds_on` observations follow citing -> cited direction;
     0 unique pairs mismatch.
3. Background overinterpretation
   - 170/335
     background observations map to a hard relation, spanning
     107 unique pairs.
   - 93 observations across
     77 unique pairs explicitly
     use that exact background passage as graph evidence. These are the priority audit queue.
4. Comparison promoted to contradiction
   - 4/69
     comparison observations became `contradicts`, spanning
     3 unique pairs.

## Suggested review order for Callum

### Tier 1: comparison -> contradiction (3 pairs)

- `arxiv:2504.01848v3::k03|arxiv:2606.11447::k01` -> `contradicts`
- `arxiv:2507.18901v1::k01|arxiv:2606.11447::k01` -> `contradicts`
- `arxiv:2606.06473::k04|openalex:W4415108068::k00` -> `contradicts`

### Tier 2: exact background evidence -> contradiction/refinement (6 pair-reasons)

- `arxiv:2504.09702v3::k02|openalex:W4403586302::k03` -> `contradicts`
- `arxiv:2507.18901v1::k01|arxiv:2606.11447::k01` -> `contradicts`
- `openalex:W4400734098::k01|openalex:W4405035007::k03` -> `contradicts`
- `arxiv:2504.09702v3::k02|openalex:W4402952811::k03` -> `refines`
- `arxiv:2504.09702v3::k02|openalex:W4403586302::k01` -> `refines`
- `arxiv:2510.27598::k01|arxiv:2602.15112v2::k00` -> `refines`

### Tier 3: `uses_extends` not represented as `builds_on` (7 pair-reasons)

- `arxiv:2504.21776::k03|arxiv:2511.19399v3::k04` -> `supports`
- `arxiv:2506.11763::k03|arxiv:2603.20884v3::k02` -> `supports`
- `openalex:W4404783497::k02|openalex:W4405035007::k03` -> `supports`
- `arxiv:2504.01848v3::k00|arxiv:2505.24785v2::k00` -> `related`
- `arxiv:2505.18705v1::k00|openalex:W7119558012::k02` -> `related`
- `arxiv:2506.11763::k01|arxiv:2603.20884v3::k02` -> `related`
- `arxiv:2511.02824v2::k00|openalex:W4414827381::k00` -> `related`

The pair-level JSON queue contains passages, confidence, intent justification,
graph rationale, direction, and exact contribution IDs. The remaining background
queue (mostly `builds_on` and `supports`) is lower priority and can be sampled.

## Interpretation caveat

Intent is site-level and graph relations are contribution-pair-level. Multiple
citation sites—and multiple intents—can map to the same contribution pair. Queue
membership is an audit pointer, not a claim that the graph edge is wrong.
