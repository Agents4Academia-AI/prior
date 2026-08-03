# Validation results

## 1. S2 intent eval — `s2_intent_eval.json`

- our typed edges: 525
- present in S2 ref graph: 237
- carrying an intent tag: 10
- flagged isInfluential: 23
- mapping: {'background': 'background', 'methodology': 'uses_extends'}
- agreement on comparable classes (background/uses_extends): 6/9
- cross (our intent × mapped S2 intent): {"uses_extends": {"background": 1, "uses_extends": 1}, "background": {"background": 5, "uses_extends": 1, "result/other": 1}, "compares_contrasts": {"uses_extends": 1}}
- isInfluential by our intent [not_influential, influential]: {"background": [167, 9], "compares_contrasts": [30, 10], "uses_extends": [17, 4]}
- note: S2 has no contrast class; silver standard only

### Disagreement edges (3)

#### openalex:W4403795293->openalex:W4402345509
- s2_title: LAB-Bench: Measuring Capabilities of Language Models for Biology Research
- s2_intents: ['background'] → mapped: background
- isInfluential: False
- our_intent: uses_extends
- our justification: The citing paper generated/adopted LitQA2 from the target work as its evaluation benchmark.
- claim: ater publication which found that rs1344706's effects on cortical thickness, surface area, and cortical volume in the brain aggravate the risk of schizophrenia[CITED]. Answering scientific questions To evaluate AI systems on retrieval over the scientific literature, we first generated LitQA2,[CITED:TARGET] a set of 248 multiple choice questions with answers that require retrieval from scientific literature ( fig:litqa_performance A ). LitQA2 questions are designed to have answers that appear in the main body of a paper, but not in the abstract, and ideally appear only once in the set of all scientific li

#### openalex:W4404350150->openalex:W4403006832
- s2_title: AI-Driven Review Systems: Evaluating LLMs in Scalable and Bias-Aware Academic Reviews
- s2_intents: ['methodology'] → mapped: uses_extends
- isInfluential: False
- our_intent: background
- our justification: Descriptive mention grouped with another citation, no adoption or specific critique.
- claim: ies [CITED]. [CITED] conducted small-scale qualitative experiments to evaluate the effectiveness of ChatGPT in the peer review process, while [CITED] invited 10 participants to assess the benefits of GPT-4 in assisting with peer review. [CITED] and [CITED:TARGET] used GPT-4 to evaluate full-text PDFs of scientific papers. However, when LLMs act as judges, even the most advanced models, such as GPT-4 [CITED] and Gemini [CITED], still lag behind reward models specifically trained for the task, as seen in RewardBench [CITED]. Th

#### openalex:W4402952811->openalex:W4402952666
- s2_title: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery
- s2_intents: ['methodology'] → mapped: uses_extends
- isInfluential: False
- our_intent: compares_contrasts
- our justification: Explicit 'Different from... concurrent to AI Scientist' singles out the target for contrast.
- claim: eter tuning with limited exploration of novel models, structures, or data. Moreover, they lack robust feedback mechanisms, leaving no guarantee that the experiment will converge with no address of the root cause of errors in code. Figures/framework Different from all the above (and concurrent to AI Scientist [CITED:TARGET]), we aim to build a fully autonomous framework to tackle the entire process of machine learning research. We present \ (Figure fig:framework ), a systematic framework designed to enhance productivity through automatic generation and implementation/verification with LLM agents. It takes the paper as

## 2. Second-judge re-eval — `second_judge_intent.json`

- second model: claude-opus-5 | our model: claude-sonnet-5
- sample: 100 sites, seed 13, stratify targets {'uses_extends': 33, 'compares_contrasts': 33, 'background': 34}
- raw agreement (balanced sample): 0.86
- Cohen's kappa: 0.7900419916016796


Confusion matrix — our label (rows) × Opus label (cols):

