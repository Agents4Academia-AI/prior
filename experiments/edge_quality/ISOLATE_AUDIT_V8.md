# Citation-isolate audit after manifestation resolution

Date: 13 August 2026

This audit tested the seven v7 isolates whose cached bibliographies parsed. It
checked outgoing reference text, stable identifiers and alternate titles,
OpenAlex reference lists, Semantic Scholar reference lists, and incoming
citations from both APIs against all 152 canonical works. Fuzzy similarities
were inspected but never promoted without identity evidence.

## Confirmed correction

BioMARS was a false isolate. Its bibliography cites `arXiv:2404.18021` with
numeric marker `[2]`. That preprint is the arXiv manifestation of the canonical
OpenAlex/Nature work **CRISPR-GPT for agentic automation of gene-editing
experiments** (`openalex:W4412759774`). Preserving and indexing manifestations
recovers:

`openalex:W4417183033 -> openalex:W4412759774`

The same alias expansion also recovered previously missed incoming citations to
SciAgents and CRISPR-GPT elsewhere in the corpus. The graph grows from 853 to
863 edges and isolates fall from 11 to 10.

## Remaining six parsed isolates

No intra-corpus edge was found for:

- `arxiv:2605.21404v1` — 23 parsed references; S2 reports 3 incoming citations,
  none from this corpus.
- `openalex:W7134059863` — arXiv twin `2509.00098`; 33 parsed references;
  OpenAlex/S2 report 2/15 incoming citations, none from this corpus.
- `arxiv:2603.28376v1` — 56 parsed references; S2 reports 9 incoming citations,
  none from this corpus.
- `openalex:W4401336365` — no arXiv twin found; OpenAlex exposes 16 outgoing
  references and S2 reports 3 incoming citations, none intersecting the corpus.
  Its cached bibliography segmentation is weak (only one entry), so the API
  result is more informative than the text parser here.
- `openalex:W4394769973` — 28 parsed references and 19 OpenAlex references;
  OpenAlex/S2 report 4/8 incoming citations, none from this corpus.
- `openalex:W7161113436` — arXiv twin `2602.00185`; 8 parsed references and 17
  OpenAlex references; S2 reports 9 incoming citations and OpenAlex none, with no
  corpus intersection.

These six are provisionally genuine **intra-corpus** isolates. This does not
mean they have no citations; each has outgoing and/or incoming citations outside
this deliberately scoped 152-work collection. SCIHYPO retains a parser-quality
warning, but its independent OpenAlex graph also has no corpus overlap.

## Pipeline implication

Thorough citation resolution must run in this order:

1. resolve one canonical work and preserve all source manifestations;
2. build a work-level alias index over every arXiv ID, DOI, source ID and title;
3. parse outgoing bibliographies and resolve them against that alias index;
4. reconcile OpenAlex and centrally paced Semantic Scholar reference lists;
5. check incoming citation APIs against the same work matcher;
6. localize body markers where possible and retain bibliography/API-only tiers;
7. audit residual isolates without promoting unsupported fuzzy matches.

