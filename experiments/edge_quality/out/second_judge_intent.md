# Intent axis — second-judge cross-check (Opus 5 vs our Sonnet-5)

Blind second annotator over a **stratified 100-site sample** (seed 13, targets {'uses_extends': 33, 'compares_contrasts': 33, 'background': 34}). Same evidence + `[CITED:TARGET]` marker convention as production; **clean-room rubric** (Opus was NOT given our tie-breakers) so the two annotators' errors are de-correlated. Blind = Opus never saw our label.

> This measures **reliability** (do two independent strong judges converge?), not ground truth. It tells us *where* the taxonomy boundaries are soft, and seeds the hand-label set.


## Headline

| metric | value | read |
|---|---:|---|
| Agreement, balanced sample | **86%** | on the 34/33/33 sample |
| Agreement, reweighted to true 82/11/7 | **81%** | honest whole-corpus figure |
| Cohen's κ | **0.79** | *substantial*, ≈ human–human on citation-intent tasks |
| Disagreements | **14 / 100** | all on known grey-zones (below) |

## Confusion matrix — our label (rows) × Opus label (cols)

| ours ＼ opus | background | uses_extends | compares_contrasts | row total |
|---|---|---|---|---|
| **background** | 27 | 2 | 5 | 34 |
| **uses_extends** | 1 | 30 | 2 | 33 |
| **compares_contrasts** | 4 | 0 | 29 | 33 |

Diagonal = agreement. Per-class agreement (on the balanced sample):

| our class | agree / n | rate |
|---|---:|---:|
| background | 27/34 | 79% |
| uses_extends | 30/33 | 91% |
| compares_contrasts | 29/33 | 88% |

`background` is the lowest-agreement class **and** the majority class, so it pulls the reweighted headline below the balanced number. `uses_extends` — the class we worried about — is the *highest* agreement.


## Disagreements, grouped by pattern

None are random errors — every one lands on a genuine taxonomy boundary. Ordered by cluster size.


### `background` → `compares_contrasts`  (5)

Grouped comparison — target sits in a comparison/benchmark table or a grouped 'existing systems lack X' motivation. Ours routes grouped comparisons to `background` (only a contrast that singles out the target = `compares_contrasts`); Opus reads table membership itself as contrast. **Definitional fork on the majority class.**


- **arxiv:2511.10902->openalex:W4404350150#0** — ours `background` (0.75) · opus `compares_contrasts` (0.7)
  - ours: Row in a feature-comparison table listing multiple systems, no singling-out text.
  - opus: Target appears as a row in a feature-comparison table of prior systems.
  - claim: *d & Text Summary & Multi-Dimensional & Actionable To-Do & Multimodal Perception & Web-Data Integration \\ MARG [CITED] & & & & & \\ CycleResearcher [CITED:TARGET] & & & & & \\ OpenReviewer [CITED] & & & & & \\ DeepReview [CITED] & & & & & \*

- **arxiv:2602.15112v2->openalex:W4416540539#0** — ours `background` (0.75) · opus `compares_contrasts` (0.72)
  - ours: Descriptive comparison table row among data-driven discovery benchmarks.
  - opus: Listed as a benchmark row in a comparison table of existing benchmarks.
  - claim: *rcross & & & -- & & -- & & 24GB & -- & --\\ EXP-Bench[CITED] & Papers & Output Match & & & & -- & & -- & & 2-640GB+ & -- & --\\ Data Driven Discovery & & & & & & & & & \\ HypoBench [CITED:TARGET] & Mixed & Heuristic & & & & -- & & -- & -- & -- 4hr & -- & 5.5\ \\ DiscoveryBench [CITED] & Papers & LLM Judge & & & & -- & …*

- **arxiv:2602.15112v2->arxiv:2505.24785v2#0** — ours `background` (0.75) · opus `compares_contrasts` (0.65)
  - ours: Table row listing EXP-Bench's attributes among many other benchmarks.
  - opus: Appears as a row in a benchmark comparison table contrasting features against the citing work.
  - claim: *& --\\ LMR-Bench [CITED] & Papers & Unit tests & & & & -- & & -- & & -- & -- & --\\ RECODE-H [CITED] & Papers & Unit tests & & & & -- & & -- & & 24GB & -- & --\\ EXP-Bench[CITED:TARGET] & Papers & Output Match & & & & -- & & -- & & 2-640GB+ & -- & --\\ Data Driven Discovery & & & & & & & & & \\ HypoBench [CITED] & Mixe…*

