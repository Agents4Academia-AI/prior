# Citation intent versus the enriched contribution graph

Date: 14 August 2026

This note compares citation intent with the corrected full-text + citation
relabeling of the 989 contribution pairs retained by the legacy graph. Citation
intent is defined at the citation-site/paper-edge level; graph relations are
defined between selected contribution pairs, so compatibility is an audit signal,
not exact edge-level ground truth.

## Label provenance

- The intent classifier labelled 809 citation sites on 525 paper-citation edges.
- Callum manually labelled a blinded gold set of 122 sites on 109 paper edges.
- The classifier achieved 76/80 (95.0%) accuracy on the uniform random gold block;
  reweighted accuracy was 94.6% and macro-F1 was 0.892.
- The earlier 225-pair graph audit used automated edge-level intent rollups, not
  225 manually checked labels.

## Automated-intent audit (225 matched contribution pairs)

1. `uses_extends` -> `builds_on`
   - 33/37 pairs became `builds_on` (89.2%).
   - Three remained `related`; one became `supports`.
   - The exceptions concern narrow sub-method reuse or contribution endpoints that
     do not represent the cited dependency.
2. Direction
   - All 33 `uses_extends` -> `builds_on` edges point from the citing paper's
     contribution to the cited paper's contribution (33/33).
3. Background overinterpretation
   - 80/140 background-labelled citations became `related`.
   - 60/140 received a specific relation.
   - In 47/60, the classifier cited the background passage as evidence; these are
     the priority audit queue, not automatically erroneous edges.
4. Comparison promoted to contradiction
   - 3/48 `compares_contrasts` pairs became `contradicts`.
   - All three compare performance across differing domains, tasks, or agent
     configurations and may overstate incompatibility.

## Callum-gold-only audit

The 122 human-labelled sites cover 109 paper edges. Thirty-two of those paper
edges match the fixed legacy-pair audit sample (10 `uses_extends`, 12 `background`,
10 `compares_contrasts`). Seven gold paper edges contain mixed site intents; the
same strongest-site rollup was used for comparability.

1. `uses_extends` -> `builds_on`
   - 8/10 pairs became `builds_on` (80%).
   - Two became `supports`; both graph explanations say the selected contributions
     corroborate a finding while the citation uses only a narrower sub-method.
2. Direction
   - All eight `builds_on` edges follow citing -> cited direction (8/8).
3. Background overinterpretation
   - 7/12 became `related`.
   - 5/12 received a specific relation: two `builds_on`, two `contradicts`, and one
     `supports`.
   - All five cite the background passage as evidence and should be audited.
4. Comparison promoted to contradiction
   - 0/10 became `contradicts`.

## Interpretation

The human-only subset supports the same narrow conclusions as the larger
automated-intent audit: `uses_extends` is a strong lineage/direction check, and
background-labelled passages identify a useful strong-edge audit queue. It does
not reproduce the automated subset's three possible false contradictions, so that
finding should be framed as an automated-label audit lead rather than a
human-confirmed result.
## Incoming v12 incremental update (2026-08-14)

- Compared the expanded 884-edge citation substrate with the previous complete
  525-edge intent artifact.
- Found 119 newly localized citation edges containing 294 citation sites.
- Classified all 294 sites with Callum's validated three-way rubric:
  248 `background`, 21 `uses_extends`, 25 `compares_contrasts`.
- Preserved site-level labels only. No edge rollup was generated or supplied to
  Cartographer.
- The 119 newly evidenced paper citations intersect 34 frozen legacy
  contribution pairs across 27 citation directions.
- Relabeled only those 34 pairs using raw citation passages plus the established
  contribution quote and retrieved-full-text packet. All 34 had two full texts
  and citation passages; 32/34 decisions cited a citation passage explicitly;
  no prediction cited a nonexistent evidence ID.
- Overlaying the 34 predictions leaves the graph at exactly 989 pairs. Thirteen
  relation labels changed. Counts moved from 644 `related`, 104 `builds_on`,
  203 `supports`, 10 `refines`, 27 `contradicts`, 1 `none` to 639 `related`,
  109 `builds_on`, 203 `supports`, 10 `refines`, 27 `contradicts`, 1 `none`.
- Full substantive topology is unchanged. Excluding `related`, the typed-edge
  subgraph grows from 344 to 349 edges.
- Audit caveat: some newly recovered windows remain bibliography-like rather
  than semantically useful body passages. Localization success should therefore
  remain distinct from evidence strength in future substrate QA.