| ours ＼ opus | background | uses_extends | compares_contrasts | row total |
|---|---|---|---|---|
| background | 27 | 2 | 5 | 34 |
| uses_extends | 1 | 30 | 2 | 33 |
| compares_contrasts | 4 | 0 | 29 | 33 |

Per-class agreement:

| our class | agree / n | rate |
|---|---|---|
| background | 27/34 | 0.7941176470588235 |
| uses_extends | 30/33 | 0.9090909090909091 |
| compares_contrasts | 29/33 | 0.8787878787878788 |

### Disagreement edges (14)

#### arxiv:2511.10902->openalex:W4404350150#0
- ours: background (0.75) — Row in a feature-comparison table listing multiple systems, no singling-out text.
- opus: compares_contrasts (0.7) — Target appears as a row in a feature-comparison table of prior systems.
- claim: d & Text Summary & Multi-Dimensional & Actionable To-Do & Multimodal Perception & Web-Data Integration \\ MARG [CITED] & & & & & \\ CycleResearcher [CITED:TARGET] & & & & & \\ OpenReviewer [CITED] & & & & & \\ DeepReview [CITED] & & & & & \

#### arxiv:2602.15112v2->openalex:W4416540539#0
- ours: background (0.75) — Descriptive comparison table row among data-driven discovery benchmarks.
- opus: compares_contrasts (0.72) — Listed as a benchmark row in a comparison table of existing benchmarks.
- claim: rcross & & & -- & & -- & & 24GB & -- & --\\ EXP-Bench[CITED] & Papers & Output Match & & & & -- & & -- & & 2-640GB+ & -- & --\\ Data Driven Discovery & & & & & & & & & \\ HypoBench [CITED:TARGET] & Mixed & Heuristic & & & & -- & & -- & -- & -- 4hr & -- & 5.5\ \\ DiscoveryBench [CITED] & Papers & LLM Judge & & & & -- & & -- & -- & -- & -- & --\\ ScienceAgentBench [CITED]

#### arxiv:2602.15112v2->arxiv:2505.24785v2#0
- ours: background (0.75) — Table row listing EXP-Bench's attributes among many other benchmarks.
- opus: compares_contrasts (0.65) — Appears as a row in a benchmark comparison table contrasting features against the citing work.
- claim: & --\\ LMR-Bench [CITED] & Papers & Unit tests & & & & -- & & -- & & -- & -- & --\\ RECODE-H [CITED] & Papers & Unit tests & & & & -- & & -- & & 24GB & -- & --\\ EXP-Bench[CITED:TARGET] & Papers & Output Match & & & & -- & & -- & & 2-640GB+ & -- & --\\ Data Driven Discovery & & & & & & & & & \\ HypoBench [CITED] & Mixed & Heuristic & & & & -- &

#### arxiv:2507.16280->arxiv:2504.01848v3#0
- ours: background (0.6) — Critique of 'these frameworks' applies to the group of prior benchmarks, not PaperBench alone.
- opus: compares_contrasts (0.6) — Cited amid the claim that existing frameworks fail to capture insight generation, motivating their new benchmark.
- claim: rowsecomp , focusing on breadth of information retrieval rather than conceptual understanding and insight generation. These frameworks fail to capture a crucial dimension of research assistance: the ability to understand, analyze, and provide meaningful insights on highly specialized, cutting-edge scientific problems. [CITED:TARGET] Such problems are characterized by inherent ambiguity, absent definitive answers, and the need for creative synthesis of disparate ideas [CITED]. To address this critical gap in evaluation methodology, we introduce ResearcherBench , the first benchmark specifically designed to evalua

#### arxiv:2602.15112v2->arxiv:2411.15114v2#0
- ours: background (0.7) — Grouped under general limitation that implementation-focused benchmarks give little headroom for ideation.
- opus: compares_contrasts (0.62) — Framed as an existing evaluation covering only a fragment with 'little headroom', positioning the new benchmark.
- claim: ics defined in ( sec:eval-metrics ). -4pt fig:rg figure* Existing evaluations target fragments of the research cycle: ideation work focuses on generating hypotheses without implementation [CITED], while implementation work assesses ML engineering [CITED:TARGET] or paper reproduction [CITED], offering little headroom for creative ideation. Meanwhile, closed-loop research benchmarks either (1) require heavy compute (for example, 8 H100 GPUs), making them difficult to reproduce nathani2025mlgym

