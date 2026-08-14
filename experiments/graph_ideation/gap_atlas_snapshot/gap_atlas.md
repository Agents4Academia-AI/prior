# Prior Research Gap Atlas — draft snapshot

Generated 2026-08-14. 20 candidate gaps.

> These are hypotheses for human review, not claims that the literature gaps are real. Supporting quotations and graph relations are the evidence substrate; each proposed gap and resolving study must still be checked against the literature.

## 1. Contradiction Resolution

**Status:** `draft_unverified`  
**Card:** `gap:3449d52437ae`

### Candidate gap

The end-to-end automation claims of AI Scientist (S1) and AI Scientist-v2 (S3) directly contradict the empirical ceiling established by DS-1000/SciCode-style benchmarks (S2), which show state-of-the-art agents solve at most 32.4–42.2% of essential data-driven scientific coding subtasks — yet no study has applied the same granular, task-level benchmark methodology from S2 to the specific subtask outputs generated inside the S1/S3 pipelines, leaving unresolved whether the end-to-end systems actually clear the capability bar that S2 shows current agents cannot reach, or whether their apparent success is an artifact of LLM-based self-review masking failures on the same task classes.

### Evidence substrate

- **S1: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”
- **S2: ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery (2024).** State-of-the-art language agents solve at most 32.4% of real-world data-driven scientific coding tasks unaided and 34.3% with expert-provided knowledge; inference-time scaling (OpenAI o1-preview) raises this to 42.2% but at more than 10× the cost, while simpler self-debug frameworks outperform interactive CodeAct agents at a fraction of the price — collectively showing that current agents cannot automate essential tasks in scientific workflows.
  - Supporting quote: “the best-performing agent can only solve 32.4% of the tasks independently and 34.3% with expert-provided knowledge. In addition, we evaluate OpenAI o1-preview with direct prompting and self-debug, which can boost the performance to 42.2%, demonstrating the effectiveness of increasing inference-time compute but with more than 10 times the cost of other LLMs. Still, our results underscore the limitations of current language agents in generating code for data-driven discovery, let alone end-to-end automation for scientific research.”
- **S3: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”

Graph motif: `contradicts`. Contribution A claims a fully automated, end-to-end LLM pipeline can autonomously conduct scientific discovery in ML at low cost, validating the pipeline via an LLM-based reviewer. Contribution B directly and explicitly contests this claim: it constructs a benchmark showing that the best language agents solve at most 32.4–42.2% of essential data-driven scientific coding tasks, and explicitly argues that end-to-end automation claims (citing Contribution A by name) outpace actual agent capabilities. Evidence B:004 states "we contend that… before claiming they can automate data-driven discovery end-to-end" and critiques the LLM-based reviewer evaluation approach used in A. Evidence B:007 states results "suggest language agents cannot yet automate essential tasks in data-driven discovery nor the research pipelines end-to-end, in contrast to claims in recent work such as Lu et al. (2024)" — directly referencing Contribution A. CIT:2 further reinforces this, advocating for task-level evaluations "instead of purely relying on end-to-end evaluations… using an LLM-based reviewer to assess generated papers." This constitutes a genuine empirical and conceptual contradiction between the two contributions on the same construct: whether current LLM agents can automate scientific workflows end-to-end.

### What is missing

Granular, task-level success rates on the same categories of scientific coding tasks measured in S2 (e.g., data wrangling, statistical modeling, result interpretation, figure generation) as they appear within actual runs of the S1/S3 pipelines, evaluated by an objective, non-LLM ground-truth oracle rather than by LLM self-review — allowing a direct, apples-to-apples comparison of agent capability as measured end-to-end (S1/S3) versus as measured at the subtask level (S2).

### Smallest resolving study

Instrument the AI Scientist / AI Scientist-v2 pipeline to log every discrete scientific coding subtask it attempts (data loading, statistical analysis, visualization, etc.) during a fixed set of N ≥ 30 complete paper-generation runs. Map each logged subtask to the taxonomic categories used in S2's benchmark. Evaluate each subtask output against ground-truth solutions using the same automated, execution-based grading rubric from S2 (i.e., not an LLM reviewer). Compute per-category and aggregate pass rates and compare them directly to the 32.4–42.2% ceiling reported in S2. A statistically significant gap between end-to-end pass rates and the S2 benchmark ceiling would resolve the contradiction; parity or superiority would validate the automation claims; inferiority would confirm that self-review masks systematic failures.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 2. Contradiction Resolution

**Status:** `draft_unverified`  
**Card:** `gap:9fde6aef01dc`

### Candidate gap

S1 (The AI Scientist) claims that fully automated LLM-driven pipelines already produce ML papers exceeding a top-conference acceptance threshold, implying end-to-end scientific workflow automation is achievable today; S2 (ScienceAgentBench) directly contradicts this, reporting that the best agents solve at most 42.2% of individual scientific coding tasks and explicitly states agents "cannot yet automate essential tasks in data-driven discovery nor the research pipelines end-to-end, in contrast to claims in recent work such as Lu et al. (2024)." These two findings cannot simultaneously be true as stated: either current LLM agents can meaningfully automate scientific workflows end-to-end (S1) or they cannot (S2). The contradiction is unresolved because the two studies use incomparable evaluation instruments — S1 uses an LLM-based reviewer judging holistic paper quality across a narrow set of ML sub-topics, while S2 uses per-task programmatic evaluation across 102 real-world scientific coding problems spanning multiple disciplines. It is therefore unknown whether S1's positive result reflects genuine end-to-end capability, an artifact of its LLM-reviewer evaluation methodology, or domain specificity to narrow ML research tasks.

### Evidence substrate

- **S1: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** Fully automated LLM-driven scientific discovery can produce novel machine learning papers in diffusion modeling, transformer-based language modeling, and learning dynamics that exceed the acceptance threshold of a top machine learning conference as judged by an automated reviewer.
  - Supporting quote: “. The AI Scientist can produce papers that exceed the acceptance threshold at a top machine learning conference as judged by our automated reviewer. This approach signifies the beginning of a new era in scientific discovery in machine learning: bringing the transformati”
- **S2: ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery (2024).** State-of-the-art language agents solve at most 32.4% of real-world data-driven scientific coding tasks unaided and 34.3% with expert-provided knowledge; inference-time scaling (OpenAI o1-preview) raises this to 42.2% but at more than 10× the cost, while simpler self-debug frameworks outperform interactive CodeAct agents at a fraction of the price — collectively showing that current agents cannot automate essential tasks in scientific workflows.
  - Supporting quote: “the best-performing agent can only solve 32.4% of the tasks independently and 34.3% with expert-provided knowledge. In addition, we evaluate OpenAI o1-preview with direct prompting and self-debug, which can boost the performance to 42.2%, demonstrating the effectiveness of increasing inference-time compute but with more than 10 times the cost of other LLMs. Still, our results underscore the limitations of current language agents in generating code for data-driven discovery, let alone end-to-end automation for scientific research.”
- **S3: Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers (2024).** A controlled experimental framework for comparing human and LLM research idea generation — enforcing style standardization, matched topic distributions, and blind expert review — enables statistically rigorous head-to-head evaluation of ideation capabilities for the first time.
  - Supporting quote: “We address this by establishing an experimental design that evaluates research idea generation while controlling for confounders and performs the first head-to-head comparison between expert NLP researchers and an LLM ideation agent.”

Graph motif: `contradicts`. Contribution A (The AI Scientist) claims that fully automated LLM-driven scientific discovery can produce papers exceeding the acceptance threshold of a top ML conference, implying current agents can automate scientific workflows end-to-end. Contribution B (ScienceAgentBench) directly and explicitly contests this claim: it argues that agents solving at most 42.2% of individual scientific coding tasks cannot automate essential steps in scientific workflows, let alone full end-to-end research pipelines. Evidence B:004 directly names Lu et al. (2024) / Contribution A and disputes the claim of end-to-end automation, and CIT:2 explicitly contrasts its approach of careful per-task evaluation against Contribution A's LLM-based reviewer evaluation of generated papers. B:007 reinforces this by stating results "suggest language agents cannot yet automate essential tasks in data-driven discovery nor the research pipelines end-to-end, in contrast to claims in recent work such as Lu et al. (2024)." This is a genuine incompatibility in findings about the same construct — whether LLM agents can currently automate scientific discovery.

### What is missing

A controlled head-to-head evaluation that applies both evaluation instruments — (a) the holistic LLM-based paper-quality reviewer used in S1 and (b) the per-task programmatic correctness metrics used in S2 — to the same set of agent-generated scientific outputs, across both the narrow ML domains tested in S1 and the broader scientific coding domains tested in S2. Without this, it is impossible to determine whether the contradictory conclusions stem from (i) genuine capability differences across scientific domains, (ii) the evaluation methodology inflating or deflating apparent capability, or (iii) both.

### Smallest resolving study

Select a matched set of 20–30 scientific research tasks: half drawn from the ML sub-domains used in S1 (diffusion modeling, transformer LM, learning dynamics) and half from the non-ML scientific coding tasks in S2's benchmark. Run the same fully automated LLM agent pipeline from S1 on all tasks. For each output, apply both evaluation instruments in parallel: (1) the LLM-based reviewer scoring used in S1 (does the paper exceed acceptance threshold?), and (2) the per-task programmatic correctness metrics from S2 (does the generated code produce scientifically correct results?). A 2×2 analysis of domain (ML vs. non-ML) × evaluation method (holistic vs. per-task) will directly test whether the contradiction between S1 and S2 is attributable to evaluation methodology, domain specificity, or both — resolving whether the claimed end-to-end automation capability is real or an artifact of measurement.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 3. Contradiction Resolution

