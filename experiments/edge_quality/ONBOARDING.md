# Cartographer edge-quality — student onboarding

> **⚠️ Read this first — what is already done, and what your job is**
>
> 1. **The citation graph is already built.** `out/citations_core.json`
>    (661 deduped, directed intra-corpus edges: 383 bbl-only + 278 api; 680
>    after the fuzzy-title batch landed via merge_citations.py) and
>    `out/citation_contexts.json` (525 pairs) are finished outputs. Do **not**
>    re-run the mining scripts or rebuild the graph with any other tool — treat
>    those files as inputs. Counts in this doc can drift — the JSON's own
>    `coverage.merged_edges` field is the source of truth:
>    `python3 -c "import json; print(json.load(open('out/citations_core.json'))['coverage'])"`
> 2. **Your project starts at the "YOUR PROJECT" section below.** It is to port
>    pieces of Team 2's **RefWarden**
>    ([`citation_verification`](https://github.com/Agents4Academia-AI/citation_verification))
>    into Prior as a *verification* stage — not to run RefWarden standalone, and
>    not to redo citation mining with it.
> 3. If RefWarden's resolver finds citation edges the core graph doesn't have,
>    that's a known coverage gap (fuzzy-title resolution — confirmed: +19 real
>    edges — plus PDF ingestion for the ~51 papers without arXiv LaTeX sources;
>    96/152 yielded bbl/bib) — report the diff, don't silently swap graphs. Note
>    RefWarden counts one row per **(claim, citation) site**; dedupe to directed
>    (citer, citee) pairs and drop out-of-corpus citees before comparing counts.

Welcome! This branch (`exp/edge-quality`) is a complete workbench for the most
valuable open problem in Prior: **making the Cartographer's cross-paper
relations trustworthy**. The public README says it plainly — relations are the
weak link. This branch measures exactly how, and prototypes the fixes. Your job
is to beat the numbers below.

## Context in one paragraph

Prior reads primary literature and builds a *contribution atlas*: each paper's
self-declared contributions (grounded in verbatim quotes), linked across papers
by typed relations (`supports` / `builds_on` / `refines` / `contradicts`, plus
`contrast` / `mentions` in the current vocab). Nodes are good (grounding mean
0.95). Communities are good (independently validated, see below). The relation
*types* are the problem — and they're what makes the atlas more than a
similarity map.

## What's here

```
experiments/edge_quality/
  ├─ Citation mining (LLM-free; already run, outputs in out/)
  │   fetch_arxiv_bbl.py           arXiv LaTeX sources → .bbl/.bib bibliographies
  │   scan_fulltext_citations.py   arXiv-id/title scan of cached fulltexts
  │   backfill_citations.py        OpenAlex + Semantic Scholar APIs
  │   merge_citations.py           3-way union → out/citations_core.json (661 edges)
  │   extract_citation_contexts.py ±320-char windows around \cite{} → 525 pairs
  ├─ Relation labeling
  │   relate_decomposed.py         Arms B/C: ONE pair per LLM call
  ├─ Evaluation
  │   judge_edges.py               blind 3-verdict judge (opus), all contradicts included
  │   diff_arms.py                 what citation-awareness changes (B vs C)
  │   temporal_holdout.py          no-LLM graph-structure eval
  │   make_human_queue.py          blinded human-annotation CSV
  └─ run_overnight.sh              orchestrator; everything checkpoints & resumes
```

Data bundle: `../prior-core-v0.2` — 152 papers, 581 grounded contributions,
989 consensus edges (this is "Arm A", the shipped public graph).

On this machine use `./.venv-exp/bin/python`; elsewhere any Python ≥3.9 with
`numpy rank_bm25 pexpect networkx`.

## The experiment & results (your baselines)

Three arms, same corpus: **A** = shipped graph (batched labeling, 4-way vocab,
no escape valve). **B** = pairwise decomposed (1 pair/call, 6-way vocab, BM25
top-4 universe ∪ A's pairs). **C** = B + citation signal ("X cites Y" + the
sentence around the citation in the prompt; citation-linked pairs added to the
universe).

Blind judge (opus, 250 sampled edges/arm + every `contradicts`):

| arm | correct | wrong type | fabricated | contradicts precision |
|---|---|---|---|---|
| A | 11% | 58% | 31% | **9.6%** |
| B | 17% | 60% | 22% | 36% |
| C | 15% | 46% | 39%* | 36% |

*C attempts harder pairs (citation-proposed ones B never saw); on shared pairs
C has the best type accuracy.

What we learned (details in `out/*.json`, run `diff_arms.py` to reproduce):

1. **Relatedness is mostly real; TYPE is the weak link.** correct+wrong_type =
   69% (A) / 77% (B). The judge's dominant complaint: "shared topic alone is
   not a defensible relation" — topical proximity dressed as evidence.
2. **Decomposition ~4×'d contradicts precision** (9.6%→36%). A's contradicts
   are mostly novelty-framing or different-benchmark comparisons misread as
   clashes.
3. **Citation context recovers lineage.** 35% of citation-informed verdicts
   flip vs B; the top flow is `contrast`→`builds_on` (builds_on: 99 edges in
   B → 514 in C). Authors' own citation sentences are gold for edge typing.
4. **The communities are robust** even where edges are noisy: citation-enriched
   (29% intra vs 18% cross vs 6% random) and stable across edge sets
   (ARI 0.32). Mislabeled edges blur types, not neighbourhoods.
5. **LLM-free forward validation**: semantic pairs too young to cite each other
   are citation-confirmed at 17%, rising to ~30% after a year — 4× the random
   baseline at every age. The graph anticipates the citation record.
6. **Only the citation-aware graph is anticipatory** (temporal holdout: does
   new work attach to already-central early nodes? chance = 0.50 median /
   25% top-quartile):

   | graph | lineage edges | median antecedent pct | top-quartile |
   |---|---|---|---|
   | A (shipped) | 52 | 0.51 | 31% |
   | B (decomposed only) | 42 | 0.46 | 21% |
   | **C (citation-aware)** | **237** | **0.755** | **51%** |
   | C substantive-only | 237 | 0.748 | 50% |

   A and B are null — decomposition alone does NOT restore structure; the
   citation signal is the ingredient that makes the graph a usable prior.
   Honest caveat for any writeup: part of C's signal is inherited
   preferential attachment from the citation network itself, so frame it as
   "semantic-only graphs miss the field's real accumulation structure;
   the citation-aware graph recovers it" — not as magic foresight.
   Reproduce: `temporal_holdout.py --bundle <staged dir>` (staged B/C bundles
   live in `out/b_atlas`, `out/c_atlas`, `out/c_atlas_core`).

## YOUR PROJECT — join citation-verification into Prior

The scoped summer project: bring **RefWarden** —
**[citation_verification](https://github.com/Agents4Academia-AI/citation_verification)** —
(Team 2's hackathon agent: for a (claim, citation) pair — is the reference real,
is the metadata right, does the cited paper actually support the claim?) into
Prior as a first-class stage. Everything below it in "the menu" is supporting
material for this.

Why this project: the experiment results say the citation signal is what makes
the graph trustworthy AND anticipatory (findings 3, 5, 6) — but Prior currently
*mines* citations without *verifying* anything against them. citation-verification
is the missing verifier, already built, already public.

Suggested milestones (each independently shippable):

1. **Port RefWarden's reference resolution into `academia-core`, then wire
   Prior to it.** Lift RefWarden's `grounding/` layer (`resolver.py` +
   `paper_lookup.py`, optionally `url_validate.py`) into the org's shared
   [`academia-core`](https://github.com/Agents4Academia-AI/academia-core)
   library — it's already import-safe, LLM-free, and one-dep (rapidfuzz).
   Credit Team 2 in the module docstring and commit. Scope discipline: the
   grounding layer ONLY — verification stages and `CitationRecord` stay in
   RefWarden. Then Prior consumes it twice: at ingestion (normalized ids +
   a citation channel for the ~51 non-arXiv orphan papers) and as a fourth
   mining source via `merge_citations.py` — extra edges over
   `citations_core.json` are *added with provenance* after the
   dedupe/in-corpus filtering described in the box at the top, never a graph
   swap. (Later, optionally: a PR offering RefWarden the core version —
   their call whether to take it.)
2. **Verified edges** — run c-v-style support checks on Prior's relation edges:
   given the two contributions' verbatim quotes, does the evidence actually
   support the asserted relation? Each edge gains a verification stamp
   ({verified / disputed / unverifiable}) as a new trust tier. The WEEK_2
   "verification-stamp schema" sketch is exactly this.
3. **Citation-intent stage** — apply c-v's support-judgment to the 525 mined
   citation contexts (out/citation_contexts.json): classify each citation as
   supporting / contrasting / mentioning (scite-style) BEFORE relation
   labeling, and feed the intent in as a prior on edge type.
4. **Measure it** — re-run the existing judge harness on stamped vs unstamped
   edges. Success criterion: precision lift on the verified subset (baselines
   in the table above; contradicts precision is the headline number to move).

Stretch: package the stamp schema so ANY atlas (or any org project) can consume
c-v as an enricher — the shared-substrate idea from the org's library RFC
(github.com/Agents4Academia-AI/.github issue #1).

## The menu (roughly in order of value-for-effort)

1. **Rebuild the shipped bundle with the current Cartographer.** The code in
   `src/prior/cartographer.py` already has the two big fixes (the
   `contrast`/`mentions` escape valve + citations-propose-text-disposes), but
   the public v0.2 bundle predates them. Rebuilding + judging is the cheapest
   large win.
2. **A `contradicts` rubric.** Require a genuine empirical/theoretical clash
   (same construct, incompatible findings); the current 36% precision still
   means 2 of 3 are wrong. See `S_SYSTEM` in `relate_decomposed.py` for the
   current wording.
3. **Type definitions.** wrong_type dominates every arm — much of it is
   rubric ambiguity, very fixable with sharper definitions + few-shot examples.
4. **Direction.** The model's builds_on/refines arrow is noise (known result);
   use citation direction > publication date. `relate_decomposed.py` stage 3
   already does this deterministically — port it into the Cartographer.
5. **Richer per-pair evidence for lineage.** Citation contexts helped; method
   sections, shared-benchmark detection, and author overlap are unexplored.
6. **Go deeper on citation awareness — the biggest open seam.** Finding 6
   says the citation signal is what makes the graph anticipatory, and we've
   barely scratched it. Concretely unexplored: using MORE contexts per pair
   (we cap at 2×450 chars); section-position of the citation (intro vs
   methods vs baselines — a strong type prior); citation *intent*
   classification as its own stage (scite-style supporting/contrasting/
   mentioning) before relation labeling; coverage for the ~51 non-arXiv papers
   (no LaTeX source — need another channel); and the two-layer design
   (citation edges as facts, semantic relations as assertions) which is
   sketched in the 2026-07-07 session notes but not built.

There is also a second experiment on this branch: `experiments/vocab_collapse/`
(raw-LLM parametric memory vs the atlas as a census — Artiles et al.,
arXiv:2603.01092 analog). Same harness, same iteration loop; results land in
its `out/collapse_summary.json`.

## Your iteration loop

```bash
# label a small slice with your changed prompt (checkpointed, resumable)
PRIOR_LLM_BACKEND=claude-cli ./.venv-exp/bin/python \
  experiments/edge_quality/relate_decomposed.py \
  --bundle ../prior-core-v0.2 --arm B --limit-pairs 100 --workers 4

# judge it blind
PRIOR_LLM_BACKEND=claude-cli ./.venv-exp/bin/python \
  experiments/edge_quality/judge_edges.py --arms B --sample 100

# compare against the table above
cat experiments/edge_quality/out/judge_summary.json
```

Delete `out/arm?_verdicts.jsonl` to relabel from scratch; otherwise re-runs
resume and mop up failures. Keep changed-prompt runs in separate out dirs (or
rename the checkpoint) so you never overwrite a baseline.

## Backend rules (read this twice)

- `PRIOR_LLM_BACKEND=claude-cli` drives the **interactive** Claude Code TUI via
  a pty — it runs on the Max **subscription**. Do **not** use `claude -p`,
  the Agent SDK, or the API unless you've been given a key: those meter credits.
- The driver has two hard-won fixes (input-swallow at startup, pty-drain during
  polling) — on this branch and in PR #35. If calls start failing with JSON
  parse errors on *every* pair, set `PRIOR_CLI_DEBUG=1` and read the screen
  dump from `$TMPDIR/prior_dbg_*.txt` before theorizing.
- Keep `--workers` ≤ 6 and expect usage-window throttling on long runs;
  everything resumes, so just re-run.

## Conventions

- `main` is protected (PR + CI required). Branch off `exp/edge-quality` for
  experiment work, off `main` for anything heading into the product.
- `out/human_queue.csv` is a **blinded** annotation set — if you're asked to
  label it, do not open `human_queue_key.json` first.
- Never commit `out/eprints/` (cached arXiv sources; gitignored) or anything
  with API keys.

## Reading list

- Public README ("Why now", "Does it hold up?", Limitations) + `ROADMAP.md`
- `docs/EVAL.md` — the eval framework you'll be scoring against
- `docs/CLUSTERS.md` — how communities are computed and validated
- `src/prior/cartographer.py` (the thing you're improving) and
  `src/prior/consensus.py` (how edges get trust tiers)
