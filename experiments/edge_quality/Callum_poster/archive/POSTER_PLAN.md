# Poster plan — "Typed citation edges for Prior"

*This is **my** file: recommendations, word budgets, figure specs, and the reasoning behind
the layout. You don't write in here. You write in `POSTER_CONTENT.md`.*

**Format decided:** A0 **portrait**, 3 columns, `beamerposter`.
**Audience:** student poster session — statistics students + supervisors, none of whom
know what Prior is, all of whom will be standing 1–1.5 m away for about 90 seconds
before they either walk off or ask you a question.

---

## 0. How this works (the painless loop)

```
POSTER_PLAN.md      ← me. ideas, budgets, figure specs. read once, then ignore.
POSTER_CONTENT.md   ← you. one block per poster section, pre-filled with my draft
                      bullets in your voice. edit / overwrite / delete freely.
poster.tex          ← me. I read POSTER_CONTENT.md and rebuild this.
poster.pdf          ← compiled locally (MiKTeX is installed — I can run it and look
                      at the result myself, so you never have to touch LaTeX).
```

**The loop:** you edit `POSTER_CONTENT.md` → you say "rebuild" → I regenerate
`poster.tex`, compile, and check it visually → you open `poster.pdf`. You can rebuild
after editing one section; you don't have to finish the whole thing first.

**You do not need a template.** I've built one from scratch inside `poster.tex` — three
columns, boxed sections, a colour scheme, and all charts drawn natively in TikZ/pgfplots
(no image files to manage, everything stays vector-sharp at A0). Nothing to download.
If you *do* find a departmental template you're required to use, hand it to me and I'll
port the content across — it's about 20 minutes of work, not a rewrite.

**On "D3":** that's just the JavaScript charting library our graph viewers are built on
(`view_global_d3.html`, `view_intent.html`). It means those viewers are live web pages,
not images — so a screenshot is the only way to get them onto a poster.

---

## 1. Total word budget

**~1,150 words of body text.** That is already at the upper end for A0. The failure mode
for this poster is not "too little content", it's a wall of text that nobody reads. Every
section below has a hard cap. If you overrun, the compile will still work but the
columns will unbalance and I'll tell you what to cut.

Rough rule for what the numbers mean at A0: body text is 25 pt, which is comfortably
readable at 1.5 m. ~1,150 words at that size leaves roughly 45% of the poster area for
figures and whitespace, which is the right ratio.

---

## 2. Section-by-section

### Header — title, authors, affiliation
**~25 words.** Not counted in the 1,150.

- Title should name the *thing you built*, not the *area*. "Citation intent classification"
  is an area. Something like **"Why did this paper cite that one? Typed citation edges
  for a research-literature knowledge graph"** is a thing.
- The statistics students will latch onto anything quantitative in the title. A second
  line with the headline number (95% accuracy on a blind gold set, κ = 0.79) earns
  attention cheaply — I've put a slot for it.

---

