# Poster content — write here

*This is **your** file. Everything below is a first-pass draft I've written into the
structure so you're never staring at a blank box — overwrite it, cut it, keep the bits
that already sound like you. When you want to see it, say **"rebuild the poster"** and
I'll regenerate `poster.tex` from whatever is in here and compile it.*

**How to use this file**
- Write **only inside the `>>>` … `<<<` fences.** I parse those; everything outside is
  notes and gets ignored.
- `WORDS:` is the cap. Going a bit over is fine, going 50% over will unbalance the column
  and I'll flag it.
- Set `STATUS:` to `mine` once you've rewritten a block, so I know to stop touching it.
  It starts as `draft-claude` for everything.
- `NEEDS YOU:` tells you which four blocks actually deserve your time. The rest are
  numbers and scaffolding and are fine as they are for a first draft.

---

## HEADER

```
TITLE:      Why did this paper cite that one?
SUBTITLE:   Typed citation edges for a research-literature knowledge graph
KICKER:     809 citation sites · 3-class intent taxonomy · 95% on a blind gold set (macro-F1 0.892)
AUTHOR:     Callum Young
AFFIL:      <your department / supervisor / institution — fill in>
```

---

## §1 · WHAT PRIOR IS, AND WHY CITATIONS
`WORDS: 220` · `STATUS: draft-claude` · **NEEDS YOU: yes — this is the block that decides whether they keep reading**

>>>
**Prior** reads a corpus of research papers and builds a map of them. It pulls out each
paper's *contributions* — the specific things that paper claims to have done — and then
draws typed, directed relations between the contributions of different papers, so that
you can ask "what is actually known about X?" and get an answer grounded in the
literature rather than a plausible-sounding summary.

The map has a weak link. Those relations are drawn from **semantic similarity plus an
LLM's reading of two contribution statements**. The model never sees whether one paper
actually cited the other, or what it said when it did. The result is a map that agrees
with itself: **70% of the edges are `supports`**, and the `contradicts` label — the one
you would most want a literature map for — has been measured at around **36% precision**.

Meanwhile the citation record is sitting right there, unused. And a citation is a
different kind of object: paper $p_1$ citing $p_2$ is a **fact**, whereas an LLM saying
their ideas "build on" each other is an **assertion**.

But raw citations are blunt. In the graph, $p_1$ extending $p_2$'s method, $p_1$
mentioning $p_3$ in passing, and $p_1$ name-dropping $p_4$ out of obligation are all the
same edge with the same weight. The reason for a citation is the missing variable.

**So: type the citation edges, then use those facts to discipline the assertions.**
<<<

*Figure here: `figures/atlas.png` — the Prior atlas viewer, zoomed out to show topic clusters.*

---

## §2 · THE TAXONOMY, AND WHY OURS
`WORDS: 190` · `STATUS: draft-claude` · **NEEDS YOU: yes — the reasoning here is genuinely yours**

>>>
We started from **RefWarden**, a citation-verification tool, which asks three questions
of a citation: does the cited paper **exist**, does it **support** the claim it is
attached to, and is it **obligatory or merely helpful**. Those are good questions — but
they all ask *is this citation sound?* Prior needs to know *why the citation is there at
all*.

So we added a primary **intent** axis and kept support and priority as secondary stamps:

- **`background`** — cited as context, prior art, or a passing mention.
- **`uses_extends`** — the citing paper actually adopts or builds on the target.
- **`compares_contrasts`** — the citing paper sets its own work *specifically* against
  the target.

**The rule we used to pick the classes: a class only earns its place if the downstream
system would act differently on it.** That single test does all the work. ACL-ARC's
`uses` and `extends` collapse into one class, because Prior treats them identically.
Semantic Scholar's `result` is dropped — it is ambiguous and triggers no distinct action.
`exists` is excluded here because every cited paper is already in the corpus, so it is
trivially yes (it is parked for the hallucinated-citation demo on AI-generated papers).

**And the reason we could not simply use an off-the-shelf label set: Semantic Scholar has
no contrast class at all.** Contrast is the single most valuable signal for Prior,
because `contradicts` is exactly the relation the semantic graph gets wrong. The standard
taxonomy cannot express the one thing we most need.

Intent is also not redundant with verification: **65% of `compares_contrasts` sites still
`support` their local claim**, so the support axis genuinely cannot see intent.
<<<

*Figure here: taxonomy comparison table (I draw it).*

---

## §3 · THE PIPELINE
`WORDS: 110` · `STATUS: draft-claude` · **NEEDS YOU: no — numbers and plumbing, fine as-is**

>>>
The corpus is **152 papers** on AI-for-science, already carrying **581 contributions** and
**989 semantic edges** from Prior's existing pipeline.

For each paper we extract the bibliography from its arXiv LaTeX source, resolve each
reference back to a paper in the corpus, and pull the **passage around the citation**,
marking the one reference being typed as `[CITED:TARGET]` and any neighbours as `[CITED]`.
Intra-corpus citations only.

