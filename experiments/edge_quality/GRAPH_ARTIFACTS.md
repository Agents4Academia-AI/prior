# Cartographer graph artifacts

## Canonical graph

`out/canonical_semantic_candidates_enriched_evidence_v12.json`

- **Status:** canonical
- **Contribution pairs:** 989
- **Candidate policy:** preserve the contribution pairs selected by the legacy
  semantic Cartographer pipeline.
- **Evidence policy:** relabel those pairs using grounded contribution quotes,
  retrieved full text from both papers, and localized citation passages wherever
  one parent paper cites the other.
- **Citation policy:** citations provide evidence and direction; they do not add
  contribution pairs to the graph.

This is the graph to use for downstream analysis and the Callum citation-intent
audit.

## Deprecated experimental expansion

The historical `cartographer_rebuild_candidates.json` and
`cartographer_rebuild_normalized.jsonl` contain 2,188 candidate pairs:

- 989 legacy semantic candidates;
- 1,199 additional citation-only candidates created by selecting up to two
  contribution pairs for each resolved paper citation.

That top-2 paper-citation projection was rejected as a topology policy. Its
outputs may be retained for retrospective ablations, but they must not be called
the canonical, complete, or full graph. A generated file named
`fulltext_citation_enriched_v12_graph.json` belongs to this deprecated experiment
and is intentionally ignored.

## Terminology

“Enriched” describes the evidence used to classify a contribution pair. It does
not mean that paper citations automatically create new contribution-pair edges.