**Status:** `draft_unverified`  
**Card:** `gap:58468f275b1c`

### Candidate gap

There is a direct, unresolved contradiction between DN-Hypo-Pipeline (S1), which reports that LLM-generated hypotheses yield novel algorithms that outperform highly-cited baselines, and MLGym (S2), which finds that frontier LLMs fail to generate novel hypotheses or algorithms beyond hyperparameter tuning on open-ended AI research tasks. S3 partially bridges these by showing occasional but unreliable above-baseline performance (1/15 tasks). The contradiction cannot currently be resolved because no controlled experiment holds the task domain, baseline quality, evaluation protocol, scaffolding, and LLM family constant across both paradigms to determine whether the divergent findings stem from methodological differences (e.g., structured hypothesis scaffolding vs. open-ended prompting, curated vs. open task sets, how "novel" and "outperform" are operationalized) or reflect a genuine capability boundary.

### Evidence substrate

- **S1: DN-Hypo-Pipeline: An AI-Driven Workflow for Hypothesis Generation via Large Language Models and Scientific Explanations (2026).** Novel algorithms derived from LLM-generated hypotheses that outperform baseline models from highly cited data science papers, providing end-to-end experimental validation of AI-generated scientific hypotheses.
  - Supporting quote: “we validated the two highest-scoring generated hypotheses by developing corresponding novel algorithms, which outperformed the baseline models presented in the original papers.”
- **S2: MLGym: A New Framework and Benchmark for Advancing AI Research Agents (2025).** Frontier LLMs (Claude-3.5-Sonnet, Llama-3.1 405B, GPT-4o, o1-preview, Gemini-1.5 Pro) can improve on given baselines primarily through hyperparameter tuning but do not generate novel hypotheses, algorithms, or architectures when evaluated on open-ended AI research tasks.
  - Supporting quote: “ng algorithms for training agents on AI research tasks. We find that current frontier models can improve on the given baselines, usually by finding better hyperparameters, but do not generate novel hypotheses, algorithms, architectures, or substantial improvements.”
- **S3: ResearchGym: Evaluating Language Model Agents on Real-World AI Research (2026).** Frontier AI agents exhibit a sharp capability–reliability gap on end-to-end research tasks: a GPT-5-based agent surpasses provided baselines in only 1 of 15 evaluations (6.7%) and completes 26.5% of sub-tasks on average, yet in one run exceeds the human reference solution of an ICML 2025 Spotlight task, showing occasional but unreliable state-of-the-art performance.
  - Supporting quote: “improves over provided baselines in only 1 run (6.7%) and completes just 26.5% of sub-tasks on average, with performance plateauing after 9 hours. Yet this single successful run outperforms the human reference solution on an ICML 2025 Spotlight task, demonstrating that current frontier agents can occasionally reach state-of-the-art, but do so unreliably”

Graph motif: `contradicts`. Both contributions directly investigate the same central question: whether LLMs can generate novel hypotheses and algorithms that surpass existing baselines in AI/data science research tasks. Contribution A (DN-Hypo-Pipeline) reports that LLM-generated hypotheses led to novel algorithms that outperformed baseline models from highly cited papers [AQ, A:001]. Contribution B (MLGym) directly and explicitly finds the opposite: frontier LLMs (Claude-3.5-Sonnet, GPT-4o, o1-preview, Llama-3.1 405B, Gemini-1.5 Pro) "do not generate novel hypotheses, algorithms, architectures, or substantial improvements" beyond hyperparameter tuning [BQ, B:002]. The capability framework in B [B:008, B:009] defines Level 3 as "novel scientific contribution" — the very capability A claims to demonstrate but B finds absent. These findings are genuinely incompatible on the same construct (LLM capacity for novel hypothesis/algorithm generation in AI research), making this a contradicts relationship. The lack of citation between them is consistent with them being independent evaluations arriving at conflicting conclusions.

### What is missing

A head-to-head controlled comparison measuring the same LLMs (e.g., Claude-3.5-Sonnet, GPT-4o) on the same set of AI/data science tasks under two conditions — (A) the structured hypothesis-generation pipeline used in DN-Hypo-Pipeline and (B) the open-ended agent framework used in MLGym — using a shared, pre-registered definition of "novel algorithm" and "outperforms baseline," with the same baselines drawn from highly-cited papers. Without this, it is impossible to attribute the contradictory results to scaffold design, task selection, evaluation criteria, or an actual LLM capability ceiling.

### Smallest resolving study

Select 6–10 AI/data science tasks that satisfy both frameworks' eligibility criteria (i.e., have a clearly defined baseline from a high-citation paper and are open-ended enough for MLGym-style evaluation). For each task, run the same set of frontier LLMs (at minimum Claude-3.5-Sonnet and GPT-4o) under two conditions in a within-task, within-model design: Condition A replicates the DN-Hypo-Pipeline structured hypothesis-elicitation and algorithm-derivation scaffold; Condition B replicates the MLGym open-ended agent loop with identical compute budget and iteration limit. Pre-register a binary operationalization of "novel algorithm that outperforms baseline" (e.g., statistically significant improvement on a held-out test set, with the proposed method differing from the baseline in at least one non-hyperparameter design choice, as judged by two blinded domain experts). Primary outcome: proportion of tasks where a novel, above-baseline algorithm is produced, compared across the two conditions and between models. This directly tests whether the contradiction is attributable to scaffold design (condition difference) or LLM capability (no condition difference, both near zero or both above zero).

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 4. Contradiction Resolution

**Status:** `draft_unverified`  
**Card:** `gap:f136eb3e686c`

### Candidate gap

Agentic AI systems show diametrically opposed performance on social science reproducibility tasks — below random-guessing (21.4%) in end-to-end assessment (S1) versus near-ceiling accuracy (93.4% task-level) in computational reproduction (S2) — yet it is unknown whether this contradiction reflects a genuine capability difference driven by agent architecture (general-purpose vs. purpose-built coding agent) or by task scope (end-to-end assessment vs. isolated computational reproduction), because no study has held one variable constant while varying the other on a shared benchmark.

### Evidence substrate

- **S1: REPRO-Bench: Can Agentic AI Systems Assess the Reproducibility of Social Science Research? (2025).** State-of-the-art agentic AI systems perform below random-guessing baseline on end-to-end social science reproducibility assessment, with the best evaluated agent (CORE-Agent) reaching only 21.4% accuracy on a four-class scoring task.
  - Supporting quote: “We evaluate three representative AI agents on REPRO-Bench , with the best-performing agent achieving an accuracy of only 21.4%. Building on our empirical analysis, we develop REPRO-Agent , which improves the highes”
- **S2: AI Coding Agents Can Reproduce Social Science Findings (2026).** Frontier AI coding agents achieve high computational reproducibility on social science findings: Claude Code reaches 93.4% task-level and 78.0% paper-level accuracy, substantially outperforming Codex (62.1% / 35.8%) and considerably exceeding reproduction rates previously reported for general-purpose LLM-based agents on comparable benchmarks.
  - Supporting quote: “we find that both can reproduce a large share of social science findings, with Claude Code substantially outperforming Codex. These reproduction rates considerably exceed those previously reported for general-purpose LLM-based agents on comparable reproducibility benchmarks”
- **S3: ReplicationBench: Can AI Agents Replicate Astrophysics Research Papers? (2025).** An evaluation framework for scientific AI agents that measures replication success on end-result-graded, objectively scorable tasks — assessing both faithfulness (adherence to original methods) and correctness (technical accuracy) — without requiring extensive human-written rubrics, enabling scalable measurement of agent reliability in computational research.
  - Supporting quote: “Evaluation Framework for Scientific Agents: We establish a broader evaluation framework, measuring agent reliability in computational research tasks by measuring replication success on objectively gradable tasks.”

Graph motif: `contradicts`. Both contributions directly address the capability of agentic AI systems on social science reproducibility tasks, and their findings are genuinely incompatible. Contribution A reports that the best-performing agent (CORE-Agent) reaches only 21.4% accuracy on REPRO-Bench — below the 25% random-guessing baseline — concluding that current agentic AI systems are inadequate for reproducibility assessment (A:005, A:026, AQ). Contribution B reports that frontier coding agents (Claude Code: 93.4% task-level, 78.0% paper-level) achieve high computational reproducibility on social science findings, explicitly framing this as exceeding prior benchmarks where "best-case performance on reproducibility tasks rarely surpassed 35–40% even with task-specific scaffolding" (B:034, B:035, BQ). Critically, B:018 directly references REPRO-Bench's best result of 36.6% (Contribution A's improved REPRO-Agent) as representative of general-purpose LLM-agent limitations that frontier coding agents now substantially surpass. The two contributions thus offer diametrically opposed pictures of agentic AI capability on the same construct (social science reproducibility), with incompatible quantitative findings on overlapping benchmarks and agent types. The key distinction — general-purpose vs. purpose-built coding agents and task scope (end-to-end assessment vs. computational reproduction) — partially mediates the gap, but both contributions frame their results as characterizing agentic AI on social science reproducibility broadly, making the contradiction substantive and direct.

### What is missing

A controlled comparison in which both a general-purpose agentic system (matching S1's CORE-Agent class) and a frontier coding agent (matching S2's Claude Code class) are evaluated on the same set of social science reproducibility items, scored under both (a) the end-to-end four-class assessment rubric used in S1/REPRO-Bench and (b) the binary computational-reproduction rubric used in S2, with the S3 faithfulness/correctness framework applied uniformly. Without this 2×2 design (agent type × task scope), it is impossible to determine whether the ~70-percentage-point performance gap between S1 and S2 is attributable to agent architecture, task operationalization, or both.

