# Reconciled citation substrate — frozen 152-paper corpus

Date: 12 August 2026

This pass preserves the original 680-edge `citations_core.json` and reconciles
additional channels onto the same 152 canonical paper IDs. It does not claim
absolute recall over citations in reality; it produces the most complete
auditable intra-corpus graph available from the frozen artifacts and caches.

## Inputs and fixes

- Original multi-source graph: 680 directed edges.
- Callum resolver atlas: 499 directed edges; all 152 paper identities mapped
  unambiguously to the frozen snapshot.
- Corrected full-text scan: 151/152 cached texts, instead of 57/152. The old
  scanner only recognized arXiv-named cache files and skipped OpenAlex-named
  caches. It found 501 edges, including 73 absent from the prior union.
- Refreshed reference lists: 205 edges, retrieved through Prior's centralized
  Semantic Scholar adapter (plus the existing OpenAlex path). Thirteen were new
  beyond the resolver/full-text union.

## Result

- Reconciled union: **831 directed intra-corpus citation edges**.
- Added relative to the frozen 680 graph: **151 edges**.
- No invalid endpoints, ambiguous identity mappings, self-links, or unmapped
  resolver endpoints were admitted.
- Corpus citation isolates decreased from 14 in the initial reconciled union to
  **11** after the corrected scan and API refresh. An isolate means no detected
  *intra-corpus* citation; it is not evidence that a paper has no references.

New-edge provenance relative to the 680 baseline includes:

- 35 exact arXiv-ID and exact-title full-text matches;
- 28 exact-title-only full-text matches;
- 10 exact arXiv-ID-only full-text matches;
- 13 refreshed API-only matches;
- the remainder supported by resolver/API/full-text combinations.

## Citation contexts

- Existing LaTeX citation contexts: 525 edges.
- Newly localized from exact full-text occurrences: 62 by arXiv ID and 75 by
  normalized title.
- Total with an observed passage: **662/831**.
- `context_unavailable`: 169/831. These retain citation direction and source
  provenance but must not be represented as passage-grounded.
- The sole paper without cached full text did not create a source-side context
  gap among the 831 detected edges.

## Trust and remaining limitations

- Exact IDs, exact long titles, bibliography entries, and API reference lists
  are deterministic signals, but the 831-edge union has not been human-audited.
- Fuzzy-title edges retain fuzzy provenance and should remain distinguishable.
- Publication-year inversions require date-level inspection rather than blanket
  removal: many corpus records use venue years that postdate preprint citation.
- Full-text occurrence localization establishes that a cited paper is mentioned
  near the returned passage. It does not itself classify citation intent.
- Absolute completeness is unknowable without authoritative bibliographies for
  every paper. Completeness here means every available frozen channel was run
  against one identity-normalized snapshot, with missing contexts explicit.

## Reproduction

1. `scan_fulltext_citations.py` writes a separate complete-scan artifact.
2. `backfill_citations.py` routes all Semantic Scholar traffic through
   `prior.sources.semanticscholar`; it contains no independent S2 requests or
   sleeps.
3. `reconcile_citation_substrate.py` unions channels and audits identities.
4. `localize_fulltext_citations.py` produces passage availability statuses.

The next Cartographer experiment should use `citations_reconciled.json` for
direction/provenance and `citation_contexts_reconciled.json` for passages while
holding the 152-paper corpus and candidate policy fixed across legacy and
enriched arms.

## Reusable bibliography and passage recovery (v2)

The follow-up pass treats citation acquisition and context localization as
separate, auditable stages rather than assuming any title occurrence is a body
passage.

- Full-text acquisition now preserves HTML block boundaries and extracts all PDF
  pages by default. The previous 14-page PDF cap commonly stopped before the
  bibliography.
- `refextract.reference_entries()` parses line-oriented and flattened numeric or
  author-year bibliographies while retaining their citation markers.
