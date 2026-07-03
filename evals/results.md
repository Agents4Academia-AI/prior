# Eval results

Real run for the Friday demo. Reproduce with the command shown per section.

**Run context**

| | |
|---|---|
| Date | 2026-06-18 |
| Atlas topic | "retrieval augmented generation reduces hallucination" |
| Papers / claims | 19 / 111 |
| Backend | `claude-code` (Claude Code / Max login — no API credits) |
| Models | reader = claude-sonnet-4-6 · cartographer = claude-sonnet-4-6 · navigator = claude-opus-4-8 |

---

> **Two layers — match the numbers to the artifact.** The Reader/Cartographer
> numbers below are the **CLAIM layer** (`atlas.json`) — that's also what the
> `ask`/`origin` demos answer from. The **evolution view** you *show* is the
> **CONTRIBUTION layer** (`contributions.json`), a different, smaller artifact —
> its numbers are in their own section. Don't put "191 relations" next to a
> screenshot of the 17-relation contribution graph.

## Reader — groundedness (`python evals/groundedness.py`)  · CLAIM layer

| Metric | Value |
|--------|-------|
| Claims extracted | 111 over 17 papers (6.53 / paper) |
| **Groundedness rate** (evidence span found in source) | **100.0%** |
| Mean evidence overlap | 100.0% |
| Mean confidence | 0.93 |
| Type distribution | methodological 44 · empirical 40 · definitional 26 · theoretical 1 |

## Cartographer — graph stats (`python evals/graph_stats.py`)  · CLAIM layer

| Metric | Value |
|--------|-------|
| Citation edges | 11 |
| Semantic relations | **191** — supports 107 · extends 49 · refines 29 · **contradicts 6** |
| Contradiction rate | 3.1% |
| Linked-claim rate | 87.4% (14 isolated) |

## Contribution layer — the evolution view (`contributions.json`)

Primary literature only (3 reviews excluded), full-text extraction, standalone
self-declared contributions. **This is what the `prior view --evolution` /
`--contributions` graphs show.**

| Metric | Value |
|--------|-------|
| Papers / contributions | 12 / **39** (4 papers skipped — no accessible full text) |
| Kinds | empirical_finding 15 · method 14 · framework 4 · analysis 3 · dataset/model/other 3 |
| Cross-paper relations | **17** — supports 8 · extends 5 · refines 4 · contradicts 0 |
| Linked contributions | 23 / 39 (clusters of ≤4; not yet one connected component) |

Note the honest gaps vs. the claim layer: smaller (reviews excluded + 4 no-full-text
papers, incl. the clinical ones), and **0 contradictions** — at the contribution
level papers mostly *extend/support* (everyone proposes their own method); the
6 contradictions live in the claim layer (where review syntheses surface tension).

## Navigator (forward) — use case (a), state of the art

**Q: "Does retrieval-augmented generation reduce hallucination?"** → verdict **EMERGING**.
Prior surfaces that most claims assert the reduction *definitionally* ("thought
to reduce") while only Shuster et al. (2021) gives human-evaluated empirical
evidence, and Zhang et al. (2025) note RAG pipelines introduce their *own*
hallucination sources — citing 8 papers across supporting / contradicting / open.

## Navigator (forward) — graceful "no"

**Q: "Has anyone used RAG for protein structure prediction?"** → verdict
**NOT_FOUND**. Prior refuses to fabricate: *"None touch proteins, molecular
biology, or structure prediction."*
- **Closest:** retrieval-augmented image generation [arxiv:2506.06962v3] + general RAG definitions.
- **Gap:** all claims target LLM text/image generation; none address biomolecular/structural-biology applications.

## Navigator (backward) — origin (`prior origin "retrieval-augmented generation"`)

Traces within the atlas and **flags its own limits**: *"The atlas almost
certainly misses the true origin. The canonical source is Lewis et al. (2020) …
none of which appear in this list."* Calibrated honesty over a confident guess.
(`--cite-hops 1` would pull the true origin into the graph.)

---

## Prior vs. vanilla Claude (`python evals/baseline_vanilla.py`)

Full side-by-side: [`baseline_comparison.md`](baseline_comparison.md). Highlights:

| Question | Vanilla Claude (no grounding) | Prior (grounded) |
|----------|-------------------------------|------------------|
| RAG reduces hallucination? | "**Yes, RAG substantially reduces hallucination**" — confident, uncited | **EMERGING** — only 1 of N claims is measured; flags definitional vs. empirical; 8 cited papers |
| RAG for clinical decision support? | Lists specific papers (Almanac, Med-PaLM 2, BioViL-T) **from memory** | **EMERGING** — cites the 2 real in-atlas papers (Zakka 2024, Miao 2024), hedges "potential to be effective" |
| RAG for protein structure prediction? | — | **NOT_FOUND** — honest "no" with closest + gap |

**Takeaway for the slide:** vanilla Claude answers confidently (and invents
citations); Prior answers with calibrated confidence, real citations, and an
honest "no" when the literature doesn't cover the question.

---

## Notes / caveats
- Built at `--max-papers 15` (→ 19 with arXiv) so the Cartographer relation pass
  finished on the Max plan tonight. Re-runnable at 25.
- Reader/Cartographer numbers are over the demo atlas, not a held-out gold set —
  groundedness is a faithfulness proxy, not extraction recall.
- SciFact harness (`evals/scifact/`) is wired but not run tonight (dataset not
  downloaded); it's the path to a held-out accuracy number.