### Smallest resolving study

Select 30–50 social science papers from REPRO-Bench that have both (i) a scorable end-to-end reproducibility verdict (four-class, as in S1) and (ii) extractable computational reproduction steps (as in S2). Assign each paper to four conditions in a 2×2 factorial design: [CORE-Agent class | Claude Code class] × [end-to-end assessment rubric | computational reproduction rubric]. Score all conditions using the S3 faithfulness-and-correctness framework as a common measurement layer. The primary outcome is accuracy per cell; the critical test is the interaction term — if agent type dominates, the gap persists across both rubrics; if task scope dominates, both agents converge when given the narrower computational-reproduction task. This design directly resolves the contradiction by isolating its source without requiring new benchmarks or human-written rubrics beyond what S1–S3 already provide.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 5. Boundary Generalization

**Status:** `draft_unverified`  
**Card:** `gap:f549c8bdbc34`

### Candidate gap

HypoRefine's collaborative literature-grounded hypothesis refinement architecture is validated only on five social-science text-classification tasks that share structural similarities (short-text, label-based classification). It is unknown whether the boundary of this advantage — specifically the gains over the data-only HypoGeniC backbone — generalises to domains with qualitatively different hypothesis structures, such as natural-science or biomedical tasks where hypotheses involve quantitative relationships, causal mechanisms, or multi-step reasoning rather than social-construct labels.

### Evidence substrate

- **S1: Literature Meets Data: A Synergistic Approach to Hypothesis Generation (2024).** HypoRefine — a method that grounds data-driven hypothesis generation (via HypoGeniC) with literature-based insights through a collaborative agent architecture that refines and maintains a shared hypothesis pool — outperforms literature-only, data-only, and few-shot baselines on out-of-distribution generalization across five social-science classification tasks (15.75%, 3.37%, and 8.97% gains, respectively).
  - Supporting quote: “We propose the first approach to using both literature information and data for LLM-powered hypothesis generation.”
- **S2: Hypothesis Generation with Large Language Models (2024).** HypoGeniC — an iterative hypothesis generation algorithm for LLMs inspired by the upper confidence bound (UCB) multi-armed bandit framework — generates and refines data-grounded hypotheses by maintaining a wrong-example bank and a reward-driven exploitation-exploration tradeoff, enabling LLMs to handle arbitrarily large training sets without long-context limitations.
  - Supporting quote: “We propose a novel computational framework for generating and evaluating hypotheses with LLMs.”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `builds_on`. HypoRefine (Contribution A) explicitly and directly builds on HypoGeniC (Contribution B) as its data-driven backbone. Evidence is unambiguous: CIT:1 shows A adopts HypoGeniC's algorithm directly ("our data-driven hypothesis generation adopts in [CITED:TARGET]"); A:010 describes HypoRefine integrating paper summaries "with HypoGeniC" in both initialization and update stages, reusing HypoGeniC's reward function and hypothesis bank update process unchanged; A:005 states "For the data-driven component, we use HypoGeniC as the backbone"; and A:002 frames HypoRefine as extending HypoGeniC with literature-based insights. Contribution A does not merely cite B for background — it structurally incorporates B's algorithm as a core component and extends it with a collaborative literature-based agent architecture.

### What is missing

Direct performance comparison between HypoRefine and HypoGeniC on at least one non-social-science domain (e.g., biomedical phenotype prediction, clinical NLP, or physical-science classification) where the underlying hypotheses are not social-construct labels but quantitative or mechanistic rules. Without this, the 15.75% and 3.37% gains reported for HypoRefine over literature-only and data-only baselines cannot be attributed to the general architecture rather than to the specific structure of social-science hypothesis spaces.

### Smallest resolving study

Take the existing HypoRefine and HypoGeniC implementations unchanged. Select two out-of-domain benchmark datasets whose hypotheses are structurally distinct from social-science labels — e.g., a biomedical text-classification task (such as PubMed disease subtype classification) and a physical-science task (such as material-property prediction from descriptions). Run both systems under identical conditions (same LLM backbone, same train/test split protocol, same out-of-distribution evaluation setup used in the original five tasks). Compare HypoRefine vs. HypoGeniC accuracy gains and the qualitative form of the generated hypotheses. If the literature-grounding advantage shrinks or reverses, the benefit is boundary-limited to social-science hypothesis structures; if it persists, the architecture generalises beyond its tested domain.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 6. Boundary Generalization

**Status:** `draft_unverified`  
**Card:** `gap:afb648d74975`

### Candidate gap

It is unknown whether the AI Scientist-v2's template-free, agentic tree-search pipeline generalizes to scientific domains outside machine learning (e.g., biology, chemistry, or physics), or whether its autonomous discovery capabilities remain boundary-limited to the ML settings in which both v1 and v2 were developed and evaluated.

### Evidence substrate

- **S1: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”
- **S2: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”
- **S3: Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers (2024).** A controlled experimental framework for comparing human and LLM research idea generation — enforcing style standardization, matched topic distributions, and blind expert review — enables statistically rigorous head-to-head evaluation of ideation capabilities for the first time.
  - Supporting quote: “We address this by establishing an experimental design that evaluates research idea generation while controlling for confounders and performs the first head-to-head comparison between expert NLP researchers and an LLM ideation agent.”

Graph motif: `builds_on`. The AI Scientist-v2 (Contribution B) explicitly and directly extends the original AI Scientist (Contribution A). Evidence is overwhelming: B:000 describes v2 as a successor to "its predecessor (v1, Lu et al., 2024)" and enumerates concrete improvements over it; B:001 provides a direct feature-by-feature comparison table contrasting v1 and v2; B:002 states "The AI Scientist-v1 (Lu et al., 2024) introduced the first AI system that entirely automates scientific discovery… However, despite representing a significant step forward, The AI Scientist-v1 was subject to limitations," and proceeds to describe how v2 addresses each limitation. The citation passages (CIT:1, CIT:2) further confirm that B explicitly identifies A's system as the artifact being extended, noting it "relied heavily on human-authored code templates" and other constraints that B's agentic tree-search methodology directly resolves. This is a canonical builds_on relationship: v2 takes v1's pipeline as its foundation and augments it with agentic tree search, VLM feedback, parallel execution, and template-free operation.

### What is missing

Neither v1 (S1) nor v2 (S2) reports performance, paper quality, or experimental success rates outside machine learning domains. S3's controlled evaluation framework for LLM ideation was also applied only within ML. No evidence exists for how the pipeline behaves when the hypothesis space, experimental tooling, data modalities, or domain conventions differ substantially from ML — meaning the domain boundary of the system's generalization is entirely untested.

### Smallest resolving study

Select two non-ML scientific domains with well-defined experimental tasks and ground-truth benchmarks (e.g., a computational biology task such as protein property prediction, and a chemistry task such as reaction yield optimization). Apply the AI Scientist-v2 pipeline unchanged (no domain-specific tuning) to each domain. Use the S3-style blind expert review protocol — with style standardization and domain-matched human-authored idea baselines — to score autonomously generated manuscripts on novelty, correctness, and executability. Compare these scores to v2's published ML-domain scores to determine whether performance is maintained, degraded, or collapses outside ML, thereby establishing the generalization boundary of the agentic pipeline.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 7. Boundary Generalization

**Status:** `draft_unverified`  
**Card:** `gap:7be9af90741e`

### Candidate gap

It is unknown whether the template-free, agentic architecture of AI Scientist-v2 generalizes beyond machine learning to scientific domains with fundamentally different experimental modalities (e.g., wet-lab biology, chemistry, or physics), or whether its performance gains over v1 are specific to the ML-code-execution boundary condition in which both systems were evaluated.

### Evidence substrate

- **S1: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”
- **S2: Towards end-to-end automation of AI research (2026).** The AI Scientist — a fully automated, end-to-end scientific research pipeline that autonomously generates research ideas, writes and executes code, runs experiments, analyzes and plots results, writes complete machine-learning conference manuscripts, and performs automated peer review.
  - Supporting quote: “ere we present a pipeline for automating the entire scientific process end to  end. We present The AI Scientist, which creates research ideas, writes code, runs  experiments, plots and analyses data, writes the entire scientific manuscript, and  performs its own peer revie”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `builds_on`. Contribution A (AI Scientist-v2) explicitly positions itself as a direct successor and extension of Contribution B (AI Scientist-v1/Lu et al., 2024). Evidence A:000 states it "eliminates the reliance on human-authored code templates" compared to "its predecessor (v1, Lu et al., 2024)." Evidence A:002 explicitly names "The AI Scientist-v1 (Lu et al., 2024)" as the system it extends, describing the limitations it overcomes. Evidence A:001 provides a direct feature comparison table between v1 and v2. Evidence A:013 again cites v1 as the foundational prior work. The AQ quote states v2 "significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems." A builds directly on B's pipeline architecture, extending it with agentic tree search, VLM feedback, and template-free operation.

### What is missing

Neither S1 (v2) nor S2/S3 (v1) provide any evaluation of the end-to-end pipeline outside of machine learning tasks. All reported experiments, manuscripts, and peer-review cycles are situated within ML subdomain benchmarks. There is no evidence about how the progressive agentic tree-search, VLM figure-refinement loop, or template-free hypothesis generation perform when the "experiment" step cannot be reduced to runnable Python code — i.e., when it requires physical lab operations, external instrumentation, or multi-day iterative wet-lab protocols. The boundary at which the architecture's autonomy claims hold is entirely untested.