### §1. What Prior is, and why citations (COLUMN 1)
**Cap: 220 words.** *(You pushed back on 180 — you're right. This audience has zero
context, and this is the block that decides whether they keep reading. 220 is the most
I'd give it; beyond that it starts eating the method.)*

**What you need to write:**
- What Prior is, in two sentences, to someone who has never heard of it. Resist jargon:
  no "cartographer", no "contributions", no "atlas" until you've said what it *does*.
  Something like: it reads a body of papers and builds a map of how the ideas in them
  relate, so a researcher can ask "what's actually known about X?" and get a grounded
  answer rather than a summary.
- The specific weakness you attacked: **Prior's map is built from semantic similarity
  plus an LLM's reading of two contribution statements. It never looks at the citations.**
- Why that's a problem, with the numbers: the semantic graph is **70% `supports`**, and
  its `contradicts` label has **~36% precision**. It corroborates everything and it
  can't reliably find disagreement — which is exactly what you'd want a literature map
  for.
- The pitch in one line: a citation is a **fact** (paper X really does cite paper Y);
  a semantic edge is an **assertion** (an LLM thinks these two ideas relate). Use facts
  to discipline assertions.
- One sentence of "not all citations are equal" — the notion.md framing about $p_1$
  extending $p_2$ vs. name-dropping $p_4$. This is the intuition the whole poster rests
  on and a statistics audience will get it instantly.

**Visual: the original semantic atlas screenshot.**
You're right that the original one is the right choice here — it's topic-grouped and it
looks good, and at this point in the poster you're selling *Prior*, not your own work.
File: `data/atlas/view_global_d3.html` (or `frontend/public/viewer.html`, which is the
prettier one — try both, take whichever screenshots better).

*Screenshot brief:* zoomed out enough to show the whole cluster structure, no side panel
open, no tooltip. Landscape crop roughly 4:3. Take it on a large browser window
(≥2000 px wide) so it doesn't pixelate at A0. Save as `figures/atlas.png`.

---

### §2. The taxonomy — and why ours (COLUMN 1)
**Cap: 190 words.**

This is one of the two most interesting sections on the poster and it's the one you're
best placed to write, because the reasoning is genuinely yours.

**What you need to write:**
- Start from RefWarden's axes, since that's where you started: `exists`,
  `supports_claim`, `priority`. Say plainly what each asks.
- Then the move: those ask *is the citation sound?* Prior needs *why is it there?* — a
  different question. So you added an **intent** axis and kept support/priority as
  secondary.
- The three classes: `background`, `uses_extends`, `compares_contrasts`. Define each in
  ~8 words.
- **The design rule** — this is the bit to be proud of and it's your sentence:
  *a class only exists if the downstream system would act differently on it.* That's why
  ACL-ARC's `uses` and `extends` merged (Prior does the same thing with both), why S2's
  `result` was dropped (no distinct action), and why `exists` was excluded (every citee
  is already in the corpus, so it's trivially yes).
- **The killer argument for a custom taxonomy:** Semantic Scholar has *no contrast class
  at all*. Contrast is the single most valuable signal for Prior, because `contradicts`
  is precisely the relation the semantic graph gets wrong. So the off-the-shelf label set
  cannot give us the one thing we most need.
- One line on `exists` being parked for the AI-generated-paper hallucination demo — it's
  a good hook for questions.

**Visual: taxonomy comparison table.** I'll draw it — a 4-column table (scite / ACL-ARC /
Semantic Scholar / **ours**) with arrows showing what merged into what and what was
dropped. The empty cell under Semantic Scholar's contrast column is the whole argument,
rendered visually. Already drafted in `poster.tex`.

---

### §3. The pipeline (COLUMN 1, bottom)
**Cap: 110 words.** Deliberately short — this is plumbing, and plumbing is what
poster visitors skim.

**What you need to write:**
- The corpus: **152 papers** on AI-for-science, **581 contributions**, **989 semantic
  edges** in the existing graph.
- How the citation edges were mined: arXiv `.bbl` / bibliography extraction → resolve
  each reference to a corpus paper → pull the **citing sentence window** around each
  `[CITED:TARGET]` marker. Intra-corpus only.
- The scale you ended up with: **525 edges / 809 claim-sites**, later extended to
  **1,103 sites / 643 pairs**.
- One sentence on the unit distinction, because it recurs in every table:
  a **site** is one (edge, citing-passage) pair; an **edge** is one citing→cited paper
  pair, rolled up from its sites.
- Worth one clause: everything ran on a Claude Code subscription, not a metered API —
  which is *why* the runners are checkpointed and resumable. Supervisors like a
  constraint that shaped the engineering.

**Visual: pipeline strip diagram.** I'll draw it: papers → .bbl → resolved edge →
citing-sentence window → judge → typed edge `(p1, p2, t)`. Horizontal, five boxes,
minimal. Already drafted.

---

### §4. Building the judge, and the prompt (COLUMN 2, top)
**Cap: 210 words.** The second of the two most interesting sections, and the one where
you have material nobody else has: `prompt_changes.md`.

**What you need to write:**
- The build: you reused RefWarden's judge **transport** — same batching, same evidence
  assembly, same JSON contract — and **swapped the rubric**. Support/priority came free;
  intent was a prompt change, not new software. Say that explicitly, it's a good line.
- What the judge sees: the citee's abstract as evidence (L0), plus the citing passage
  with `[CITED:TARGET]` marking the one citation to classify and other `[CITED]` markers
  as context.
- **The interesting constraint flip.** This is your best paragraph, so give it room:
  - The original RefWarden rubric's hard problem is telling the model **what *not* to do**
    — don't judge neighbouring citations, don't use prior knowledge, abstain when the
    abstract doesn't say.
  - The intent rubric's hard problem is the opposite: the model must **commit to a class
    on every single site**, with no abstain option. Caution is no longer safe — it just
    becomes a systematic bias toward the majority class.
  - And you watched exactly that happen. v2 was too cautious and **underfired
    `uses_extends`** — the rubric was asymmetric, it demanded "the target is a dependency"
    for adoption while accepting far weaker cues for background.
- The version arc, concretely (this is the content of `prompt_changes.md`):
  - **v2 → v3**: broadened `uses_extends` from "is a dependency" to "provides an
    ingredient, method, formulation, metric, dataset or architectural block the citing
    paper actively uses"; added the baseline tie-breaker (rerun-to-beat →
    `compares_contrasts`; adopt-their-protocol → `uses_extends`).
  - **v3 → v4**: v3 then **overfired `compares_contrasts` on group critiques** —
    "current systems [TARGET] are limited to small-scale experiments" is a critique of a
    field, not of a paper. The fix that worked was structural, not additive: **move the
    rule from a negative clause ("do NOT over-use") into the positive definition of
    `background`.** Telling a model what a class *is* beats telling it what another class
    *isn't*.
