# Cartographer edge-quality — student onboarding

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
  │   merge_citations.py           3-way union → out/citations_core.json (711 edges)
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
