# Non-citation edge quality — interim labeling

> **Status: PRELIMINARY.** 45-edge stratified sample of the 854 non-citation ('extra-info') contribution edges, hand-labeled by Claude (Claude Code session, 2026-06-30) — *not* an independent eval. Judge = same model family that drew the edges (possible leniency); n=15/tier (wide CIs); judged from statements + the model's own evidence text, not from the papers. Treat genuine% as an upper bound. Per-edge calls: `data_hackathon/atlas/noncite_edge_labels_interim.json`.

## Result (weighted to population: triple 42% / double 45% / opus-only 13%)

| tier | n | genuine (omission+missed-cite) | type-overstated | spurious |
|---|--:|--:|--:|--:|
| triple | 15 | 87% | 7% | 7% |
| double | 15 | 40% | 47% | 13% |
| opus_only | 15 | 87% | 13% | 0% |
| **weighted** | | **~66%** | **~26%** | **~9%** |

**Headline:** true hallucination (unrelated papers) is **<10%**. Dominant error = **over-labeling `builds_on`** on parallel/contemporaneous work. By relation type: `supports` ≈ 90% genuine; `builds_on` ≈ 77% over-labeled.

## Per-edge calls

| # | rel | tier | trust | A | B | label | note |
|--:|---|---|--:|---|---|---|---|
| 1 | supports | triple | 0.79 | Nathani et al. (2025) (2025) | Cai et al. (2026) (2026) | **missed_cite** | B reports results ON A's AUP metric -> uses/should-cite A |
| 2 | supports | triple | 0.84 | Cheng et al. (2025) (2025) | Gupta et al. (2026) (2026) | **genuine** | independent end-to-end pipelines; genome study instantiates A's clai |
| 3 | supports | triple | 0.74 | Lu et al. (2026) (2026) | Zhang et al. (2025) (2025) | **genuine** | both report AI research output reaches good quality |
| 4 | supports | triple | 0.94 | R'ios-Garc'ia et al. (2026) (2 | Kurjan et al. (2026) (2026) | **genuine** | both document LLM-agent epistemic/reasoning failures |
| 5 | supports | triple | 0.84 | Kumar et al. (2025) (2025) | Banker et al. (2024) (2024) | **genuine** | A's general LLM-idea finding supports B's specific result |
| 6 | supports | triple | 0.86 | Liu et al. (2024) (2024) | Ghareeb et al. (2025) (2025) | **genuine** | parallel full-process multi-agent discovery systems corroborate feas |
| 7 | builds_on | triple | 0.64 | Yamada et al. (2025) (2025) | Liu et al. (2024) (2024) | **type_overstated** | AI Scientist-v2 vs FalsificationAgent: parallel improvements, not li |
| 8 | supports | triple | 0.84 | Chen et al. (2025) (2025) | R'ios-Garc'ia et al. (2026) (2 | **genuine** | both highlight agent result-fabrication / eval limits |
| 9 | supports | triple | 0.94 | Wu et al. (2026) (2026) | Cheng et al. (2025) (2025) | **genuine** | parallel clinical end-to-end frameworks reinforce |
| 10 | supports | triple | 0.64 | Miller et al. (2025) (2025) | Nair et al. (2026) (2026) | **spurious** | 'loosely complementary'; different claims, no shared finding |
| 11 | supports | triple | 0.79 | Lyu et al. (2026) (2026) | Gottweis et al. (2026) (2026) | **genuine** | parallel self-evolution mechanisms refine ideas |
| 12 | supports | triple | 0.84 | Trehan et al. (2026) (2026) | Liu et al. (2024) (2024) | **genuine** | B's falsification principle aligns with A's design-principle set |
| 13 | supports | triple | 0.79 | Wu et al. (2026) (2026) | Hou et al. (2026) (2026) | **genuine** | complementary beyond-lexical novelty-review eval methods |
| 14 | supports | triple | 0.69 | Schmidgall et al. (2025) (2025 | Wu et al. (2025) (2025) | **genuine** | pipeline (A) + environment (B), complementary |
| 15 | supports | triple | 0.79 | Shen et al. (2026) (2026) | Hu et al. (2025) (2025) | **genuine** | both: planning/query quality drives retrieval performance |
| 16 | supports | double | 0.72 | Trehan et al. (2026) (2026) | Chen et al. (2025) (2025) | **genuine** | parallel modular multi-stage research scaffolds |
| 17 | builds_on | double | 0.52 | Holtdirk et al. (2026) (2026) | Ziming et al. (2025) (2025) | **type_overstated** | reproducibility vs auditing; 'weak relation' -> builds_on overstated |
| 18 | builds_on | double | 0.82 | Lu et al. (2026) (2026) | Wu et al. (2026) (2026) | **missed_cite** | Medical AI Scientist explicitly = clinical version of The AI Scienti |
| 19 | builds_on | double | 0.62 | Ghafarollahi et al. (2024) (20 | Park et al. (2023) (2023) | **type_overstated** | multi-agent discovery; 'could be seen as elaborating', wrong-directi |
| 20 | builds_on | double | 0.67 | Yang et al. (2026) (2026) | Huang et al. (2025) (2025) | **type_overstated** | dynamic tool integration; no evidence text; likely parallel |
| 21 | supports | double | 0.57 | Villaescusa-Navarro et al. (20 | Lu et al. (2026) (2026) | **genuine** | A is a benchmark for the class B is in (real) |
| 22 | builds_on | double | 0.52 | Bragg et al. (2025) (2025) | Xu et al. (2025) (2025) | **type_overstated** | AstaBench vs ResearcherBench: independent benchmarks labeled builds_ |
| 23 | builds_on | double | 0.52 | Qiu et al. (2025) (2025) | Brunnsåker et al. (2025) (2025 | **type_overstated** | LLM-driven bio experiment design; 'link loose' |
| 24 | builds_on | double | 0.57 | Lin et al. (2026) (2026) | Zhou et al. (2024) (2024) | **spurious** | 'link weak, possibly same project' |
| 25 | supports | double | 0.57 | Hambardzumyan et al. (2026) (2 | Bai et al. (2026) (2026) | **spurious** | single- vs multi-agent; unclear/opposed framing |
| 26 | builds_on | double | 0.67 | Du et al. (2026) (2026) | Bu et al. (2026) (2026) | **type_overstated** | memory algorithm 'could be a component of' -> builds_on overstated |
| 27 | supports | double | 0.67 | Riffle et al. (2026) (2026) | Bu et al. (2026) (2026) | **genuine** | parallel autonomous bioinformatics frameworks aligned |
| 28 | supports | double | 0.62 | Chen et al. (2025) (2025) | Xu et al. (2025) (2025) | **genuine** | parallel rubric-based LLM eval frameworks |
| 29 | builds_on | double | 0.72 | Chen et al. (2025) (2025) | Tang et al. (2025) (2025) | **type_overstated** | both extend a common modular concept; parallel, not B-on-A |
| 30 | supports | double | 0.72 | Tadiparthi et al. (2024) (2024 | Zhao et al. (2026) (2026) | **genuine** | parallel hypothesis/idea-generation frameworks |
| 31 | supports | opus_only | 0.55 | Yamada et al. (2025) (2025) | Ghareeb et al. (2025) (2025) | **genuine** | parallel end-to-end discovery systems corroborate |
| 32 | contradicts | opus_only | 0.35 | Jansen et al. (2024) (2024) | Ma et al. (2026) (2026) | **genuine** | real opposing claims on agent discovery capability (contradicts) |
| 33 | supports | opus_only | 0.55 | Ghareeb et al. (2025) (2025) | Park et al. (2023) (2023) | **genuine** | parallel multi-agent discovery frameworks |
| 34 | supports | opus_only | 0.45 | Si et al. (2024) (2024) | Kumar et al. (2025) (2025) | **genuine** | eval framework (A) + complementary alignment metric (B) |
| 35 | supports | opus_only | 0.45 | Si et al. (2024) (2024) | Kumar et al. (2025) (2025) | **genuine** | eval framework (A) + complementary diversity metric (B) |
| 36 | supports | opus_only | 0.5 | Schmidgall et al. (2025) (2025 | Trehan et al. (2026) (2026) | **genuine** | parallel autonomous multi-stage research pipelines |
| 37 | supports | opus_only | 0.62 | Chen et al. (2025) (2025) | Kon et al. (2025) (2025) | **genuine** | parallel ML-research-task benchmarks corroborate eval need |
| 38 | supports | opus_only | 0.55 | Tang et al. (2025) (2025) | Agrawal et al. (2026) (2026) | **genuine** | B's findings align with A's benchmark purpose |
| 39 | builds_on | opus_only | 0.55 | Tang et al. (2025) (2025) | Starace et al. (2025) (2025) | **type_overstated** | Scientist-Bench 'could build on' PaperBench; parallel benchmarks |
| 40 | supports | opus_only | 0.6 | Ye et al. (2024) (2024) | Meguimtsop et al. (2026) (2026 | **genuine** | both document LLM framing/disclosure sensitivity in scholarly contex |
| 41 | builds_on | opus_only | 0.5 | Li et al. (2025) (2025) | Tyser et al. (2024) (2024) | **missed_cite** | A documents blind spots B's error-injection method finds -> should c |
| 42 | supports | opus_only | 0.55 | Tang et al. (2025) (2025) | Gottweis et al. (2026) (2026) | **genuine** | parallel autonomous multi-agent research systems |
| 43 | supports | opus_only | 0.6 | Kumbhar et al. (2025) (2025) | Xiong et al. (2024) (2024) | **genuine** | parallel hypothesis-gen benchmarks |
| 44 | supports | opus_only | 0.55 | D’Arcy et al. (2024) (2024) | Idahl et al. (2024) (2024) | **genuine** | both on LLM-reviewer quality/leniency |
| 45 | builds_on | opus_only | 0.5 | Lyu et al. (2026) (2026) | Gottweis et al. (2025) (2025) | **type_overstated** | competing/extending co-scientist systems; parallel |

## Fix: stop over-labeling `builds_on` (~26%) — for the Cartographer-v2 pass

`supports` non-citation edges are ~90% genuine (independent corroboration — the value Prior adds). `builds_on`/`refines` are ~77% over-labeled: the agent reaches for *lineage* on *parallel* work. Not hallucination — a relation-**type** precision problem.

**Changes, priority order:**

1. **Post-relate downgrade rule (no LLM).** Downgrade `builds_on`/`refines` -> `supports`/`related` unless (a) a real citation exists between the papers (`citation_graph_s2.json`), or (b) directed + clear newer->older year gap + evidence says *extends/builds on/successor*. Heuristic: *no citation + |yearA-yearB|<=1 -> `related`.* Genuine lineage almost always has a citation (AI Scientist -> v2), so false-downgrades are rare.
2. **Add a `related`/`parallel_to` edge type.** Current vocab has no slot for 'same problem, independent system', so the model forces `builds_on` or a loose `supports`. A `related` type absorbs these and sharpens the rest.
3. **Citation-context grounding (the real fix).** For citation-linked pairs, pull the citing sentence, feed it to the labeler (set `builds_on` only when the citance says so), and store it as the edge's evidence quote.
4. **Direction from dates, not the LLM.** Keep `builds_on` direction = newer->older; flag LLM-vs-date disagreements as suspect.
5. **Re-eval gate.** Re-run this labeling (or the clean LLM-judge, once credits return) on the fixed graph. Target: non-citation `builds_on` over-label < 20% (from ~77%).

**Code touch points:** `pipeline._relate_chunk` (prompt + `_RELATE_SCHEMA`: add `related`); a post-relate cleanup pass joining `citation_graph_s2.json` + paper `year`; a citance extractor over `data_hackathon/fulltext/`.