#### arxiv:2505.24785v2->openalex:W4399116274#0
- ours: background (0.75) — Target appears only as a row in a garbled benchmark-listing table with no stated relation.
- opus: uses_extends (0.6) — The target appears as an entry/paper included in the citing paper's constructed dataset table.
- claim: ro-shot Anomaly Detection[CITED] & 339 & 150 & Deep Learning LLMs & propose an architecture & memory: 24GB; GPU: RTX 3090; amount: 1 & 5 & 3 & 1 \\ 19388 & Unmasking and Improving Data Credibility: A Study with Datasets for Training Harmless Language Models[CITED:TARGET] & 2706 & 20 & Social Aspects Accountability & Other & standard resources + 1 GPU recommended & 3 & 3 & 6 \\ 17776 & RepoBench: Benchmarking Repository-Level Code Auto-Completion Systems[CITED] & 145 & 139 & Deep Learning LLMs & propose a data

#### arxiv:2510.21652v2->openalex:W4403707291#1
- ours: background (0.65) — Descriptive entry in a comparison table of benchmark scopes, no contrastive cue against target alone
- opus: uses_extends (0.78) — The suite incorporates CORE-Bench-Hard as one of its evals, noting it omits GPU-requiring tasks from the original.
- claim: ic questions. [CITED] tests an agent's ability to create a literature review table. [CITED] tests the ability of code agents to set up and execute Python machine learning experiments reported in ML and NLP papers. [CITED:TARGET] tests an agent's ability to reproduce experiments and analyses from papers. omits GPU-requiring tasks from the original CORE-Bench-Hard; see sec:appendix-evals . [CITED] tests the ability of agents on data science tasks encountered in research.

#### arxiv:2606.11447->arxiv:2504.01848v3#0
- ours: compares_contrasts (0.8) — Cites PaperBench's specific score (27% vs 41% human) which is later contrasted with the citing paper's own higher results.
- opus: background (0.7) — Reports PaperBench's agent vs human scores as context on prior reproducibility performance.
- claim: oducibility performance in prior work depended heavily on domain-specific scaffolding rather than model capability alone. Similarly, PaperBench found that even the top-performing AI agent scored just 27\ on replication tasks drawn from ICML 2024 papers, while human ML experts scored 41\ under comparable conditions [CITED:TARGET]. Subsequent work on REPRO-Bench, focused specifically on social science papers, reported a best accuracy of 36.6\ after substantial agent-specific engineering—a result the authors characterized as well below practical thresholds for reliable automation [CITED]. The considerably higher reproduction rates ob

#### openalex:W4402952811->openalex:W4402952666#1
- ours: compares_contrasts (0.7) — Describes AI Scientist's scope specifically as concurrent/differing work, continuing the contrast set up earlier.
- opus: background (0.7) — Described as concurrent work with a neutral summary of its framework.
- claim: zed tasks. In contrast to our work on automatic ML hypothesis generation and research with broad utilities (action space), these models operate under more restricted conditions, focusing on predefined tasks with existing code and limited interaction capabilities based on parametric knowledge. Concurrent to our work, [CITED:TARGET] proposes AI Scientist : a framework that generates ideas, implements \& executes experiments to obtain results, and finally summarizes them into ML papers. the first comprehensive fully automatic research agent by enabling frontier LLMs to conduct a series of research processes. While its successor A