- **arxiv:2507.16280->arxiv:2504.01848v3#0** — ours `background` (0.6) · opus `compares_contrasts` (0.6)
  - ours: Critique of 'these frameworks' applies to the group of prior benchmarks, not PaperBench alone.
  - opus: Cited amid the claim that existing frameworks fail to capture insight generation, motivating their new benchmark.
  - claim: *rowsecomp , focusing on breadth of information retrieval rather than conceptual understanding and insight generation. These frameworks fail to capture a crucial dimension of research assistance: the ability to understand, analyze, and provide meaningful insights on highly specialized, cutting-edge scientific problems. …*

- **arxiv:2602.15112v2->arxiv:2411.15114v2#0** — ours `background` (0.7) · opus `compares_contrasts` (0.62)
  - ours: Grouped under general limitation that implementation-focused benchmarks give little headroom for ideation.
  - opus: Framed as an existing evaluation covering only a fragment with 'little headroom', positioning the new benchmark.
  - claim: *ics defined in ( sec:eval-metrics ). -4pt fig:rg figure* Existing evaluations target fragments of the research cycle: ideation work focuses on generating hypotheses without implementation [CITED], while implementation work assesses ML engineering [CITED:TARGET] or paper reproduction [CITED], offering little headroom fo…*

### `compares_contrasts` → `background`  (4)

Survey / concurrent framing — a contrastive cue ('In contrast', 'Unlike the above', 'concurrent to') is present but the target is otherwise described neutrally. Ours fires on the cue; Opus reads it as a neutral related-work description. **Where our judge may over-fire `compares_contrasts`.**


