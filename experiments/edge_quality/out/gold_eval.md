# Gold-set evaluation — intent axis

- labelled sites: **122** (+0 skipped)
- by sample block: `disagreement`=12, `random_eval`=80, `strat_topup`=30
- gold class mix: background=74, uses_extends=24, compares_contrasts=24

## 1. Random-sample accuracy (the headline)

**95.0%**  (76/80 sites)  ·  95% CI [87.8%, 98.0%]

> Site-level. Sites on the same edge/paper are not independent, so the true CI is a little wider than the binomial one above.

## 2. Stratified reweighted estimate

| judge class | pop. weight | n labelled | P(correct \| judge=c) |
|---|---|---|---|
| background | 82.2% | 63 | 95.2% |
| uses_extends | 6.8% | 24 | 91.7% |
| compares_contrasts | 11.0% | 23 | 91.3% |

**Reweighted accuracy: 94.6%**

### Reweighted confusion (population-scaled), judge (rows) × gold (cols)

| judge ＼ gold | background | uses_extends | compares_contrasts |
|---|---|---|---|
| background | 78.3% | 1.3% | 2.6% |
| uses_extends | 0.3% | 6.2% | 0.3% |
| compares_contrasts | 1.0% | 0.0% | 10.0% |

| class | precision | recall | F1 |
|---|---|---|---|
| background | 95.2% | 98.4% | 0.968 |
| uses_extends | 91.7% | 82.7% | 0.869 |
| compares_contrasts | 91.3% | 77.6% | 0.839 |

**macro-F1 = 0.892**

## 3. Second-judge disagreement block (referee on the forks)

On 12 labelled hard cases: **ours right 6**, **Opus right 5**, neither 1.

| fork (ours→opus) | gold sides with ours | with Opus |
|---|---|---|
| background->compares_contrasts | 3 | 0 |
| background->uses_extends | 2 | 0 |
| compares_contrasts->background | 0 | 4 |
| uses_extends->background | 0 | 1 |
| uses_extends->compares_contrasts | 1 | 0 |

> These sites are deliberately enriched for hard cases — never fold them into the accuracy numbers above.

## 4. Secondary axes (where labelled)

- `support`: not labelled yet
- `priority`: not labelled yet

## 5. Accuracy by quality gate

| slice | n | accuracy |
|---|---|---|
| bibtex_valid = True | 102 | 94.1% |
| bibtex_valid = False (blob) | 8 | 87.5% |
| citee abstract ok | 110 | 93.6% |

## 6. Misses (13)

#### arxiv:2602.15112v2->openalex:W4414827381#0  ·  `random_eval`
- **citing:** ResearchGym: Evaluating Language Model Agents on Real-World AI Research (2026)
- **cited:** The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025)
- gold: **compares_contrasts** · judge: background (0.62)
- judge said: Part of a grouped critique of a general line of work, not singled out individually
- claim: …onduct closed-loop research: a long-horizon process of proposing hypotheses, designing executable experiments, testing against empirical evidence, and updating beliefs in response to results. Yet a growing line of work proposes LLM-augmented systems that claim to automate end-to-end research with self-reported studies [CITED:TARGET], lacking standardized comparison across systems. This creates an inflated perception of capabilities: systems shine on curated examples, but fail to sustain real-world research when subjected to systematic scrutiny [CITED]. figure* [ht]…

#### openalex:W4389761608->openalex:W4365211632#0  ·  `random_eval`
- **citing:** PaperQA: Retrieval-Augmented Generative Agent for Scientific Research (2023)
- **cited:** Emergent autonomous scientific research capabilities of large language models (2023)
- gold: **background** · judge: compares_contrasts (0.85)
- judge said: Explicitly states CORE API 'does not perform on par with the other two', singling it out in a direct comparison.
- claim: …-2021 3. `keyword1, keyword2, 2020-2021` lstlisting minipage We thus evaluate recall, i.e. finding the original paper. Figure fig:retrieval-abstract shows the cumulative recall curve, where Google Scholar and Semantic Scholar show outstanding ability to retrieve the original paper. Although CORE API [CITED:TARGET] does not perform on par with the other two, we include it here as their main contribution to the field of scientific literature is their standardisation of open-access article repositories. tables/retrieval-fig-and-table-abstract Full-Text Retrieval Metric appendix:full-text-retrieval…

#### openalex:W4416026872->openalex:W4402952666#1  ·  `random_eval`
- **citing:** Jr. AI Scientist and Its Risk Report: Autonomous Scientific Exploration from a Baseline Paper (2025)
- **cited:** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024)
- gold: **compares_contrasts** · judge: background (0.7)
- judge said: Limitation ('limited to small-scale code experiments') attributed to 'current systems' generally, not target specifically.
- claim: …y automated science is overly ambitious and often lacks clearly defined scientific goals for AI Scientists. Without a specific goal, these systems tend to generate undirected discoveries that appear to lack genuine scientific value. Another limitation is that current systems are limited to small-scale code experiments [CITED:TARGET], lacking the scale and complexity needed for meaningful science. Achieving real scientific contributions requires not just ideas but strong implementation capability to handle complex codebases. As an initial step toward enabling AI Scientists to produce genuine scientific value, we can take inspiration from how stud…