#### arxiv:2603.28589v1->openalex:W4416043407#0
- ours: compares_contrasts (0.75) — 'In contrast, Google's AI co-scientist... operates as a collaborator' explicitly contrasts it with the previously described Agent Laboratory.
- opus: background (0.72) — Neutral description of AI co-scientist among related frameworks in related work.
- claim: y balance exploration and exploitation to discover novel methods. Agent Laboratory [CITED] extends this by automating the execution and reporting of user-provided ideas, acting as an accelerator for human researchers rather than an independent ideator. In contrast, Google's AI co-scientist [CITED:TARGET] operates as a collaborator in a "scientist-in-the-loop" paradigm, leveraging models like Gemini to assist domain experts with hypothesis generation. Alongside these frameworks, complementary toolkits have been developed to support AI agent systems by enhancing resource integration and accessibility. ToolUniverse

#### openalex:W4417070798->openalex:W4417287919#1
- ours: compares_contrasts (0.75) — 'Unlike the above systems... Robin emphasizes a different research target' singles out Robin's distinct focus.
- opus: background (0.8) — Neutral survey-style description of Robin's different research target versus other prior systems.
- claim: aboratoryusingllm is designed to assist human scientists in executing their research ideas while allowing flexible levels of human involvement, where users can choose to provide feedback at any stage of scientific research. Furthermore, unlike the above systems that mainly automate research in computer science, Robin [CITED:TARGET] emphasizes a different research target: it discovers and validates therapeutic candidates (i.e., a potential new drug or treatment compound) within an iterative ``lab-in-the-loop" framework, where computational hypotheses are repeatedly generated, tested, analyzed, and refined against laboratory experiments conducted

#### openalex:W4414827381->openalex:W4407760093#1
- ours: uses_extends (0.65) — Detailed explanation of AIDE's node/tree mechanism feeding into the citing paper's own tree-search design.
- opus: background (0.75) — AIDE described neutrally as a recent advance in LLM code generation with tree search.
- claim: on. The human-driven scientific process, on the other hand, relies on open-ended hypothesis generation, stepping-stone collection, and iterative hypothesis refinement. Recent advances using code generation as an action space have opened new opportunities for LLM-driven automated workflows [CITED]. AIDE [CITED:TARGET] combines LLM-based code generation with tree search, demonstrating state-of-the-art performance on the MLEBench benchmark [CITED], designed for machine learning engineering tasks. In AIDE, each node represents a potential solution state with a corresponding scalar evaluation score (e.g., validation ac

#### arxiv:2605.28655->openalex:W4411005431#0
- ours: uses_extends (0.72) — Authors rerun Biomni under their own unified compute setting as a baseline system.
- opus: compares_contrasts (0.62) — Biomni is rerun as a baseline under a unified compute setting for head-to-head comparison.
- claim: Implementation Details of BioML-Bench app:biomlbench Setup Experiment compute resources In the BioML-Bench protocol drug discovery, protein engineering, and single cell omics tasks are run on CPU-only machines with an 8-hour limit. In contrast, we run , Autoresearch, and rerun Biomni [CITED:TARGET] under a unified experimental-compute setting of 4 hours on 1 H100 GPU with 16 CPUs and 48\,GB memory for all tasks except for biomedical imaging which had a wall-clock budget of 16 hours instead. We therefore compare against the published BioML-Bench baselines while noting that results for other baselines on drug disc

#### openalex:W4407806895->openalex:W4403324055#0
- ours: uses_extends (0.55) — Citing paper aligns its own script-based evaluation design with the target's approach ('also use a script based evaluation approach').
- opus: compares_contrasts (0.55) — Positions its own script-based evaluation design relative to the target ('also use ... whereas MLE-Bench').
- claim: ct instructions. The LLM agent can then be prompted to follow the submission instructions and write the appropriate code. Moreover, the evaluation script is read-only for the LM agent, so while it can inspect the evaluation format, it cannot modify the script to change the evaluation logic. Existing works such as [CITED:TARGET] also use a script based evaluation approach, whereas MLE-Bench [CITED] uses a Kaggle style evaluation. All our design decisions for the Agent, Environment, Dataset, and Tasks are meant to reduce overhead on the developers' and researchers' side and enhance reproducibility in this

