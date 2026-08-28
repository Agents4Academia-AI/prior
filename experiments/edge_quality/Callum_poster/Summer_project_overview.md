# Summer project overview — citations as evidence in Prior

*Callum, 6 weeks, branch `callum/verification`. Written 27 August 2026 as the
complete record behind [`POSTER_FINAL.pdf`](POSTER_FINAL.pdf), which shows about a
fifth of it.*

This document walks the whole project in the order it happened: from picking up
RefWarden and porting reference resolution, through typing and validating a
citation layer, folding that layer against Prior's semantic graph, and finally
two experiments that ask whether the resulting atlas is actually *useful* — an
ideation study and a question-answering study. Every claim points at the file that
holds the evidence. Section 13 is a flat index of every artifact if you would
rather jump.

**Reading order if you only read three things:**
[`REFERENCE_RESOLUTION.md`](../../../REFERENCE_RESOLUTION.md) (what M1 built),
[`MILESTONE_2_QUICKSTART.md`](../../../MILESTONE_2_QUICKSTART.md) (the core of the
work), [`question_answering/RESULTS.md`](../../question_answering/RESULTS.md)
(what it was good for).

---

## 0. The one-paragraph version

Prior reads a corpus of 152 AI-for-science papers and draws a graph of typed
relations between their contributions. Every one of those relations is *inferred*:
a model reads two claims and asserts `supports` / `builds_on` / `refines` /
`contradicts`, without ever seeing whether the two papers acknowledge each other.
Citations are the evidence it is missing. Over the summer I built the citation
layer that supplies it — resolved the edges, typed all 809 citing passages with a
three-class intent taxonomy, and validated that classifier three independent ways
(a silver standard, a blind stronger second judge at κ = 0.79, and a hand-labelled
gold set at 95.0%). I then measured how the two layers relate, and ran two
experiments to test whether an agent given the combined atlas does better work
than the same agent given a browser. On structure-seeking questions it does: the
atlas wins 5 of 6, loses both controls it was predicted to lose, and gains +2.50
groundedness over closed-book against a browser's +1.83, with 0 fabrications in 57
named papers.

---

## 1. The starting point

### 1.1 What already existed

The repo and the `exp/edge-quality` workbench were Klara's. Before I touched
anything, the branch already held:

| | |
|---|---|
| the data bundle | `data/prior-core-v0.2` — 152 papers, 581 grounded contributions, 989 consensus semantic edges ("Arm A", the shipped public graph) |
| citation mining | `fetch_arxiv_bbl.py`, `scan_fulltext_citations.py`, `backfill_citations.py`, `merge_citations.py` → `out/citations_core.json` (661 edges) |
| citation contexts | `extract_citation_contexts.py` → ±320-char windows around `\cite{}`, with `[CITED:TARGET]` markers |
| the edge-quality experiment | arms A/B/C, a blind judge (`judge_edges.py`), `diff_arms.py`, `temporal_holdout.py` |

The baselines I inherited are all in [`ONBOARDING.md`](../ONBOARDING.md) — worth
reading in full, because it is the document that frames the entire project. The
numbers that mattered most:

- **Relatedness is real; type is the weak link.** Correct + wrong-type ran 69–77%
  across arms, i.e. the model usually picks a genuinely related pair and then
  mislabels the relationship.
- **`contradicts` precision was 9.6%** on the shipped graph, rising to 36% with
  pairwise decomposition. Two of three `contradicts` edges are still wrong.
- **Only the citation-aware arm was anticipatory** in the temporal holdout
  (median antecedent percentile 0.755 vs ~0.50 chance for the semantic-only arms).

That is the argument for the whole summer: the citation signal is what makes the
graph trustworthy, and Prior mines citations without verifying anything against
them.

### 1.2 The scoped project