#### arxiv:2603.26499v2->openalex:W4407760093#1  ·  `random_eval`
- **citing:** AIRA_2: Overcoming Bottlenecks in AI Research Agents (2026)
- **cited:** AIDE: AI-Driven Exploration in the Space of Code (2025)
- gold: **uses_extends** · judge: background (0.55)
- judge said: Cites target's observed finding as supporting context rather than adopting or singling it out critically.
- claim: …ion; (2) Generalization Gap ---validation-test divergence misleads the search signal, causing overfitting over extended research horizons; and (3) Operator Capability ---fixed, single-turn operators limit the agent to shallow, single-turn reasoning that sophisticated search cannot overcome. As noted by [CITED:TARGET], these performance plateaus emerge even within a relatively short 24-hour regime, suggesting that addressing these fundamental bottlenecks is a prerequisite for effectively utilizing additional compute. Guided by these insights, we introduce , a research agent designed to overcome these structural bottlen…

#### arxiv:2606.11447->arxiv:2504.01848v3#0  ·  `disagreement`
- **citing:** AI Coding Agents Can Reproduce Social Science Findings (2026)
- **cited:** PaperBench: Evaluating AI's Ability to Replicate AI Research (2025)
- gold: **background** · judge: compares_contrasts (0.8) · opus: background
- judge said: Cites PaperBench's specific score (27% vs 41% human) which is later contrasted with the citing paper's own higher results.
- claim: …oducibility performance in prior work depended heavily on domain-specific scaffolding rather than model capability alone. Similarly, PaperBench found that even the top-performing AI agent scored just 27\ on replication tasks drawn from ICML 2024 papers, while human ML experts scored 41\ under comparable conditions [CITED:TARGET]. Subsequent work on REPRO-Bench, focused specifically on social science papers, reported a best accuracy of 36.6\ after substantial agent-specific engineering—a result the authors characterized as well below practical thresholds for reliable automation [CITED]. The considerably higher reproduction rates ob…

#### openalex:W4417070798->openalex:W4417287919#1  ·  `disagreement`
- **citing:** The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems (2025)
- **cited:** Robin: A multi-agent system for automating scientific discovery (2025)
- gold: **background** · judge: compares_contrasts (0.75) · opus: background
- judge said: 'Unlike the above systems... Robin emphasizes a different research target' singles out Robin's distinct focus.
- claim: …aboratoryusingllm is designed to assist human scientists in executing their research ideas while allowing flexible levels of human involvement, where users can choose to provide feedback at any stage of scientific research. Furthermore, unlike the above systems that mainly automate research in computer science, Robin [CITED:TARGET] emphasizes a different research target: it discovers and validates therapeutic candidates (i.e., a potential new drug or treatment compound) within an iterative ``lab-in-the-loop" framework, where computational hypotheses are repeatedly generated, tested, analyzed, and refined against laboratory experiments conducted…

#### arxiv:2603.28589v1->openalex:W4416043407#0  ·  `disagreement`
- **citing:** Towards a Medical AI Scientist (2026)
- **cited:** Towards an AI co-scientist (2025)
- gold: **background** · judge: compares_contrasts (0.75) · opus: background
- judge said: 'In contrast, Google's AI co-scientist... operates as a collaborator' explicitly contrasts it with the previously described Agent Laboratory.
- claim: …y balance exploration and exploitation to discover novel methods. Agent Laboratory [CITED] extends this by automating the execution and reporting of user-provided ideas, acting as an accelerator for human researchers rather than an independent ideator. In contrast, Google's AI co-scientist [CITED:TARGET] operates as a collaborator in a "scientist-in-the-loop" paradigm, leveraging models like Gemini to assist domain experts with hypothesis generation. Alongside these frameworks, complementary toolkits have been developed to support AI agent systems by enhancing resource integration and accessibility. ToolUniverse…

#### openalex:W4407806895->openalex:W4403324055#0  ·  `disagreement`
- **citing:** MLGym: A New Framework and Benchmark for Advancing AI Research Agents (2025)
- **cited:** ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery (2024)
- gold: **background** · judge: uses_extends (0.55) · opus: compares_contrasts
- judge said: Citing paper aligns its own script-based evaluation design with the target's approach ('also use a script based evaluation approach').
- claim: …ct instructions. The LLM agent can then be prompted to follow the submission instructions and write the appropriate code. Moreover, the evaluation script is read-only for the LM agent, so while it can inspect the evaluation format, it cannot modify the script to change the evaluation logic. Existing works such as [CITED:TARGET] also use a script based evaluation approach, whereas MLE-Bench [CITED] uses a Kaggle style evaluation. All our design decisions for the Agent, Environment, Dataset, and Tasks are meant to reduce overhead on the developers' and researchers' side and enhance reproducibility in this…