### Smallest resolving study

Select two non-ML scientific domains that differ maximally in experimental modality — one that permits simulation-based execution (e.g., computational chemistry via a Python-callable simulator) and one that does not (e.g., a standard molecular biology assay requiring physical lab steps). Apply both AI Scientist-v1 (as the template-dependent baseline, per S2/S3) and AI Scientist-v2 (template-free, per S1) to an identical, pre-specified hypothesis-generation prompt in each domain. Measure (a) task completion rate (full manuscript produced), (b) hypothesis–experiment alignment score assessed by domain expert reviewers blind to system version, and (c) the proportion of experiment cycles that required human intervention. This 2×2 design (system version × domain modality) directly tests whether the autonomy improvements documented in v2 generalize beyond the ML boundary or are artifacts of the code-executable experimental setting shared by both versions.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 8. Boundary Generalization

**Status:** `draft_unverified`  
**Card:** `gap:cde08c88b196`

### Candidate gap

It is unknown whether the integrated literature-based + data-driven hypothesis generation approach (S1, arxiv:2410.17309v3) retains its generalizability advantage over HypoGeniC alone (S2) when applied to scientific discovery domains beyond the five NLP/behavioral datasets on which it was evaluated — particularly in the kind of open-ended, multi-disciplinary machine-learning research setting operationalized by The AI Scientist pipeline (S3).

### Evidence substrate

- **S1: Literature Meets Data: A Synergistic Approach to Hypothesis Generation (2024).** Automatic evaluation across five datasets shows that integrating literature-based and data-driven hypothesis generation yields the best generalizability, measured by out-of-distribution accuracy, across all task and model configurations, and that the generated hypotheses transfer effectively to different inference models.
  - Supporting quote: “mplementation and Baselines 4 Results 4.1 Automatic Evaluation Hypotheses generated by combining information from literature and data achieves the best performance across all task and model configurations ( Table 1 ).”
- **S2: Hypothesis Generation with Large Language Models (2024).** HypoGeniC — an iterative hypothesis generation algorithm for LLMs inspired by the upper confidence bound (UCB) multi-armed bandit framework — generates and refines data-grounded hypotheses by maintaining a wrong-example bank and a reward-driven exploitation-exploration tradeoff, enabling LLMs to handle arbitrarily large training sets without long-context limitations.
  - Supporting quote: “We propose a novel computational framework for generating and evaluating hypotheses with LLMs.”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `builds_on`. Contribution A (arxiv:2410.17309v3) explicitly and directly builds on Contribution B (HypoGeniC, openalex:W4394647523). Evidence A:005 states "For the data-driven component, we use HypoGeniC as the backbone," and describes how the literature-based hypothesis agent interacts with HypoGeniC. Evidence A:010 details HypoRefine, which integrates literature summaries with HypoGeniC's pipeline, preserving HypoGeniC's reward function and update process. The citation passage CIT:1 confirms that A's data-driven hypothesis generation "adopts" the method in B (HypoGeniC). CIT:2 situates B as the data-driven baseline that A extends by combining it with literature-based approaches. A's central contribution — the first method integrating literature-based and data-driven hypothesis generation — explicitly uses HypoGeniC as a core component and extends it rather than merely citing it as background. This is a clear builds_on relationship from A to B.

### What is missing

Out-of-distribution accuracy and hypothesis transfer rates for the integrated method versus the HypoGeniC-only baseline across task domains that differ structurally from the original five datasets — specifically domains characterized by long experimental cycles, heterogeneous literature corpora, and auto-generated training signals, as exemplified by The AI Scientist's autonomous ML research loop.

### Smallest resolving study

Instantiate the integrated literature+data-driven hypothesis generator (arxiv:2410.17309v3) and the HypoGeniC baseline (openalex:W4394647523) within The AI Scientist's end-to-end pipeline (openalex:W4402952666) by treating each AI-Scientist-generated experimental result as a labeled training example and the associated literature search outputs as the literature corpus. Run both systems on at least three ML sub-domains (e.g., image classification, language modeling, reinforcement learning) held out from the original five evaluation datasets. Measure out-of-distribution accuracy of generated hypotheses (evaluated by held-out experiment outcomes) and transfer accuracy to a different inference model, comparing the two systems under identical compute budgets. A statistically significant difference in out-of-distribution accuracy would confirm or refute boundary generalization of the integrated approach beyond its original task distribution.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 9. Replication Validation

**Status:** `draft_unverified`  
**Card:** `gap:405774311f40`

### Candidate gap

It remains unvalidated whether the peer-review success reported independently by AI Scientist (S2/S3) and AI Scientist-v2 (S1) reflects a reproducible, system-agnostic phenomenon or whether the single passing manuscript in each case is an outlier attributable to idiosyncratic reviewer leniency, workshop-specific standards, or cherry-picking from a larger submission pool.

### Evidence substrate

- **S1: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** A fully AI-generated manuscript can successfully pass peer review at a recognized machine learning workshop, with one AI-generated submission exceeding the average human acceptance threshold at an ICLR workshop.
  - Supporting quote: “We demonstrate, for the first time, that an AI-generated manuscript can successfully pass peer review at a recognized machine learning workshop, marking a critical milestone for AI science.”
- **S2: Towards end-to-end automation of AI research (2026).** AI-generated research manuscripts can pass the first round of peer review at a workshop of a top-tier machine learning conference, demonstrating that fully autonomous scientific output meets a non-trivial human-evaluated quality bar.
  - Supporting quote: “ts ideas, execution and presentation are of sufficient  quality that the manuscript generated by this AI system passed the first round of peer  review for a workshop of a top-tier machine learning conference”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `supports`. Both contributions make the same empirical claim: a fully AI-generated manuscript successfully passed peer review at a workshop of a top-tier machine learning conference (ICLR), establishing a milestone for autonomous AI-driven scientific output. Contribution A (AI Scientist-v2) reports one manuscript exceeding the average human acceptance threshold at the ICBINB@ICLR workshop with a score of 6.33 [A:001, A:008], while Contribution B (AI Scientist, published in Nature) reports passing the first round of peer review at a workshop of a top-tier ML conference [BQ, B:000, B:004]. The core empirical finding — that an AI system can produce a manuscript of sufficient quality to clear a human peer-review bar at an ICLR workshop — is materially the same across both contributions. The overlapping author sets (Lu, Lange, Yamada, Hu, Ha, Foerster, Clune) and the shared framing of this as a "milestone" [AQ, B:004] further confirm that these are parallel or sequential demonstrations of the same phenomenon. Neither corrects nor extends the other's method in a directional sense; they independently corroborate the same finding, making 'supports' (symmetric) the most defensible relation.

### What is missing

Neither contribution provides a controlled, pre-registered replication: (a) the full distribution of scores across all AI-generated submissions to the same venue is not disclosed, (b) no independent research group has re-run either pipeline and submitted to the same or an equivalent ICLR workshop to reproduce the pass rate, and (c) no side-by-side comparison of reviewer scores for matched AI-generated vs. human-authored submissions to the same workshop call exists to confirm that the reported threshold-crossing is reliably above chance rather than within normal score variance.

### Smallest resolving study

Pre-register a replication study in which two independent labs each run the full AI Scientist (v1, S3) pipeline and the AI Scientist-v2 pipeline (S1) to generate N ≥ 10 manuscripts per system, then submit all manuscripts blind to the same ICLR workshop call (or a directly comparable venue). Record the complete distribution of reviewer scores for all submissions—not only those that pass—and compare pass rates across systems and against a matched control set of human-authored workshop submissions from the same call. A statistically significant pass rate above the human baseline in at least one independent replication would constitute confirmatory evidence; failure to replicate would reveal the original reports as non-representative single-case milestones.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 10. Replication Validation

**Status:** `draft_unverified`  
**Card:** `gap:28bbbad18d75`

### Candidate gap

The tournament-evolution self-improving hypothesis generation mechanism reported by S1 and S2 has not been independently validated under the replication framework defined by S3. Specifically, it is unknown whether an AI agent implementing the tournament-evolution process can replicate the core empirical claims of either paper—namely that iterative win/loss-driven hypothesis revision produces measurably higher-quality hypotheses than a non-tournament baseline—when evaluated by an objective, rubric-free framework assessing both faithfulness to original methods and correctness of outcomes.

### Evidence substrate

- **S1: Towards an AI co-scientist (2025).** A tournament evolution process — where hypotheses compete, win/loss patterns are identified, and losing hypotheses are iteratively revised — enables self-improving hypothesis generation in AI-assisted scientific discovery.
  - Supporting quote: “ay based scientific debate step for generating novel research hypotheses; tournaments that compare and rank hypotheses via the process of finding win and loss patterns, and a hypothesis evolution process to improve their quality. Fin”
- **S2: Accelerating scientific discovery with Co-Scientist (2026).** Tournament-based evolution using self-play scientific debate iteratively compares, ranks, and refines hypotheses to improve their quality.
  - Supporting quote: “a tournament evolution  process for self-improving hypotheses generatio”
- **S3: ReplicationBench: Can AI Agents Replicate Astrophysics Research Papers? (2025).** An evaluation framework for scientific AI agents that measures replication success on end-result-graded, objectively scorable tasks — assessing both faithfulness (adherence to original methods) and correctness (technical accuracy) — without requiring extensive human-written rubrics, enabling scalable measurement of agent reliability in computational research.
  - Supporting quote: “Evaluation Framework for Scientific Agents: We establish a broader evaluation framework, measuring agent reliability in computational research tasks by measuring replication success on objectively gradable tasks.”