That gives **525 citation edges across 809 claim-sites** — later extended to **1,103 sites
over 643 paper-pairs**. A **site** is one (edge, passage) pair; an **edge** is one
citing→cited paper pair, rolled up from its sites. Most tables below report both.

Everything ran on a Claude Code subscription rather than a metered API, which is why every
runner is checkpointed, resumable, and stops cleanly when the usage window closes.
<<<

*Figure here: pipeline strip (I draw it).*

---

## §4 · BUILDING THE JUDGE, AND THE PROMPT
`WORDS: 210` · `STATUS: draft-claude` · **NEEDS YOU: yes — you have material here nobody else has**

>>>
We reused RefWarden's judge **transport** — the batching, the evidence assembly, the JSON
contract — and swapped out the **rubric**. Support and priority came for free; the intent
axis was a prompt change, not new software. The judge sees the cited paper's abstract as
evidence, plus the citing passage with the target marked.

**The interesting part is that the constraint inverted.** RefWarden's hard problem is
telling the model **what not to do**: don't judge the neighbouring citations, don't use
prior knowledge, abstain when the abstract doesn't say. Intent has no abstain option —
the model must **commit to a class on every site**. Caution stops being safe, because it
just becomes a systematic bias toward the majority class.

Which is exactly what happened.

- **v2 was too cautious and underfired `uses_extends`.** The rubric was asymmetric: it
  demanded the target be "a dependency of the citing work" for adoption, while accepting
  much weaker cues for background.
- **v3 broadened it** — the target "provides an ingredient, method, formulation, metric,
  dataset or architectural block that the citing paper actively uses" — and added a
  baseline tie-breaker: rerunning a system to beat it is `compares_contrasts`, adopting
  its protocol or code is `uses_extends`.
- **v3 then overfired `compares_contrasts` on group critiques.** "Another limitation is
  that current systems are limited to small-scale code experiments [CITED:TARGET]" is a
  critique of a field, not of a paper.
- **v4 fixed it by moving the rule rather than adding one.** The "don't over-use
  `compares_contrasts`" warning came *out* of the negative clause and went *into* the
  positive definition of `background`: if the target is grouped with other papers to
  describe a general limitation, it **is** background. **Telling the model what a class is
  beats telling it what a neighbouring class isn't.**

This was iterative hand-review rather than a controlled ablation — but v4 is the version
that was then measured, blind, at 95%.
<<<

*Figure here: prompt v2→v3→v4 strip (I draw it).*

---

## §5 · EVALUATION
`WORDS: 200` · `STATUS: draft-claude` · **NEEDS YOU: not for the first draft — but it's your audience's favourite block, so come back to it**

>>>
Three validation stages, in increasing order of cost and of trust.

**A. Semantic Scholar as a silver standard — a negative result.** Free, no LLM. Only 237
of our 525 edges appear in S2's reference graph and only **10 carry an intent label** at
all: SciCite has not been run on 2025–26 papers. On the 9 comparable edges S2 agreed 6/9,
and **on all three disagreements S2 was the coarser one** — it has no contrast class. This
is why the remaining two stages were necessary.

**B. A blind second judge.** A *stronger* model (Opus 5) relabelled a stratified 100-site
sample, given a **clean-room rubric** — it never saw our tie-breakers, so the two
annotators' errors decorrelate — and blind to our label. **Cohen's κ = 0.79**, 86%
agreement on the balanced sample, **81% reweighted** to the true class distribution. The
result that matters is not the number: **all 14 disagreements land on known taxonomy
boundaries, and none are random errors.** A judge that only argues on the genuinely
ambiguous cases is a credible judge.

**C. A hand-labelled gold set — the real number.** 122 sites, labelled blind through a
purpose-built web app; the judge's verdicts and quality gates sat in the backing sheet but
were never sent to the browser. The queue is **blocked by sample type**: an 80-site
`random_eval` block in random order, so any labelled prefix is still a uniform sample and
the headline accuracy is unbiased; a `disagreement` block of stage-B hard cases, **excluded
from accuracy** and used only to referee the taxonomy forks; and a stratified top-up to
~27 per class for macro-F1.

**95.0% (76/80)**, 95% CI **[87.8%, 98.0%]**. Reweighted to the population class mix,
**94.6%**; **macro-F1 = 0.892**. Sites on the same edge are not independent, so the true
interval is a little wider than binomial.

**And the referee result:** on the 12 hard cases where our judge and Opus disagreed, gold
sided with **ours 6, Opus 5, neither 1**. The stronger model was not the more accurate
one — and the split was clean: ours won every `background`→X call, Opus won every
X→`background` call.
<<<

*Figures here: accuracy panel, confusion matrix, κ strip (I draw all three).*

---

## §6 · FOLDING CITATIONS INTO THE SEMANTIC GRAPH
`WORDS: 200` · `STATUS: draft-claude` · **NEEDS YOU: yes — the hand-inspection verdicts are yours and only yours**

>>>
Prior now holds two graphs over the same 152 papers, answering different questions. The
citation graph is paper→paper and it is a **fact**. The semantic graph is
contribution→contribution and it is an **assertion**. Rolling the 989 semantic edges up to
paper-pairs and intersecting gives:

**535 semantic-only · 118 shared · 406 citation-only.**

They are **complementary, not redundant** — which is the answer to the obvious question of
whether citations make the semantic layer unnecessary. Citations alone miss parallel work
that never cites; semantics alone invents relations.

**The result that justifies the taxonomy:** of the 26 shared pairs typed
`compares_contrasts`, **only 4 carry any semantic `contradicts` edge**. The critique signal
is almost entirely invisible to the semantic pass — so the contrast class is not a
refinement, it is new information.

**Direction is nearly free.** Citation direction agrees with the semantic arrow on 66
pairs and disagrees on 52 — the LLM's `builds_on`/`refines` arrow is close to a coin flip.
On the audited `uses_extends` pairs, citation direction was correct **33/33**.

**We then read the divergent pairs by hand**, marking each as *complementary*,
*semantic-wrong*, *citation-wrong*, or *rollup-artifact*. The dominant verdict was
**complementary** — the two signals were describing different facets of the same pair
rather than disagreeing. The clearest case is MLEvolve→AlphaEvolve, which is genuinely
**both** `builds_on` **and** `contradicts`: it extends the paradigm *and* claims to beat
it. A majority-vote rollup would have hidden that tension entirely.

**So the conclusion is deliberately conservative: use citation signal as complementary
evidence and as a direction fix, not as a relabel.** When the graph was re-typed with
citation evidence made visible, `uses_extends` pairs became `builds_on` **89% of the
time** — the prior holds, without ever overwriting the semantic layer.
<<<

*Figures here: overlap Venn, intent × relation cross-tab (I draw both), plus
`figures/view_intent.png` — your two-layer viewer, filtered to the overlap.*

---

## §7 · GRAPH vs. WEB IDEATION  *(optional — say the word and I cut it)*
`WORDS: 130` · `STATUS: draft-claude` · **NEEDS YOU: no — and consider cutting it entirely**

>>>
**The question:** does an LLM exploring the Prior atlas propose better research directions
than the same LLM exploring the open web? Same seed topic, same task, same output schema,
same generator; only the environment differs. Judged blind and pairwise by a stronger
model, order-swapped.

**Status: 10 ideas per arm generated, judging not yet built.** Three findings from the
pilots are already worth reporting:

1. **Blinding failed first.** 9 of 10 ideas leaked their arm — the graph arm cited
   internal node IDs, the web arm said "web search". Fixed with an explicit blinding
   contract and an automated leakage gate before judging.
2. **The arms converged.** 3 of 4 seeds produced the *same core idea* on both sides —
   unsurprising in hindsight, since the corpus **is** the public literature the web arm
   retrieves.
3. **The cause was that the graph arm wasn't using the graph.** Across four runs it called
   `get_edges` once and the citation tools zero times: it was using the atlas as a private
   search index over the same papers. The fix was not to force traversal but to make
   structure **advertise itself** — surfacing typed-relation breakdowns and citation counts
   in every tool result. Traversal rose to 3–4 edge calls per run and 3 of 4 seeds then
   diverged from the web arm.

Cost per idea is comparable across arms, so the claim under test is *better-grounded ideas
at similar cost*, not *cheaper*.
<<<

*Figure here: arm-comparison table (I draw it).*

---

## §8 · TAKEAWAYS
`WORDS: 100` · `STATUS: draft-claude` · **NEEDS YOU: no — but these are the four sentences people repeat afterwards, so read them twice**

>>>
- **A taxonomy chosen by downstream action, not by convention.** Three intent classes,
  each kept only because Prior would act differently on it — validated blind at **95%
  accuracy, macro-F1 0.892**.
- **The rubric was the lever, not the model.** The constraint inverted from "do not
  classify" to "must classify", and the fix for over-firing was to define a class
  **positively** rather than forbid its neighbour.
- **The two graphs are complementary** — 118 shared pairs out of 1,059 — and the contrast
  signal is nearly invisible to the semantic layer (4 of 26 pairs). Citation evidence
  belongs as evidence and direction, not as a relabel.
- **Next:** feed intent into the cartographer's labelling prompt and measure whether
  `contradicts` precision moves off 36%.
<<<

---

## SCREENSHOTS I NEED FROM YOU

Drop these into `Callum_poster/figures/` with exactly these names and they appear on the
next rebuild. Until then the poster shows correctly-sized grey placeholders, so nothing
shifts when they land.

| file | what | how to frame it |
|---|---|---|
| `figures/atlas.png` | the original Prior atlas (`data/atlas/view_global_d3.html`, or `frontend/public/viewer.html` if that one looks better) | zoomed out to show topic clusters, no side panel, no tooltip, roughly 4:3 |
| `figures/view_intent.png` | your citation-intent viewer (`experiments/edge_quality/out/view_intent.html`) | **both layers on, filtered to the overlap** — the full hairball reads as noise at A0. Legend visible. Ideally include a pair with both a `compares_contrasts` citation and a `contradicts` semantic edge |

Maximise the browser on your largest display and zoom the *page* out rather than shrinking
the window — that keeps labels sharp. Anything narrower than ~1600 px will look soft at A0.
