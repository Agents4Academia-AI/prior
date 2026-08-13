# Citation-map regeneration after bibliography-boundary repair

The arXiv source cache was reacquired from scratch on 2026-08-13 after merging
the bounded `.bbl`/`.bib` parser from #56. One initially timed-out source was
retried successfully. Coverage was 102 source bundles, 97 with a `.bbl` or
`.bib`, and 647 raw intra-corpus bibliography links.

`extract_citation_contexts.py` then produced **476** one-to-one citation-context
records. Compared with the previous 525-record artifact:

- 445 `(citing_id, cited_id, cite_key)` mappings are unchanged;
- 80 old mappings are absent under bounded, ambiguity-safe parsing;
- 31 mappings are newly recovered from the refreshed source set;
- 36 of the 54 formerly blob-flagged mappings are removed;
- the remaining 18 formerly flagged mappings now contain bounded single entries;
- no regenerated entry contains multiple BibTeX `@...` records or multiple
  `title=` fields.

Seven bounded entries exceed 2,000 characters (maximum 3,462), due to long
author/consortium lists. None contains a second entry marker, bibliography
terminator, or multiple title fields, so length alone is not treated as proof of
fusion.

The motivating `zhu2025deepreview` case now maps to `arxiv:2503.08569`
(DeepReview), with bounded entry bodies of 201–216 characters. It no longer maps
to PaperQA2.

Artifacts:

- `out/citation_map.json` — 476 auditable join records;
- `out/citation_contexts.json` — the corresponding context lookup;
- `out/citations_bbl.json` — 647 raw bibliography links and acquisition counts.

The source archives themselves remain ignored and are not redistributed.