#### openalex:W4402952811->openalex:W4402952666#1  ·  `disagreement`
- **citing:** MLR-Copilot: Autonomous Machine Learning Research based on Large Language Models Agents (2024)
- **cited:** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery (2024)
- gold: **background** · judge: compares_contrasts (0.7) · opus: background
- judge said: Describes AI Scientist's scope specifically as concurrent/differing work, continuing the contrast set up earlier.
- claim: …zed tasks. In contrast to our work on automatic ML hypothesis generation and research with broad utilities (action space), these models operate under more restricted conditions, focusing on predefined tasks with existing code and limited interaction capabilities based on parametric knowledge. Concurrent to our work, [CITED:TARGET] proposes AI Scientist : a framework that generates ideas, implements \& executes experiments to obtain results, and finally summarizes them into ML papers. the first comprehensive fully automatic research agent by enabling frontier LLMs to conduct a series of research processes. While its successor A…

#### openalex:W4414827381->openalex:W4407760093#1  ·  `disagreement`
- **citing:** The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025)
- **cited:** AIDE: AI-Driven Exploration in the Space of Code (2025)
- gold: **background** · judge: uses_extends (0.65) · opus: background
- judge said: Detailed explanation of AIDE's node/tree mechanism feeding into the citing paper's own tree-search design.
- claim: …on. The human-driven scientific process, on the other hand, relies on open-ended hypothesis generation, stepping-stone collection, and iterative hypothesis refinement. Recent advances using code generation as an action space have opened new opportunities for LLM-driven automated workflows [CITED]. AIDE [CITED:TARGET] combines LLM-based code generation with tree search, demonstrating state-of-the-art performance on the MLEBench benchmark [CITED], designed for machine learning engineering tasks. In AIDE, each node represents a potential solution state with a corresponding scalar evaluation score (e.g., validation ac…

#### arxiv:2511.19399v3->arxiv:2506.11763#1  ·  `strat_topup`
- **citing:** DR Tulu: Reinforcement Learning with Evolving Rubrics for Deep Research (2025)
- **cited:** DeepResearch Bench: A Comprehensive Benchmark for Deep Research Agents (2025)
- gold: **compares_contrasts** · judge: uses_extends (0.75) · opus: uses_extends
- judge said: DeepResearchBench is used as one of the evaluation benchmarks to report performance on
- claim: …ng model responses. -8B outperforms the strongest open 8--32B models, including previous state-of-the-art Tongyi DR 30B [CITED], by 4.8--41.8 percentage points on four long-form DR benchmarks---AstaBench-ScholarQA-CS2 (SQAv2) [CITED], DeepResearchBench [CITED:TARGET], ResearchQA [CITED], and HealthBench [CITED]. In addition, it matches or exceeds proprietary systems such as OpenAI DR, Perplexity DR, and Gemini3 Pro + Search. As Figure fig:first-results shows, -8B is substantially more cost-efficient than all other models:…

#### openalex:W4416026872->arxiv:2505.18705v1#1  ·  `strat_topup`
- **citing:** Jr. AI Scientist and Its Risk Report: Autonomous Scientific Exploration from a Baseline Paper (2025)
- **cited:** AI-Researcher: Autonomous Scientific Innovation (2025)
- gold: **background** · judge: compares_contrasts (0.75) · opus: compares_contrasts
- judge said: Explicit 'our work differs from prior studies [CITED:TARGET] in several key aspects' singles out the target for contrast.
- my note: Group
- claim: …ation based on the limitations of a given paper, (2) automatic implementation and iteratively experiments until improvements are achieved, and (3) automatic writing of a research paper based on the obtained results. This system is built upon AI Scientist v2 [CITED], but our work differs from prior studies [CITED:TARGET] in several key aspects: First, by leveraging the latest coding agents ( Claude Code [CITED]), our system can perform meaningful improvements and edits on real multi-file codebases, which were challenging for previous AI Scientist systems. Second, by incorporating the full set of resources from a given b…

#### openalex:W4417287919->openalex:W4403795293#1  ·  `strat_topup`
- **citing:** Robin: A multi-agent system for automating scientific discovery (2025)
- **cited:** Language agents achieve superhuman synthesis of scientific knowledge (2024)
- gold: **background** · judge: uses_extends (0.9)
- judge said: Explicitly states Crow and Falcon are 'literature search agents based on PaperQA2'.
- claim: …Robin: A multi-agent system for scientific discovery Robin integrates multiple language agents in a structured workflow to generate therapeutic candidates for a given disease (Figure 1A,B). Crow and Falcon are literature search agents based on PaperQA2 that conduct concise and deep literature summaries, respectively [CITED:TARGET]. PaperQA2 achieves expert-level performance in information retrieval and summarization, with access to scientific literature, clinical trial reports, and the Open Targets Platform [CITED]. Finch is a scientific data analysis agent that performs analyses of experimental data from assays, such as RN…