Graph motif: `supports`. Both contributions describe an essentially identical mechanism: a tournament evolution process combined with self-play/debate that iteratively compares, ranks, and refines hypotheses to achieve self-improving hypothesis generation. Evidence A:001 and B:005 use nearly verbatim language ("a tournament evolution process for self-improving hypotheses generation"), and A:007/AQ describe "tournaments that compare and rank hypotheses via the process of finding win and loss patterns, and a hypothesis evolution process to improve their quality," which is mirrored in BQ and B:025's "tournament-based selection, and iterative evolution and refinement." The two papers (an AI co-scientist / Co-Scientist) appear to be closely related or co-timed versions of the same system (A:012 references "a co-timed report"), producing materially corroborating findings about the same tournament-evolution approach. No citation exists between them in the corpus, but the convergent findings mutually corroborate one another, making 'supports' the most defensible relation. 'Builds_on' is not warranted since neither is shown to explicitly extend the other's prior published result; rather they report the same core contribution concurrently.

### What is missing

No study has applied the scalable replication evaluation framework from S3 (end-result-graded, faithfulness + correctness scoring, no extensive human rubrics) to the tournament-evolution hypothesis generation system described in S1 and S2. There is no independent, objectively scored replication confirming that the tournament self-play mechanism actually produces the self-improvement effect claimed, as opposed to an artifact of the specific experimental setup or human evaluation choices used in the original reports.

### Smallest resolving study

Implement the tournament-evolution hypothesis generation pipeline as described in S1/S2 (hypothesis competition, win/loss pattern identification, iterative revision via self-play debate) in a controlled computational research domain with objectively scorable ground-truth outcomes (e.g., a well-characterized benchmark in bioinformatics or chemistry). Apply the S3 evaluation framework to score: (1) faithfulness—does the agent's pipeline adhere to the tournament-evolution procedure as specified?—and (2) correctness—do the evolved hypotheses achieve measurably superior scores compared to a non-tournament (single-pass) baseline on the same tasks? Run both conditions with the same underlying model and hyperparameters, across at least three independent task domains included in or analogous to S3's benchmark suite, and report replication success rates, effect sizes, and any failure modes identified by the automated scorer.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 11. Replication Validation

**Status:** `draft_unverified`  
**Card:** `gap:9d2fdbd3287a`

### Candidate gap

The peer-review passage result reported for The AI Scientist in the 2026 Nature article (S2) has not been independently replicated: both the automated-reviewer threshold result (S1) and the human peer-review passage result (S2) originate from the same overlapping author team describing the same system, so no independent group has confirmed that a fully autonomous LLM-driven pipeline can produce manuscripts that clear a human peer-review bar at a top-tier ML venue.

### Evidence substrate

- **S1: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** Fully automated LLM-driven scientific discovery can produce novel machine learning papers in diffusion modeling, transformer-based language modeling, and learning dynamics that exceed the acceptance threshold of a top machine learning conference as judged by an automated reviewer.
  - Supporting quote: “. The AI Scientist can produce papers that exceed the acceptance threshold at a top machine learning conference as judged by our automated reviewer. This approach signifies the beginning of a new era in scientific discovery in machine learning: bringing the transformati”
- **S2: Towards end-to-end automation of AI research (2026).** AI-generated research manuscripts can pass the first round of peer review at a workshop of a top-tier machine learning conference, demonstrating that fully autonomous scientific output meets a non-trivial human-evaluated quality bar.
  - Supporting quote: “ts ideas, execution and presentation are of sufficient  quality that the manuscript generated by this AI system passed the first round of peer  review for a workshop of a top-tier machine learning conference”
- **S3: ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery (2024).** State-of-the-art language agents solve at most 32.4% of real-world data-driven scientific coding tasks unaided and 34.3% with expert-provided knowledge; inference-time scaling (OpenAI o1-preview) raises this to 42.2% but at more than 10× the cost, while simpler self-debug frameworks outperform interactive CodeAct agents at a fraction of the price — collectively showing that current agents cannot automate essential tasks in scientific workflows.
  - Supporting quote: “the best-performing agent can only solve 32.4% of the tasks independently and 34.3% with expert-provided knowledge. In addition, we evaluate OpenAI o1-preview with direct prompting and self-debug, which can boost the performance to 42.2%, demonstrating the effectiveness of increasing inference-time compute but with more than 10 times the cost of other LLMs. Still, our results underscore the limitations of current language agents in generating code for data-driven discovery, let alone end-to-end automation for scientific research.”

Graph motif: `supports`. Both contributions report the same core empirical finding: The AI Scientist system, which fully automates the scientific research lifecycle using LLMs, produced manuscripts that met or exceeded a peer-review acceptance threshold at a top-tier machine learning conference/workshop. Contribution A (the 2024 preprint) reports that generated papers exceed the acceptance threshold as judged by an automated reviewer (AQ, A:000, A:002), while Contribution B (the 2026 Nature article) reports that an AI-generated manuscript passed the first round of human peer review at a workshop of a top-tier ML conference (BQ, B:000, B:001, B:004). The two contributions are from overlapping author teams (Lu, Lu, Lange, Foerster, Ha, Clune) and describe the same system and its key result from different stages of publication/maturation. The findings materially corroborate each other—both establish that fully autonomous AI scientific output meets a non-trivial quality bar—making 'supports' the most defensible relation. The lack of a direct citation is consistent with the A→B evolution of the same project rather than independent corroboration, but the framing of each as a distinct contribution (automated reviewer threshold vs. human peer-review passage) means 'supports' is more appropriate than 'builds_on', as neither contribution explicitly uses or extends the other's method or artifact in a one-directional sense at the contribution level described.

### What is missing

An independent replication—conducted by a team with no overlap with the original authors—demonstrating that a fully autonomous LLM-based scientific discovery system produces manuscripts that pass at least one round of human peer review at a recognised ML conference or workshop. Crucially, S3 establishes that current agents solve at most 42.2% of real-world scientific coding tasks, suggesting the pipeline may succeed on manuscript quality while failing on underlying scientific task execution; an independent replication would reveal whether the peer-review passage result is robust or an artifact of the specific system, task selection, or evaluation context used by the original team.

### Smallest resolving study

