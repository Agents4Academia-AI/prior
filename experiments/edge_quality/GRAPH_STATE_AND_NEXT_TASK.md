# Graph state across branches, and what I need for the ideation task

*Written 2026-08-18 (Callum). A map of what the contribution graph and the
citation graph actually are right now, after Klara's weekend work landed on
`dev`/`main` — where every file lives, which of mine are stale, and the exact
file set I need to bring over for the next task (enriched graph as LLM context
for research ideation). Companion to Klara's `GRAPH_ARTIFACTS.md` (her canonical
declaration) and `graph_artifact_manifest.json`.*

---

## 0. TL;DR

- **Two graphs, same 152-paper corpus.** The **contribution (semantic) graph**
  was *relabelled*, not expanded. The **citation graph** was *genuinely expanded*
  (+119 paper-pairs / +294 sites) on top of a *regenerated* citation substrate.
- **`dev` is a superset of `main`** (19 commits ahead, 0 behind — main is fully
  merged into dev). All of Klara's fixes are on both. **My branch
  (`callum/verification`) diverged from `exp/edge-quality` weeks ago**, so it does
  *not* have those fixes except what I've now surgically pulled.
- **My `citations_intent.json` is still canonical** — Klara reused it verbatim as
  `callum_complete_809`. But my **`citation_map.json` is stale** (she regenerated
  it with bounded bibliography extraction).
- **Klara already prototyped my "next task"** in `experiments/graph_ideation/` —
  but it uses the *deprecated* edge set and **no citation signal**. My job is to
  point it at the canonical enriched graph and inject the citation intents.

---

## 1. The contribution (semantic) graph — relabelled, not expanded

| layer | file | where | notes |
|---|---|---|---|
| base bundle | `data/prior-core-v0.2/{papers_core.jsonl, contributions_core_grounded.json, contributions_core_consensus.json}` | **identical** on my branch, `dev`, `main` (same hashes) | 152 papers, 581 contributions, 989 legacy consensus edges. Not regenerated. |
| **canonical enriched graph** | `experiments/edge_quality/out/canonical_semantic_candidates_enriched_evidence_v12.json` | `dev` → **now staged on my branch** | **The one to use.** Same 989 pairs, **relabelled** with grounded quotes + full text + localized citation passages. `edges` (989) + `contributions` (581) + `_meta`. |
| deprecated expansion | `cartographer_rebuild_{candidates.json, normalized.jsonl}`, `fulltext_citation_enriched_v12_graph.json` | `dev` | **2188 pairs** (989 + 1199 citation-only). A rejected top-2 citation projection. *Do not* call this the full graph. |

**Key policy (from `GRAPH_ARTIFACTS.md`):** *"citations provide evidence and
direction; they do not add contribution pairs."* So the enriched v12 is a
**re-typing** of the existing 989 pairs, seeing citation + full-text evidence the
original blind Cartographer never saw. That relabel is why 5 of my 11 already-
annotated pairs changed relation (e.g. `supports → builds_on`, `contradicts →
refines`) — see `semantic_crossover/queue_worklist.md` Part 1.

Each edge: `src, dst, relation, direction, existence_confidence, type_confidence,
evidence_ids, reason, citation_directions, relabel_source`.

---

## 2. The citation graph — expanded on a regenerated substrate

| piece | file | count | where |
|---|---|---|---|
| **my intents (canonical)** | `experiments/edge_quality/out/citations_intent.json` | 525 edges / **809 sites** / 524 paper-pairs | mine; reused by Klara as `callum_complete_809`. *Not* on dev. |
| my typed axis | `citations_typed.json` | support / priority for the 809 | mine. *Not* on dev. |
| **new intents** | `citations_intent_incoming_v12_new.json` | **294 sites** / **119 brand-new** paper-pairs (0 overlap with mine) | `dev` → **now staged on my branch** |
| regenerated resolution | `citation_map.json` | — | `dev`/`main` — **differs from mine (mine is stale)** |
| resolution docs | `CITATION_MAP_REGENERATION_2026-08-13.md`, `CITATION_SUBSTRATE_152.md` | — | `dev` (reference) |

**Full current citation graph = 809 + 294 = 1103 sites / 643 paper-pairs.** That
1103 is exactly what the audit (`audit_full_intent_graph.py`) joined against the
989-pair enriched graph to build the review queue. Intent distribution of the new
294: 248 background, 21 uses_extends, 25 compares_contrasts.

### 2a. The `[CITED:TARGET]` marker gap (the "horrible numbers")
The 294 new-substrate sites' `claim` windows have **no `[CITED]`/`[CITED:TARGET]`
markers** (some are bibliography-list windows — Klara flagged this herself). The
marked source, `citation_contexts_incoming_v12.json`, is **only in Klara's local
worktree** (`/Users/kk1918_1/.../prior-citation-substrate/...`), not pushed. The
pushed `citation_contexts.json` recovers marked windows for only **7** of the 119
new pairs, **none of which are in the queue**. So in `queue_worklist.md` those
windows are now labelled *"raw window — no marker available"* rather than fixed.
**→ To fully fix: ask Klara to push `citation_contexts_incoming_v12.json` (or a
marked export of the 294).**

---