Bring [citation_verification / RefWarden](https://github.com/Agents4Academia-AI/citation_verification)
— a hackathon agent that answers, for a (claim, citation) pair, *is the reference
real, is the metadata right, does the cited paper actually support the claim* —
into Prior as a first-class stage.

Two documents number the milestones differently.
[`notion.md`](../../../notion.md) is the current framing and the one I followed:

| | notion.md (current) | ONBOARDING.md (older) |
|---|---|---|
| build the citation graph (resolution) | **M1** | "M1 Resolve" |
| type + verify the edges | **M2** (taxonomy) + **M3** (extract & evaluate) | "M2 Verified edges" / "M3 Citation-intent" |
| use typed edges to improve the cartographer | **M4** | "the menu" |

### 1.3 Two constraints that shaped everything

1. **No API key, ever.** All generation and judging runs on my Claude Code
   subscription. Every runner asserts `apply_auth(load_settings()) == "subscription"`
   and aborts otherwise. On a Pro plan (not Max) this also forced `claude-sonnet-5`
   as the default worker model and made every long run resumable — see §11.
2. **`main` is protected.** All work lives on `callum/verification`, which forked
   from `exp/edge-quality` at `1a7286e` and diverged for six weeks. §6.4 is the
   reconciliation.

---

## 2. Timeline at a glance

| date | commit | phase |
|---|---|---|
| 19 Jul | `74ec673` | bring `prior-core-v0.2` bundle onto the branch |
| 22 Jul | `c03e8f5` | **M1** resolution port + the fuzzy-title channel (19 new edges) |
| 26–27 Jul | `f0a518d`, `2ccc77f` | first RefWarden runs over citations; resumable runner |
| 29–30 Jul | `ad628e7`, `5f4c04e` | full support/priority pass (809 sites); intent axis built and run |
| 3 Aug | `b0da2ce` | validation stage A (S2) + stage B (blind Opus second judge) |
| 6 Aug | `6660210` | gold labeller built; 122 sites hand-labelled; accuracy computed |
| 10 Aug | `b08c177` | semantic × citation overlap analysis; multi-gold labeller |
| 13 Aug | `05ade52` | crossover case inspection; disagreement analysis |
| 20 Aug | `2c0bcd3`, `f36f915` | graph-vs-web ideation experiment; poster first draft |
| 20–23 Aug | `fa2cf49`, `d7418ed`, `da99975` | question-answering experiment + visualisations |
| 24 Aug | `2712b25` | QA write-ups, trace figures, post-hoc analysis |
| 27 Aug | *(uncommitted)* | hybrid routing pilot; poster rebuild |

---

## 3. Phase 1 — Milestone 1: reference resolution

**Full write-up: [`REFERENCE_RESOLUTION.md`](../../../REFERENCE_RESOLUTION.md).
Contemporaneous log: [`WORKLOG.md`](../../../WORKLOG.md).**

### 3.1 What I built

A thin, flagged resolution stage wrapping RefWarden, off by default so the shipped
build is unchanged:

| file | role |
|---|---|
| [`src/prior/sources/refresolve.py`](../../../src/prior/sources/refresolve.py) | **Adapter.** Layer 1: raw reference → canonical identity (DOI → arXiv-id → gated fuzzy title) via RefWarden's `MultiSourceResolver`. Layer 2: identity → an *existing* Prior node, by arXiv stem → DOI → normalized title. |
| [`src/prior/sources/refextract.py`](../../../src/prior/sources/refextract.py) | **Extractor.** Channel cascade (caller-mined refs → full-text bibliography → none), plus `_split_blob()` to segment whole-bibliography "mega-records" into individual references. |
| [`src/prior/citelinks.py`](../../../src/prior/citelinks.py) | **Wired stage.** `resolve_and_link(atlas)`: refs → resolve → map → deduped, provenance-tagged `cites` edges. Additive, fail-soft, behind `PRIOR_RESOLVE_CITATIONS`. |
| `pyproject.toml` `[resolve]` extra | RefWarden as a SHA-pinned git dependency (`52c109c`), not vendored. |
| `tests/test_refresolve.py`, `test_refextract.py`, `test_citelinks.py` | offline suites, green; network smokes gated behind env flags |

Two design decisions worth defending out loud: the **explicit-id fallback** (trust
a written-out arXiv id or DOI even when RefWarden's fraud-tuned gate abstains —
correct for *edge building*, which is not fraud detection), and treating
title-twin collisions as a **corpus-side** problem rather than adapter code.

### 3.2 The mistake, and the audit

I first validated the port by running it over `out/citation_map.json` and reported
**16 net-new edges**. That was wrong twice over:

1. **Circular input.** `citation_map.json` is *derived from* Klara's already-
   resolved exact-match pairs. Re-resolving it mostly re-derives her graph and, by
   construction, cannot show fuzzy matching's value — everything in it already
   resolved by exact matching.
2. **Phantom edges.** A per-edge audit cut 16 → **4 genuinely new**. The other 12
   were edges Klara already had, mis-mapped onto a *different-title twin*: the
   arXiv preprint "Towards an AI co-scientist" (`W4416043407`) and its Nature
   version "Accelerating scientific discovery with Co-Scientist" (`W7161731996`)
   are two corpus nodes for the same work. A title-key dedup does not collapse
   them, so they looked new.

Evidence kept for the record in
[`out/resolve_run_report.json`](../out/resolve_run_report.json). The lesson, which
I carried into every later measurement: **dedup must be DOI/arXiv-aware, and a
channel must be tested on inputs it can actually improve.**

### 3.3 The honest test, and the win

The non-circular probe ran fuzzy title matching over the **raw arXiv `.bbl`
bibliographies** of all 102 arXiv papers (96 usable) — references that had to
resolve on their own, with no external per-reference lookup, so ~11 minutes rather
than ~7 hours. Each intra-corpus link is classified by its strongest signal:

| signal | intra-corpus edges |
|---|---|
| `arxiv_id` (exact, already found) | 405 |
| `exact_title` (already found) | 231 |
| **`fuzzy_title` (new channel)** | **35** → 16 already present, **19 genuinely new** |

All 19 checked by hand, 0 twins. Fuzzy caught exactly what exact-substring
matching drops:

- **LaTeX small-caps letter-spacing** — `.bbl` renders titles as `R esearch A gent`,
  `a gent r eview`, `cycle r esearcher`.
- **Subtitle / prefix drift** — a reference cites *"…evaluating frontier AI R&D
  capabilities…"* where the corpus title is prefixed `RE-Bench:` (same for `Robin:`).
- **Wording variants** — *"revolutionizing research **in** novel idea"* vs *"**via**"*.

They land on real intra-corpus hubs the graph was under-counting: AgentReview (×5),
Robin (×4), ResearchAgent (×2), "Can LLMs Generate Novel Ideas" (×2).

Folded in as a **fourth provenance-tagged source** in `merge_citations.py` (add,
don't graph-swap), and I fixed a bug where re-merging flattened existing
provenance tags. Result: `citations_core.json` **661 → 680** edges — `api` 278,
`bbl` 383, `fuzzy_title` 19.

**Artifacts:** [`out/citations_fuzzy.json`](../out/citations_fuzzy.json) (the 19,
provenance-tagged) · [`out/fuzzy_probe_report.json`](../out/fuzzy_probe_report.json)
(per-edge evidence) · [`out/citations_core.json`](../out/citations_core.json) (the
merged graph) · [`merge_citations.py`](../merge_citations.py).

### 3.4 Where it left resolution

Essentially done, and likely moving to the shared `academia-core` library
alongside PDF parsing. Three gaps written down and not closed here: PDF ingestion
for the ~50 non-arXiv citers (no `.bbl`, so the fuzzy probe cannot see them); the
preprint↔published twin merge; and a "RefWarden-without-citation" stage for
Prior's purely semantic edges.

---

## 4. Phase 2 — Milestone 2: typing the citation graph

**Living plan, and the single most important document in the project:
[`MILESTONE_2_QUICKSTART.md`](../../../MILESTONE_2_QUICKSTART.md).**
All result tables: [`out/citation_tables.md`](../out/citation_tables.md).

### 4.1 The deliverable

Turn each bare citation edge into a **typed** edge `(p1, p2, t)` — "p1 cites p2
for reason t" — and verify it. Working set: the **525 edges / 809 claim-sites** in
`out/citation_map.json`, each carrying the join key *and* the citing passage, i.e.
a ready-made RefWarden input. Every citee is already a corpus paper, so RefWarden's
`exists` axis is trivially yes and was excluded.

The final schema:

| field | values | what it answers |
|---|---|---|
| **`intent`** — the primary `t` | `background` · `uses_extends` · `compares_contrasts` | *why* is it cited? |
| `support` (RefWarden `supports_claim`) | supports / partial / does_not / inconclusive | does the citee back the claim? |
| `priority` (RefWarden) | obligatory / helpful | how necessary is the citation? |
| quality gates | `bibtex_valid`, `citee_has_real_abstract`, `context_clean`, `evidence_level`, `model` | is this edge trustworthy at all? |

### 4.2 The taxonomy decision record — why three classes

This is the part of the work that most reads as research rather than engineering,
and it is the guiding test that makes it defensible: **a class earns its place only
if the downstream cartographer would act differently on it.** If two classes
trigger the same action, they merge. Full table in
[`MILESTONE_2_QUICKSTART.md` §7](../../../MILESTONE_2_QUICKSTART.md):

- `background` — **keep**. Most common; the anchor that maps onto Semantic Scholar
  for a free eval; a weak/context edge downstream.
- S2 `method` / ACL `uses` + ACL `extends` — **merge into `uses_extends`**. The
  cartographer acts identically on "uses" and "extends"; splitting is pure label
  cost. This is the `builds_on` prior.
- ACL `compare-contrast` / scite "contrasting" — **keep as `compares_contrasts`**.
  Highest value, because it priors Prior's single noisiest relation (`contradicts`,
  36% base precision) — **and S2 has no contrast class at all, which is the concrete
  reason we need our own judge rather than a free label.**
- S2 `result` — **drop** (ambiguous, no distinct action). ACL `motivation` /
  `future_work` — **drop into background** (rare here, not distinct dependencies).

Three functional classes is the minimum that (a) maps back onto S2 for a free
eval and (b) gives the cartographer a distinct action per class.

### 4.3 Support and priority (`type_citations.py`)

All 809 sites, abstract-only evidence (L0), subscription, clean finish, mixed
model (240 Opus + 569 Sonnet, after Opus exhausted the Pro window at site 280).

| level | supports | partial | inconclusive | does_not |
|---|---|---|---|---|
| SITE (n=809) | 63.8% | 21.8% | 7.9% | 6.6% |
| EDGE (n=525) | 72.8% | 16.4% | 4.8% | 6.1% |

Priority: 52.3% obligatory / 47.7% helpful at site level. Mean confidence 0.69.

One caveat measured and then retired: **`priority` is model-sensitive** (Opus 72%
obligatory vs Sonnet 44%); `support` is model-stable. Output:
[`out/citations_typed.json`](../out/citations_typed.json).

### 4.4 Three investigations that came out of the `does_not` bucket

These are the parts I would defend hardest, because each one is a negative result
that saved work.

**(a) The megablob bibtex bug — a data-pipeline fault, not model misuse.**
Root-causing the 53 `does_not` sites found that ~two-thirds were an extraction
bug: a reference's `bibtex` field runs past its own `\end{thebibliography}` and
swallows an appended `anthology.bib` — the `zhu2025deepreview` field is **127 KB
of fused references**. The resolver then fuzzy-matches over the whole blob, picks
the **wrong** paper, and fans one bad entry out into up to **5 spurious edges**. I
wrote a detector (`bibtex_valid=false` if past `thebibliography`, ≥2 `@`-entries,
≥2 `title=`, or len > 2000): **54 of 525 edges (10%)** are affected, and
`does_not` runs **66% on blob edges vs 10% baseline — a 6.8× lift**. Flags:
[`out/citation_map.bibtex_flags.json`](../out/citation_map.bibtex_flags.json).
Raised as an M1 fix (bound bibitem extraction, gate on `bibtex_valid`, re-resolve
the 54); real `does_not` would drop 53 → ~18. Carried as a **quality gate** in the
meantime rather than silently fixed.

**(b) Full-text escalation — tested and rejected.** Reach: arXiv intro 0/5, full
text 5/5 via eprint/HTML/PDF. Cost was low (chunk-selected, ~450 tokens/claim).
But **yield ≈ 0: full text changed 0 of 6 verdicts**, matching an earlier 1/30
intro result — because stuck claims are mis-localized or framing problems, not
missing-evidence problems. Kept only RefWarden's built-in capped safety net.
Evidence level stays at **L0**. *This is the "we tested it and it wasn't worth the
tokens" result, and it is worth having ready.*

**(c) Claim localization — a real but modest sharpener
([`localize_rejudge.py`](../localize_rejudge.py)).** Every context carries
`target_offset`, the exact `[CITED:TARGET]` position, so the target's own sentence
can be extracted with siblings stripped (mean −59% length). Re-judging the 117
distrust sites: **24/117 changed, all in the correct direction**. It rescued
**8 of 18 clean `does_not`** but only **1 of 35 blob `does_not`** — because when
the endpoint itself is wrong, a claim-side fix cannot help. Adopted as a
sharpener; explicitly *not* the lever for the blob problem. Output:
[`out/citations_typed.localized.json`](../out/citations_typed.localized.json).

### 4.5 The intent axis — the actual M2 deliverable (`type_intents.py`)

S2 cannot supply intent on this corpus (§5.1), so the judge is ours: RefWarden's
`build_relevance_judge()` transport with the **rubric swapped** from "does it
support the claim?" to "why is it cited?" — a prompt change, not new software.

Three decisions that matter:

1. **Run separately from support/priority.** The secondary axes were already good;
   no reason to recompute and risk them.
2. **Full claim window, NOT localized.** Intent needs the surrounding sentences —
   "we build on…", "unlike…" — which localization strips. Instead the rubric tells
   the model that `[CITED:TARGET]` is the one citation to classify and other
   `[CITED]` markers are context.
3. **Site-level, not edge-level.** A paper can cite another five times for five
   different reasons, so the unit is the citing passage; the edge rollup is a
   separate, explicit decision.

**Results (809 sites / 525 edges,
[`out/citations_intent.json`](../out/citations_intent.json)):**

| level | background | uses_extends | compares_contrasts |
|---|---|---|---|
| SITE (n=809) | 665 (82%) | 55 (6.8%) | 89 (11%) |
| EDGE (n=525) | 406 (77%) | 40 (7.6%) | 79 (15%) |

Mean confidence 0.74; 0 unresolved; only 22 sites (2.7%) below 0.6.

**Intent is orthogonal to support, not redundant** — the payoff that justifies the
axis. Even **65% of `compares_contrasts` sites are also `supports`**: a contrast
citation still backs its local claim, so the support axis genuinely cannot see
intent. Of the 53 `does_not` sites, 9 are correctly typed `compares_contrasts`
(genuine critiques the support-only view conflates with misuse) and 30 of the 40
`does_not` + `background` sites sit on blob edges, i.e. the data bug, not
classifier error.

**Two findings that look like problems and are not:**

1. **`uses_extends` is only ~7%, and that is correct.** The corpus is
   intro/related-work heavy, so genuine build-on lives in methods sections that
   are a minority of contexts; and the rubric is deliberately precision-first (a
   false `builds_on` is worse than a missed one). Validated: all 55 are genuine
   first-person adoptions, and sweeping the 665 `background` sites for use-verbs
   found no systematic miss — the model correctly separates *"[TARGET] uses LLMs"*
   (third person → background) from *"we use [TARGET]"* (adoption → uses_extends).
2. **`uses_extends` has a 35% support-distrust rate vs 12% for background.**
   Expected: a methods-adoption citation ("we follow their protocol") makes a
   claim the citee's *abstract* cannot confirm. L0 is the wrong evidence for it.
   → downstream rule: a `does_not` on a `uses_extends` edge is **not** a misuse
   flag, unlike on `background`.

### 4.6 The prompt loop

Four rubric versions, each written against a specific observed failure, with the
full text of each kept in [`prompt_changes.md.md`](prompt_changes.md.md).

The memorable one: v2 was **asymmetric against `uses_extends`** and over-cautious.
The fix that worked was not adding another prohibition — it was **moving a rule
out of a negative instruction and into a positive definition of the other class**.
"Do not classify this as a contrast" left the model guessing where the boundary
was; "the target provides an ingredient, method, formulation, metric, dataset, or
architectural block that the citing paper actively utilizes or adapts" told it
where the boundary *is*. Later versions added explicit tie-breakers for the two
grey zones (baseline-to-outperform → `compares_contrasts`; adopt-their-protocol →
`uses_extends`).

Worth conceding if pressed: versions were selected by inspecting failures, so the
gold set (§5.3) is the only clean measurement of the final prompt.

### 4.7 Known caveats carried forward, not fixed

- **Blob contamination.** 78 sites / 54 edges sit on megablob edges. Intent leans
  on the citing passage so most land in `background` (71/78) and they minimally
  pollute the high-value classes — but the **endpoint is still wrong**. Gate on
  `bibtex_valid`.
- **The baseline-vs-subject-system grey zone.** A competitor you benchmark and
  beat → `compares_contrasts`; a system you adopt as apparatus → `uses_extends`.
  Applied consistently, but this is where residual noise lives.

---

## 5. Phase 3 — validating the intent judge

Three independent checks, deliberately in increasing order of cost and authority.
Rendered results: [`out/validations_results.md`](../out/validations_results.md),
[`out/second_judge_intent.md`](../out/second_judge_intent.md),
[`out/gold_eval.md`](../out/gold_eval.md).

### 5.1 Stage A — Semantic Scholar silver standard ([`s2_intent_eval.py`](../s2_intent_eval.py))

Pure REST, no LLM, no subscription spend. Group our 525 edges by citing paper
(~84 fetches), match `citedPaper.externalIds` back to us, map
`background→background`, `methodology→uses_extends`, `result→(no map)`.

**Result: too thin to grade with, exactly as predicted.** Only 237 of 525 edges
are in S2's reference graph and only **10 carry an intent label** — SciCite has
not run on this 2025–26 frontier, and 22 of 84 citing papers return *empty*
reference lists (The AI Scientist resolves with 0 parsed refs). On the ~9
comparable labelled edges: agreed 6, disagreed 3 — and **on all three
disagreements S2 is the coarser one** (no contrast class; under-called an
adoption; fired `methodology` on a surface "used…evaluate"). Confirms direction
only. Output: [`out/s2_intent_eval.json`](../out/s2_intent_eval.json).

*This is also the concrete evidence for the taxonomy decision: the free label is
not available on frontier work, and where it is, it cannot express contrast.*

### 5.2 Stage B — blind second judge ([`second_judge_intent.py`](../second_judge_intent.py))

A **different, stronger model** (Opus 5) re-labels a stratified 100-site sample
(34/33/33) of the Sonnet output. Same evidence and same `[CITED:TARGET]`
convention, but a **clean-room rubric** — Opus was deliberately *not* given our
tie-breakers, so the two annotators' errors de-correlate — and **blind**: it never
sees our label. Report rendered by
[`report_second_judge.py`](../report_second_judge.py).

**κ = 0.79** (substantial; roughly human–human on citation-intent tasks), 86% raw
agreement on the balanced sample, **81% reweighted** to the true 82/11/7
population mix.

| class | agreement |
|---|---|
| `uses_extends` | **91%** (the class we worried about — the highest) |
| `compares_contrasts` | 88% |
| `background` | 79% (lowest, and the majority class, so it drags the reweighted headline) |

**All 14 disagreements land on known taxonomy boundaries — zero random errors.**
Three clusters: grouped comparison-table rows (5 cases, ours→`background`,
Opus→`compares_contrasts` — a *definitional fork* sitting on the majority class);
survey/concurrent framing (4 cases, where our judge may over-fire); baseline-rerun
adopt-vs-compare (2 cases); plus 2 candidate misses of reuse.

**The disagreement *pattern* is the finding, not the headline number.** Errors
that cluster on a named boundary mean the rubric has a soft edge you can point at
and decide. Errors that scatter would mean the task is not learnable.

### 5.3 Stage C — the hand-labelled gold set (the real accuracy number)

**Tooling: [`gold/`](../gold/), setup in [`gold/README.md`](../gold/README.md).**

I built a small labelling system rather than using a bare spreadsheet, for one
specific reason worth saying out loud: **Apps Script sidebars and custom menus do
not run in the Google Sheets mobile app**, so the usual "Extensions → Apps Script
→ show a sidebar" recipe is desktop-only. Deploying the *same* Apps Script project
as a **web app** gives it a URL, renders a normal mobile page, and still talks to
the sheet server-side. Sheet stays the single source of truth; the labelling
actually gets done, on a phone.

```
export_gold_sheet.py → sheet.csv → one Google Sheet tab (`sites`)
                                       ↓
                        Apps Script web app (phone/desktop URL)
                                       ↓  writes the gold_* columns
                        download the tab → score_gold.py → out/gold_eval.md
```

Labelling is **blind**: the judge verdicts, quality gates and second-judge fields
sit in the sheet for post-hoc analysis but are never sent to the browser. The
queue is **blocked by `sample_type`** so the numbers are computable without bias:

| block | n | purpose |
|---|---|---|
| `random_eval` | 80, in random order | any labelled prefix is still a uniform sample → **unbiased headline accuracy** |
| `disagreement` | 12 of the 14 stage-B hard cases | referees the forks; **excluded from accuracy** |
| `strat_topup` | 30 | tops the rarer classes up to 27 each for macro-F1 |

**Results — 122 sites labelled ([`out/gold_eval.md`](../out/gold_eval.md)):**

| | |
|---|---|
| **random-block accuracy** | **95.0%** (76/80), 95% CI [87.8%, 98.0%] |
| **reweighted accuracy** | **94.6%** |
| **macro-F1** | **0.892** |

| class | precision | recall | F1 |
|---|---|---|---|
| background | 95.2% | 98.4% | 0.968 |
| uses_extends | 91.7% | 82.7% | 0.869 |
| compares_contrasts | 91.3% | 77.6% | 0.839 |

Accuracy by quality gate: `bibtex_valid=True` 94.1% (n=102) vs blob edges 87.5%
(n=8) — the gate is doing something.

**The referee block.** On the 12 hard cases: **ours right 6, Opus right 5, neither
1.** Neither judge dominates on the boundary — and the fork splits by direction:
where we said `background` and Opus said `compares_contrasts`/`uses_extends`, gold
sided with us 5–0; where we said `compares_contrasts`/`uses_extends` and Opus said
`background`, gold sided with Opus 5–0. Both judges over-fire in their own
direction on grouped comparisons.

**Two things a statistics audience will reach for, so have them ready:** sites on
the same edge are **not independent**, so the binomial CI is optimistic; and the
reweighted figure exists precisely because the labelled sample is deliberately not
the population mix. The multi-labeller cross-check (`?who=h` / `?who=k`, blind to
each other and to the judge) was built and wired into `score_gold.py` §6, but only
one labeller's column is filled, so there is **no inter-annotator κ** — an honest
gap, stated in the file itself.

---

## 6. Phase 4 — folding the two layers together

### 6.1 The quantitative overlap ([`graph_overlap.py`](../graph_overlap.py) → [`out/graph_overlap.md`](../out/graph_overlap.md))

Zero LLM cost. Prior holds two graphs over the same 152 papers answering different
questions:

| | citation graph (mine) | semantic graph (Cartographer) |
|---|---|---|
| unit | paper → paper | contribution → contribution |
| nature | **fact** — X cites Y | **assertion** — a model's reading of how two ideas relate |
| labels | intent · support · priority | supports · builds_on · refines · contradicts |

Method: split each contribution id on `::` to roll the 989 cross-paper semantic
edges up to **653 paper-pairs**, then intersect with the **524 citation pairs**.
Cross-tabs are **presence-based** — a pair counts toward *every* relation type it
carries — so nothing is collapsed to a "dominant" label that could bury a rare
relation.

**Finding 1 — the graphs are complementary, not redundant.**

| region | pairs |
|---|---|
| semantic only | 535 |
| citation only | 406 |
| **both** | **118** |

Only 118 of 1059 pairs are shared. Coverage comes first: the citation graph misses
papers with no LaTeX source; the semantic graph adds BM25 text-neighbour pairs
that were never cited (uncited parallel work, which pure-citation tools cannot
find at all).

**Finding 2 — the semantic graph washes out exactly the distinction intent
makes.** The semantic mix is supports 695 · builds_on 212 · refines 9 ·
contradicts 73, i.e. **70% `supports`**. Only 4 of the 26 shared
`compares_contrasts` pairs carry any `contradicts` semantic edge. *Disagreement is
what the model's graph misses, and what a citation states plainly.*

**Finding 3 — the rollup is mostly safe, but not entirely.** 21 of 118 shared
pairs carry more than one distinct relation type, and **4 hide a `contradicts`
under a `supports`**. Handled by presence counting plus a **severity** colour rule
(`contradicts` > `refines` > `builds_on` > `supports`) in the viewer, never by
frequency — so a contradiction is never buried and there is no arbitrary tiebreak.

**Finding 4 — citation direction is the cleaner orientation.** It agrees with the
heavier semantic direction on **66** pairs and disagrees on **52**, consistent with
the known result that the model's `builds_on`/`refines` arrow is noise.

**The naming trap, worth saying out loud:** citation **support** ("does the cited
abstract back this claim?") and semantic **supports** ("do these two contributions
corroborate each other?") are different questions that share a word.

**Feasibility note — and the reason a whole planned experiment was not run.**
"Stamped" = a semantic edge whose paper-pair also has a citation. There are 225
stamped vs 764 unstamped edges, so an overall correct%-lift comparison is
*powered*. But the headline `contradicts`-precision lift is **not**: only **16**
stamped `contradicts` edges exist, CI ≈ ±25pp. Not worth the Opus judge budget on
a Pro plan. Writing that down and stopping was the right call.

### 6.2 Case-by-case inspection ([`semantic_crossover/`](../semantic_crossover/))

The quantitative overlap says *how much* the layers differ; it does not say
*which one is wrong*. [`select_cases.py`](../semantic_crossover/select_cases.py)
pulls divergent pairs into
[`overlap_cases.md`](../semantic_crossover/overlap_cases.md) with a four-way
verdict vocabulary I defined for the task:

| verdict | meaning |
|---|---|
| `complementary` | both correct, describing different facets — the citation adds information the semantic edge lacks |
| `semantic-wrong` | the Cartographer's type is wrong; the citation is the better read |
| `citation-wrong` | the intent/support label is wrong; the semantic edge is the better read |
| `rollup-artifact` | not a real divergence — the citation concerns a *different contribution* of the same paper |

11 pairs annotated by hand
([`queue_annotations.json`](../semantic_crossover/queue_annotations.json)); the
dominant verdict is **`complementary`**, which is the honest headline and a better
result than "the citation corrects the model". The design note for what to build
next is [`semantic_crossover/PLAN.md`](../semantic_crossover/PLAN.md), which
includes a careful read of `cartographer.py` and four ranked, unbuilt improvement
ideas (intent as a typing prior in the labelling prompt; a verification stamp as a
trust tier rather than a re-type; direction from citation rather than from the
model; an intent→relation soft map as a re-ranker).

The reconciled worklist
([`queue_worklist.md`](../semantic_crossover/queue_worklist.md)) is worth a look
for a second reason: when the v12 relabel landed, **5 of my 11 already-annotated
pairs had changed relation** (e.g. `supports → builds_on`, `contradicts →
refines`), so each carried verdict is flagged with whether it still transfers.
That is the kind of bookkeeping that stops a stale annotation being quietly reused
as evidence about a new edge.

### 6.3 Auditing intent against the enriched graph

[`CALLUM_INTENT_GRAPH_AUDIT.md`](../CALLUM_INTENT_GRAPH_AUDIT.md) and
[`out/full_intent_graph_audit.md`](../out/full_intent_graph_audit.md) run four
checks joining the site-level intents to the relabelled v12 contribution graph:

1. **`uses_extends` → `builds_on`** holds strongly: 33/37 pairs (89.2%) on the
   automated audit, 8/10 on the human-gold-only subset.
2. **Direction** is unanimous: 33/33 (and 8/8 on gold) point citing → cited.
3. **Background overinterpretation** is the useful audit queue: 60/140
   background-labelled citations received a *specific* relation, and in 47 of
   those the graph cited the background passage itself as its evidence. Not
   automatically errors — a prioritised review list.
4. **Comparison promoted to contradiction**: 3/48 pairs, all comparing performance
   across *different* domains or configurations, so possibly overstating
   incompatibility. **The human-gold subset does not reproduce this (0/10)**, so it
   is framed as an automated-label audit lead, not a confirmed result.

That last distinction — reporting the human subset separately and refusing to let
the automated number stand alone — is the methodological point of the document.

### 6.4 Reconciling the branches ([`GRAPH_STATE_AND_NEXT_TASK.md`](../GRAPH_STATE_AND_NEXT_TASK.md))

Written 18 August, when Klara's weekend work landed on `dev`/`main` and my
six-week-old branch had to be reconciled with it. The map:

- **The contribution graph was *relabelled*, not expanded.** Same 989 pairs,
  re-typed against grounded quotes, full text and localized citation passages →
  `out/canonical_semantic_candidates_enriched_evidence_v12.json`. **This is the
  canonical semantic layer used everywhere downstream.** A rejected 2188-pair
  citation projection also exists on `dev` and should *not* be called the full
  graph.
- **The citation graph was genuinely expanded.** My 809 sites / 525 edges remain
  canonical (reused verbatim upstream as `callum_complete_809`), plus 294 new
  sites across 119 brand-new paper-pairs, zero overlap → **1103 sites / 643
  pairs**.
- **My `citation_map.json` is stale** (regenerated upstream with bounded
  bibliography extraction — the fix for §4.4(a)).
- A known gap recorded honestly: the 294 new sites' windows carry **no
  `[CITED:TARGET]` markers**, because the marked source was never pushed.

The two-layer viewer built alongside this is
[`out/view_intent.html`](../out/view_intent.html).

---

## 7. Phase 5 — does the atlas produce better research ideas?

**[`graph_vs_web_ideation/PLAN.md`](../../graph_vs_web_ideation/PLAN.md) ·
generated ideas and audit trail:
[`out/REPORT.md`](../../graph_vs_web_ideation/out/REPORT.md)**

### 7.1 The design

Same model, same seed topic, same task, same blinding contract, same output
schema. **Only the environment differs:**

| | GRAPH arm | WEB arm |
|---|---|---|
| environment | the full v12 atlas via [`graph_tools.py`](../../graph_vs_web_ideation/graph_tools.py), local JSON, no network | the open web via `WebSearch`/`WebFetch` |
| tools | `overview`, `search_contributions`, `get_contribution`, `get_paper`, `get_edges`, `get_neighbors`, `get_citations`, `citations_between` | Agent SDK built-ins |
| model | `claude-sonnet-5` | `claude-sonnet-5` |

Judge: `claude-opus-5` (strictly stronger than the generator), pairwise, blind,
order-swapped. Seeds: 26 broad topic labels from TF-IDF + KMeans over the corpus
([`select_seeds.py`](../../graph_vs_web_ideation/select_seeds.py)). Nothing is
pre-chewed: the graph arm has to *discover* the typed relations, the edge `reason`
justifications and the citation intents by traversing.

### 7.2 Three pilots, three real problems found

This is the part worth talking about, because each pilot killed a version of the
experiment that would have produced a meaningless number.

**Pilot v0 (5 seeds) — blinding was broken.** 9 of 10 ideas leaked provenance: the
graph arm cited internal node IDs and said "no edge exists"; the web arm said
"web search shows". Fix: a **blinding contract** in the shared prompt (write a
self-contained proposal, cite prior work *by name*, reveal nothing about tools),
plus [`check_leakage.py`](../../graph_vs_web_ideation/check_leakage.py) as a gate
that must pass before anything is judged. Also fixed the novelty framing: the
graph arm was justifying novelty by "absent from the graph", i.e. corpus-scoped.
Both arms now target novelty against the **broader literature**, and the judge is
the novelty authority — which also neutralises the web arm's live-search
*verification* advantage.

**Pilot v1 (4 seeds) — the graph arm was not consuming the graph.** Over four runs
it called `get_edges` **once** and `citations_between` **zero** times. It was using
the atlas as a private search index over the same papers — which is exactly what
the web arm does, and which explains the second problem: **3 of 4 seeds produced
the same core idea on both sides.** The citation layer, i.e. all of the annotation
work, went untouched, and was in fact half-unreachable (no way to navigate
citations *from* a paper). Fixes, all zero-cost: added `get_citations(paper_id)`;
made `overview` name the two layers and the citation-intent counts; made
`search`/`get_contribution` surface the typed-relation breakdown so structure
advertises itself; rewrote the system prompt to say plainly that the signal lives
in the *relations*, not the isolated contribution text. Convergence is now
**measured and reported, never gated**
([`convergence.py`](../../graph_vs_web_ideation/convergence.py)) — and lexical
cosine badly under-detects it (mean 0.18, flagged 0 of 4 pairs that were in fact
the same idea), so the authoritative "same core idea?" call moved into the judge.

**Pilot v2 (4 seeds) — within-arm mode collapse and topic drift.** The fix worked
(`get_edges` now fires 3–4× per run) but two graph seeds produced essentially the
same idea and one drifted off its own topic. Cause: I had over-primed
"tensions/contradictions" and `overview` dumped all 27 contradictions, so
traversal kept rediscovering the single juiciest structural tension. Fixes:
`overview` now returns two example edges of *each* relation type; the prompt says
all four relations matter equally and "do not force every idea into the same
mould"; and a topic-adherence clause was added to the *shared* task so it applies
to both arms.

**Judge pilot (3 seeds × 2 orders).** Two findings. Scores **compress to 6–8** —
not a judge failure, since every idea is a competent grounded proposal, so 1–4 and
9–10 correctly never fire; the fix is to analyse **paired** within-seed deltas and
to add a **forced comparison** (`more_novel` / `sounder` plus a margin) in the same
call, for free. And **position bias is negligible**: swapping A/B moved a score by
at most 1 point and flipped zero winners, so judging drops from 2× to 1× per seed
with alternating order, halving the cost. The six two-order rows are kept as the
evidence
([`out/judge_v1_bothorders.jsonl`](../../graph_vs_web_ideation/out/judge_v1_bothorders.jsonl)).

### 7.3 Where it got to

**24 of 26 seeds generated on both arms (48 ideas), blinding gate clean on all 48,
judging on the final schema not run.** The generation is done and the report
renders every idea in full; what is missing is the aggregate winrate.

Measured effort, which is a real result on its own:

| arm | ideas | mean explore calls | mean seconds | mean cost |
|---|---|---|---|---|
| GRAPH (Prior atlas) | 24 | **13.5** | 92 | $0.447 |
| WEB (search) | 24 | 4.6 | 104 | $0.406 |

The graph arm explores ~3× more at **comparable cost and slightly less wall
clock**, so the honest efficiency claim is *comparable spend, better-grounded
ideas*, not "cheaper". Total generation spend $20.47. Mean lexical convergence
0.16 (range 0.07–0.30) across the 24 pairs — but see the pilot-v1 note: that
number under-detects real convergence and is a floor only.

**Why it stopped here.** The question-answering experiment (§8) was the same
underlying question — is the atlas worth more than a browser — in a form where a
single question yields an inspectable trace and a registered prediction, rather
than requiring 24 judged pairs before anything can be said. With roughly one rate
window a day, that was the better use of the remaining time. The ideation study is
a complete, resumable build one `python judge.py` away from a number.

---

## 8. Phase 6 — the question-answering experiment

**[`question_answering/README.md`](../../question_answering/README.md) is the front
door. Then [`RESULTS.md`](../../question_answering/RESULTS.md) (everything that
came out), [`ARMS.md`](../../question_answering/ARMS.md) (how answers were
produced), [`JUDGING.md`](../../question_answering/JUDGING.md) (how they were
scored), [`PLAN.md`](../../question_answering/PLAN.md) (the design record and the
registered predictions).**

### 8.1 The question

When a researcher asks something whose answer *is* a piece of graph structure —
*what actually builds on X? do these papers disagree? where did this method come
from?* — does **having** that structure produce a better answer than **searching**
for it?

Three arms, same eight questions, blind judge:

| | |
|---|---|
| **GRAPH** | the v12 atlas through 12 local tools. No web. |
| **WEB** | `WebSearch` + `WebFetch`. No atlas. |
| **NULL** | no tools at all — the model closed-book. **The true baseline.** |

The null arm is the design decision that makes the rest interpretable, and it did
not exist in the ideation study.

### 8.2 The questions, and the controls

Six structural questions plus **two controls the atlas was predicted to lose**,
all registered in [`questions.json`](../../question_answering/questions.json)
before the run and never shown to any arm:

| id | family | question (abbreviated) | expected |
|---|---|---|---|
| q01 | builds-on | which later papers actually *extend* The AI Scientist, as opposed to citing it in passing? | graph |
| q02 | disagreement | is the field agreed that LLMs generate genuinely novel research ideas, or do studies disagree? | graph |
| q03 | disagreement | is "autonomous AI scientists already produce publishable research" contested? | graph |
| q04 | uses-findings | what research is being built on the HypoGeniC findings? | graph |
| q05 | evidence-base | how well does LLM feedback on student drafts actually work — has anyone found it doesn't? | graph |
| q06 | lineage | where did AIDE come from, and who has built on it? | graph |
| **c01** | control, out of scope | what recent work builds on AlphaFold for de-novo protein binder design? | **web** |
| **c02** | control, full text | what score does the best agent get on PaperBench, on which subset, vs the human PhD baseline? | **web** |

**Leading with the controls is the strongest way to present this.** "Six it should
win, two it should lose, and that is exactly what happened" pre-empts the obvious
objection — that I picked the questions. I did, and saying so first is what makes
the rest credible. A result reading "Prior wins 8/8" would be a rigged benchmark.

### 8.3 Two harness bugs, caught and reported

Both are the kind that look like results:

1. **The v1 arms were unsealed.** `out_v1/` is kept but is **not valid for
   scoring**. Every row since carries `off_arm_tools`, and every run asserts it is
   empty.
2. **`submit_answer` was last-wins**, so a model that retried had its *degraded*
   attempt stored — 14 of 24 rows submitted more than once, two submitted eleven
   times, one ending in an 823-char stub with `limits="test"` that the judge then
   scored. Fixed to first-complete-wins with every attempt retained and
   `n_submits` on the row; the two affected rows were regenerated.

### 8.4 The tool-surface redesign, and the cost diagnosis

A fair challenge after v1: *if Prior is a compact representation of the
literature, why did the graph arm not cost less than a web search?* Diagnosis in
[`notes/TOOL_SURFACE_V2.md`](../../question_answering/notes/TOOL_SURFACE_V2.md):
the graph arm pulled 1.7–2× more tokens into context than web search, its cost
*per turn* was **lower** ($0.026 vs $0.046), and it lost purely by taking 2–3×
more turns. Replaying q01 offline showed three faults, all mine:

- **Granularity mismatch** — every question is *paper*-level, every v1 traversal
  tool was *contribution*-level, so covering one paper's relations meant
  `get_paper` and then N× `get_edges`.
- **Flat, unranked returns** — `get_citations` dumped 56 citing papers with no
  ordering.
- **Empty calls** — several `get_edges` returned 2 characters.

The v2 and v3 surfaces aggregate at the paper level (`find_paper`,
`paper_neighbourhood`, `topic_structure`, `edge_reasons`). Two rules I held to:
the deliberately question-shaped option (`papers_building_on`) was **rejected**
because it would have encoded these eight questions, and v3 changed
*serialisation*, not content, so no evidence was added or removed.

### 8.5 Results

24 generations + 24 judgements (8 questions × 3 order-rotated runs, `claude-opus-5`,
blind, sealed), **$11.76 total**.

| q | expected | best | prediction | GRAPH | WEB | NULL |
|---|---|---|---|---|---|---|
| q01 | graph | **graph** (3/0/0) | ✅ | 9.0/8.0/9.0 | 8.0/7.7/8.0 | 7.0/7.7/5.7 |
| q02 | graph | **graph** (3/0/0) | ✅ | 8.7/8.0/8.7 | 8.0/9.0/8.0 | 6.0/8.0/6.0 |
| q03 | graph | **graph** (3/0/0) | ✅ | 9.0/8.0/9.0 | 8.3/8.0/8.3 | 7.0/7.7/7.3 |
| q04 | graph | **graph** (3/0/0) | ✅ | 8.0/7.7/7.7 | 8.0/4.7/7.7 | 5.3/8.0/4.0 |
| q05 | graph | **graph** (3/0/0) | ✅ | 9.0/8.7/8.0 | 7.0/7.7/8.0 | 5.7/3.7/5.3 |
| q06 | graph | **web** (0/3/0) | ❌ **miss** | 8.0/5.0/7.3 | 8.3/8.3/8.3 | 5.7/8.0/5.0 |
| c01 | web | **web** (0/3/0) | ✅ | 2.7/7.7/2.7 | 8.0/7.7/9.0 | 8.0/8.3/8.0 |
| c02 | web | **web** (0/3/0) | ✅ | 7.3/8.3/6.7 | 8.3/7.0/8.7 | 5.7/5.7/5.3 |

*(groundedness / correctness / usefulness, means of three runs)*

**The five things it establishes:**

1. **The atlas beats a browser on the questions it was built for and loses the
   controls it was designed to lose.** 5 of 6 structural, 0 of 2 controls. The
   second half is what makes the first half believable — a judge that handed the
   graph arm the controls too would be measuring fluency, not grounding.
2. **Lift over closed book is the number to quote, not graph − web.** Structural
   groundedness: GRAPH 8.61 / WEB 7.94 / NULL 6.11 → **graph +2.50, web +1.83**.
   Graph − web is only 0.67, below the judge's own noise floor, so it is not
   reported as a result and there is **no win rate anywhere in RESULTS.md**.
3. **The judge is stable on winners and noisy on scores.** 8 of 8 questions had a
   unanimous winner across all three order-rotated runs, but the median widest
   single-axis spread between runs is **1 point**. Any gap at or below that is a
   tie whatever the mean says.
4. **Nothing was fabricated.** All **57** paper titles the graph arm named resolve
   to the 152-paper corpus
   ([`verify_named.py`](../../question_answering/verify_named.py)), and all **9**
   of the judge's `fabricated` flags were overturned on inspection — they were
   real corpus papers published after the judge's training cutoff
   ([`check_fabrication.py`](../../question_answering/check_fabrication.py)). The
   same check is not available for web or null, and that asymmetry runs *against*
   the graph arm.
5. **The compactness prediction failed and the efficiency prediction held.**

### 8.6 The registered prediction that failed

**[`ARMS.md` §6](../../question_answering/ARMS.md).** Falsified twice, on two
successive tool surfaces:

| | GRAPH | WEB | |
|---|---:|---:|---|
| payload chars / answer | 24,533 | 14,314 | graph **1.71× more** |
| exploration calls / answer | 6.8 | 5.8 | graph more |
| cost / answer | $0.236 | $0.447 | graph **half** |
| papers named / answer | 7.1 | 5.5 | graph more |

Three reasons, worked through honestly:

- **(a) The gap is mostly the evidence I deliberately added.** `edge_reasons`
  accounts for 48,513 of the graph arm's 196,265 characters — 25% of everything it
  read — full recorded justification prose, median 1,095 chars per edge. Strip it
  and the graph arm sits at 18,469 against web's 14,314, i.e. 1.29× not 1.71×.
  Which exposes the flaw in the metric: **bytes are not evidence**. A
  6,930-character justification and 6,930 characters of search snippets are the
  same number and not remotely the same thing.
- **(b) The prediction assumed one neighbourhood call per question; the model made
  2.4.** Payload scales with *how interesting the structure is*, not with how well
  it is serialised. A compact API does not make a model incurious.
- **(c) The web arm reads less because search *delivers* less.** The null arm
  settles this: it reads **zero** characters and scores 6.11 groundedness; web
  reads 14,314 and scores 7.94. Web's entire payload buys +1.83, and 88% of it is
  snippets.

**So is Prior a compact representation?** Two claims were tangled. *Compact per
byte returned* — no, and this experiment says so plainly; drop the claim rather
than defend it. *Compact per fact established* — yes, and it is demonstrable, but
not by this experiment. **Reporting a registered prediction that failed is the most
credible thing in the whole write-up.**

### 8.7 The q06 failure — an alias in the edge justifications

**[`NOTES.md` §1](../../question_answering/NOTES.md).** The only one of eight
registered predictions to miss, and the most instructive result in the project.

q06 asked where AIDE came from. The graph arm answered well — correct authorship,
correct descendants, a precise account of two critiques — then wrote one wrong
sentence calling *"Towards end-to-end automation of AI research"* **the original**
AI Scientist. It is a 2026 paper; the original is Lu et al. 2024, which used Aider
and human-written experiment templates. Agentic tree search was **v2's** headline
change. The judge caught it all three runs and it cost the graph arm the question.

**It was not invented; it was inherited.** Replaying the five logged calls
(`python trace.py --questions q06`) shows the model had no room to make it up.
`edge_reasons` returned a recorded justification that **glosses the 2026 paper by
the system name "The AI Scientist"**. Everything the arm wrote is a faithful
restatement of that sentence. The single word it added from its own knowledge was
*"The original"* — and that word is where the claim became false.

**The alias is systematic.** That paper has 42 typed edges; **36 of them call it
"The AI Scientist" in the justification prose**, and one asserts the
identification outright. Meanwhile the corpus separately holds the real 2024
paper, and eleven corpus papers have "AI Scientist" in the title. The edge
labeller used a system name where only a paper id disambiguates.

**What it is evidence of.** It is the honest counterweight to the wins. The
atlas's advantage is that it ships recorded *justifications* rather than bare
adjacency, and the arm reads them carefully — which is why it wins the structural
questions. The cost of that advantage is that **the arm inherits the labeller's
errors as confidently as the labeller's insights, with no marker distinguishing
them.** The poster framing: *Prior does not make a model correct, it makes a model
checkable* — this error traces to one recorded sentence in one edge, which is more
than can be said for the web arm's mistakes.

Cheap fixes, ranked, in the file: put the **year** on typed-relation lines (a 2026
paper called "the original" is a contradiction the model would likely have
caught); **flag alias collisions at build time** (36 of 42 edges is not subtle);
prefix paper mentions in `edge_reasons` with the id the prose refers to. And
explicitly: **do not "fix" this by relabelling and re-running q06** — the
prediction missed and the miss is reported.

### 8.8 The trace figures ([`trace.py`](../../question_answering/trace.py))

Every graph-arm answer logs its tool calls *with arguments*, so `trace.py` can
**replay them against the atlas** — which is deterministic — and draw what the
agent actually touched. Three rings: papers the agent chose, papers whose evidence
it read, papers only listed; a gold outline means the paper reached the final
answer. **They are replays, not illustrations**, which is what makes them evidence
rather than decoration. Reading guide:
[`visualisations_explained.md`](../../question_answering/visualisations_explained.md).
Outputs in `out/traces/` as `.svg`/`.png`/`.json`/`.md`; q01 and q03 are the two
bottom-row figures on the poster.

### 8.9 The mechanical checks

All free, all no-LLM, all rerunnable — the results that no post-hoc correction
touches:

| file | what it proves |
|---|---|
| [`verify_named.py`](../../question_answering/verify_named.py) | every title the graph arm named resolves to the corpus — **0 of 57 fail** |
| [`check_fabrication.py`](../../question_answering/check_fabrication.py) | re-examines every judge `fabricated` flag — **9 raised, 9 overturned** |
| [`check_leakage.py`](../../question_answering/check_leakage.py) | no answer reveals how it was produced — clean on 24/24 |
| [`check_docs.py`](../../question_answering/check_docs.py) | every prompt quoted in ARMS.md and JUDGING.md still matches the code |

### 8.10 The demo ([`ask.py`](../../question_answering/ask.py))

`python ask.py "Which papers actually extend AIDE, rather than just citing it?"`
runs the graph arm on any question, prints the answer, and writes four files: the
answer with a table of every call it made, the exploration figure as vector SVG
that drops straight into PowerPoint, a call-by-call narrative including the **full
justification text of every relationship it read**, and the explored subgraph in
Prior's `GlobalGraph` shape. `--dry-run` is free and shows the exact prompt.
Roughly $0.25 and 30–90 seconds a question; re-asking a saved question replays
from disk for free. **This is the thing to demo on a laptop.**

### 8.11 Limits, stated first

Full list in [`PLAN.md` §8](../../question_answering/PLAN.md). The load-bearing
ones:

- **Question selection is not blind.** I chose them knowing the graph's shape. The
  controls and the registered predictions are the mitigation, not a fix.
- **The method is three post-hoc corrections deep** — tool surface twice, judge
  rubric once, each made after a result moved against the graph arm. Every old
  number is kept beside the new one and each change is argued from the data model
  rather than from the metric, but a reader is entitled to discount the efficiency
  and judge scores on this basis. That is exactly why the fabrication check, the
  specificity count and the attribution errors in the other arms carry the
  argument — no correction touches them.
- **The judge is noisier than the effect** (measured, not assumed) and **n = 8**.
  This is an illustration with worked examples, not a significance test.
- **c02 is a weaker control than designed.** PaperBench's *abstract* carries the
  headline numbers, which the graph arm read via `get_paper`, so it scored the
  highest correctness of the three arms while honestly declining on the subset
  detail and losing on usefulness. It measured "correct and bounded vs complete
  and slightly wrong", not coverage depth. **c01 remains a clean control** and
  behaved exactly as registered: `find_paper` refused, the arm said it could not
  establish the topic, confidence `low`, and it ranked last.

---

## 9. Phase 7 — the hybrid pilot: what if the agent has both?

**[`hybrid/PLAN_HYBRID.md`](../../question_answering/hybrid/PLAN_HYBRID.md) ·
[`hybrid/FINDINGS.md`](../../question_answering/hybrid/FINDINGS.md) ·
[`hybrid/RESULTS_HYBRID.md`](../../question_answering/hybrid/RESULTS_HYBRID.md)**

The obvious next question: the arms were *sealed* apart, but a real tool would have
both. 4 questions × 2 hybrid variants (`directed`, given an explicit routing
policy; `hands-off`, told only "you have an atlas and a browser, use whichever you
judge appropriate"), judged 3× each against the parent experiment's winner. $4.92
total.

**Four findings, only one of which I predicted:**

1. **Given both, the model stays in the graph.** Eight runs, **two web calls
   total**. The hands-off arm never opened the browser once. It opened with the
   atlas 4 times out of 4 — and picked the right entry point unprompted
   (`find_paper` on the three questions that name a paper, `topic_structure` on the
   one that does not). The registered prediction said it would open with a search
   on at least 2 of 3. **That prediction did not just miss, it inverted.**
2. **The one clear hybrid win was structure-plus-*identity*, not
   structure-plus-coverage.** q03/directed scored the best in the batch
   (9.0/8.7/9.0, 3/3) using twelve atlas calls for the disagreement structure and
   then **one** web call — issued *after* those twelve, targeting a paper the atlas
   had already surfaced — to check who built the thing and what it is. *The graph
   says what relates to what; the browser says what things are.*
3. **Prompting a model to verify does not tell it what to doubt.** The routing
   policy's verification trigger was written specifically for the q06 alias. On q06
   the directed arm **did** fire a verification search — and verified **AIDE**, the
   paper the question was about and the one that was never in doubt, not the paper
   where the alias lived. It reproduced the identical error. Meanwhile the
   hands-off arm, with no policy at all, avoided it. A model verifies what feels
   *salient*, not what is *fragile*. **This is evidence for fixing the data
   (marking alias collisions in the `edge_reasons` payload) over fixing the
   prompt.**
4. **The pilot cannot speak to coverage**, which was the hybrid's main motivation:
   the out-of-corpus control was never run. 92 titles named across eight answers,
   **0 unresolved** — neither hybrid ever left the corpus. The obvious next step is
   c01 and c02 with both variants.

Cost: the hybrid is the graph arm plus about 15% payload and 30% more calls — and
most of that extra is *atlas* traffic, not web traffic. The arms explored the graph
**more** for having an alternative.

**Every margin in all 12 judgements was `slight`.** It is a routing study that
happens to carry scores; the routing is the part that is not noise-limited, and
the routing is what it should be reported for.

---

## 10. Phase 8 — the poster

**[`POSTER_GUIDE.md`](POSTER_GUIDE.md) is the build spec; the sheet is
[`POSTER_FINAL.pdf`](POSTER_FINAL.pdf); the LaTeX first draft is in
[`archive/`](archive/).**

The first draft was LaTeX and had too much text. The rebuild is A0 portrait, two
columns, assembled in PowerPoint from generated SVG figures
([`figsrc/make_figures.py`](figsrc/make_figures.py) → [`figures/`](figures/)),
against one hard rule that drove everything else:

> **Nothing on a figure is smaller than 22 pt on the sheet.**

A figure drawn on a `C`-px canvas placed `M` mm wide gives
`pt = px × (M/C) × 2.8346`. Every figure is drawn on a 1200 px canvas at 368 mm —
one full column — so the multiplier is 0.869 and 26 px of body text lands at 23 pt.
The rule is what forces each figure down to **one idea and a handful of words**,
and it is why the first set of figures (report figures shrunk down, landing at
7.8 pt body text) had to be redrawn and one figure cut entirely.

Five numbered sections, mapping onto this document:

| § | poster section | figure | this doc |
|---|---|---|---|
| 1 | what Prior is, and why citations | atlas screenshot / `p2_two_layers` | §1, §6.1 |
| 2 | three classes, and a judge | `p3_taxonomy_comparison` | §4.2, §4.5 |
| 3 | does it work? | `p6_evaluation_panel` | §5 |
| 4 | folding the layers together | `p7_citation_semantic_venn` | §6.1 |
| 5 | using the graph to answer questions | `p10_qa_scoreboard` + traces `p11` / `p12` | §8 |

Spares drawn to the same rule but not placed: `p9_qa_three_arms` (the three arms
in one strip), `p13_qa_honesty` (the three numbers the result rests on, including
the failed prediction), `p8_intent_relation_crosstab` (mechanism rather than
coverage), `p4_judge_pipeline` (if anyone says the method is not spelled out).

[`POSTER_GUIDE.md` §12](POSTER_GUIDE.md) lists what was **deliberately left off**
with a one-line answer for each if asked — the prompt versions, the bibliography
bug, full-text escalation, the support and priority axes, the referee block, the
gold-labelling tool, the three post-hoc corrections in the QA experiment, and
where Klara's work ends and mine begins. That table is the closest thing to a Q&A
prep sheet.

---

## 11. Method habits that carried across everything

Worth naming separately, because they are transferable and several of them saved
the project from a bad number.

- **Register the prediction before the run.** Every experiment has predictions
  written down first, and the ones that failed (compactness, twice; hybrid
  routing, inverted; q06) are reported in the same table as the ones that held.
- **Build the control you expect to lose.** c01 and c02 are the reason the
  structural wins are believable. The same logic makes the null arm — not the web
  arm — the reference point.
- **Blind everything that can be blinded, and gate it mechanically.** The gold
  labelling UI never receives the judge's label; the second judge never sees ours
  and gets a clean-room rubric; `check_leakage.py` gates the ideation and QA sets
  before a judge is ever called.
- **Separate the fact layer from the assertion layer, and never merge them
  silently.** Citation edges are facts; semantic relations are assertions. Where
  they disagree, the four-way verdict vocabulary (§6.2) forces the question "is
  either one *wrong*?" instead of assuming the newer signal wins.
- **Never let an aggregate bury a rare class.** Presence-based cross-tabs and a
  severity colour rule rather than frequency-dominance, specifically because 4
  shared pairs would otherwise have had a `contradicts` hidden under a `supports`.
- **Measure whether you are powered before spending.** The stamped-vs-unstamped
  `contradicts` comparison was designed, costed, found to be n=16 / ±25pp, and not
  run.
- **Report the negative results.** Full-text escalation changed 0 of 6 verdicts.
  S2 could label only ~4% of our edges. Localization rescued 1 of 35 blob cases.
  Each one closed a direction.
- **Root-cause before blaming the model.** Two-thirds of the `does_not` verdicts
  were a bibliography-extraction bug, not misuse; the q06 error was inherited from
  a recorded justification, not hallucinated. In both cases the trace was the
  evidence.
- **Every long run is checkpointed, resumable, `Ctrl+C`-safe and never persists a
  failure verdict**, because a Pro-plan usage window will run out mid-run. Runners
  pause on a `STOP` file and re-runs resume from the last good site.
- **Every runner asserts it is on the subscription** and aborts if an API key is
  present.

---

## 12. What is not done

Stated plainly, in rough order of value.

1. **M4 — the citation-aware cartographer.** The whole point of the typed layer is
   to discipline the semantic graph, and nothing has yet been fed back into
   `cartographer.py`. The four ranked, unbuilt proposals are in
   [`semantic_crossover/PLAN.md` §4](../semantic_crossover/PLAN.md); the cheapest
   is injecting the validated intent plus the citing sentence into the labelling
   prompt for citation-linked pairs.
2. **The downstream eval that ultimately matters** — does the intent signal lift
   `judge_edges.py`'s `contradicts` precision above its 36% base? Designed, and
   measured as underpowered at n=16 stamped `contradicts` on a Pro budget.
3. **The ideation experiment's judging pass.** 48 ideas generated and gated;
   `judge.py` and the aggregation are built; one command from a number.
4. **The hybrid controls** — c01 and c02 with both variants. If the hands-off arm
   does not search on c01 either, that is a much stronger and much stranger result
   than anything currently in the pilot.
5. **Inter-annotator agreement on the gold set.** The multi-labeller path is built
   and wired; only one labeller's column is filled.
6. **The M1 re-resolve of the 54 blob edges**, which would take real `does_not`
   from 53 down to ~18.
7. **The alias-collision detector** at graph build time (§8.7), which the hybrid
   pilot turned into the highest-value data fix.
8. **PDF ingestion for the ~50 non-arXiv papers** and the preprint↔published twin
   merge — both scoped to `academia-core`.

---

## 13. Index of everything

### Design and record documents

| file | what |
|---|---|
| [`ONBOARDING.md`](../ONBOARDING.md) | the inherited workbench, baselines and backend rules — start here |
| [`notion.md`](../../../notion.md) | the current milestone framing (M0–M5) |
| [`REFERENCE_RESOLUTION.md`](../../../REFERENCE_RESOLUTION.md) | M1 build record, the circular-eval mistake, the fuzzy win |
| [`WORKLOG.md`](../../../WORKLOG.md) | contemporaneous M1 log |
| [`MILESTONE_2_QUICKSTART.md`](../../../MILESTONE_2_QUICKSTART.md) | **the core document** — M2 plan, taxonomy decision record, all results and caveats |
| [`GRAPH_STATE_AND_NEXT_TASK.md`](../GRAPH_STATE_AND_NEXT_TASK.md) | cross-branch map of both graphs after the v12 relabel |
| [`GRAPH_ARTIFACTS.md`](../GRAPH_ARTIFACTS.md) | Klara's canonical artifact declaration |
| [`CALLUM_INTENT_GRAPH_AUDIT.md`](../CALLUM_INTENT_GRAPH_AUDIT.md) | intent vs the enriched graph, automated and human-gold subsets kept separate |
| [`semantic_crossover/PLAN.md`](../semantic_crossover/PLAN.md) | how the Cartographer works, and four unbuilt improvement ideas |
| [`POSTER_GUIDE.md`](POSTER_GUIDE.md) | poster build spec, section drafts, and the "left off / if asked" table |
| [`prompt_changes.md.md`](prompt_changes.md.md) | the four intent-rubric versions in full, with the failure each fixed |

### Code — citation layer

| file | what |
|---|---|
| [`src/prior/sources/refresolve.py`](../../../src/prior/sources/refresolve.py) | reference → identity → Prior node |
| [`src/prior/sources/refextract.py`](../../../src/prior/sources/refextract.py) | reference extraction + mega-blob segmentation |
| [`src/prior/citelinks.py`](../../../src/prior/citelinks.py) | the wired, flagged resolution stage |
| [`merge_citations.py`](../merge_citations.py) | provenance-preserving 4-way merge into `citations_core.json` |
| [`type_citations.py`](../type_citations.py) | support + priority over all 809 sites |
| [`localize_rejudge.py`](../localize_rejudge.py) | claim localization and re-judge of the 117 distrust sites |
| [`type_intents.py`](../type_intents.py) | **the intent axis** — the M2 deliverable |
| [`s2_intent_eval.py`](../s2_intent_eval.py) | validation stage A (Semantic Scholar) |
| [`second_judge_intent.py`](../second_judge_intent.py) / [`report_second_judge.py`](../report_second_judge.py) | validation stage B (blind Opus) |
| [`gold/`](../gold/) | validation stage C — exporter, Apps Script web app, scorer |
| [`graph_overlap.py`](../graph_overlap.py) | citation × semantic overlap, zero LLM |
| [`semantic_crossover/select_cases.py`](../semantic_crossover/select_cases.py) | divergent-case sampler for hand inspection |
| [`gen_validations_results.py`](../gen_validations_results.py) | renders `validations_results.md` |

### Data and results — citation layer

| file | what |
|---|---|
| [`out/citations_core.json`](../out/citations_core.json) | the merged citation graph, 680 edges, provenance-tagged |
| [`out/citations_fuzzy.json`](../out/citations_fuzzy.json) · [`out/fuzzy_probe_report.json`](../out/fuzzy_probe_report.json) | the 19 fuzzy-title edges and their per-edge evidence |
| [`out/resolve_run_report.json`](../out/resolve_run_report.json) | the earlier circular run, kept for the record |
| [`out/citation_map.json`](../out/citation_map.json) | the 525-edge / 809-site working set (**now stale** vs upstream) |
| [`out/citation_map.bibtex_flags.json`](../out/citation_map.bibtex_flags.json) | `bibtex_valid` per edge — the megablob detector |
| [`out/citations_typed.json`](../out/citations_typed.json) · [`.localized.json`](../out/citations_typed.localized.json) | support + priority, and the localized re-judge |
| [`out/citations_intent.json`](../out/citations_intent.json) | **the 809 intent labels** — canonical, reused upstream |
| [`out/citations_intent_incoming_v12_new.json`](../out/citations_intent_incoming_v12_new.json) | 294 sites on 119 new pairs |
| [`out/citation_tables.md`](../out/citation_tables.md) | all three axes and the cross-tabs |
| [`out/validations_results.md`](../out/validations_results.md) | stages A and B rendered |
| [`out/second_judge_intent.md`](../out/second_judge_intent.md) | κ, confusion matrix, all 14 disagreements grouped by pattern |
| [`out/gold_eval.md`](../out/gold_eval.md) | **the gold-set numbers** and every miss with its passage |
| [`out/graph_overlap.md`](../out/graph_overlap.md) / [`out/graph_overlap.json`](../out/graph_overlap.json) | the overlap analysis |
| [`out/full_intent_graph_audit.md`](../out/full_intent_graph_audit.md) | the four checks over all 1103 sites |
| [`semantic_crossover/overlap_cases.md`](../semantic_crossover/overlap_cases.md) · [`queue_worklist.md`](../semantic_crossover/queue_worklist.md) · [`queue_annotations.json`](../semantic_crossover/queue_annotations.json) | hand-inspected divergences |
| [`out/canonical_semantic_candidates_enriched_evidence_v12.json`](../out/canonical_semantic_candidates_enriched_evidence_v12.json) | the canonical enriched semantic layer (989 pairs) |
| [`out/view_intent.html`](../out/view_intent.html) | the two-layer viewer |

### Ideation experiment

| file | what |
|---|---|
| [`PLAN.md`](../../graph_vs_web_ideation/PLAN.md) | design, prompts, and the three pilot audits with their decisions |
| [`graph_tools.py`](../../graph_vs_web_ideation/graph_tools.py) | the 8-tool atlas environment |
| [`arms.py`](../../graph_vs_web_ideation/arms.py) · [`gen.py`](../../graph_vs_web_ideation/gen.py) · [`judge.py`](../../graph_vs_web_ideation/judge.py) | the two arms, the resumable driver, the blind judge |
| [`select_seeds.py`](../../graph_vs_web_ideation/select_seeds.py) · [`seeds.json`](../../graph_vs_web_ideation/seeds.json) | 26 topic seeds from TF-IDF + KMeans |
| [`convergence.py`](../../graph_vs_web_ideation/convergence.py) · [`check_leakage.py`](../../graph_vs_web_ideation/check_leakage.py) | the two gates |
| [`out/REPORT.md`](../../graph_vs_web_ideation/out/REPORT.md) | all 48 ideas in full, effort table, convergence, archived judge pilot |
| `out/pilot_v0/`, `out/pilot_v1/`, `out/pilot_v2/` | every superseded run, kept |

### Question-answering experiment

| file | what |
|---|---|
| [`README.md`](../../question_answering/README.md) | front door, how to run `ask.py`, what the experiment does not show |
| [`PLAN.md`](../../question_answering/PLAN.md) | design, registered predictions, §8 known limits |
| [`ARMS.md`](../../question_answering/ARMS.md) | prompts, the 12 tools, the seal, **§6 why compactness failed** |
| [`JUDGING.md`](../../question_answering/JUDGING.md) | judge prompt, rubric, schema, order rotation, measured noise |
| [`RESULTS.md`](../../question_answering/RESULTS.md) | **every number**, all 24 answers, all 24 judge runs, the call traces |
| [`NOTES.md`](../../question_answering/NOTES.md) | **the q06 alias investigation** |
| [`visualisations_explained.md`](../../question_answering/visualisations_explained.md) | how to read the trace figures |
| [`questions.json`](../../question_answering/questions.json) | the 8 questions, families, expected winners |
| [`qa_arms.py`](../../question_answering/qa_arms.py) · [`qa_gen.py`](../../question_answering/qa_gen.py) · [`qa_judge.py`](../../question_answering/qa_judge.py) · [`report.py`](../../question_answering/report.py) | the pipeline |
| [`trace.py`](../../question_answering/trace.py) · [`ask.py`](../../question_answering/ask.py) | the replay figures and the live demo |
| `verify_named.py` · `check_fabrication.py` · `check_leakage.py` · `check_docs.py` | the four mechanical checks |
| `notes/TOOL_SURFACE_V2.md` · `notes/JUDGE_RUNS.md` | superseded write-ups, kept as the contemporaneous record |
| `out_v1/`, `out_v2_graph/`, `out_judge_v1/` | archived runs — **`out_v1/` is not valid for scoring (unsealed arms)** |

### Hybrid pilot

| file | what |
|---|---|
| [`hybrid/PLAN_HYBRID.md`](../../question_answering/hybrid/PLAN_HYBRID.md) | the two variants, the routing policy, registered predictions |
| [`hybrid/FINDINGS.md`](../../question_answering/hybrid/FINDINGS.md) | **the four findings**, including the verification trigger that fired at the wrong target |
| [`hybrid/RESULTS_HYBRID.md`](../../question_answering/hybrid/RESULTS_HYBRID.md) | every score, answer and judge reason |
| [`hybrid/routing.py`](../../question_answering/hybrid/routing.py) · [`hybrid_gen.py`](../../question_answering/hybrid/hybrid_gen.py) · [`hybrid_judge.py`](../../question_answering/hybrid/hybrid_judge.py) · [`hybrid_report.py`](../../question_answering/hybrid/hybrid_report.py) | the pipeline |

### Poster

| file | what |
|---|---|
| [`POSTER_FINAL.pdf`](POSTER_FINAL.pdf) | the sheet |
| [`POSTER_GUIDE.md`](POSTER_GUIDE.md) | build spec, layout map, placement table, section drafts, Q&A prep |
| [`figures/`](figures/) · [`figsrc/make_figures.py`](figsrc/make_figures.py) | all generated SVG/PNG figures and the script that draws them |
| [`archive/`](archive/) | the LaTeX first draft and its content plan |