- **arxiv:2606.11447->arxiv:2504.01848v3#0** — ours `compares_contrasts` (0.8) · opus `background` (0.7)
  - ours: Cites PaperBench's specific score (27% vs 41% human) which is later contrasted with the citing paper's own higher results.
  - opus: Reports PaperBench's agent vs human scores as context on prior reproducibility performance.
  - claim: *oducibility performance in prior work depended heavily on domain-specific scaffolding rather than model capability alone. Similarly, PaperBench found that even the top-performing AI agent scored just 27\ on replication tasks drawn from ICML 2024 papers, while human ML experts scored 41\ under comparable conditions [CIT…*

- **openalex:W4402952811->openalex:W4402952666#1** — ours `compares_contrasts` (0.7) · opus `background` (0.7)
  - ours: Describes AI Scientist's scope specifically as concurrent/differing work, continuing the contrast set up earlier.
  - opus: Described as concurrent work with a neutral summary of its framework.
  - claim: *zed tasks. In contrast to our work on automatic ML hypothesis generation and research with broad utilities (action space), these models operate under more restricted conditions, focusing on predefined tasks with existing code and limited interaction capabilities based on parametric knowledge. Concurrent to our work, [C…*

- **arxiv:2603.28589v1->openalex:W4416043407#0** — ours `compares_contrasts` (0.75) · opus `background` (0.72)
  - ours: 'In contrast, Google's AI co-scientist... operates as a collaborator' explicitly contrasts it with the previously described Agent Laboratory.
  - opus: Neutral description of AI co-scientist among related frameworks in related work.
  - claim: *y balance exploration and exploitation to discover novel methods. Agent Laboratory [CITED] extends this by automating the execution and reporting of user-provided ideas, acting as an accelerator for human researchers rather than an independent ideator. In contrast, Google's AI co-scientist [CITED:TARGET] operates as a …*

- **openalex:W4417070798->openalex:W4417287919#1** — ours `compares_contrasts` (0.75) · opus `background` (0.8)
  - ours: 'Unlike the above systems... Robin emphasizes a different research target' singles out Robin's distinct focus.
  - opus: Neutral survey-style description of Robin's different research target versus other prior systems.
  - claim: *aboratoryusingllm is designed to assist human scientists in executing their research ideas while allowing flexible levels of human involvement, where users can choose to provide feedback at any stage of scientific research. Furthermore, unlike the above systems that mainly automate research in computer science, Robin […*

### `background` → `uses_extends`  (2)

Possible under-called reuse — Opus reads the target as actually incorporated (dataset entry / one of the evals) where ours saw only a table row. **Candidate ours-miss.**


- **arxiv:2505.24785v2->openalex:W4399116274#0** — ours `background` (0.75) · opus `uses_extends` (0.6)
  - ours: Target appears only as a row in a garbled benchmark-listing table with no stated relation.
  - opus: The target appears as an entry/paper included in the citing paper's constructed dataset table.
  - claim: *ro-shot Anomaly Detection[CITED] & 339 & 150 & Deep Learning LLMs & propose an architecture & memory: 24GB; GPU: RTX 3090; amount: 1 & 5 & 3 & 1 \\ 19388 & Unmasking and Improving Data Credibility: A Study with Datasets for Training Harmless Language Models[CITED:TARGET] & 2706 & 20 & Social Aspects Accountability & Ot…*

- **arxiv:2510.21652v2->openalex:W4403707291#1** — ours `background` (0.65) · opus `uses_extends` (0.78)
  - ours: Descriptive entry in a comparison table of benchmark scopes, no contrastive cue against target alone
  - opus: The suite incorporates CORE-Bench-Hard as one of its evals, noting it omits GPU-requiring tasks from the original.
  - claim: *ic questions. [CITED] tests an agent's ability to create a literature review table. [CITED] tests the ability of code agents to set up and execute Python machine learning experiments reported in ML and NLP papers. [CITED:TARGET] tests an agent's ability to reproduce experiments and analyses from papers. omits GPU-requi…*

### `uses_extends` → `compares_contrasts`  (2)

Baseline rerun — the citing paper re-runs the target as a baseline. Ours calls adopting the target to run it `uses_extends`; Opus calls the head-to-head `compares_contrasts`. **Known adopt-vs-compare grey-zone.**


- **arxiv:2605.28655->openalex:W4411005431#0** — ours `uses_extends` (0.72) · opus `compares_contrasts` (0.62)
  - ours: Authors rerun Biomni under their own unified compute setting as a baseline system.
  - opus: Biomni is rerun as a baseline under a unified compute setting for head-to-head comparison.
  - claim: *Implementation Details of BioML-Bench app:biomlbench Setup Experiment compute resources In the BioML-Bench protocol drug discovery, protein engineering, and single cell omics tasks are run on CPU-only machines with an 8-hour limit. In contrast, we run , Autoresearch, and rerun Biomni [CITED:TARGET] under a unified expe…*

- **openalex:W4407806895->openalex:W4403324055#0** — ours `uses_extends` (0.55) · opus `compares_contrasts` (0.55)
  - ours: Citing paper aligns its own script-based evaluation design with the target's approach ('also use a script based evaluation approach').
  - opus: Positions its own script-based evaluation design relative to the target ('also use ... whereas MLE-Bench').
  - claim: *ct instructions. The LLM agent can then be prompted to follow the submission instructions and write the appropriate code. Moreover, the evaluation script is read-only for the LM agent, so while it can inspect the evaluation format, it cannot modify the script to change the evaluation logic. Existing works such as [CITE…*

### `uses_extends` → `background`  (1)

Mechanism description vs adoption — ours reads the target's mechanism as feeding the citing paper's design; Opus reads it as a neutral description of prior work.


- **openalex:W4414827381->openalex:W4407760093#1** — ours `uses_extends` (0.65) · opus `background` (0.75)
  - ours: Detailed explanation of AIDE's node/tree mechanism feeding into the citing paper's own tree-search design.
  - opus: AIDE described neutrally as a recent advance in LLM code generation with tree search.
  - claim: *on. The human-driven scientific process, on the other hand, relies on open-ended hypothesis generation, stepping-stone collection, and iterative hypothesis refinement. Recent advances using code generation as an action space have opened new opportunities for LLM-driven automated workflows [CITED]. AIDE [CITED:TARGET] c…*