## 3. What Klara did over the weekend (commits + her Slack)

On `main` (merged PRs) — the upstream fixes that make *my* derived files stale:
- **#52 / #55** recover 8 broken abstracts + preserve provenance.
- **#56** bound bibliography entries during citation extraction (the "bibtex
  endings" bug I flagged).
- **#57** regenerate the bounded citation context map → new `citation_map.json`.
- **#54** manifestation-aware citation substrate; **#58** work-identity crosswalk
  (DOI/arXiv aliases); **#59** Scoper search ledger.

On `dev` (eval work, not yet in main):
- Relabelled the 989 pairs with citation+full-text evidence → **canonical v12**.
- Localized +119 citation edges → **+294 intent sites** (`incoming_v12_new`).
- Built the **audit queue** (`full_intent_graph_audit*`) I'm working through.
- Integrated citation evidence into an offline Cartographer relabel (**not** a
  change to `src/prior/cartographer.py`).
- **Prototyped research-gap ideation** in `experiments/graph_ideation/` (§5).

---

## 4. Branch map

```
main ──●───────────────●  (#49..#59: bundle, abstract + bibtex + citation-map fixes, crosswalk)
        \               (fully merged into dev)
dev      ●──────────────●  = main + { canonical v12, incoming_v12_new, audit queue, graph_ideation }
                        ▲ 19 commits ahead of main, 0 behind

exp/edge-quality ──●
                    \  (I branched here ~weeks ago)
callum/verification  ●──────●  MY branch: my citation-intent pipeline (809 sites) + my
                             semantic_crossover work; now + surgically-pulled dev artifacts.
```

**Which of my files are outdated:** `citation_map.json` (regenerated upstream) and
anything I'd rebuild *from full text / bibliography* (the bibtex-ending fix
changed extraction). **Still canonical:** `citations_intent.json` / `citations_typed.json`
(Klara reused them as-is). The base contribution bundle is identical everywhere.

---

## 5. Next task: enriched graph → LLM research directions vs. no-graph baseline

**Klara already built most of the harness** in `experiments/graph_ideation/` (on
`dev`, *not yet on my branch*):

- `run_pilot.py` — orchestrates **three arms**: `closed_box`/`flat` (**the no-graph
  baseline** = "an LLM's ideas without the graph"), `legacy`, `enriched`. Stages:
  prepare → generate → judge.
- `generate_gap_aware.py` — the graph-aware generator (select a gap from a seed's
  1–2-hop typed neighbourhood, then design 3 studies).
- Judges + calibration: `judge_antecedents.py`, `judge_field_value.py`,
  `analyze_portfolios.py`, `calibrate_novbench.py`, `motif_balanced_resample.py`.
- `build_gap_atlas.py` — renders grounded, human-reviewable gap cards.
- Outputs: `out/{generations,judgements,summary}.jsonl/json`; docs
  `GAP_AWARE_PILOT.md`, `RETROSPECTIVE_GAP_FORECAST.md`, `NOVBENCH_CALIBRATION.md`.

**The gap = my contribution.** The pilot currently reads the **deprecated
2188-pair `cartographer_rebuild_normalized.jsonl`** as its edge source and injects
**no citation intent/support at all**. So my task is a clean extension:
1. Point the edge source at the **canonical v12 enriched graph**.
2. Add an arm (or enrich the `enriched` arm) that puts **citation intent/support**
   into the LLM context (the seam the Cartographer never sees).
3. Compare against the existing `flat`/`closed_box` baseline with the existing
   judges. The graph-vs-no-graph comparison scaffold already exists.

### 5a. File set I need on the branch for this task
- ✅ already have / staged: `data/prior-core-v0.2/*`, `canonical_...v12.json`,
  `citations_intent.json` (+typed), `citations_intent_incoming_v12_new.json`.
- ⬜ **bring over: the whole `experiments/graph_ideation/` directory** (scripts +
  docs + `out/` pilot outputs) to reuse the harness instead of rebuilding.
- ⬜ optional: `cartographer_rebuild_normalized.jsonl` (only if I want to
  reproduce Klara's `legacy`/`enriched` arms exactly before swapping the source).
- ⬜ reference: regenerated `citation_map.json` + resolution docs.

**There is no single pre-combined "enriched graph with intents" file** — it's
assembled at load time from (canonical v12 edges+contributions) + (809 + 294
intent sites) + (papers bundle). If I want one artifact, I'd write a small
join script; but the ideation harness loads them separately anyway.

---

## 6. Open questions / needs input
1. **Marker gap:** get `citation_contexts_incoming_v12.json` from Klara so the 16
   new-pair queue cases show real `[CITED:TARGET]` windows.
2. **Bring `graph_ideation/` onto my branch, or work on `dev`?** It's Klara's; I
   should confirm whether I fork it into my branch or she wants it developed on
   `dev`.
3. **Which edge set for the enriched arm** — canonical v12 (989, policy-clean) is
   my assumption; confirm we're *not* reviving the deprecated 2188.
4. Should the citation signal enter as **extra context text** in the prompt, or as
   a **filter/re-ranker** on which gaps get surfaced? (Mirrors the
   `semantic_crossover` finding: citation is best as complementary context, not a
   relabel.)
