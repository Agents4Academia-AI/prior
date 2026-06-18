# Prior

> An open-source agentic system that builds a **multi-layer knowledge graph**
> of **contributions** (the literature level) and **claims** (the paper level)
> from primary sources, with calibrated confidence and visual navigation.

**Team 6** (merged with Team 4): Klara · Harit

**Hackathon:** [Agents4Academia](https://agents4academia.github.io), 14–26 Jun 2026

Most "research agents" answer literature questions by Googling and summarising
snippets — a black box you can't audit. Prior instead builds a transparent graph
of *claims* and *contributions* extracted from primary sources (OpenAlex + arXiv),
each carrying its provenance and citation links, and reasons over that graph.
The built atlas is a clean **hand-off API**: a structured, grounded corpus that
verification and baseline teams can build on directly.

## Use cases

Prior is designed to support three use cases over the same underlying graph:

- **(a) Assess the state of the art** on a problem — given a question, surface
  supporting evidence, contradicting evidence, and open questions, all cited.
  
- **(b) Find novel ideas and gaps** in the literature using agents — what
  hasn't been done yet? What's under-supported? 
- **(c) Identify contradictions and inconsistencies** in the literature and
  their downstream impact on follow-up works. 


## Architecture — two graph layers, three agents

Prior maintains two complementary graph layers over the same source material:

```
LOCAL GRAPH (per paper)                  GLOBAL GRAPH (across the literature)
┌──────────────────────────┐             ┌─────────────────────────────────────┐
│  Paper P                 │             │  Canonical claims                   │
│   ├ claims C1, C2, …     │  ─────▶     │   ├ aggregated confidence           │
│   ├ typed edges:         │  canon-     │   ├ contradicts                     │
│   │   extends            │  icalize    │   ├ supersedes (chronological)      │
│   │   refines            │             │   └ equivalent_to (cross-field)     │
│   │   stated_in (C→P)    │             │                                     │
│   │   cites    (P→P)     │             │  Citation graph (papers)            │
│   └ contributes_to       │             │                                     │
│                          │             │  Plus aggregated evidence per       │
│  Captures what one paper │             │  canonical claim:                   │
│  says/argues internally  │             │   ├ contributing_papers             │
└──────────────────────────┘             │   └ contradicting_papers            │
                                         └─────────────────────────────────────┘
        │                                                  │
        └────────────────────────┬─────────────────────────┘
                                 ▼
                            Navigator
                            ├ forward:  state of the field on a question
                            ├ backward: trace concept to its origin
                            └ render:   web view · structured corpus · IP-X report
```

Three agents, working on these two layers:

- **Reader** — paper → local subgraph (claims + edges + provenance).
- **Cartographer** — local subgraphs → canonical global graph (clustering
  equivalent claims, detecting contradictions, computing IPCC confidence).
- **Navigator** — query + global graph → grounded answer; also renders the
  visual navigation view.

> **Auditor agent** (verification of claim-extraction fidelity and citation
> honesty — real / relevant / fair) - work from **team 2** slots in naturally here.


## Acknowledgements

Built during [Agents4Academia](https://github.com/Agents4Academia-AI),
14–26 June 2026. Released under the MIT License.

**Adjacent and prior work:**

- **ORKG** (Open Research Knowledge Graph, TIB Hannover) — the established
  academic version of structured contribution graphs; primarily human-curated.
  Prior is the agentic counterpart; Prior-generated comparison drafts could
  feed ORKG upstream.
- **NCG** (NLPContributionGraph, SemEval 2021) — defined a structured schema
  for extracting NLP paper contributions (ResearchProblem / Approach / Model /
  Dataset / Baselines / Results / ...). Aligned in spirit; Prior's claim
  schema is compatible.
- **AutoSci / OmegaWiki** (skyllwt) — wiki-centric full research-lifecycle
  platform on Claude Code. Our atlas could plug into theirs upstream.
- **FutureHouse PaperQA2 / Aviary** — RAG-based scientific Q&A.
- **Open Knowledge Format** (Google, Jun 2026) — markdown + YAML knowledge
  bundle spec; Prior is aligned in spirit, with a planned exporter.
- **OpenAlex, arXiv, Semantic Scholar** — citation graph substrate.


**Additional inspiration:**
- Mastrandrea et al. 2010 — IPCC AR5 Guidance Note on Treatment of Uncertainties
- IPBES Guide on the Production of Assessments
- Parkinson 2026 — *"Writing science that humans and machines can read"*
  (The Transmitter) 