- Be honest that this was iterative hand-review, not a controlled ablation. Say it in
  one clause and move on — an audience of statisticians will respect the disclosure far
  more than they'd punish the informality. And you have the receipts: v4 is the version
  that scored 95%.

**Visual: prompt-version diagram.** I'll draw a three-panel strip: v2 (arrow: too few
`uses_extends`) → v3 (arrow: too many `compares_contrasts`) → v4, each with the one-line
failure mode and the one-line fix underneath. This makes the whole section legible in
five seconds. Already drafted.

---

### §5. Evaluation (COLUMN 2, bottom)
**Cap: 200 words.** Your statistics audience will spend most of their time here. Lead
with the design, not the number — they'll respect the design more.

**What you need to write:**
- **Three validation stages, in order of increasing cost and increasing trust:**
  1. **Semantic Scholar silver standard** — free, no LLM. **Verdict: too thin to grade
     with.** Only 237 of 525 edges appear in S2's reference graph and only **10 carry an
     intent label**; SciCite hasn't run on 2025–26 papers. On the 9 comparable edges S2
     agreed 6/9 and **on all 3 disagreements S2 was the coarser one**. Report it as a
     negative result — it's *why* stages B and C were necessary.
  2. **Blind second judge** — a *stronger* model (Opus 5) relabels a stratified 100-site
     sample. **Clean-room rubric** (it was never given your tie-breakers, so the two
     annotators' errors decorrelate) and **blind** to your label. **κ = 0.79**, 86% on the
     balanced sample, **81% reweighted** to the true class distribution.
     - The finding that matters: **all 14 disagreements land on known taxonomy
       boundaries — none are random errors.** Say this. A judge that only argues on the
       genuinely ambiguous cases is a credible judge.
  3. **Hand-labelled gold set** — the real number. **122 sites**, labelled blind by you
     through a purpose-built web app; the judge's verdicts, the quality gates and the
     second-judge fields were all in the backing sheet but never sent to the browser.
- **The sampling design is the part to be proud of** and it's the part this audience will
  actually appreciate. Explain it in one sentence: the queue is **blocked by sample
  type** — an 80-site `random_eval` block in random order (so any labelled prefix is
  still a uniform sample → unbiased accuracy), a `disagreement` block (the stage-B hard
  cases, **excluded** from the accuracy figure and used only to referee the forks), and a
  `strat_topup` block to reach ~27/class for macro-F1.
- **The numbers:**
  - **95.0% (76/80)** on the random block, 95% CI **[87.8%, 98.0%]**.
  - **94.6%** reweighted to the population class mix; **macro-F1 = 0.892**.
  - Per class F1: `background` 0.968, `uses_extends` 0.869, `compares_contrasts` 0.839.
  - The honest caveat you should keep: sites on the same edge aren't independent, so the
    true CI is a little wider than binomial.
- **The referee result, which is the fun one:** on the 12 hard cases where you and Opus
  disagreed, gold sided with **you 6, Opus 5, neither 1**. The stronger model was not
  more right. It split cleanly by fork: you won every `background`→X call, Opus won every
  X→`background` call.

**Visuals (three, tightly packed):**
1. **Gold accuracy panel** — the 95.0% with its CI as a horizontal interval, plus
   reweighted 94.6% and macro-F1 0.892 as large numerals. I'll draw it.
2. **Confusion matrix** — judge × gold, population-reweighted, as a small shaded 3×3
   heatmap. I'll draw it.
3. **κ / agreement callout** — the second-judge headline as a compact stat strip.
   I'll draw it.

*I'd skip the gold-app screenshot* — you asked and I agree. It's a tool, and a screenshot
of a form doesn't convey the thing that's actually clever (the blocked sampling design),
which is better carried by one sentence of text. If you want to show it, keep it as a
phone photo on your laptop for whoever asks how you labelled 122 sites on a train.

---

### §6. Folding citations into the semantic graph (COLUMN 3, top)
**Cap: 200 words.** This is the payoff section — the reason any of the previous work
matters. Don't let it get squeezed.

**What you need to write:**
- The setup: two graphs over the same 152 papers, answering different questions.
  Citation = paper→paper, a fact. Semantic = contribution→contribution, an LLM assertion.
  Roll the 989 semantic edges up to **653 paper-pairs** and intersect with the **524**
  citation pairs.
- **They barely overlap: 535 semantic-only, 406 citation-only, 118 both.** Frame this
  as the good news it is — they're complementary, not redundant. A citation graph alone
  misses parallel work that never cites; a semantic graph alone invents relations.
- **The finding that justifies the taxonomy choice:** of the 26 shared pairs your judge
  typed `compares_contrasts`, **only 4** carry any semantic `contradicts`. The critique
  signal you spent six weeks extracting is almost entirely invisible to the semantic
  pass. That is the argument that the contrast class earns its keep.
- **Direction:** citation direction agrees with the semantic arrow on 66 pairs and
  disagrees on 52 — i.e. the LLM's `builds_on`/`refines` arrow is close to a coin flip,
  and citation direction is a deterministic, free fix. On the audited `uses_extends`
  pairs the citation direction was right **33/33** (and 8/8 on the gold-only subset).
- **The hand-inspection result — this is the part only you can write.** You went through
  the divergent pairs one at a time and classified each as
  *complementary / semantic-wrong / citation-wrong / rollup-artifact*. The dominant
  verdict was **complementary**: the two signals were describing different facets, not
  contradicting each other. Give one concrete case — the MLEvolve→AlphaEvolve pair is
  perfect, because it is genuinely **both** `builds_on` **and** `contradicts` (extends the
  paradigm *and* claims to beat it), and a majority-vote rollup would have hidden the
  tension.
- **The conclusion you actually reached**, which is nicely conservative and worth stating
  as such: citation signal is best used as **complementary evidence and as a direction
  fix — not as a relabel.** And you have evidence it works: when the graph was relabelled
  *with* citation evidence visible, `uses_extends` pairs became `builds_on` **89%** of the
  time, and several of your previously-annotated pairs corrected in the right direction.

**Visuals:**
1. **The overlap diagram** — a proportional two-circle Venn: 535 / 118 / 406. Simple,
   instantly readable, carries the "complementary" message on its own. I'll draw it.
2. **The intent × relation cross-tab** — small 3×4 table with the `compares_contrasts` ×
   `contradicts` cell (4 of 26) highlighted. I'll draw it.
3. **Your citation-intent viewer screenshot.** *This* is where your own viewer belongs —
   it's the artifact that shows both layers at once, and by this point in the poster the
   reader knows what the layers are.
   *Screenshot brief:* `experiments/edge_quality/out/view_intent.html`. Turn **both**
   layers on, then use the filter to **isolate the overlap** — the whole hairball at A0
   will look like noise. A dozen papers with solid intent-coloured citation arrows and
   dashed semantic edges, ideally including one pair carrying both a
   `compares_contrasts` citation and a `contradicts` semantic edge. Legend visible.
   Save as `figures/view_intent.png`.
   You mentioned it's a bit outdated — that's fine, it's illustrative here, not a result.
   If it screenshots badly, say so and I'll swap in a hand-drawn TikZ schematic of the
   two-layer idea instead, which might actually read better at A0 anyway.

---

### §7. Graph vs. web ideation (COLUMN 3, middle) — *optional*
**Cap: 130 words.** Only if you have time. It's a genuinely good hook but it has **no
result yet**, and a poster block that promises a comparison and delivers no number is
worse than no block at all.

**How to make it honest and still interesting:** present it as *design + pilot findings*,
not as results. The pilot findings are real and they're methodologically interesting,
which is the right register for this audience.

**What you'd write:**
- The question: does an LLM exploring **the Prior atlas** produce more novel, better
  grounded research ideas than the same LLM exploring **the open web**? Same seed topic,
  same task, same output schema, same generator (Sonnet 5); only the environment differs.
  Blind pairwise judging by a stronger model (Opus 5), order-swapped.
- **Pilot finding 1 — blinding failure.** 9 of the first 10 ideas leaked which arm they
  came from (the graph arm cited internal node IDs; the web arm said "web search"). Fixed
  with an explicit blinding contract plus an automated leakage gate before judging.
- **Pilot finding 2 — the arms converge.** 3 of 4 seeds produced the *same core idea* on
  both sides, because the corpus **is** the public literature the web arm finds. Root
  cause turned out to be that the graph arm wasn't using the graph — over 4 runs it
  called `get_edges` once and the citation tools zero times. It was using the atlas as a
  private search index over the same papers.
- **Pilot finding 3 — the fix, and why it's the interesting one.** The fix was *not* to
  force the model down an edge; it was to make structure **advertise itself** (surface
  typed-relation breakdowns and citation counts in every tool result, add citation
  navigation from a paper). After that, edge traversal rose to 3–4 calls per run and 3 of
  4 seeds diverged from the web arm.
- Current status, stated plainly: **10 graph / 10 web ideas generated; judge not yet
  built.** Cost is comparable across arms (~$0.46 vs ~$0.41 per idea), so the claim under
  test is *better ideas at similar cost*, not *cheaper*.

**Visual:** a small two-row arm-comparison table (environment / tools / explore calls /
seconds / cost). I'll draw it. Keep it minimal — it's a status box, not a result box.

**If you're short on time, cut this section.** §6 expands to fill the space and the
poster is stronger for being a complete story rather than a broad one. I've built
`poster.tex` so this block can be commented out with a single line.

---

### §8. Takeaways / what's next (COLUMN 3, bottom)
**Cap: 100 words, as 4 bullets.** Write these last, and write them as the four things
you'd want someone to repeat to their supervisor afterwards.

My suggested four (edit freely):
1. A three-class intent taxonomy chosen by *downstream action*, not by convention —
   and validated at **95% / macro-F1 0.892** against a blind gold set.
2. A rubric, not a model, was the lever: the interesting constraint inverted from
   "don't classify" to "must classify", and the fix for over-firing was to state a class
   **positively** rather than to forbid its neighbour.
3. The citation and semantic graphs are **complementary** (118 of 1,059 pairs shared);
   citation signal is best as evidence and direction, not as a relabel.
4. Next: fold intent into the cartographer's prompt and measure whether `contradicts`
   precision moves off 36%.

---

## 3. Figure inventory

| # | figure | where | source | status |
|---|---|---|---|---|
| F1 | Prior atlas screenshot | §1 | `data/atlas/view_global_d3.html` | ⬜ **you** → `figures/atlas.png` |
| F2 | Taxonomy comparison table | §2 | — | ✅ me, TikZ |
| F3 | Pipeline strip | §3 | — | ✅ me, TikZ |
| F4 | Prompt v2→v3→v4 strip | §4 | `prompt_changes.md` | ✅ me, TikZ |
| F5 | Gold accuracy panel + CI | §5 | `out/gold_eval.md` | ✅ me, TikZ |
| F6 | Confusion matrix (reweighted) | §5 | `out/gold_eval.md` | ✅ me, TikZ |
| F7 | κ / second-judge stat strip | §5 | `out/second_judge_intent.md` | ✅ me, TikZ |
| F8 | Overlap Venn 535/118/406 | §6 | `out/graph_overlap.md` | ✅ me, TikZ |
| F9 | Intent × relation cross-tab | §6 | `out/graph_overlap.md` | ✅ me, TikZ |
| F10 | Citation-intent viewer screenshot | §6 | `out/view_intent.html` | ⬜ **you** → `figures/view_intent.png` |
| F11 | Ideation arm-comparison table | §7 | `out/generations.jsonl` | ✅ me, TikZ |

**Your two screenshots are the only blocking items.** Until they arrive, `poster.tex`
renders labelled grey placeholders at the exact final size, so the layout is already
correct and nothing shifts when you drop the real images in. Put them in
`Callum_poster/figures/` with those filenames and they'll appear automatically on the
next rebuild.

Screenshot technique, so they don't look bad at A0: maximise the browser window on the
largest display you have, zoom the page **out** rather than resizing the window (keeps
the labels sharp), and use Win+Shift+S to crop. Anything under ~1600 px wide will look
soft when blown up to a 300 mm-wide poster block.

---

## 4. Things I'd deliberately leave off

Stated so you can overrule me rather than wonder whether I forgot:

- **The megablob bibtex bug.** Genuinely good detective work (54/525 edges, 6.8× lift in
  `does_not`), but it's an upstream data bug, it needs 100 words to explain, and it
  doesn't advance the narrative. **Keep it in your pocket** — it's the perfect answer to
  "did you find anything unexpected?" and it lands much better spoken than written.
- **The full-text escalation experiment.** A clean negative result (0/6 verdicts changed)
  but it's a dead end you correctly parked.
- **Claim localization.** Same reasoning — a real, modest result (24/117 changed) about a
  sub-component, and it's specifically *not* used for intent, which makes it confusing to
  mention.
- **The support/priority distributions.** They're computed and they're fine, but intent
  is the story. One clause in §3 noting they exist as secondary axes is enough. The one
  fact from them worth keeping is the orthogonality result — **65% of
  `compares_contrasts` sites still `support` their local claim** — because it proves
  intent isn't redundant with verification. I've put that in §2 as a single line.
- **Klara's parallel work / the branch topology.** Important to you, invisible to the
  audience.

---

## 5. What I need from you, in priority order

1. **Write §1, §2, §4, §6 in `POSTER_CONTENT.md`.** These are the four where your voice
   and your reasoning genuinely matter. My drafts are there as scaffolding — overwrite
   them.
2. **Take the two screenshots** (F1, F10). These block nothing else, but they're the
   slowest thing to chase at the end.
3. §3, §5, §7, §8 you can leave as my drafts for the first pass — they're mostly numbers
   and structure, and I've written them to be defensible as they stand. Come back and
   put them in your own words when the first four are done.
4. Tell me the **title, your name, and the affiliation line**, and whether §7 is in or
   out.