An independent research group (no author overlap with S1/S2) runs a fully automated LLM-driven research pipeline—replicating the AI Scientist setup as closely as possible using the published description and any released code—on at least three ML sub-domains (matching S1's domains: diffusion modeling, transformer LM, and learning dynamics). The resulting manuscripts are submitted blind to the same workshop venue or a directly comparable ML workshop. The primary outcome is the fraction of submissions that pass the first round of human peer review, benchmarked against the S2 claim of at least one passing manuscript. A secondary outcome records the fraction of underlying scientific coding sub-tasks successfully completed by the agent, enabling direct comparison with the ≤42.2% ceiling reported in S3 and assessment of whether manuscript quality and task-execution capability are decoupled.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 12. Replication Validation

**Status:** `draft_unverified`  
**Card:** `gap:5f7129d6bddf`

### Candidate gap

It is unverified whether the multi-agent, asynchronous task-execution architecture reported independently by the two co-timed AI co-scientist papers (S1, S2) actually replicates in terms of hypothesis quality, compute-scaling behavior, and tournament evolution outcomes when both systems are subjected to identical benchmark inputs, evaluation rubrics, and computational budgets.

### Evidence substrate

- **S1: Towards an AI co-scientist (2025).** A multi-agent architecture with an asynchronous task execution framework enables flexible compute scaling for hypothesis-generation pipelines in scientific discovery systems.
  - Supporting quote: “Key contributions include: (1) a multi-agent architecture with an asynchronous task execution framework for flexible compute scaling”
- **S2: Accelerating scientific discovery with Co-Scientist (2026).** A multi-agent architecture with asynchronous task execution framework flexibly allocates computational resources for scientific reasoning, enabling dynamic scaling of test-time compute.
  - Supporting quote: “a multi-agent architecture with an  asynchronous task execution framework for flexible compute scalin”
- **S3: Robin: A multi-agent system for automating scientific discovery (2025).** Robin — a multi-agent system integrating literature search agents (Crow for concise reviews, Falcon for deep reviews) with an experimental data analysis agent (Finch) — automates hypothesis generation, experimental design, result interpretation, and iterative hypothesis refinement in a single continuous workflow, constituting the first end-to-end AI system for autonomous scientific discovery within a lab-in-the-loop framework.
  - Supporting quote: “we introduce Robin, the first multi-agent system capable of fully automating the key intellectual steps of the scientific process. By integrating literature search agents with data analysis agents, Robin can generate hypotheses, propose experiments, interpret experimental results, and generate updated hypotheses, achieving a semi-autonomous approach to scientific discovery”

Graph motif: `supports`. Both contributions describe virtually identical architectural findings: a multi-agent system built on Gemini with an asynchronous task execution framework that enables flexible scaling of test-time compute for scientific hypothesis generation. Evidence AQ and BQ show near-verbatim matching contribution statements. A:001 and B:005 both describe key contribution (1) in identical language ("a multi-agent architecture with an asynchronous task execution framework for flexible compute scaling") and share the same tournament evolution process as key contribution (2). A:012 and A:022 further confirm Paper A's system design, while B:009 and B:025 confirm Paper B's. The two papers appear to be co-timed parallel reports (A:012 references "co-timed report [20, 21]") describing the same or very closely related systems (AI co-scientist vs. Co-Scientist, both on Gemini), arriving at materially identical architectural findings. Without a citation between them, and given they are parallel/co-timed works rather than one explicitly building on the other, 'supports' is the most defensible classification — their comparable findings mutually corroborate one another. A 'builds_on' relation is not warranted since neither paper explicitly uses or extends the other's artifact; they appear to be concurrent parallel developments.

### What is missing

A direct, controlled replication study comparing the S1 and S2 systems on the same scientific hypothesis-generation benchmarks under matched conditions (same seed hypotheses, same compute budget, same evaluator). S3 (Robin) demonstrates that an end-to-end autonomous discovery workflow with distinct specialist agents (Crow, Falcon, Finch) can be constructed and evaluated; however, no evidence exists that the near-identical architectural claims of S1 and S2 yield reproducibly equivalent outputs when independently re-run or cross-evaluated, nor that their shared tournament evolution process converges to the same hypothesis rankings across independent instantiations.

### Smallest resolving study

Select three to five scientific hypothesis-generation tasks spanning distinct domains (e.g., one used as a benchmark in S1 and one from S2's reported evaluations). Feed identical seed inputs, literature corpora, and compute budgets to both systems. Score all generated hypotheses using a single blinded panel applying the same rubric (e.g., novelty, feasibility, specificity). Record compute-scaling curves (hypothesis quality vs. test-time compute) and tournament bracket outcomes. Test whether the two systems produce statistically indistinguishable hypothesis quality distributions (equivalence test, δ = 0.2 SD) and whether scaling curves are parallel. This directly resolves whether the matching architectural descriptions in S1 and S2 constitute a genuine replication or merely terminological convergence masking divergent implementations.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 13. System Integration

**Status:** `draft_unverified`  
**Card:** `gap:6fbe13f503dd`

### Candidate gap

No study has integrated PaperBench, CORE-Bench, and AI Scientist into a unified evaluation pipeline to determine whether an end-to-end autonomous research system (AI Scientist) that generates, executes, and writes up experiments can also pass the structured reproducibility and replication criteria defined by CORE-Bench and PaperBench — leaving it unknown whether autonomous scientific pipelines produce outputs that satisfy human-interpretable, rubric-graded reproducibility standards.

### Evidence substrate

- **S1: PaperBench: Evaluating AI's Ability to Replicate AI Research (2025).** PaperBench — a benchmark of 20 ICML 2024 Spotlight and Oral papers with hierarchically decomposed, author-approved rubrics (8,316 individually gradable leaf criteria) and an automated LLM-based grading workflow for evaluating AI agents' ability to replicate AI research from scratch.
  - Supporting quote: “PaperBench: a benchmark of 20 ML research papers and author-approved rubrics, and an automated grading workflow using LLM-based judges.”
- **S2: CORE-Bench: Fostering the Credibility of Published Research Through a Computational Reproducibility Agent Benchmark (2024).** CORE-Bench — a benchmark of 270 tasks derived from 90 scientific papers across computer science, social science, and medicine — measures AI agent accuracy on computational reproducibility at three difficulty levels, covering both language-only and vision-language tasks with Python and R codebases.
  - Supporting quote: “CORE-Bench (Computational Reproducibility Benchmark). CORE-Bench comprises 270 tasks derived from 90 papers across computer science, social science, and medicine with Python or R codebases.”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `related`. PaperBench (A) explicitly cites CORE-Bench (B) and characterizes it as "prior work" covering the ability to use existing research code — specifically, CORE-Bench tasks agents to reproduce paper results *given* the repository, whereas PaperBench tasks agents to replicate from scratch. This is a meaningful, substantive relationship: PaperBench defines its own contribution partly in contrast to CORE-Bench, and uses the citation to justify its design choice of disallowing access to original codebases. However, the relationship does not cleanly fit 'builds_on' (PaperBench does not extend CORE-Bench's methods or artifacts) or 'refines' (it does not narrow/correct CORE-Bench's claims) or 'supports'/'contradicts' (different constructs are measured). PaperBench positions itself as a complementary but distinct benchmark in the same space, explicitly differentiating its scope. The most defensible classification is 'related' — a clear substantive connection (both are AI agent benchmarks for scientific paper reproducibility/replication) without a hard directional type being warranted.

### What is missing

There is no controlled measurement of AI Scientist outputs scored against (a) CORE-Bench's computational reproducibility tasks and (b) PaperBench's hierarchical replication rubrics. Specifically, it is unknown whether the code, data, and manuscripts autonomously produced by AI Scientist can be reproduced by an independent agent under CORE-Bench conditions (given the repository) or replicated from scratch under PaperBench conditions (without the original codebase), and how these scores compare to human-authored papers evaluated on the same benchmarks.

### Smallest resolving study

Run AI Scientist on 5–10 open-ended ML research tasks to produce complete paper artifacts (code, data, manuscript). Then: (1) Feed the generated repositories into CORE-Bench's three-difficulty-level evaluation pipeline and record agent accuracy on computational reproducibility tasks. (2) Submit the generated manuscripts (without repositories) to PaperBench's LLM-grader against its hierarchical rubrics and record leaf-criterion pass rates. Compare both scores against a matched set of human-authored CORE-Bench and PaperBench papers as a baseline. The study requires no new benchmark development — only applying existing grading infrastructure to AI Scientist outputs — and directly tests whether end-to-end autonomous research integrates with established reproducibility standards.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 14. System Integration

**Status:** `draft_unverified`  
**Card:** `gap:3a7f678e5f5a`

### Candidate gap

No study has integrated the distinct architectural components of AI-Researcher (multi-agent pipeline with role-separated agents), AI Scientist-v2 (agentic tree-search experiment manager + VLM figure-refinement feedback loop), and AI Scientist (cost-bounded self-review loop) into a unified system and measured whether cross-system integration yields additive, subadditive, or superadditive performance on end-to-end autonomous research quality — leaving it unknown which subsystem combinations actually drive scientific output quality versus being redundant or mutually incompatible.

### Evidence substrate

- **S1: AI-Researcher: Autonomous Scientific Innovation (2025).** AI-Researcher — a fully autonomous multi-agent system that orchestrates the complete scientific research pipeline from literature review and hypothesis generation through algorithm implementation, experimental validation, and publication-ready manuscript preparation with minimal human intervention.
  - Supporting quote: “we introduce AI-Researcher, a fully autonomous research system that transforms how AI-driven scientific discovery is conducted and evaluated. Our framework seamlessly orchestrates the complete research pipeline–from literature review and hypothesis generation to algorithm implementation and publication-ready manuscript preparation–with minimal human intervention.”
- **S2: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `related`. AI-Researcher (A) explicitly cites AI Scientist-v2 (B) as foundational prior work in the same paradigm of end-to-end autonomous scientific discovery. Evidence CIT:1 describes B as "AI Scientist-v2 [CITED:TARGET], enhanced these capabilities through agentic tree search methodology," and CIT:2 frames A as "Building on this paradigm" established by B. A:017 echoes this framing directly. However, 'builds_on' would require A to materially reuse or extend B's specific methods, artifacts, or results — the evidence shows A situates itself in the same paradigm and cites B as prior art, but develops its own distinct architecture (multi-agent pipeline, Scientist-Bench benchmark) without demonstrably reusing B's tree-search methodology, VLM feedback loop, or codebase. B:013 (from B's related work) also lists "AI-Researcher" as a parallel system in the same landscape, treating it as a co-occurring rather than derivative effort. The relationship is substantive (same research niche, mutual awareness, citation) but the hard 'builds_on' classification is not defensible from the evidence; 'related' is the most accurate type.

### What is missing

There is no controlled evidence showing what happens when the multi-agent role decomposition of AI-Researcher is combined with the tree-search experiment manager of AI Scientist-v2 and the self-review loop of AI Scientist. Specifically, no study reports: (1) whether the VLM feedback loop from AI Scientist-v2 and the manuscript self-review loop from AI Scientist can operate jointly without degradation; (2) whether the role-separated agent architecture of AI-Researcher improves or disrupts the tree-search methodology from AI Scientist-v2 when substituted as its orchestration layer; and (3) whether integrating all three subsystems produces manuscripts rated higher in quality than any single system alone on a shared benchmark (e.g., Scientist-Bench).

### Smallest resolving study

Construct four system variants on a fixed compute and cost budget: (A) AI-Researcher pipeline alone, (B) AI Scientist-v2 tree-search + VLM loop alone, (C) AI Scientist self-review loop alone, and (D) an integrated system combining AI-Researcher's role-separated multi-agent orchestration, AI Scientist-v2's tree-search experiment manager and VLM figure-refinement, and AI Scientist's self-review loop. Run all four variants on the same set of 10–20 research tasks drawn from Scientist-Bench. Evaluate all outputs on identical criteria (hypothesis novelty, experimental validity, manuscript quality, reviewer scores) using both automated metrics and blinded human expert review. Compare variant D against each single-system baseline to determine whether integration is additive, subadditive, or superadditive, and identify which pairwise combinations (tree-search + self-review; multi-agent + VLM loop) are the primary drivers of any performance change.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 15. System Integration

**Status:** `draft_unverified`  
**Card:** `gap:f9601b935716`

### Candidate gap

HypoRefine's collaborative agent architecture for hypothesis generation (grounding data-driven hypotheses with literature-based insights) has never been integrated as the ideation front-end of an end-to-end automated research pipeline such as The AI Scientist or AI Scientist-v2. It is therefore unknown whether substituting HypoRefine's structured, literature-grounded hypothesis refinement for the ad-hoc LLM ideation stage of these pipelines improves the scientific validity and out-of-distribution generalizability of the hypotheses that subsequently drive experiment design, execution, and manuscript authoring.

### Evidence substrate

- **S1: Literature Meets Data: A Synergistic Approach to Hypothesis Generation (2024).** HypoRefine — a method that grounds data-driven hypothesis generation (via HypoGeniC) with literature-based insights through a collaborative agent architecture that refines and maintains a shared hypothesis pool — outperforms literature-only, data-only, and few-shot baselines on out-of-distribution generalization across five social-science classification tasks (15.75%, 3.37%, and 8.97% gains, respectively).
  - Supporting quote: “We propose the first approach to using both literature information and data for LLM-powered hypothesis generation.”
- **S2: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”
- **S3: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”

Graph motif: `related`. HypoRefine (A) cites The AI Scientist (B) explicitly, but only as a background reference in the "automated scientific research with LLMs" landscape review — characterizing it as designing "an LLM agent to generate full research papers" — and then immediately distinguishes its own focus on hypothesis generation from B's end-to-end paper-generation pipeline. Evidence [CIT:arxiv:2410.17309v3->openalex:W4402952666:1] and [A:031] confirm this is a contrast/background citation, not a methodological dependency. A does not build on, refine, or contradict B's findings; it merely acknowledges B as a related effort in the broader space of LLM-assisted science. The two contributions address substantially different problems (hypothesis generation + social-science classification vs. fully automated ML paper writing), share no common empirical constructs, and have no materially corroborating findings. A hard relation type (builds_on, refines, supports, contradicts) is not defensible from the evidence supplied; the relationship is substantive but only topical.

### What is missing

No study has measured what happens to downstream pipeline outputs (experiment designs, manuscript quality, reviewer scores) when HypoRefine's multi-agent hypothesis refinement loop replaces the native ideation module of an end-to-end autonomous research system. Neither The AI Scientist (v1 or v2) reports hypothesis quality metrics comparable to HypoRefine's out-of-distribution classification gains, and HypoRefine itself was never tested as a component feeding into automated experimentation or paper-writing stages. The integration seam — passing a refined hypothesis pool from HypoRefine into an experiment manager agent — has no empirical characterisation.

### Smallest resolving study

Take the AI Scientist-v2 pipeline and create two conditions: (A) the unmodified pipeline with its native LLM ideation stage, and (B) a modified pipeline in which HypoRefine's collaborative agent loop (data-driven HypoGeniC + literature-grounding agents + shared hypothesis pool) replaces the ideation stage, with the top-ranked refined hypothesis passed to the experiment manager agent. Run both conditions on a fixed set of social-science ML tasks (matching the five classification domains used in HypoRefine's evaluation) with identical compute budgets. Evaluate: (i) hypothesis quality via the same out-of-distribution held-out classification accuracy metric used in HypoRefine, (ii) downstream manuscript quality via the AI Scientist-v2 automated reviewer scores, and (iii) experiment success rate. A statistically significant improvement in at least two of the three metrics under condition B would confirm that integrating structured hypothesis refinement into an end-to-end pipeline yields compounding benefits beyond either system operating in isolation.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 16. System Integration

**Status:** `draft_unverified`  
**Card:** `gap:b5a3b408fb0c`

### Candidate gap

No evidence exists for whether MARG's multi-agent review component (S1) produces evaluation signal that is consistent with, or systematically diverges from, blind expert review when embedded as the peer-review stage inside a fully automated end-to-end research pipeline such as The AI Scientist (S3), nor whether that integrated review signal is calibrated against the human-vs-LLM ideation quality baseline established by S2's controlled framework.

### Evidence substrate

- **S1: MARG: Multi-Agent Review Generation for Scientific Papers (2024).** MARG (Multi-Agent Review Generation) — a system in which multiple LLM instances each receive a portion of a scientific paper, engage in structured internal discussion, and collectively generate peer-review feedback for papers whose full text exceeds any single LLM's context window.
  - Supporting quote: “We propose a novel method (MARG) that can generate high-quality peer-review feedback even for papers longer than the context size of the base model.”
- **S2: Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers (2024).** A controlled experimental framework for comparing human and LLM research idea generation — enforcing style standardization, matched topic distributions, and blind expert review — enables statistically rigorous head-to-head evaluation of ideation capabilities for the first time.
  - Supporting quote: “We address this by establishing an experimental design that evaluates research idea generation while controlling for confounders and performs the first head-to-head comparison between expert NLP researchers and an LLM ideation agent.”
- **S3: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”

Graph motif: `related`. Contribution B (W4403586302) cites Contribution A (W4390784029) twice, but exclusively as background context — once in a broad enumeration of "research-related tasks" LLMs have been applied to (automatic review generation), and once as a named example of a multi-agent review system with automatic and human evaluation. The citation passages (CIT:1, CIT:2) explicitly contrast MARG with the focal work ("Unlike these works, we tackle the…"), signalling that the relationship is one of thematic proximity rather than methodological dependency or corroboration. Contribution A addresses peer-review generation under context-window constraints; Contribution B addresses research idea generation with a controlled human-LLM comparison. The two contributions target different tasks (review generation vs. idea generation), use different evaluation designs, and report on different constructs. B does not build on, refine, or contradict A's findings; A's methods or results are not extended or corrected by B. The citation is a background/survey citation establishing the broader landscape of LLM-for-research tasks. A substantive topical relationship exists (both operate in the LLM-for-scientific-research space), but no harder relation (builds_on, refines, supports, contradicts) is defensible from the evidence supplied.

### What is missing

Quantitative comparison of review quality and inter-rater agreement between (a) MARG-generated reviews, (b) AI-Scientist self-reviews, and (c) blind human expert reviews, applied to the same set of LLM-generated research outputs evaluated under the style-standardized, topic-matched protocol of S2—revealing whether automated review components can serve as reliable proxies for human evaluation within an integrated autonomous research system.

### Smallest resolving study

Draw a sample of ~30–50 research ideas and associated mini-papers produced by The AI Scientist pipeline (S3). For each output: (1) collect a blind human expert review using the standardized rubric from S2; (2) collect a MARG multi-agent review (S1); (3) collect The AI Scientist's built-in self-review. Score all three on a common quality rubric (novelty, soundness, clarity). Compute inter-rater agreement (e.g., Krippendorff's α) and rank-order correlation across the three review sources. This directly tests whether the automated review components in the integrated pipeline are calibrated to the human-expert baseline, requiring no new methodological development beyond combining the three existing systems.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 17. Missing Feedback Loop

**Status:** `draft_unverified`  
**Card:** `gap:4f1dba767eeb`

### Candidate gap

The AI Scientist (v1 and v2) operates as a fully closed autonomous loop — generating ideas, running experiments, writing papers, and self-reviewing — but there is no evidence that the quality signal produced by its self-review stage is fed back to improve upstream stages (idea generation, experimental design, or manuscript writing) within or across research cycles. The controlled human-vs-LLM ideation evaluation (S3) establishes that LLM idea quality can be rigorously measured by blind expert review, yet neither the v1 nor v2 system uses such an external or internalized quality signal as a corrective feedback loop to steer future idea generation or experimental decisions.

### Evidence substrate

- **S1: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”
- **S2: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”
- **S3: Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers (2024).** A controlled experimental framework for comparing human and LLM research idea generation — enforcing style standardization, matched topic distributions, and blind expert review — enables statistically rigorous head-to-head evaluation of ideation capabilities for the first time.
  - Supporting quote: “We address this by establishing an experimental design that evaluates research idea generation while controlling for confounders and performs the first head-to-head comparison between expert NLP researchers and an LLM ideation agent.”

Graph motif: `open_wedge`. 

### What is missing

No evidence exists that the self-review scores or expert-rated quality signals generated at the end of an AI Scientist research cycle are used to update, re-rank, or prune the upstream idea generation and experimental design decisions in subsequent cycles. Specifically, it is unknown whether closing this feedback loop — routing manuscript review quality back into the idea-generation and experimental-planning stages — improves the rated quality of subsequently produced papers relative to the open-loop baseline.

### Smallest resolving study

Using the AI Scientist-v2 framework (S2), run two matched cohorts of autonomous research cycles on the same seed topics: (A) the existing open-loop system where self-review output is not used to influence future idea generation or experimental design, and (B) a feedback-closed variant where self-review scores and structured critiques are returned as conditioning context to the idea-generation and experiment-manager agents at the start of each subsequent cycle. After N cycles per cohort, apply the blind expert review protocol from S3 (style-standardized, topic-matched, scored by domain experts) to all produced manuscripts. Compare mean expert-rated novelty, feasibility, and overall quality scores between cohorts A and B using the same statistical tests as S3. This minimal study would directly test whether the missing self-review-to-ideation feedback loop produces measurable quality improvement.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 18. Missing Feedback Loop

**Status:** `draft_unverified`  
**Card:** `gap:16393ee86bf1`

### Candidate gap

None of the three systems closes the loop between the quality of a system's own outputs and the inputs it uses for subsequent research cycles: AI Scientist (S2) and AI Scientist-v2 (S1) operate in an open-ended loop but use externally fixed quality signals, while Agent Laboratory (S3) incorporates optional human feedback but only at discrete, human-triggered checkpoints. No evidence exists that any system feeds machine-assessable quality metrics from completed papers (e.g., reviewer scores, reproducibility outcomes, or citation-proxy signals) back as an adaptive signal that reshapes hypothesis generation, experiment design, or template selection in the next cycle—meaning compounding self-improvement across iterations has never been demonstrated or measured.

### Evidence substrate

- **S1: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”
- **S2: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”
- **S3: Agent Laboratory: Using LLM Agents as Research Assistants (2025).** Agent Laboratory — an autonomous LLM-based pipeline that accepts a human-provided research idea and completes the full research cycle (literature review, experimentation, and report writing) to produce a code repository and research report, with optional human feedback at each stage.
  - Supporting quote: “introduce Agent Laboratory, an autonomous LLM- based framework capable of completing the entire research process. This framework ac- cepts a human-provided research idea and pro- gresses through three stages–literature review, experimentation, and report writing–in order to produce research, including a code repository and a research report, while enabling users to provide feedback and guidance at each stag”

Graph motif: `open_wedge`. 

### What is missing

A quantitative demonstration that quality-derived feedback signals from one research cycle (reviewer scores, experiment reproducibility rates, or VLM figure-quality scores) are propagated back to modify the priors, search heuristics, or prompting strategy used in the immediately following cycle, and that this closed loop produces measurably better outputs over successive iterations compared to an open-loop baseline running the same number of cycles.

### Smallest resolving study

Run AI Scientist-v2 (chosen because it already integrates VLM feedback for figure refinement, providing the most mature internal quality signal) for N consecutive research cycles (e.g., N=10) on a fixed domain. In the closed-loop condition, extract a scalar quality score from each completed cycle (using the system's own automated review mechanism from S2/S1) and use it to reweight the tree-search exploration policy of the experiment manager agent before the next cycle begins. In the open-loop control condition, run the identical number of cycles with a fixed, unmodified policy. Compare output quality (automated review scores, reproducibility of reported results, and human expert ratings on a blinded subset of papers) across cycles between conditions. If the closed-loop condition shows a statistically significant positive trend in quality across cycles while the open-loop condition does not, the missing feedback loop is confirmed to be causally beneficial.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 19. Missing Feedback Loop

**Status:** `draft_unverified`  
**Card:** `gap:4831d905cefb`

### Candidate gap

The AI Scientist's fully automated loop (S2) generates ideas, executes experiments, writes papers, and performs self-review, but there is no feedback mechanism by which the quality signal from expert or peer review is fed back into subsequent ideation or experimental design cycles. S1 establishes that human vs. LLM idea quality can be rigorously measured via blind expert review, yet this measurement is never re-injected into the AI Scientist's pipeline to steer future idea generation. S3 catalogues failure modes across all phases — including ideation and review — but does not document whether any review-phase signal loops back to correct upstream ideation failures. The result is a purely open-loop system: review outputs are produced but never consumed by the generator, leaving systematic ideation deficiencies uncorrectable across iterations.

### Evidence substrate

- **S1: Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers (2024).** A controlled experimental framework for comparing human and LLM research idea generation — enforcing style standardization, matched topic distributions, and blind expert review — enables statistically rigorous head-to-head evaluation of ideation capabilities for the first time.
  - Supporting quote: “We address this by establishing an experimental design that evaluates research idea generation while controlling for confounders and performs the first head-to-head comparison between expert NLP researchers and an LLM ideation agent.”
- **S2: The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024).** The AI Scientist — an end-to-end, fully automated pipeline in which a frontier LLM generates research ideas, searches the literature, designs and executes experiments, visualizes results, writes a complete scientific manuscript, and performs self-review in an open-ended loop — enables autonomous scientific discovery in machine learning at a cost of under $15 per paper.
  - Supporting quote: “We introduce the first end-to-end framework for fully automated scientific discovery in Machine Learning research, enabled by frontier LLMs (Section 3). This fully automated process includes idea generation, experiment design, execution, and visualizing and writing up the results into a full manuscript.”
- **S3: Jr. AI Scientist and Its Risk Report: Autonomous Scientific Exploration from a Baseline Paper (2025).** A comprehensive risk taxonomy for autonomous AI scientist systems, cataloguing concrete failure modes and hazards across the idea-generation, experimentation, writing, and review phases, derived from end-to-end system development and deployment experience.
  - Supporting quote: “we comprehensively report various risks identified during development. We believe this study clarifies the current role and limitations of AI Scientist systems, offering insights into the areas that still require human expertise and the risks that may emerge as these systems evolve.”

Graph motif: `open_wedge`. 

### What is missing

Evidence that the quality scores produced during the AI Scientist's self-review (or an external blind expert review as operationalized in S1) are propagated back as a conditioning signal into the idea-generation and experimental-design phases, and that doing so measurably improves the rated novelty, feasibility, and significance of ideas produced in subsequent autonomous cycles relative to a no-feedback control condition.

### Smallest resolving study

Run the AI Scientist pipeline for N autonomous end-to-end cycles on a fixed set of ML research topics. In the feedback condition, after each cycle the blind expert review scores (collected using the standardized rubric from S1) for novelty, feasibility, and significance are concatenated to the idea-generation prompt as structured critiques before the next cycle begins. In the no-feedback (open-loop) control condition, the pipeline runs identically but review scores are withheld from the generator. Compare the distribution of expert-rated idea quality scores across cycles between the two conditions using a mixed-effects model. A statistically significant upward trend in quality scores across cycles in the feedback condition — absent in the control — would confirm that closing the review-to-ideation loop improves autonomous scientific discovery.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

## 20. Missing Feedback Loop

**Status:** `draft_unverified`  
**Card:** `gap:3334995da280`

### Candidate gap

Neither Agent Laboratory (S1), AI Scientist-v2 (S2), nor MLR-Bench (S3) establishes a closed feedback loop in which the benchmark evaluation signal from MLR-Bench is routed back to steer or refine the autonomous research pipeline (Agent Laboratory or AI Scientist-v2) during its execution. The pipelines accept optional human feedback (S1) or VLM figure feedback (S2), but benchmark-derived performance scores measuring idea quality, experimental rigor, and paper quality are never fed back as an automated signal to guide in-progress agentic decisions. As a result, it is unknown whether incorporating structured, benchmark-generated evaluation feedback mid-run improves the quality of autonomously produced research artifacts compared to pipelines that operate without such feedback.

### Evidence substrate

- **S1: Agent Laboratory: Using LLM Agents as Research Assistants (2025).** Agent Laboratory — an autonomous LLM-based pipeline that accepts a human-provided research idea and completes the full research cycle (literature review, experimentation, and report writing) to produce a code repository and research report, with optional human feedback at each stage.
  - Supporting quote: “introduce Agent Laboratory, an autonomous LLM- based framework capable of completing the entire research process. This framework ac- cepts a human-provided research idea and pro- gresses through three stages–literature review, experimentation, and report writing–in order to produce research, including a code repository and a research report, while enabling users to provide feedback and guidance at each stag”
- **S2: The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025).** The AI Scientist-v2 — an end-to-end agentic system for automated scientific discovery that eliminates reliance on human-authored code templates, uses a progressive agentic tree-search methodology managed by a dedicated experiment manager agent, and integrates VLM feedback for iterative figure refinement — can autonomously formulate hypotheses, design and execute experiments, analyze data, and author complete scientific manuscripts across diverse machine learning domains.
  - Supporting quote: “We introduce The AI Scientist-v2, an automated scientific discovery framework enhanced by agentic tree search, VLM feedback, and parallel experiment execution. It thereby significantly improves the autonomy, flexibility, and scientific exploration depth of previous systems.”
