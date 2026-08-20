# Graph-grounded vs. web-search research ideation

*Callum, 2026-08. Does letting an LLM **explore the enriched Prior atlas** produce
**more novel and more efficient** research ideas than the same LLM **exploring the
web** (a researcher with a browser)? Fresh build — understands but does not reuse
`../graph_ideation/` (Klara's, §7). Full graph provenance:
`../edge_quality/GRAPH_STATE_AND_NEXT_TASK.md`.*

## Hard constraints
- **No API key, no metered spend.** Everything runs on my Claude Code **Pro
  subscription** via `PRIOR_LLM_BACKEND=claude-code` (the Agent SDK path — supports
  custom tools + WebSearch and reports token usage). The `api` backend is off-limits.
- **Expensive steps run in *my* terminal, killable + resumable** (§5). No long batch
  is ever launched from inside a Claude Code session — that could rate-limit me out.

## 1. Design — two arms explore an environment, same seed
Both arms get the **same lightweight topic seed** each round (keeps them on the
corpus's subject and lets us pair them), a **tool environment to explore**, the
**same task** ("propose one novel, concrete research direction: the gap, the study,
the expected result"), and the **same output schema**. Only the environment differs:

| | **GRAPH arm** | **WEB arm** |
|---|---|---|
| environment | the full v12 atlas via `graph_tools.py` | the open web via `WebSearch` / `WebFetch` |
| tools | `overview, search_contributions, get_contribution, get_paper, get_edges, get_neighbors, citations_between` | Agent SDK built-ins |
| budget | ≤ ~12 tool calls, `max_turns` capped | ≤ ~12 searches, `max_turns` capped |

The graph arm *discovers* the typed relations, edge `reason` justifications and
citation intents by exploring — nothing is pre-chewed. That's the fair parallel to
the web arm sifting search results, and it tests Prior as a product, not my
retrieval heuristic.

## 2. Inputs (what feeds the graph, and from where)
All already on this branch (see GRAPH_STATE doc). `graph_tools.py` reads exactly:
| layer | file |
|---|---|
| enriched semantic edges + contributions (989 pairs, 581 contribs; relation/direction/**reason**) | `edge_quality/out/canonical_semantic_candidates_enriched_evidence_v12.json` |
| my citation intents (809 sites) + support/priority | `edge_quality/out/citations_intent.json`, `citations_typed.json` |
| new-substrate citation intents (294 sites / 119 new pairs) | `edge_quality/out/citations_intent_incoming_v12_new.json` |
| papers (title/abstract/authors) | `data/prior-core-v0.2/papers_core.jsonl` |

Using the **old** 809 intents as-is (no regenerate — decided). The 809 + 294 are
disjoint at paper-pair level → the full 1103-site / 643-pair citation layer.

## 3. Models (decided)
- **Generator: `claude-sonnet-5`** (both arms — cheaper, and a mid-tier generator
  is *more* context-dependent, which isolates the graph's value better).
- **Judge: `claude-opus-5`** (strictly stronger than the generator; ≠ generator).
- Self-preference bias cancels: both arms share the generator, so the judge's
  Claude-family preference applies equally to each side. *Confirm `/model` exposes
  opus-5 on my subscription.*

## 4. Judging + metrics
- **Pairwise, blind, order-swapped.** Judge sees two anonymized ideas for the same
  seed, scores each on **novelty** + **feasibility/soundness**, picks per-criterion
  and overall winners. Run each pair **twice with A/B swapped**; count a win only if
  consistent (report the swap-disagreement rate as a bias measure). Instruct the
  judge to ignore length/verbosity.
- **Winrate** = fraction the GRAPH arm wins (primary result).
- **Efficiency** (per idea): input/output tokens, **# tool calls**, **wall-clock
  seconds** → "graph reaches a good idea with less exploration than the web."
- v2 only if promising: sampled cross-product Elo; citations-on/off ablation.

## 5. Killable + resumable execution (for the expensive scripts)
The generation and judging scripts (`gen.py`, `judge.py`) will be built so that:
- **I launch them in my own terminal** (`! python -m ...` or a separate shell), never
  spawned by the assistant — so I control and can `Ctrl+C` them.
- **Checkpointed**: each finished unit is appended as one line to a `.jsonl` the
  instant it completes (atomic append). On restart the script reads the checkpoint,
  builds the done-set keyed by `(seed_id, arm)` / `(pair_id, order)`, and **skips
  what's done** — safe to kill and re-run any time.
- **`Ctrl+C` safe**: a partial unit is never written; the loop exits cleanly.
- **Throttled + capped**: serial by default (`--workers 1`), `--sleep` between calls,
  `max_turns` + tool-budget caps per idea so one run can't run away and burn my quota.
- **Pilot flags**: `--limit N` / `--seeds a,b,c`, and `--dry-run` (assemble prompts,
  print token estimate, **no model call**) so I can sanity-check cost first.
- **Start tiny**: ~10-seed pilot → eyeball ideas → scale to 30–50 (100 optional).

## 6. Build order & status
1. ✅ `graph_tools.py` — the graph exploration environment (self-tested, zero cost).
2. ✅ `select_seeds.py` → `seeds_draft.json` (TF-IDF+KMeans clusters) → `seeds.json`
   (26 broad, neutral topic labels covering the corpus). *(no LLM)*
3. ✅ `arms.py` — both arms on the Agent SDK: graph arm = `graph_tools` as in-process
   MCP tools + `submit_idea`, no web; web arm = `WebSearch`/`WebFetch` + `submit_idea`,
   no graph. `python arms.py --selftest` passes (no model call).
4. ✅ `gen.py` — resumable/killable driver (§5); `--dry-run` verified. *(live run = subscription)*
   *(v1: `get_citations` added, structure surfaced in tool results, `GRAPH_SYS` steers to traverse — §7b.)*
5. ✅ `convergence.py` — lexical TF-IDF cosine per seed pair, report-only (§7b). *(no LLM; a floor — judge is authority)*
6. ⬜ `judge.py` — blind, order-swapped, **1-10 per idea** (novelty + feasibility) + same-idea flag → `out/judgements.jsonl`. *(subscription)*
7. ⬜ `aggregate.py` → `RESULTS.md` (winrate from 1-10 scores + efficiency + convergence). *(no LLM)*

**Next action is yours (first subscription spend):** in your own terminal, run a
1-seed live pilot — `cd experiments/graph_vs_web_ideation && python gen.py --limit 1`
— then we inspect `out/generations.jsonl` together before scaling and before I build
`judge.py`.

## 7. Not this: `../graph_ideation/` (Klara's — reference only)
Her pilot makes gap *cards* with three graph arms over the **deprecated 2188-pair**
edge set and **no citation intents**, judged by antecedent/field-value graders. Mine
is a **graph-vs-web head-to-head**, **agentic exploration**, **canonical v12 + citation
intents as first-class**, **pairwise novelty/feasibility winrate**, **credit-free**.

## 7a. Pilot v0 audit (2026-08-18, 5 seeds) → decisions
Both arms produced strong, judgeable ideas and used their environments correctly.
Two things fixed before the real run (v0 archived in `out/pilot_v0/`):
- **Blinding was broken** — 9/10 ideas leaked provenance (graph arm cited internal
  IDs + "the graph / no edge"; web arm said "web-search"). Fix: a **blinding contract**
  in the shared prompt (both arms output a self-contained proposal, cite prior work
  **by name**, reveal nothing about tools/graph/search). `check_leakage.py` gates the
  set before judging.
- **Novelty framing** — the graph arm justified novelty by "absent from the graph"
  (corpus-scoped). Fix: both arms target novelty vs the **broader literature**, and
  the **opus-5 judge is the novelty authority** (rates from its own knowledge) — which
  also neutralizes the web arm's live-search *verification* advantage.
- **Efficiency (honest):** the `max_turns` cap is **not binding** — both arms
  self-terminate, so we already measure their chosen spend. Observed: the graph arm
  costs *slightly more*, not less. So **do not rig caps**; use `cost_usd` + wall-clock
  (not tool-count — a local `get_edges` ≠ a `WebSearch`) and reframe the claim to
  *comparable cost, better-grounded/more-novel ideas*. `ToolSearch` excluded from the
  exploration count (`n_explore`).
- Loop depth is producing good work and isn't the bottleneck — **left unchanged**.

## 7b. Pilot v1 audit (2026-08-19, 4 seeds, blinding fixed) → decisions
Blinding held (ideas read clean, cite by name). Two real threats surfaced:
- **The arms converge.** 3 of 4 seeds produced the *same core idea* on both sides
  (s01 both = robust aggregation vs adversarial review; s02 both = a manuscript-blind
  independent verification gate; s04 both = select ideas on downstream value not
  novelty). Root cause: the corpus IS the public AI-for-science literature, so the web
  arm googles up the exact same papers. If they keep converging, a ~50% novelty winrate
  would understate Prior, not reflect it.
- **The graph arm wasn't consuming the graph.** Over 4 runs it called `get_edges` once
  and `citations_between` zero times — it used the atlas as a private *search index over
  the same papers*, which is exactly what the web arm does (hence the convergence). The
  citation layer (all the annotation work) went untouched, and was in fact half-
  unreachable: no way to navigate citations *from a paper*.

Fixes (all zero-cost, applied — re-run to take effect):
- **Made the whole graph reachable + worth traversing** (not by forcing an edge — by
  making structure pay off): new `get_citations(paper_id)` walks the citation layer
  from any paper (what it cites / what cites it, with intents); `overview` now names the
  two layers + citation-intent counts; `search`/`get_contribution` now surface the typed-
  relation breakdown + citation count so structure advertises itself; `GRAPH_SYS`
  rewritten to say plainly that the signal (tensions, lineages, citation intents) lives
  in the RELATIONS, not the isolated contribution text. Web arm unchanged.
- **Convergence is measured + reported, never gated** (`convergence.py`): even a near-
  duplicate pair is still fully judged — one may be written out better. NOTE: lexical
  TF-IDF badly *under-detects* this convergence (mean 0.18, flagged 0/4, yet 3/4 are
  the same idea), so it's only a cheap floor. **The authoritative "same core idea?" call
  goes in the judge** (opus-5 reads both, emits a same-idea flag alongside the scores).
- **Judging = absolute 1-10 per idea** (decided): the judge sees the pair, scores EACH
  idea 1-10 on novelty and on feasibility/soundness, order-swapped for consistency, plus
  a same-idea flag. Keep the 1-10 (more signal); binarize to a winrate only when needed.

## 7c. Pilot v2 audit (2026-08-19, 4 graph seeds re-run) → decisions
The graph-consumption fix worked: `get_edges` now fires 3-4×/run (was 1 across all 4),
`get_citations`/`get_neighbors` appear, and ideas are explicitly grounded in "a
documented tension." Graph-vs-web diverged on 3/4 (only s01 still converges). But a
NEW failure surfaced:
- **Within-arm mode collapse + topic drift.** s02 and s04 graph ideas were essentially
  the same idea ("LLM-judge novelty is broken → use citation-graph structure"), and s02
  DRIFTED off its own topic (autonomous scientists) into s04's territory. Cause: I over-
  primed "tensions/contradictions", and `overview` dumped all 27 contradictions — so
  traversal kept rediscovering the single juiciest structural tension.
Fixes (prompt + tool, zero-cost; graph seeds re-run as v3):
- **De-emphasised any single relation.** `overview` no longer dumps contradictions; it
  now returns 2 example edges of EACH typed relation. `GRAPH_SYS` says all four
  relations matter equally, "do not fixate on one kind of relation or one striking edge,
  and do not force every idea into the same mould," and anchors exploration on the
  seed's own region (search the topic first; use `overview` only for orientation).
- **Topic adherence (shared `TASK`, both arms):** the proposal MUST sit squarely within
  the stated topic; if exploration drifts, bring it back to THIS topic.
- Web arm unchanged → web rows kept; only the 4 graph seeds regenerate (pilot_v2 archived).

## 8. Open questions
- ✅ `opus-5` available on my subscription (judge). Generator `sonnet-5`.
- ✅ Web arm: web **+ general knowledge** (realistic strong baseline).
- ✅ Seeds: **broad topic labels** (26, in `seeds.json`), same seed to both arms.
- Exploration budget (≤12 tool calls) — tune on the pilot.
