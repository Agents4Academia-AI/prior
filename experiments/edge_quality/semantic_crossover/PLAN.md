# Semantic crossover — can citation signal improve the Cartographer?

*Exploration only. No changes to `src/prior/cartographer.py` yet. Goal: understand
the Cartographer, then decide whether (and how) the enriched citation graph
(intent / support / priority) can make its semantic relations more trustworthy.*

Companion files in this folder:
- `select_cases.py` → `overlap_cases.md` — hand-inspection set of divergent overlap pairs.
- Upstream: `../out/graph_overlap.md` (the quantitative overlap), `../../../MILESTONE_2_QUICKSTART.md`,
  `../ONBOARDING.md` (task 4: stamped-vs-unstamped), `../out/view_intent.html` (the two-layer viz).

---

## 1. What the Cartographer does (as built today)

Source: `src/prior/cartographer.py` (+ `consensus.py`, `reader.py`, `models.py`).

Prior ingests papers, the **Reader** turns each paper into **contributions** (§2),
and the **Cartographer** draws the *global* graph: typed relations between the
contributions of *different* papers. It is the step the onboarding calls the weak
link — relatedness is mostly real, but the relation **type** is often wrong.

**The pipeline (`cartographer.build` → `_relate_global`):**

1. **Candidate generation** — for each contribution, assemble a small set of
   other-paper contributions to consider, from two sources ("citations propose,
   text disposes"):
   - **citation backbone**: contributions of papers this paper actually *cites*
     (and that we hold) — `paper.referenced_works`.
   - **text neighbours**: **BM25** top-`RELATION_NEIGHBORS` (=6) nearest
     contributions by bag-of-words over `problem+method+result`/statement.
   Pairs are de-duped so each unordered pair is labelled once.
2. **Relation labelling** — one LLM call per source contribution (`_label`,
   `SYSTEM` prompt) sees the source statement + the numbered candidate statements
   and emits a relation for each pair it thinks holds, from
   **`builds_on / refines / contradicts / contrast / supports / mentions`**
   (`GLOBAL_RELATIONS`), plus a one-line reason and confidence. "Most pairs are
   unrelated — omit those." Default model `CARTOGRAPHER_MODEL` (Sonnet).
3. **Provenance stamp** — `source = both` if a citation links the two papers,
   else `text` (uncited parallel work — what pure-citation tools can't find).
4. **Consensus / trust** (`consensus.py`) — each edge gets a `trust` score and an
   `agreement.tier`. Default one-pass: `trust = 0.7·confidence + 0.3·similarity`,
   tier = triple/double/single by whether confidence and embedding similarity are
   both strong. Opt-in Opus arbiter (`PRIOR_CONSENSUS_OPUS=1`): Opus re-labels and
   gates; tiers become triple/double/opus_only.

**Key properties for us:**
- The label is decided from **contribution statements only** — the LLM does *not*
  see the citing sentence, the citation intent, or whether the citee backs a
  claim. (The citation is used only to *propose the pair* and stamp provenance,
  never to *type* the edge.) **This is the seam the citation signal can fill.**
- The shipped v0.2 bundle (`contributions_core_consensus.json`, 989 edges) is
  ~70% `supports`, ~21% `builds_on`, 7% `contradicts`, ~1% `refines`; the
  `contrast`/`mentions` classes did not survive into it. `contradicts` precision
  was measured at ~36% (2 of 3 wrong).

## 2. What is a "contribution"? (is it a well-defined object?)

Yes — it is a concrete dataclass, but its *content* is LLM-judged, so treat it as
"well-typed, soft-valued." Definition (`models.Contribution`, produced by
`reader.py`):

> One research contribution **of a paper** — the paper's *own* work, not
> background it cites — as a single self-contained **`statement`**, a **`kind`**
> from a fixed vocab (`empirical_finding · framework · method · benchmark ·
> dataset · model · analysis · resource · system · other`), and a verbatim
> **`quote`** from the text that grounds it.

- **Identity:** `id = "<paper_id>::k<NN>"` (e.g. `openalex:W4402952666::k00`). This
  is exactly why we can roll semantic edges up to paper pairs — split on `::`.
- **Count:** papers here have **2–5** contributions (mean **3.8**). So a paper is
  *several* nodes in the global graph, and one paper→paper citation can face
  *multiple* contribution→contribution semantic edges (the rollup issue we already
  handled with presence-counting + severity).
- **Grounding:** each carries a `grounding` score (token recall of the quote vs
  source); the corpus mean is ~0.95, i.e. nodes are trustworthy even where edges
  are not.
- **Not fully canonical:** the *statement* is a model paraphrase and the *kind* is
  a model choice, so two runs could word a contribution differently. It is a
  stable object within a bundle, not a platonic invariant of the paper.
- Related but distinct: a **`Claim`** is the finer *local* layer (atomic verifiable
  statements within one paper, linked up to a contribution). The Cartographer
  works at the contribution level, not the claim level.

## 3. The idea we're testing

The citation graph answers *why X cites Y* (intent) and *does Y back the claim*
(support); the Cartographer answers *how do X's and Y's contributions relate*.
Different questions — but the citation signal is computed from the **citing
sentence**, which is exactly the evidence the Cartographer never sees. So the
hypothesis is: **citation intent/support is a strong, cheap prior on the semantic
relation type** — most useful precisely where the semantic pass is weakest
(`contradicts`, direction).

The quantitative overlap (`../out/graph_overlap.md`) is consistent with this: the
semantic graph is 70% `supports` and barely fires `contradicts`, so the
contrast/critique the intent axis captures is largely invisible to it.

## 4. Initial improvement ideas (unbuilt — for discussion)

Ordered by value-for-effort. None touch `cartographer.py` yet.

1. **Intent as a typing prior in the prompt.** When a candidate pair is
   citation-linked, inject the intent + the citing sentence into `_label`'s user
   message ("A cites B; the citing sentence is '…'; intent=compares_contrasts").
   Cheapest lever; directly attacks wrong_type. (This is essentially the
   onboarding's Arm **C**, but using our *validated* intent label rather than raw
   context.)
2. **A verification/trust stamp on the edge, not a re-type.** Carry `support`
   (does the citee back the claim) + `bibtex_valid` as a new trust tier on
   citation-backed edges — the WEEK_2 "verification stamp". Lets the viewer /
   downstream weight or gate edges without changing their type. Low risk.
3. **Direction from citation, not the model.** The onboarding + our overlap both
   say the model's `builds_on`/`refines` arrow is noisy (66 vs 52 agreement).
   Citation direction (citing→cited) is a cleaner default orientation for lineage
   edges. Deterministic, no LLM.
4. **Intent→relation soft map as a candidate re-ranker or tie-breaker**
   (`uses_extends`→`builds_on`, `compares_contrasts`→`contrast`/`contradicts`,
   `background`→`mentions`/weak `supports`). Use as a prior/consistency check, not
   a hard overwrite.
5. **Measure, don't assume (onboarding task 4).** Re-judge stamped vs unstamped
   semantic edges. Powered for overall precision (225 vs 764); underpowered for
   the `contradicts` headline (n=16) — see `../out/graph_overlap.md` §7.

**Risks / open issues to hold in mind:**
- Coverage is partial — only 118 of ~1059 paper-pairs overlap, and intent is a
  paper-level label while the Cartographer types *per contribution pair*; a paper
  cites another for one contribution but relates via a different one (Case E, the
  buried `contradicts`, is exactly this).
- `background` (77% of intent edges) is a weak prior — it does not tell the
  Cartographer much.
- Don't prompt-tune the Cartographer against our own intent judge and then
  "validate" with it — that's circular. Keep the blind Opus judge as referee.

## 5. The exploration set (`overlap_cases.md`)

`select_cases.py` pulls the divergent overlap pairs into five buckets — the point
is to decide, per case, **wrong vs. complementary**:

| bucket | divergence | question |
|---|---|---|
| **A** (22) | citation `compares_contrasts`, semantic no tension | citation over-firing, or semantic missed a critique? |
| **B** (7) | citation `does_not`/`inconclusive`, semantic `supports` | which is more informative? |
| **C** (4) | citation `compares_contrasts` **and** semantic `contradicts` | positive control — do they corroborate? |
| **D** (7) | citation `uses_extends`, semantic no lineage edge | did the semantic pass under-call a dependency? |
| **E** (1) | semantic mixed, a `contradicts` buried under `supports` | what does the model say clashes? |

Early read (Case C1, MLEvolve→AlphaEvolve) already shows the thesis: the pair is
genuinely **both** `builds_on` **and** `contradicts` (MLEvolve extends the
AlphaEvolve paradigm *and* claims to outperform it). Not a disagreement — the
citation's `compares_contrasts` and the semantic `contradicts`/`builds_on` are
complementary facets, and a majority-vote rollup would hide the tension.

## 6. Decisions (2026-08-12) & the current next step

Locked with Callum:
- **Mode: exploration only** — no `cartographer.py` changes; any prototype lives
  in a sidecar script in this folder.
- **Vocabulary: the shipped 4** (`supports / builds_on / refines / contradicts`).
  So the intent→relation intuition is `uses_extends`→`builds_on`,
  `compares_contrasts`→`contradicts`, `background`→weak `supports`. (`contrast`/
  `mentions` are out of scope for now.)
- **Immediate next step: annotate `overlap_cases.md`.** For each case set
  `Verdict` ∈ {complementary, semantic-wrong, citation-wrong, rollup-artifact}
  + a one-line note. This is cheap and decisive: the tally tells us whether the
  divergences are mostly *added information* (→ citation signal is a good prior,
  worth prototyping idea 1) or mostly *rollup artifacts / citation errors* (→ less
  promising). The annotation vocabulary is defined at the top of the cases file.

Deferred (revisit after the annotation tally): prototype idea 1 offline on the
118 overlap pairs; the deterministic direction analysis (idea 3); onboarding
task 4. See §4 for all of them.

## 7. Still-open questions (not blocking the annotation)

- Once annotated: if divergences are mostly `complementary`, do we want the
  citation signal to (a) re-type edges, or (b) only add a trust/verification
  stamp and fix direction? (a) is higher-risk.
- For direction: make citation direction authoritative for lineage edges, or keep
  it a soft prior? (deterministic either way — decide when we get to idea 3.)
