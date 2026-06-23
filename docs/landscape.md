# Landscape: prior art for the two-level literature-graph design

> What exists vs. what's open, for Prior's target design: a **GLOBAL** cross-paper
> contribution graph ("builds on" / "rests on") + a **LOCAL** per-paper claim graph
> (entail / contradict / support) for internal coherence, serving novelty detection,
> navigation, and gap/idea-finding via agent-callable web services.
>
> Compiled from a multi-source deep-research pass (28 sources, 23/25 claims verified
> 3-0). Date: 2026-06-18.

## Bottom line

The individual pieces are mature and well-covered, but **no existing system combines
both levels** — a persistent global contribution-lineage graph *and* a per-paper
internal claim/coherence graph, served to agents. Each competitor owns one slice.
That integration is the whitespace.

**Caveat:** the "whitespace" is inferred from no-system-found, not positively
documented. Two claims that tried to prove it via a survey's silence were *refuted*
(votes 1-2 and 0-3). Defensible, but don't overclaim it as a documented-open gap.

## Global contribution graph — well covered

| System | What it does | Gap vs. ours | URL |
|--------|--------------|--------------|-----|
| **ORKG** | `ResearchContribution` = problem+method+result triples; cross-paper SOTA comparison tables | Curated; no support/contradict layer; tabular, not a builds-on graph | https://orkg.org/ · paper https://arxiv.org/pdf/1901.10816 |
| **GoAI** (Mar 2025) — *nearest competitor* | Papers as nodes; typed citation edges (Based-on/Extension, Support, Contrast, Refutation); LLM agent beam-searches for novel ideas | Edges are **citation-derived**, not extracted from contributions; **no local claim graph** | https://arxiv.org/abs/2503.08549 (html https://arxiv.org/html/2503.08549v1) |
| **NLPContributionGraph** (SemEval-2021 T11) | Canonical paper→contribution-triple extraction pipeline feeding ORKG | Extraction only; no local coherence, no serving layer | https://ncg-task.github.io/ · https://arxiv.org/pdf/2106.07385 · https://aclanthology.org/2021.semeval-1.44/ |
| **SPECTER** | Citation-based document embeddings (implicit relatedness) | No explicit typed edges; embedding alternative | https://arxiv.org/abs/2004.07180 |
| **RKG survey** (TIB/ORKG) | Frames the "Research Knowledge Graph" paradigm | Doesn't treat the two-level design as an established category | https://arxiv.org/html/2506.07285v1 |

## Local per-paper claim graph — only disconnected primitives

| System | What it does | Gap vs. ours | URL |
|--------|--------------|--------------|-----|
| **SciClaim** | Fine-grained claim-as-graph schema (causal/comparative/predictive/statistical edges) | A dataset/schema, not a system; no cross-paper level | https://arxiv.org/pdf/2109.10453 |
| **SciNLI** | Scientific NLI pairs (Entailment/Reasoning/Contrasting/Neutral) | Labels ≠ literal entail/contradict/support; pairwise only | https://arxiv.org/pdf/2203.06728 |
| **Sci-Arg + 2025 extension** | Scientific argument mining; extension adds **inter-document** attack/support edges from citations | Corpus, not a deployed system; closest to bridging both levels | https://drops.dagstuhl.de/storage/08tgdk/tgdk-vol003/tgdk-vol003-issue003/TGDK.3.3.4/TGDK.3.3.4.pdf · orig https://aclanthology.org/W18-5206/ |
| **Nanopublications** | Atomic RDF assertions separated from provenance | Publishing format, not extraction/coherence | https://nanopub.net/ |

## Novelty / gap / idea applications — recent, but stop short of a persistent graph

| System | What it does | Gap vs. ours | URL |
|--------|--------------|--------------|-----|
| **OpenNovelty** (live, Jan 2026; run on 500+ ICLR'26 submissions) | Extracts task+contribution claims; contribution-level comparison vs prior work | Organizes as taxonomy + local context, **explicitly not a knowledge graph**; no local claim graph | https://opennovelty.org · https://arxiv.org/pdf/2601.01576 |
| **GraphMind** (EMNLP 2025 demo) | Per-paper contribution view for novelty assessment | Per-query, not persistent cross-paper | https://arxiv.org/abs/2510.15706 · https://aclanthology.org/2025.emnlp-demos.21/ |

## Autonomous AI-scientist agents — adjacent

| System | URL |
|--------|-----|
| AutoSci / OmegaWiki | https://github.com/skyllwt/OmegaWiki |
| Google co-scientist | https://deepmind.google/blog/co-scientist-a-multi-agent-ai-partner-to-accelerate-research/ |
| Sakana AI Scientist v2 | https://github.com/sakanaai/ai-scientist-v2 |

## Not yet verified — check before claiming novelty

These were named but **not independently verified** in this pass. scite and Consensus
overlap most with the typed-edge / claim-aggregation goals; verify directly.

- **scite** — citation-statement support/contradict/mention classification at scale
- **Consensus** — claim aggregation across papers
- **Elicit**, **SciSpace**, **Undermind**, **PaperQA / FutureHouse**

## Open questions that should shape the design

1. Does scite's supports/contradicts/mentions already cover the inter-paper typed-edge
   layer at scale? (Verify before claiming the global edge layer is novel.)
2. Is there *any* system that persists a unified two-level graph (vs. computing one
   level transiently per query) and exposes it as agent-callable services?
3. Can citation-derived edges (scite, GoAI) substitute for true argument mining, or
   are they measurably different signals?
4. **Is the LOCAL per-paper coherence/"story" graph load-bearing for novelty/gap-finding,
   or a nice-to-have?** OpenNovelty gets results with *no* local claim graph — we need a
   crisp argument for why the local layer earns its cost.

## Positioning & motivation (external) — see [principles.md](principles.md)

- **AI as normal technology** (Narayanan & Kapoor) — control spectrum (audit/monitor/circuit-breaker/least-privilege); reliability > capability; reversibility + legibility. https://www.normaltech.ai/p/ai-as-normal-technology
- **Why AI hasn't replaced software engineers** (same) — decide→execute→deliver; "vibe coding" → verification is irreducible. https://www.normaltech.ai/p/why-ai-hasnt-replaced-software-engineers
- **What if AI systems weren't chatbots?** (Ghosh et al.) — task-specific tools over one-size-fits-all chatbots. https://arxiv.org/abs/2605.07896
- **Ellf** (Explosion / spaCy / Prodigy) — task-specific, data-private NLP pipeline tooling (relation extraction, annotation, QA/eval) for the extraction + review layer. https://beta.ellf.ai/