- `recover_bibliography_edges.py` matches entries to the corpus only by arXiv ID,
  DOI, or near-verbatim normalized title and records the raw matched entry.
- `localize_fulltext_citations.py` maps a matched bibliography marker back into
  the body and distinguishes `listed_without_body_marker` from a passage.

On the merged old/new full-text cache this yields:

- 124/152 sources with a parsed bibliography (3,214 entries);
- 250 entries matched to another corpus paper;
- 5 new high-confidence citation edges, increasing 831 to 836;
- 578/836 edges with an actual localized passage (525 LaTeX, 53 cached-body);
- 123/836 confirmed in a bibliography but without a recoverable body marker;
- 135/836 without a localizable context in the available text representation.

This corrects an optimistic earlier metric: 115 exact arXiv/title matches were
inside reference lists, not supporting body passages. They are now reported as
reference-list evidence only. These figures describe this corpus snapshot, not
a universal recall claim; the same deterministic stages are designed to run on
any Prior collection.

### Parser expansion and acquisition diagnostics (v3)

The next parser pass added parenthesized numeric markers, line-oriented
author-year entries using either parentheses or brackets, and yearless entries
when an independently reliable numeric marker supplies the segmentation signal.
It also records a per-paper `source_statuses` value so a production acquisition
loop can distinguish retryable text failures from unsupported layouts.

- Bibliographies parsed: **134/152** (6,087 entries).
- Entries matched to another corpus paper: **607**.
- Citation graph: **845 edges**, 14 more than the 831-edge reconciled baseline
  and 9 more than v2.
- Actual localized passages: **587/845** (525 LaTeX and 62 cached-body).
- Bibliography-only evidence: **123/845**.
- No localizable context in the available representation: **135/845**.

The 18 remaining acquisition/parser statuses are: 6 headings without a usable
reference block, 5 texts with no bibliography heading, 5 short/stub texts, 1
unavailable text, and 1 unsegmented reference block. These are explicit retry
inputs rather than papers silently interpreted as having no references.

### Bibliography-aware acquisition fallback (v4)

`fulltext.fetch_for_bibliography()` evaluates rather than merely accepts each
legal representation. It records bibliography status, parsed-entry count, and
text length; tries arXiv HTML and PDF, OpenAlex OA PDF, preprint/Unpaywall,
configured publisher routes, DOI landing-page PDF, and title-resolved arXiv;
and prevents a failed retry from overwriting a better existing representation.

The targeted retry of the 18 v3 failures recovered 4 bibliographies: two from
arXiv PDFs and two from title-resolved arXiv copies. The resulting corpus has:

- **138/152** parsed bibliographies (6,346 entries);
- **636** entries matched to another corpus paper;
- **849** citation edges, 18 beyond the 831-edge reconciled baseline;
- **591/849** actual localized passages (525 LaTeX and 66 cached-body);
- **143/849** bibliography-only edges and **115/849** unlocalized edges.

The 14 residual acquisition statuses are 5 `heading_absent`, 5
`heading_without_reference_block`, 3 `short_or_stub`, and 1 `text_unavailable`.
The complete per-channel attempt record is frozen in
`bibliography_acquisition_retry_v3.json`.

### Retrieval validation and expanded alternatives (v6)

Retrieval now persists `<paper-id>.quality.json` beside every cached text. The
manifest records the selected source, text length, bibliography status, parsed
reference count, explicit degradation flags, and all attempted channels.
`fetch_with_source(..., require_bibliography=True)` and the corresponding batch
option validate cached content, retry alternatives when necessary, keep the
best representation, and still return degraded text with an explicit flag when
no citation-ready version is obtainable.

The expanded fallback independently tries refreshed OpenAlex OA locations,
preprint HTML/XML/PDF, DOI HTML, Unpaywall, configured publisher APIs, metadata
PDF links, and arXiv title matches. On the 14 v4 residuals it recovered 2 more
biomedical-preprint bibliographies from OA PDFs, producing:

- **140/152** parsed bibliographies (6,417 entries);
- **639** entries matched to another corpus paper;
- **852** citation edges, 21 beyond the 831-edge reconciled baseline;
- **591/852** actual localized passages;
- **146/852** bibliography-only edges and **115/852** unlocalized edges.

The 12 remaining degraded representations are explicitly flagged: 4
`bibliography_not_present_in_retrieved_text`, 4
`bibliography_heading_without_entries`, 3 `likely_stub_or_truncated`, and 1
`full_text_unavailable`. They are retrieval failures, not claims that the papers
themselves lack bibliographies.

### Work identity versus manifestations (v7)

Cross-source deduplication now keeps one canonical work node while preserving
the source IDs, URLs, PDFs, DOIs, dates, and titles of all discovered
manifestations. Small publisher/preprint title changes can be merged only when
high token containment, shared authorship, and compatible years agree. Full-text
retrieval enumerates these retained manifestations before using title search.

SciAgents exposed the prior information loss: the OpenAlex/Wiley record was
retained while arXiv `2409.05556` was discarded, and exact title search failed
because the publisher title added “Bioinspired” and used a Unicode hyphen. The
normalized fallback now recovers that arXiv manifestation and its 46-entry
bibliography. The corpus result becomes **141/152** parsed bibliographies, **853**
citation edges, and **592/853** edges with an actual localized passage.

The follow-up isolate audit indexed retained manifestations during citation
resolution. BioMARS then resolved its `[2]` citation of arXiv `2404.18021` to the
canonical CRISPR-GPT work. Manifestation aliases recovered 10 additional edges
across the corpus: **863 total**, **597 with localized passages**, and **10
isolates**. Six of the isolates have parsed bibliographies and no corpus overlap
in outgoing references or incoming OpenAlex/S2 citations; they are provisionally
genuine intra-corpus isolates. See `ISOLATE_AUDIT_V8.md`.

### Full-corpus resolution ledger and incoming reconciliation (v12/v13)

The final resolution pass starts from all 152 canonical works, retains 89
alternate manifestations on 80 works, and indexes every alias back to its single
canonical node. A second, retrying pass found six manifestations missed by the
first pass. This is work-level identity preservation; it is not a claim that
every work necessarily has an alternate edition.

Bibliography segmentation now stops at post-reference appendices and rejects
navigation/conversion fragments as parsed bibliographies. This reduced malformed
mega-entries from 151 to 45. The deterministic terminal-state ledger contains
6,602 records: 609 `resolved_in_corpus`, 1,882 `resolved_external`, 4,037
`unresolved`, 45 `malformed`, 20 `non_bibliographic`, and 9
`retrieval_unavailable`. Fuzzy candidates are retained only as audit hints and
never promoted to edges. The 4,037 unresolved records are an explicit queue for
the slower pinned external resolver or human review, not inferred non-citations.

The rebuilt outgoing graph has **868 edges**. A checkpointed full-corpus incoming
pass then queried OpenAlex plus Semantic Scholar (all S2 calls through Prior's
central adapter), examined 9,615 returned records, found 352 exact
manifestation-aware corpus intersections, and added 16 missing pairs for **884
total edges**. Isolates fell from 10 to 8. The final context audit has **644/884
actual localized passages**, 128 bibliography-only edges, and 112 edges without
a localizable passage in the available representation. Incoming APIs establish
edge direction but do not manufacture citation passages.

The frozen outputs (`papers_core_manifestations_v13.jsonl`,
`resolution_ledger_v12.json`, `citations_reconciled_incoming_v12.json`, and
`citation_contexts_incoming_v12.json`) remain on the research branch
`codex/citation-substrate-152`. They are deliberately not duplicated into the
product branch: the scripts here reproduce them, while the checkpoint files on
the research branch preserve resumability and the full audit trail.
