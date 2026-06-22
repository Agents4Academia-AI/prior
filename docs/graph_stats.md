# Atlas graph statistics

From the Friday demo atlas — topic *"retrieval augmented generation reduces
hallucination"*, built 2026-06-18. Regenerate with
`python evals/graph_stats.py` (key-free).

## Size

| | |
|---|---|
| Papers | 19 (15 OpenAlex + 4 arXiv) |
| Claims | 111 (6.5 / paper) |
| Claim relations | 191 |
| Citation edges (paper→paper) | 11 |

**Relation mix:** supports 107 · extends 49 · refines 29 · **contradicts 6**.
Mostly agreement and building-on — the signature of a young, consolidating field.

## Structure (the interesting part)

- **86% of claims (95/111) sit in one connected component.** The literature is a
  single interconnected conversation, not scattered islands. (14 claims are
  isolated; a couple of tiny pairs make up the rest.)
- **100% of relations are cross-paper (191/191).** By design the Cartographer
  only links claims from *different* papers, so every edge is genuine synthesis
  across the literature rather than within a single paper.
- **The consensus hubs are all definitions.** The most-supported claim has **14**
  incoming `supports`; the top four are all "what RAG is." The field strongly
  agrees on *definitions*, far less on *measured effects* — exactly what the
  forward answer flagged ("emerging", mostly definitional support).

## The 6 contradictions (use case (c))

Surfaced automatically. Substantive ones:
- **LiVersa (specialised hepatology RAG underperforms) ⟂ Almanac (statistically
  significant clinical improvement)** — a genuine empirical clash on whether
  specialised clinical RAG helps.
- **"confabulations is the more precise term" ⟂ papers treating "hallucinations"
  as standard** — a terminology dispute in the field.

The remaining ~3 are **novelty-framing** ("unlike prior methods X…") that the
Cartographer flagged as conflict. Honest framing for a slide: *"6 candidate
contradictions surfaced automatically; ~2–3 are substantive."* Sharpening this is
the Week-2 "contradiction as its own agent" item.

## Confidence

`confidence` today is the **Reader's extraction confidence** (a float 0–1: how
sure it is the claim was faithfully extracted), shown in each node's detail
panel. Distribution: **mean 0.93, median 0.95, range 0.72–0.99**. Relations carry
a separate Cartographer confidence.

> This is *not yet* the IPCC evidence×agreement calibrated confidence from the
> README — that is the global-layer work. Say "extraction confidence" on the slide.

## Contributions vs. claims

Of the 111 claims, **26 are definitional/background** ("RAG is defined as…").
The contributions view (`prior view --contributions`) filters those out, leaving
**85 contribution claims (102 nodes, 174 edges)** — a cleaner graph of what each
paper actually adds.

## Caveats worth stating
- The corpus is **query-shaped**: papers are OpenAlex/arXiv *relevance* hits for
  the exact query, so the selection leans toward the asked relationship. Report
  it as "papers ranked most relevant to the question," not "the literature."
- Years are 2021–2025 — relevance ranking buries older foundational work
  (`--cite-hops` reaches it).
