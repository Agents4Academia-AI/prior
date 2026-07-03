# Prior

> An open-source agentic system that reads primary literature and builds an
> **auditable contribution graph** — every claim traceable to its source, with
> contradictions surfaced and confidence made explicit — that you can query and
> navigate visually.

**Team 6** (merged with Team 4): Klara · Harit
**Hackathon:** [Agents4Academia](https://agents4academia.github.io), 14–26 Jun 2026 · **Release `v06.26`**

![The Prior atlas — 152 papers · 581 contributions · 989 typed relations — cycling through the graph's lenses: contributions, communities, and a playable timeline.](docs/prior-demo.gif)

---

## Why Prior

### The problem

Most "research agents" answer a literature question by Googling, skimming
snippets, and writing a fluent paragraph. You get an answer you **can't audit**:
no way to see which paper each statement came from, whether the sources actually
agree, or how much to trust it. For real research that's a non-starter — the
provenance *is* the product.

**Prior makes a different bet:** don't summarise, **build a graph**. Read primary
sources (OpenAlex + arXiv), extract each paper's *contributions* and *claims*
with their provenance, link them across the literature (supports / extends /
refines / **contradicts**), and reason over that structure. The atlas is also a
clean hand-off artifact: a structured, grounded corpus other tools can build on.

Longer term, a map of what's **claimed, contested, and missing** is the *substrate*
a research system needs to judge **which phenomena deserve attention and what
questions to ask of them** — the call that comes *prior* to any task. Prior doesn't
make that call yet; it makes it **auditable** for whoever (or whatever) does.

---

## What it does & how

### Three things the black boxes don't

1. **Provenance.** Every contribution and claim is a node that links back to the
   paper (and, where cached, the exact supporting text) — one click from a
   statement to its source and DOI.
2. **Contradictions.** The Cartographer only links claims *across* papers, and
   flags `contradicts` edges automatically — genuine empirical clashes get
   surfaced instead of averaged into a bland summary.
3. **Confidence — made explicit.** Nodes and edges carry confidence (an extraction
   score + cross-model agreement), shown in the UI, and a self-auditing eval
   *measures* how well-calibrated it is against human labels. (Honest scope of
   what "confidence" means today: see [Roadmap & next steps](#roadmap--next-steps).)

### Architecture — one atlas, four agents

Prior builds a single **contribution atlas** over the source material (an earlier
design split it into per-paper "local" and cross-paper "global" layers; in the
end we shipped the cross-paper atlas as the product, with per-paper provenance
reachable from every node).

```
Scoper  ──▶  Contributor  ──▶  Cartographer  ──▶  Navigator
topic →      full text →       contributions →     query + render
scoped       contributions     cross-paper graph   • state of the field
corpus       + claims          (supports/extends/   • trace to origin
(recall →     + provenance      refines/contradicts, • web view / corpus / report
 precision +                    consensus tiers)
 snowball to
 saturation)
```

- **Scoper** — topic → a scoped corpus (recall-then-precision + citation
  snowball to saturation + completeness checks).
- **Contributor** — cached full text → each paper's contributions + claims, with
  extraction confidence and provenance.
- **Cartographer** — contributions across papers → the linked atlas: cross-paper
  `supports/extends/refines/contradicts` edges, consensus tiers, contradictions.
- **Navigator** — a question + the atlas → a grounded answer (cited to node ids),
  and the rendered views.

**Product surface (web UI):** `Graph` · `Papers` · `Eval` · `Report` · `Ask Prior`.

### The interface

Four views — **Graph · Papers · Eval · Report** (+ Ask Prior). The **Graph** is the
atlas above, animated through its lenses — communities, a playable timeline, and
per-cluster **knowledge frontiers** (expand a community into a lineage: foundational
work at the centre, the frontier at the rim):

![Contributions view, then a community expanded as a knowledge frontier.](docs/prior-frontier.gif)

The other three views:

- **Papers** — every source with its contribution & claim counts.
- **Eval** — the atlas audits itself: per-judge correctness (each model / human
  annotator is a column), cross-judge agreement, and calibration.
- **Report** — a system report generated live from the running graph; it reads
  like a paper.

### The atlas

Prior's flagship build maps **the hackathon's own field** — *agents for the
scientific process* — a fitting stress test: the tool mapping the literature it is
part of. It's the atlas in the GIF above.

| | |
|---|---|
| Papers | 152 |
| Contributions | 581 |
| Claims | 1,547 |
| Cross-paper relations | 989 — `supports` 695 · `builds_on` 212 · **`contradicts` 73** · `refines` 9 |
| Structure | **83%** of contributions sit in one connected component |
| Communities | Peer review · Autonomous systems · Hypothesis generation · Benchmarks & eval · Multi-agent orchestration · Domain-science agents · Idea novelty · RAG / literature QA · Safety / risk |

The corpus spans the anchors — *The AI Scientist* (v1 & v2), *ResearchAgent*,
*NovBench* — and the **73 `contradicts` edges** surface genuine tensions. One the
atlas flags automatically:

> **"LLM reviewing-agents give useful, iterative peer review"** ⟂ **"LLM-as-judge
> scores for open-ended scientific ideation systematically exceed PhD-level expert
> ratings by 3–4 points"**

i.e. whether LLMs can reliably *evaluate* science is itself contested — exactly the
kind of open question Prior is built to surface.

---

## Does it hold up?

### Evaluation — the atlas audits itself

Prior ships a **self-auditing eval** (the `Eval` and `Report` views) that grades a
built atlas along three gates:

| gate | checks | self-eval |
|---|---|:--:|
| **Faithful** | extraction faithfulness · global-edge precision | ✓ |
| **Honest** | grounding (cited ids are real) · abstention (off-topic → `not_found`) · in-scope coverage | ✓ |
| **Useful** | novelty recall (finds related work) | ✓ |

On the atlas above, the interactive `Eval` view runs a **multi-judge** scorecard —
each model judge (Claude, Qwen, Gemma…) *and* human annotator scores Contributions /
Relations / Claims. Correctness runs ~**53–80%** on contributions and ~**63–85%** on
claims, but only **21–53% on relations** — quantifying that *relation extraction is
the weak link*. Plus **cross-judge agreement** and **calibration** diagrams
(reliability + accuracy-vs-coverage).

**Honest caveats:** the headline checks are **self-eval** — the system auditing its
own output, a smoke test, *not* independent proof; a parallel **human-annotation**
track (~140-item queue) is the real cross-check. And calibration is **built but not
yet populated** on the shipped core bundle (its prebuilt contributions carry no
confidence scores), so **ECE / reliability aren't computed there yet**. "All green"
means the self-audit is clean, not that the graph is proven correct.

### Honest limitations & failure modes

The Anthropic deliverable is a report on **model behaviour and failure modes** on
agentic-research tasks. Ours, plainly:

- **Relation *direction* is unreliable.** Which of two claims `builds_on` the
  other is model noise; the viewer infers precedence from publication **year**
  instead. Don't trust edge direction as a model output.
- **Confidence is model-agreement, not evidence weight** (see Roadmap → scope of
  confidence). A claim agreed on by 3 runs can still rest on one weak study.
- **Contradiction precision is imperfect.** The atlas flags 73 `contradicts` edges,
  but some are novelty-framing ("unlike prior work X…") mis-read as conflict — treat
  them as candidates to investigate, not verdicts (the eval puts relation correctness
  at just 21–53%). "Contradiction as its own agent" is a roadmap item.
- **Grounding is semantic, not verbatim.** Quotes are faithful paraphrases, not
  guaranteed exact spans — verification should treat them as such.
- **The corpus is query-shaped.** Papers are *relevance* hits for the exact
  query, so selection leans toward the asked relationship; report it as "papers
  most relevant to the question," not "the literature." `--cite-hops` reaches
  older foundational work relevance ranking buries.
- **The citation graph is incomplete.** arXiv reference lists are largely
  missing from the sources; intra-corpus citation coverage is sparse.

---

## Use it

### Quickstart

Full runbook in **[docs/RUNNING.md](docs/RUNNING.md)**. Short version:

```bash
export PRIOR_LLM_BACKEND=claude-cli           # credit-free (Claude Code login); or set ANTHROPIC_API_KEY

# ── build your own atlas of a topic — no database, one HTML file ──
pip install -e ".[graph]"                     # core + local embeddings (Neo4j server NOT needed)
prior build "diffusion models for planning"   # → data/atlas/atlas.json
prior view --open                             # → one self-contained HTML viewer, opens in your browser

# ── or the full web app (persistent + queryable) ──
pip install -e ".[graph,web]" && docker compose up -d   # adds the web API + Neo4j
prior serve --port 8078                        # then run the frontend (see RUNNING.md)
```

Tests + evals are key-free: `pytest -q` · `python evals/graph_eval.py groundedness`.
Contributing: **[CONTRIBUTING.md](CONTRIBUTING.md)**.

### Reusable stages

Prior's pipeline is three **standalone, independently usable stages** — and they've
already been reused *beyond* Prior: another hackathon team lifted **Explore** to scope
the corpus for their own project ([**UReKA**](https://github.com/Agents4Academia-AI/UReKA)),
and the full-text and extract stages have
obvious broader uses. Take whichever you need:

| stage | what it does | one command |
|---|---|---|
| **Explore** (agentic) | topic → scoped corpus (recall-then-precision + citation snowball to saturation) | `scripts/explore.py --topic "<in/out-of-scope def>"` |
| **Get full text** (deterministic) | DOIs / arXiv ids → clean cached full text, multi-source cascade | `scripts/get_fulltext.py --ids dois.txt` |
| **Extract** (LLM) | cached full text → contributions + claims + graph | `scripts/extract.py --select all` |

**Most reusable: full text.** The free channels (arXiv, OA, Unpaywall, preprint
servers, `citation_pdf_url`) need **no keys**. See **[SHARING.md](SHARING.md)** for
what's safe to redistribute (metadata + graph) vs. not (raw full text): **closed-access
papers we cite rather than ship** — usage agreements permit mining, not
redistribution — and we prefer open **arXiv** copies where they exist.

---

## Roadmap & next steps

**Scope of "confidence" (honest note).** Today Prior's confidence answers *"was this
faithfully extracted, and do the models agree?"* — a per-node extraction score plus
`triple`/`double`/`opus_only` model-agreement tiers, with a self-audit for
calibration. It is **not yet** *"how strong is the evidence?"*. Closing that gap
(item 1) is the headline next step. Each step makes the map better at flagging
*which* phenomena deserve attention and *how sure* we should be:

1. **Evidence-weighted confidence** — calibrate a claim by the *strength and
   agreement of its evidence* (the IPCC/IPBES scheme, Mastrandrea et al. 2010), not
   just how many model runs concur.
2. **Beyond papers** — generalise the `Paper` node to a typed `Source` (talk,
   blog, video, thread, preprint) with credibility-weighted provenance, so the
   atlas reflects the whole scholarly conversation, not just the archived record.
3. **Negative & null results** — give each claim a polarity (positive / negative /
   null / mixed) so the atlas captures what *didn't* work, countering publication
   bias (`contradicts` already half-captures this).
4. **Contradiction as its own agent** — lift precision past the ~50% floor: the
   "significance everywhere vs. nowhere" selection problem, head-on.
5. **Contribution merging + novelty** — cluster equivalent contributions into
   canonical nodes; novelty (a phenomenon no one has yet addressed) falls out of the merge.
6. **Gap surfacing — a coverage view, not the graph.** Absence is invisible in a
   node-link layout; a method × task (or community × claim-type) matrix makes
   under-studied cells pop, plus a Navigator "what's under-supported?" query.
7. **Citation-aware Cartographer** (once the citation graph is backfilled) ·
   **hosted demo** (STORM-style).

Contributions welcome — start from any reusable stage above, see
[CONTRIBUTING.md](CONTRIBUTING.md), or open an issue. Design notes in [docs/](docs/);
progress log in `claude-progress.md`.

## End notes

### Built with Claude Code — token report

Prior was built almost entirely **through Claude Code on a Max subscription (no
metered API)**. Usage logged in this workspace, 2026-06-17 → 07-01, **deduplicated
by message id** (Claude Code replays messages into continuation files, so raw logs
double-count by ~2×):

| model | turns | input | cache write | cache read | output | ~$ equiv-API |
|---|--:|--:|--:|--:|--:|--:|
| Claude Opus 4.8 | 2,587 | 0.31M | 30.4M | **1.12B** | 5.2M | $992 |
| Claude Sonnet 4.6 | 2,768 | 0.01M | 12.5M | 32.5M | 9.8M | $232 |
| Claude Haiku 4.5 | 2,566 | 0.03M | 17.2M | 26.1M | 15.9M | $116 |
| **Total** | **7,921** | 0.35M | 60.0M | **1.17B** | 30.8M | **≈ $1,340** |

**≈ 1.26 B tokens**, of which **~93% were cache reads** — prompt caching did the
heavy lifting. Cache writes were **1-hour TTL** (Claude Code's default), priced at
2× input. The `$1,340` is *equivalent-API* list-price cost for scale; actual spend
was the flat Max subscription (~$96/day-equivalent). Counts cover this workspace;
teammates' machines are separate.

### Links

- **Slides:** [hackathon deck](https://docs.google.com/presentation/d/1ESDmlK8z3T8XWKAdn_xdJVWpP079jkP1iKCl95wjQLo/edit)
- **Demo:** run locally per the Quickstart (hosted instance planned)

### Acknowledgements

Built during [Agents4Academia](https://github.com/Agents4Academia-AI), 14–26 June
2026. Code **Apache-2.0**; graph/atlas data (`data/`) **CC-BY-4.0**.

**Adjacent & prior work:** ORKG (TIB Hannover) · NLPContributionGraph (SemEval
2021) · AutoSci/OmegaWiki · FutureHouse PaperQA2/Aviary · Papers with Code
(Meta → Hugging Face) · scite.ai (supporting/contradicting *Smart Citations*) ·
Elicit (Ought) · STORM (Stanford) · Connected Papers / ResearchRabbit ·
Open Knowledge Format (Google, 2026) · OpenAlex / arXiv / Semantic Scholar.

**Inspiration:** Mastrandrea et al. 2010 (IPCC AR5 uncertainty guidance) · IPBES
assessment guide · Parkinson 2026, *"Writing science that humans and machines can
read."*