- **S3: MLR-Bench: Evaluating AI Agents on Open-Ended Machine Learning Research (2025).** MLR-Bench — a benchmark of 201 open-ended machine learning research tasks drawn from NeurIPS, ICLR, and ICML workshops — enables systematic evaluation of AI research agents across nine ML topic areas with both stepwise (idea generation, proposal formulation, experimentation, paper writing) and end-to-end assessment pipelines.
  - Supporting quote: “MLR-Bench : To our knowledge, the most comprehensive evaluation benchmark for AI research agents to date, featuring 201 open-ended ML research tasks, a human-aligned MLR-Judge for automated research quality assessment, and a modular MLR-Agent supporting both stepwise and end-to-end research execution.”

Graph motif: `open_wedge`. 

### What is missing

There is no evidence of a closed-loop mechanism in which MLR-Bench's stepwise evaluation scores (idea generation, proposal formulation, experimentation, paper writing) are automatically returned to an autonomous pipeline (Agent Laboratory or AI Scientist-v2) as an in-process reward or corrective signal, nor any measurement of whether such feedback improves final artifact quality relative to a no-feedback baseline.

### Smallest resolving study

Select 40 tasks from MLR-Bench (S3) and assign them randomly to two conditions: (A) an autonomous pipeline (e.g., Agent Laboratory, S1) running without benchmark feedback — the current open-loop baseline — and (B) the same pipeline augmented with a feedback loop in which MLR-Bench's stepwise evaluator scores each completed stage (idea, proposal, experiment, paper draft) and returns structured critique to the agent before it proceeds to the next stage. Hold all other hyperparameters constant. Measure MLR-Bench end-to-end scores and stepwise sub-scores for both conditions across all 40 tasks. A statistically significant improvement in condition B over condition A would confirm that benchmark-derived evaluation signals constitute a productive feedback loop; equivalence or degradation would indicate the loop provides no benefit or is harmful.

### Review checklist

- [ ] Search for omitted or newer work that already addresses this gap.
- [ ] Verify that each quotation supports its contribution summary.
- [ ] Confirm that the graph relation is correctly typed.
- [ ] Decide whether the proposed study is minimal and genuinely informative.
- [ ] Record disputes, missing papers, and reviewer identity in the JSON card.

