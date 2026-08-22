# QA experiment — answers and judgements in full

*Generated from `out/answers.jsonl` + `out/qa_judgements.jsonl`. 8 of 8 questions answered, 8 judged. Design + registered predictions: [PLAN.md](../PLAN.md).*

> ✅ Blinding gate clean — no answer reveals how it was produced.

> ✅ Arm seal intact — no answer used a tool outside its environment.

## Scoreboard

Scores are groundedness / correctness / usefulness, each 1-10.

Each question was judged **3 times**, each run with a different presentation order. Scores are means; the winner column shows the vote as graph/web/null. See *Judge reliability* below for the spread.

| q | expected | best | margin | prediction | GRAPH | WEB | NULL |
|---|---|---|---|---|---|---|---|
| **q01** | graph | **graph** (3/0/0) | slight | ✅ hit | 9.0/8.0/9.0 | 8.0/7.7/8.0 | 7.0/7.7/5.7 |
| **q02** | graph | **graph** (3/0/0) | slight | ✅ hit | 8.7/8.0/8.7 | 8.0/9.0/8.0 | 6.0/8.0/6.0 |
| **q03** | graph | **graph** (3/0/0) | slight | ✅ hit | 9.0/8.0/9.0 | 8.3/8.0/8.3 | 7.0/7.7/7.3 |
| **q04** | graph | **graph** (3/0/0) | slight | ✅ hit | 8.0/7.7/7.7 | 8.0/4.7/7.7 | 5.3/8.0/4.0 |
| **q05** | graph | **graph** (3/0/0) | slight | ✅ hit | 9.0/8.7/8.0 | 7.0/7.7/8.0 | 5.7/3.7/5.3 |
| **q06** | graph | **web** (0/3/0) | clear | ❌ miss | 8.0/5.0/7.3 | 8.3/8.3/8.3 | 5.7/8.0/5.0 |
| **c01** | web | **web** (0/3/0) | slight | ✅ hit | 2.7/7.7/2.7 | 8.0/7.7/9.0 | 8.0/8.3/8.0 |
| **c02** | web | **web** (0/3/0) | clear | ✅ hit | 7.3/8.3/6.7 | 8.3/7.0/8.7 | 5.7/5.7/5.3 |

### Mean scores — STRUCTURAL questions  *(n=6)*

The questions the atlas is supposed to help with.

| arm | groundedness | correctness | usefulness | fabricated | unrecognised | hedged | overclaimed |
|---|---|---|---|---|---|---|---|
| GRAPH (Prior atlas) | 8.6 | 7.6 | 8.3 | 1/6 | 5/6 | 0/6 | 0/6 |
| WEB (search) | 7.9 | 7.6 | 8.1 | 1/6 | 5/6 | 0/6 | 0/6 |
| NULL (closed book) | 6.1 | 7.2 | 5.6 | 1/6 | 0/6 | 2/6 | 0/6 |

### Mean scores — CONTROLS  *(n=2)*

**The graph arm is supposed to lose these.** c01 is outside the corpus entirely; c02 needs numbers the bundle does not hold. A graph win here would mean the judge or the blinding is broken.

| arm | groundedness | correctness | usefulness | fabricated | unrecognised | hedged | overclaimed |
|---|---|---|---|---|---|---|---|
| GRAPH (Prior atlas) | 5.0 | 8.0 | 4.7 | 0/2 | 1/2 | 1/2 | 0/2 |
| WEB (search) | 8.2 | 7.3 | 8.8 | 0/2 | 1/2 | 0/2 | 0/2 |
| NULL (closed book) | 6.8 | 7.0 | 6.7 | 0/2 | 0/2 | 0/2 | 0/2 |

**Who won, by both definitions** — they are not the same measure:

| set | judge's `best_answer` | highest axis total |
|---|---|---|
| structural (q01-q06) | graph 5 / web 1 / null 0 | graph 5 / web 1 / null 0 |
| controls (c01-c02) | graph 0 / web 2 / null 0 | graph 0 / web 2 / null 0 |

> Where the two disagree the margin was `slight` — that is the instrument telling you the answers were close, and it should be reported rather than resolved by picking the more flattering rule.

**Lift over the null arm, STRUCTURAL questions only** (the number that says what each environment is worth):

| arm | Δ groundedness | Δ correctness | Δ usefulness |
|---|---|---|---|
| GRAPH (Prior atlas) | +2.5 | +0.4 | +2.7 |
| WEB (search) | +1.8 | +0.4 | +2.5 |

### Judge reliability

The same judge, the same answers, a different presentation order. This is the noise floor every score above sits on — and it is the reason not to lean on win counts.

| q | runs | winner | unanimous? | widest axis spread |
|---|---|---|---|---|
| q01 | 3 | graph (3/0/0) | yes | 1 pt (web correctness 7-8) |
| q02 | 3 | graph (3/0/0) | yes | 1 pt (graph groundedness 8-9) |
| q03 | 3 | graph (3/0/0) | yes | 1 pt (web groundedness 8-9) |
| q04 | 3 | graph (3/0/0) | yes | 1 pt (graph correctness 7-8) |
| q05 | 3 | graph (3/0/0) | yes | 2 pts (web usefulness 7-9) |
| q06 | 3 | web (0/3/0) | yes | 2 pts (graph correctness 4-6) |
| c01 | 3 | web (0/3/0) | yes | 1 pt (graph groundedness 2-3) |
| c02 | 3 | web (0/3/0) | yes | 3 pts (null correctness 4-7) |

> **8 of 8** questions had a unanimous winner. Median widest axis spread: **1 points**. Any margin at or below that is a tie, whatever the mean says.

## Efficiency

**`payload chars`** is the headline (PLAN §5) — the direct count of what the tools returned, summed by our own code, so nothing in the harness can move it. **Lower is better.** `context` = input + cache_creation + cache_read, what the model actually had to process.

> `tokens_in` (input + cache_creation) was the ORIGINAL pre-registered headline and is kept here so the record is complete, but it is **not** a measure of ingestion: `cache_creation` tracks how the conversation prefix was re-chunked across turns. On q01/graph, payload fell ~5,500 tokens between v2 and v3 while cache_creation rose 27,345. See PLAN §5.

| q | arm | **payload chars** | context | tokens_in | tool calls | turns | seconds | cost |
|---|---|---|---|---|---|---|---|---|
| q01 | graph | **25,929** | 234,120 | 59,320 | 6 | 10 | 89.0 | $0.554 |
| q01 | web | **23,099** | 222,953 | 22,208 | 8 | 12 | 121.6 | $0.506 |
| q01 | null | **0** | 51,376 | 27,878 | 0 | 2 | 50.3 | $0.239 |
| q02 | graph | **38,133** | 228,051 | 25,186 | 12 | 14 | 42.3 | $0.260 |
| q02 | web | **12,796** | 96,697 | 12,075 | 4 | 6 | 53.0 | $0.299 |
| q02 | null | **0** | 122,193 | 13,722 | 0 | 5 | 87.8 | $0.248 |
| q03 | graph | **47,576** | 202,653 | 25,607 | 11 | 13 | 44.6 | $0.263 |
| q03 | web | **13,875** | 243,367 | 47,514 | 5 | 10 | 119.1 | $0.590 |
| q03 | null | **0** | 62,866 | 12,264 | 0 | 3 | 84.0 | $0.204 |
| q04 | graph | **15,032** | 160,670 | 10,219 | 4 | 6 | 30.5 | $0.142 |
| q04 | web | **22,339** | 241,283 | 20,038 | 12 | 14 | 106.3 | $0.852 |
| q04 | null | **0** | 119,814 | 12,207 | 0 | 5 | 72.2 | $0.215 |
| q05 | graph | **32,559** | 186,579 | 20,315 | 9 | 11 | 43.2 | $0.225 |
| q05 | web | **14,021** | 125,733 | 12,842 | 6 | 8 | 62.0 | $0.247 |
| q05 | null | **0** | 30,136 | 30,136 | 0 | 2 | 42.9 | $0.232 |
| q06 | graph | **20,563** | 169,950 | 17,313 | 5 | 8 | 52.6 | $0.227 |
| q06 | web | **16,442** | 244,152 | 19,092 | 6 | 11 | 99.7 | $0.430 |
| q06 | null | **0** | 111,033 | 9,952 | 0 | 5 | 53.6 | $0.166 |
| c01 | graph | **13,162** | 130,141 | 11,762 | 5 | 8 | 30.4 | $0.144 |
| c01 | web | **6,433** | 106,099 | 25,368 | 2 | 3 | 56.9 | $0.508 |
| c01 | null | **0** | 119,676 | 12,862 | 0 | 5 | 74.8 | $0.230 |
| c02 | graph | **3,311** | 86,558 | 6,089 | 2 | 4 | 14.6 | $0.072 |
| c02 | web | **5,507** | 87,656 | 7,965 | 3 | 5 | 33.4 | $0.147 |
| c02 | null | **0** | 172,472 | 12,089 | 0 | 7 | 69.7 | $0.228 |

**Means per answer** — the number the compactness claim lives or dies on:

| arm | payload chars | context | tokens_in | tool calls | papers named | cost |
|---|---|---|---|---|---|---|
| GRAPH (Prior atlas) | **24,533** | 174,840 | 21,976 | 6.8 | 7.1 | $0.236 |
| WEB (search) | **14,314** | 170,992 | 20,888 | 5.8 | 5.5 | $0.447 |
| NULL (closed book) | **0** | 98,696 | 16,389 | 0.0 | 3.1 | $0.220 |

> **❌ Compactness prediction FAILS** — over the 8 question(s) answered by BOTH arms (q01, q02, q03, q04, q05, q06, c01, c02), the graph arm pulls 24,533 payload chars per answer against web's 14,314 (1.71×).

### Stated confidence

| q | arm | papers named | confidence |
|---|---|---|---|
| q01 | graph | 19 | high |
| q01 | web | 8 | medium |
| q01 | null | 6 | medium |
| q02 | graph | 7 | medium |
| q02 | web | 5 | medium |
| q02 | null | 2 | medium |
| q03 | graph | 8 | high |
| q03 | web | 6 | high |
| q03 | null | 6 | medium |
| q04 | graph | 5 | medium |
| q04 | web | 6 | medium |
| q04 | null | 2 | low |
| q05 | graph | 6 | medium |
| q05 | web | 5 | medium |
| q05 | null | 2 | medium |
| q06 | graph | 9 | high |
| q06 | web | 6 | medium |
| q06 | null | 2 | medium |
| c01 | graph | 2 | low |
| c01 | web | 7 | medium |
| c01 | null | 4 | medium |
| c02 | graph | 1 | high |
| c02 | web | 1 | medium |
| c02 | null | 1 | medium |

Generation total: **$7.23** (graph $1.89, web $3.58, null $1.76). Judging total: **$1.62**.


---

## q01 — builds-on

> I'm writing a related-work section on The AI Scientist (Lu et al.). Which later papers actually extend its method, as opposed to just citing it in passing?

**Expected winner:** `graph`  
**Judged best:** `graph` (slight margin) — prediction hit  
**Ranking:** graph>web>null  
**Presentation order:** graph / web / null

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

7 builds_on edges into it; 59 citation links whose intents separate uses_extends from background (53 of them are background).

</details>

### GRAPH (Prior atlas)

**9.0** grounded · **8.0** correct · **9.0** useful · flags: unrecognised

Several later papers cite The AI Scientist (Lu, Lu, Lange, Foerster, Clune and Ha, 2024) merely as background or as a comparison baseline, but a smaller set genuinely build on its pipeline and extend it methodologically. Here is the breakdown.

GENUINE METHODOLOGICAL EXTENSIONS

1. The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (2025) - this is the direct, explicit successor from an overlapping author set. It keeps the end-to-end idea-to-manuscript pipeline but replaces the human-authored code templates of v1 with a progressive agentic tree-search process managed by a dedicated experiment-manager agent, adds VLM-based feedback for iterative figure refinement, and runs experiments in parallel. The paper gives a feature-by-feature comparison against v1 and frames every design choice as fixing a stated limitation of the original system. This is the clearest and closest extension.

2. Towards end-to-end automation of AI research (2026, Nature) - also from within the same research lineage, this explicitly builds on the template-based version of The AI Scientist and extends it with a template-free, more open-ended operating mode, plus a substantive new empirical result: an AI-generated manuscript produced by the system passing the first round of peer review at a workshop of a top-tier ML conference. This is a genuine extension of both the method and its demonstrated capability, not just a citation.

3. AI-Researcher: Autonomous Scientific Innovation (2025) - adopts The AI Scientist's core pipeline structure (idea generation, experiment execution, paper writing) but restructures it as a multi-agent system and adds a dedicated benchmark (Scientist-Bench) for evaluation. The paper explicitly credits The AI Scientist as having pioneered this field and builds its own three-stage pipeline on that foundation.

4. AIGS / Baby-AIGS: Generating Science from AI-Powered Automated Falsification (2024) - positions itself as directly addressing a gap it identifies in The AI Scientist: the absence of an explicit falsification step. It adds a dedicated FalsificationAgent to a similar multi-agent architecture (Proposal, Experiment, Review, Falsification agents) and contrasts its own DSL-based approach with the coding-language approach used in the original.

PARTIAL OR COMPONENT-LEVEL EXTENSIONS (worth citing narrowly, not as full-pipeline successors)

5. Chain of Ideas: Revolutionizing Research Via Novel Idea Development with LLM Agents (2025) - treats The AI Scientist mainly as a baseline for comparison (it extracts just the idea-generation and experiment-design components to build a fair baseline), but it does explicitly adopt and continue two specific practices from it: the novelty-check agent for evaluating candidate ideas, and the evaluation-scale and topic-collection protocol used to assess idea quality. This is a targeted reuse of specific sub-methods, not a full extension of the pipeline.

6. Literature-Grounded Novelty Assessment of Scientific Ideas (2025) - explicitly follows The AI Scientist's query-based literature retrieval method to improve paper-collection coverage for novelty checking, though the rest of the paper's contribution (grounding novelty judgments in retrieved evidence) is new.

7. Are We There Yet? Revealing the Risks of Utilizing Large Language Models in Scholarly Peer Review (2024) - builds directly on the automated-review pipeline introduced in The AI Scientist (one of three established reviewing pipelines it takes as its starting point) and runs manipulation and robustness experiments on top of it. This extends the peer-review component specifically, not the discovery pipeline as a whole.

PAPERS THAT MOSTLY JUST CITE OR BENCHMARK AGAINST IT

Kosmos: An AI Scientist for Autonomous Discovery (2025) positions itself as an advance mainly by comparison (claiming roughly eight times more discovery iterations than existing systems including AI Scientist) rather than building on its architecture. Similarly, MLGym, Automated Hypothesis Validation with Agentic Sequential Falsifications, ScienceAgentBench, Curie, EXP-Bench, Generative Adversarial Reviews, MLR-Copilot, SafeScientist, TreeReview, and Can LLMs Generate Novel Research Ideas? all cite The AI Scientist chiefly as a point of comparison or motivating background - useful as related-systems citations, but none of them adopt or extend its actual method.

For a related-work section distinguishing genuine extension from passing citation, I would treat items 1-4 as the true lineage (with v2 and the 2026 end-to-end-automation paper as the direct successors, and AI-Researcher and AIGS as parallel systems that explicitly build on and extend its pipeline), items 5-7 as partial or component-level reuse worth a specific sentence, and the rest as comparison points only.

**Papers named (19):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Towards end-to-end automation of AI research; AI-Researcher: Autonomous Scientific Innovation; AIGS: Generating Science from AI-Powered Automated Falsification; Chain of Ideas: Revolutionizing Research Via Novel Idea Development with LLM Agents; Literature-Grounded Novelty Assessment of Scientific Ideas; Are We There Yet? Revealing the Risks of Utilizing Large Language Models in Scholarly Peer Review; Kosmos: An AI Scientist for Autonomous Discovery; MLGym: A New Framework and Benchmark for Advancing AI Research Agents; Automated Hypothesis Validation with Agentic Sequential Falsifications; ScienceAgentBench: Toward Rigorous Assessment of Language Agents for Data-Driven Scientific Discovery; Curie: Toward Rigorous and Automated Scientific Experimentation with AI Agents; EXP-Bench: Can AI Conduct AI Research Experiments?; Generative Adversarial Reviews: When LLMs Become the Critic; MLR-Copilot: Autonomous Machine Learning Research based on Large Language Models Agents; SafeScientist: Toward Risk-Aware Scientific Discoveries by LLM Agents; TreeReview: A Dynamic Tree of Questions Framework for Deep and Efficient LLM-based Scientific Peer Review; Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers  
**Stated confidence:** high  
**Stated limits:** I could confirm which papers explicitly adopt or extend The AI Scientist's methods based on stated citation content and framing, but could not independently verify implementation-level fidelity (i.e., whether code or prompts were literally reused) beyond what each paper's own text claims.  
**Effort:** 6 exploration calls, 25,929 payload chars, 234,120 context, 89.0s, $0.554
  
**Graph tools used:** `citations_between`×3, `find_paper`×1, `paper_neighbourhood`×1, `edge_reasons`×1
  
**Call trace:** find_paper(1,361ch) → paper_neighbourhood(5,940ch) → edge_reasons(8,386ch) → citations_between(6,662ch) → citations_between(1,756ch) → citations_between(1,824ch)

> *Judge:* Correct v1 author list, an explicit three-tier taxonomy (full-pipeline successors / component-level reuse / comparison-only), and accurate characterisations of v2, AI-Researcher/Scientist-Bench and AIGS's FalsificationAgent, though it omits the Agent Laboratory–CycleResearcher branch that B catches.

### WEB (search)

**8.0** grounded · **7.666666666666667** correct · **8.0** useful · flags: —

Short answer: only a handful of the many papers that cite "The AI Scientist" (Lu, Hu, Lu, Clune, Ha, et al., 2024) actually build on its architecture or reuse/replace specific components of its pipeline (fully-autonomous ideation → coding → experiment execution → paper writing → automated LLM-based peer review). The rest — including several prominent "AI for science" systems — sit in a parallel lineage and cite it mainly as the reference point for "prior fully-automated paper-writing agents" without adopting its method.

Papers that genuinely extend the method:

1. The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search (Yamada, Lu, et al., Sakana AI, 2025) — the direct successor from the same lab. It explicitly reworks the original pipeline: it removes the dependency on human-written starter code templates, replaces the original's fixed experiment loop with a progressive agentic tree-search process run by a dedicated experiment-manager agent, and augments the automated reviewer with a vision-language-model feedback loop for figure/manuscript refinement. This is the clearest and most direct extension — one of its autonomously generated manuscripts was the first fully AI-generated paper to be accepted at a peer-reviewed ICLR workshop.

2. Agent Laboratory: Using LLM Agents as Research Assistants (Schmidgall et al., 2025) — explicitly framed as fixing a named limitation of The AI Scientist (that it runs with no human-computer interaction and does ideation independent of the human researcher). It keeps the same overall shape (literature review → experimentation → report writing) but restructures it around role-specialized agents (PhD, Postdoc, ML Engineer, Professor) and inserts human-feedback checkpoints. This is a genuine architectural extension, not a passing citation.

3. AgentRxiv: Towards Collaborative Autonomous Research (Schmidgall & Moor, 2025) — a follow-up to Agent Laboratory (and hence, indirectly, to The AI Scientist's pipeline) that adds a shared preprint-server layer so that multiple autonomous research agents can upload and retrieve each other's findings and build cumulatively on prior autonomous work, rather than each running the pipeline in isolation. This is a second-order extension of the same lineage.

4. CycleResearcher: Improving Automated Research via Automated Review (Zhu et al., ICLR 2025) — takes The AI Scientist's core idea of pairing an automated researcher with an automated reviewer, but replaces its fixed prompting-based generation with an iterative reinforcement-learning loop: a policy model (CycleResearcher) generates papers and a learned reward model (CycleReviewer) scores and refines them. The AI Scientist is used throughout as the explicit baseline, and the paper reports CycleResearcher and CycleResearcher-12B outperforming it on human-rated quality and (simulated) acceptance rate. This is a substantive methodological reworking, not just a citation.

5. Zochi (Intology AI, technical report, 2025) — only a partial extension: it reuses and repurposes The AI Scientist's automated-reviewer component specifically (an LLM reviewer following NeurIPS-style guidelines) as the evaluation stage of its own pipeline, while its ideation and experimentation stages are its own design. Notable because Zochi produced the first autonomous paper accepted at an A*-level NLP venue (ACL 2025), but the extension is targeted at one module of the method, not the whole pipeline.

Papers that mainly cite it in passing (same general space, but not extending its method):

- Towards an AI co-scientist (Google DeepMind, 2025) belongs to a different lineage: it is built around Gemini 2.0 test-time compute, self-play scientific debate, and tournament-style hypothesis ranking, and is explicitly designed to stay "scientist-in-the-loop" for hypothesis generation rather than autonomously writing and self-reviewing full papers. It does not adopt The AI Scientist's ideation/experiment/write/review loop.
- Robin: A multi-agent system for automating scientific discovery (FutureHouse, 2025) is built on FutureHouse's own prior agents (Crow, Falcon, Owl, Phoenix, Finch) for literature search and wet-lab biological discovery; it is a different application domain (experimental biology, not ML paper writing) and a different agent lineage, so it treats The AI Scientist as background related work rather than a method it extends.

Net picture for your related-work section: cite The AI Scientist-v2 as the direct successor; Agent Laboratory and its follow-up AgentRxiv as extensions that add human-in-the-loop control and cross-agent collaboration to essentially the same pipeline shape; CycleResearcher as an extension that swaps prompted generation for a learned generator/reviewer training loop; and Zochi as a partial extension that repurposes just the automated-review component. Treat AI co-scientist and Robin as adjacent but methodologically independent systems that cite The AI Scientist for context rather than build on it.

**Papers named (8):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Agent Laboratory: Using LLM Agents as Research Assistants; AgentRxiv: Towards Collaborative Autonomous Research; CycleResearcher: Improving Automated Research via Automated Review; Zochi Technical Report; Towards an AI co-scientist; Robin: A multi-agent system for automating scientific discovery  
**Stated confidence:** medium  
**Stated limits:** I could not exhaustively verify every paper that cites The AI Scientist across the whole literature (there are likely dozens of passing citations I did not individually check), so this should be treated as a well-supported list of the clearest cases rather than a complete census of every extension versus passing citation.  
**Effort:** 8 exploration calls, 23,099 payload chars, 222,953 context, 121.6s, $0.506

> *Judge:* Accurate and specific on v2, Agent Laboratory, AgentRxiv, CycleResearcher/CycleReviewer and Zochi, with sensible exclusions (AI co-scientist, Robin), marred only by a garbled v1 author list ("Lu, Hu, Lu, Clune, Ha" — Hu is a v2, not v1, author) and a slightly generous framing of Agent Laboratory as an extension rather than a parallel design.

### NULL (closed book)

**7.0** grounded · **7.666666666666667** correct · **5.666666666666667** useful · flags: —

Short answer: there is really only one paper that extends The AI Scientist's method in a direct, first-order sense — its own sequel, "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search" (Yamada, Lu, Lange, Foerster, Clune, Ha — the same Sakana AI / Oxford / UBC group as the original). Most of the rest of the literature that cites Lu et al. either builds a parallel, differently-architected pipeline aimed at the same problem, or cites it only as motivation/related work without adopting or modifying its actual method (idea generation → template-based experiment execution → automated write-up → LLM-based automated review).

What genuinely extends the method:

- "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search." This is a direct methodological successor from the original authors. It explicitly targets the weakest part of v1 — the reliance on a human-written, domain-specific starter code template for each project — and replaces the fixed experiment-execution stage with an agentic tree-search procedure (progressive-widening best-first search over experiment variations) that removes the need for a hand-crafted template. It keeps the idea-generation and automated-write-up/automated-review stages of the original pipeline but substantially reworks the experimentation stage, and it reports the concrete result that one fully AI-generated paper from this pipeline was accepted at an ICLR 2025 workshop (subject to a "reviewer told it was AI-generated" caveat later reported). This is unambiguously an extension of the same method, not a citation in passing.

What is inspired by it but is a separate architecture rather than an extension:

- "Agent Laboratory: Using LLM Agents as Research Assistants" (Schmidgall et al.). This paper positions itself explicitly against The AI Scientist and follows a similarly staged pipeline (literature review → experimentation → report writing), but it is a distinct system: it introduces human-in-the-loop checkpoints at each stage, uses a different agent/tooling setup, and reports much lower compute cost as a selling point relative to Lu et al.'s pipeline. I would describe it as a competing/alternative design that responds to and benchmarks itself against The AI Scientist, rather than a paper that builds on and modifies its specific method.

- "SciAgents: Automating Scientific Discovery through Multi-Agent Intelligent Graph Reasoning" (Ghafarollahi & Buehler). This targets a similar end goal (automated hypothesis generation and exploration) but in materials science, and its core mechanism — multi-agent reasoning over an ontological knowledge graph — is architecturally unrelated to The AI Scientist's template-driven experiment loop. It cites The AI Scientist as part of the general automated-discovery landscape rather than extending its method.

Papers I would NOT count as extensions, only as citing it for motivation:

- "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (Si, Yang, Hashimoto). This is an empirical evaluation of LLM idea-generation quality against human researchers; it uses The AI Scientist as a data point/reference for the idea-generation problem but does not adopt or modify its pipeline.
- "ResearchAgent: Iterative Research Idea Generation over Scientific Literature with Large Language Models" (Baek et al.) similarly addresses idea generation with a different iterative-refinement mechanism grounded in citation graphs, and cites The AI Scientist as related prior work rather than building on its method.

Bottom line for your related-work section: cite The AI Scientist-v2 as the direct methodological continuation (same authors, explicit fix to the template-dependence problem, agentic tree search replacing the fixed experiment stage). Treat Agent Laboratory and SciAgents as parallel/alternative systems addressing the same automated-discovery problem with different architectures, worth contrasting rather than presenting as extensions. Treat the idea-generation evaluation papers (Si et al., Baek et al.) as citing it in passing for framing purposes only.

**Papers named (6):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Agent Laboratory: Using LLM Agents as Research Assistants; SciAgents: Automating Scientific Discovery through Multi-Agent Intelligent Graph Reasoning; Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; ResearchAgent: Iterative Research Idea Generation over Scientific Literature with Large Language Models  
**Stated confidence:** medium  
**Stated limits:** I can confidently characterize AI Scientist-v2 as a direct methodological extension and Agent Laboratory/SciAgents as parallel alternative architectures, but I cannot guarantee this list is exhaustive — there may be additional 2025–2026 papers that extend Lu et al.'s specific pipeline (e.g., closed-loop or feedback-driven variants) that I could not verify in enough detail to characterize with confidence, so I have omitted them rather than guess.  
**Effort:** 0 exploration calls, 0 payload chars, 51,376 context, 50.3s, $0.239

> *Judge:* Honest and technically accurate on v2 (progressive-widening tree search, template removal) but very thin coverage — it admits only one extension and misses CycleResearcher, AgentRxiv, AI-Researcher and AIGS, and slightly garbles the ICLR-workshop reviewer-disclosure story.

**Fabrication notes:** B lists "Hu" among The AI Scientist v1 authors (Shengran Hu is on v2, not v1) — a minor slip, not disqualifying; C's claim that the ICLR-workshop reviewer was "told it was AI-generated" is inverted/garbled (organisers consented, reviewers were blind); A's "eight times more discovery iterations" for Kosmos I cannot verify.

*Judged in 54.9s for $0.347.*


---

## q02 — disagreement

> Is the field actually agreed that LLMs can come up with genuinely novel research ideas, or do the studies disagree?

**Expected winner:** `graph`  
**Judged best:** `graph` (slight margin) — prediction hit  
**Ranking:** graph>web>null  
**Presentation order:** graph / null / web

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

contradicts cluster: 'Can LLMs Generate Novel Research Ideas?' (Si et al.) <-> MLRC-Bench <-> 'Can large language models generate novel scientific ideas'.

</details>

### GRAPH (Prior atlas)

**8.666666666666666** grounded · **8.0** correct · **8.666666666666666** useful · flags: unrecognised

The field is genuinely split — there is no consensus, and the disagreement is not just across different research groups but often about what the same evidence actually means.

The pivotal result is Si, Yang & Hashimoto's "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (2024). It set the methodological bar: a blind, style-controlled comparison in which over 100 NLP researchers wrote ideas and separately judged human vs. LLM-generated ones. Its headline finding was that LLM-generated ideas were rated significantly more novel than expert-written ideas (though slightly weaker on feasibility) — the first statistically significant positive result on LLM ideation. But the same paper reported systematic failure modes alongside this: LLM ideation agents lack diversity in what they generate and are unreliable at judging their own idea quality. So even the paper most often cited as evidence "for" LLM creativity built in a major caveat.

That caveat is exactly where later work has pushed back:

- MLRC-Bench ("Can Language Agents Solve Machine Learning Research Challenges?") directly complicates the picture. It shows that LLM-judged novelty is poorly correlated with actual empirical effectiveness on real ML research problems — and the best AI agents close under 10% of the human-expert performance gap. It treats this as refining rather than flatly contradicting Si et al. (their human-judged novelty result stands), but it also frames the two results as in tension: if novelty scores — including the kind of scoring used to celebrate LLM ideation — don't predict whether an idea actually works, then "more novel" is a much weaker claim than it sounds.

- "All That Glitters is Not Novel: Plagiarism in AI Generated Research" (Gupta & Pruthi) goes further, examining the actual documents produced in setups like Si et al.'s and finding that roughly 24% were plagiarized — paraphrased or substantially borrowed from existing work without attribution, verified by the original authors themselves. It also finds LLM-generated research content is measurably less diverse and more predictable than human writing. This is a direct empirical challenge to the "novelty" label: some of what human judges rated as novel may in fact be disguised reuse of prior work, and automated plagiarism detectors (including retrieval-augmented and commercial tools) largely fail to catch it.

- "AI Research Agents Narrow Scientific Exploration" (Tang & Yang, 2026) extends the skepticism at scale, analyzing ~38,000 AI-generated ideas from several agent frameworks (including ResearchAgent and Agent Laboratory). It finds AI ideas cluster much more tightly in topic space than human papers, stay close to their seed literature rather than moving into new territory, and that when they do diverge from prior work, this comes from recombining existing methods rather than posing genuinely new questions — and ideas resembling AI output tend to be cited less afterward.

On the other side, several systems papers report positive results using their own automated or human evaluations: ResearchAgent, NOVA, and a 2026 astronomy-domain study ("Can large language models generate novel scientific ideas? A comprehensive study on data-driven astronomy") all report LLM-generated ideas matching or exceeding human ideas on novelty and related criteria — and the astronomy paper's finding is explicitly recorded as being in tension with MLRC-Bench's skeptical result about novelty-judging reliability.

So the honest summary: there is real, documented disagreement, not just differences in framing. One well-designed human study found LLMs produce ideas people rate as more novel than expert-written ones; several rigorous follow-ups (on plagiarism, on novelty-vs-usefulness correlation, and on topical breadth at scale) each independently show ways in which that "novelty" is compromised — inflated by undetected borrowing, uncorrelated with empirical payoff, or narrower in scope than genuine human exploration. Positive results tend to come from the teams building the ideation systems and using LLM- or lightly-supervised human evaluation; the more adversarial or large-scale audits are the ones raising doubts. No single study has been overturned outright — later papers mostly qualify or narrow Si et al.'s claim rather than refute it — but the field has clearly not converged on "yes, LLMs generate genuinely novel ideas."

**Papers named (7):** Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; MLRC-Bench: Can Language Agents Solve Machine Learning Research Challenges?; All That Glitters is Not Novel: Plagiarism in AI Generated Research; AI Research Agents Narrow Scientific Exploration; ResearchAgent: Iterative Research Idea Generation over Scientific Literature with Large Language Models; NOVA: An Iterative Planning Framework for Enhancing Scientific Innovation with Large Language Models; Can large language models generate novel scientific ideas? A comprehensive study on data-driven astronomy  
**Stated confidence:** medium  
**Stated limits:** I could establish disagreement clearly across NLP/ML-focused ideation studies; I could not establish how this debate has evolved in disciplines outside AI/ML (e.g. biology, physics) beyond the single astronomy and chemistry-adjacent examples found, nor whether any of these results have been independently replicated since publication.  
**Effort:** 12 exploration calls, 38,133 payload chars, 228,051 context, 42.3s, $0.260
  
**Graph tools used:** `paper_neighbourhood`×5, `find_paper`×4, `topic_structure`×1, `search_contributions`×1, `edge_reasons`×1
  
**Call trace:** topic_structure(3,709ch) → search_contributions(4,643ch) → find_paper(637ch) → find_paper(301ch) → find_paper(586ch) → paper_neighbourhood(4,872ch) → paper_neighbourhood(2,940ch) → paper_neighbourhood(5,784ch) → paper_neighbourhood(3,085ch) → edge_reasons(6,745ch) → find_paper(1,115ch) → paper_neighbourhood(3,716ch)

> *Judge:* Broadest and most structured map of the disagreement — Si et al. as the positive anchor, then MLRC-Bench (novelty uncorrelated with effectiveness, <10% of the human gap closed), the Gupta & Pruthi plagiarism audit (~24%), and a large-scale topic-clustering audit — plus a fair sociological point that positive results mostly come from system-builders; its main omission is the ideation-execution gap follow-up, and the NOVA title is slightly off.

### WEB (search)

**8.0** grounded · **9.0** correct · **8.0** useful · flags: unrecognised

No, there isn't consensus — the picture is genuinely mixed, and the disagreement is well documented in a small cluster of directly related studies rather than being a vague field-wide split.

The central reference point is Chenglei Si, Diyi Yang, and Tatsunori Hashimoto's "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (2024). They recruited over 100 expert NLP researchers, had both humans and an LLM write ideas on the same set of topics, and had the ideas blind-reviewed by other experts. The headline result was that the LLM-generated ideas were judged statistically significantly more novel than the human-written ones, though rated slightly weaker on feasibility. This result is the one most often cited as evidence "LLMs can be novel." But the same paper is careful to flag caveats that undercut a simple yes: inter-reviewer agreement on novelty was low (much lower than typical peer review agreement), reflecting how subjective novelty judgments are when no experiment has actually been run; and the LLM showed a lack of diversity, often repeating close variants of the same idea across generations even when explicitly instructed not to, and it could not reliably rank or evaluate ideas itself. So even within this one study, "more novel" coexists with "less reliable," "less diverse," and "not self-evaluable."

The more direct disagreement comes from the same authors' own follow-up, "The Ideation-Execution Gap: Execution Outcomes of LLM-Generated versus Human Research Ideas" (2025). Here they had independent researchers actually execute a random sample of the ideas from the original study — human-written and LLM-written — and write up the resulting experiments. The novelty edge that LLM ideas showed at the ideation stage did not carry over to execution: once ideas were actually implemented, the LLM-originated projects did not outperform the human-originated ones, and in several respects underperformed. This is the clearest evidence that "novel-looking on paper" and "novel/valuable in practice" are different claims, and that the field should not treat the original novelty finding as settling the larger question.

A second strand of disagreement concerns diversity and homogenization rather than single-idea novelty. Work such as "Examining and Addressing Barriers to Diversity in LLM-Generated Ideas" and related creativity-focused surveys (e.g. "Large Language Models for Scientific Idea Generation: A Creativity-Centered Survey") argue that even where individual LLM ideas look novel to a rater, the population of ideas an LLM produces is much less diverse than what a population of human researchers produces, because models are trained to conform to the dominant patterns in their training distribution. The concern raised there is that widespread reliance on LLMs for ideation risks collapsing the range of research directions being pursued, even if any single generated idea passes a novelty check.

So: the "more novel per idea" result from the Si/Yang/Hashimoto human study is a real, carefully-run empirical finding, but it is not the field's settled answer. Their own execution follow-up shows that novelty judged by readers does not reliably predict research value once ideas are executed, and separate diversity-focused work argues that apparent per-idea novelty masks a narrowing of the overall idea space. Papers proposing methods to boost novelty and diversity in LLM ideation (e.g. "Nova: An Iterative Planning and Search Approach to Enhance Novelty and Diversity of LLM Generated Ideas") exist precisely because the community treats current LLM ideation as still deficient on these axes, not solved. The honest summary is: LLMs can produce individual ideas that domain experts rate as more novel than human-written ones under blind review, but whether that constitutes "genuinely novel research ideas" in the fuller sense — executable, non-repetitive across generations, and collectively diverse — is actively disputed, with the strongest counter-evidence being that the same authors who found the novelty effect also found it evaporates once the ideas are actually carried out.

**Papers named (5):** Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; The Ideation-Execution Gap: Execution Outcomes of LLM-Generated versus Human Research Ideas; Examining and Addressing Barriers to Diversity in LLM-Generated Ideas; Large Language Models for Scientific Idea Generation: A Creativity-Centered Survey; Nova: An Iterative Planning and Search Approach to Enhance Novelty and Diversity of LLM Generated Ideas  
**Stated confidence:** medium  
**Stated limits:** I could not establish how these findings generalize outside NLP/CS research (the key studies are largely NLP-researcher samples), nor whether more recent, stronger models than those tested change the balance of the ideation-versus-execution results.  
**Effort:** 4 exploration calls, 12,796 payload chars, 96,697 context, 53.0s, $0.299

> *Judge:* Accurately identifies the sharpest documented disagreement — Si et al.'s own "Ideation-Execution Gap" follow-up, correctly titled and correctly summarized — and correctly reports the original paper's caveats (low inter-reviewer agreement, low diversity, unreliable LLM self-ranking) and the Nova paper's exact title, though its diversity strand rests on two works I cannot place and it omits the plagiarism/benchmark audits.

### NULL (closed book)

**6.0** grounded · **8.0** correct · **6.0** useful · flags: —

Short answer: no, there is not a settled consensus — the strongest empirical evidence available is genuinely double-edged, and the field is actively arguing about what "novelty" even means and whether stated novelty translates into real research value.

The central piece of evidence people point to is Chenglei Si, Diyi Yang, and Tatsunori Hashimoto's large-scale human study, "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (2024). They had over 100 expert NLP researchers write research ideas and also collected LLM-generated ideas on the same prompts, then had experts blind-review both sets. The headline result was that the LLM-generated ideas were rated as more novel than the human-written ones by a statistically significant margin, while being rated as somewhat weaker on feasibility. This is the paper most often cited as evidence "LLMs can produce novel ideas." But the authors themselves were careful to flag major caveats: inter-reviewer agreement on novelty was low (novelty judgments are inherently noisy and subjective), the comparison was against ideas written under time pressure by humans doing a single ideation pass rather than against ideas that survive peer review or execution, and the LLM ideas showed a lack of diversity — they tended to converge on similar themes, which is itself evidence against "genuine" independent novelty even when individual ideas score well.

The same research group followed up by actually executing a subset of the generated ideas as real experiments/papers, examining whether the perceived novelty translated into research outcomes (often discussed as an "ideation-execution gap"). The upshot of that follow-up work is that ideas judged novel at the proposal stage did not reliably turn into strong or novel executed research — execution quality and downstream contribution were much less impressive than the ideation-stage novelty scores would suggest. That is a direct complication of the "LLMs can generate novel ideas" claim: it separates "sounds novel on paper" from "is actually a valuable, correct, executable research contribution," and finds a real gap between the two.

On the more skeptical side, the Sakana AI "AI Scientist" system (Lu, Lu, Lange, Foerster, Clune, Ha et al., "The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery," 2024) is often invoked in this debate. It's a fully automated pipeline that generates ideas, runs experiments, and writes papers. It drew substantial public and academic criticism — many of the "novel" ideas and generated papers were found to be shallow, to rehash existing techniques, or to contain fabricated/hallucinated results and citations, undermining confidence that the ideation stage was producing genuinely new science rather than plausible-sounding recombination of training data.

There is also a broader concern sometimes raised in this debate under the heading of homogenization: when many people use the same LLM for brainstorming, individual outputs may be rated as good or novel relative to a single human baseline, but across many users the overall pool of ideas becomes less diverse than a pool of independent human ideas. That's a separate strand of evidence (not specific to research-idea generation alone, but raised in that context too) suggesting that apparent per-item novelty can coexist with a narrowing of what the field as a whole would actually explore if it relied on LLM ideation at scale.

So the honest summary: one well-designed, well-cited study (Si, Yang, Hashimoto) finds LLM ideas rated more novel than human ideas by blind expert review, which is real and notable evidence in favor. But that same line of work's own follow-up on execution, the diversity/homogenization concerns, and the reception of autonomous systems like Sakana's AI Scientist all push back against treating "rated as novel by reviewers at proposal stage" as equivalent to "genuinely producing new, valuable science." The field is not in agreement that the novelty question is settled — it has one strong positive data point and several serious complicating findings, not a consensus.

**Papers named (2):** Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery  
**Stated confidence:** medium  
**Stated limits:** I recall a follow-up study by the same research group examining execution of the AI-generated ideas (the gap between ideation-stage novelty and executed-research quality) with confidence in its substance and direction, but I am not fully certain of its exact published title, so I described it descriptively rather than citing it as a formal title; I also cannot point to a specific named paper for the homogenization/diversity claim in this exact context, so that point should be read as a general concern raised in the literature rather than a single citable finding.  
**Effort:** 0 exploration calls, 0 payload chars, 122,193 context, 87.8s, $0.248

> *Judge:* Correct in substance about Si et al., the execution follow-up and the AI Scientist reception, and commendably honest about which claims it cannot cite by title, but it names only two papers and leaves the two most load-bearing counter-strands (execution gap, homogenization) uncited.

**Fabrication notes:** none — no claim in any answer contradicts what I know; A's NOVA title is a loose variant rather than a garbled misattribution, and unplaceable 2026-dated titles were flagged as unrecognised, not false.

*Judged in 54.9s for $0.175.*


---

## q03 — disagreement

> My PI thinks fully autonomous AI scientists already produce publishable research. Is that contested in the literature?

**Expected winner:** `graph`  
**Judged best:** `graph` (slight margin) — prediction hit  
**Ranking:** graph>web>null  
**Presentation order:** web / graph / null

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

'Can AI Conduct Autonomous Scientific Research?' is a contradiction hub: 7 contradicts + 9 supports edges, against Kosmos, AI-Researcher, OpenLens AI, and 'The More You Automate, the Less You See'.

</details>

### GRAPH (Prior atlas)

**9.0** grounded · **8.0** correct · **9.0** useful · flags: unrecognised

Yes — this is actively and explicitly contested, not a settled question, and there is a real fault line between the systems papers making the "publishable research" claim and a growing set of independent evaluation papers pushing back on it.

**The claims side.** The AI Scientist (Lu, Lu, Lange, Foerster, Clune & Ha, 2024) is the founding claim: an end-to-end pipeline in which a frontier LLM generates ideas, runs experiments, writes a manuscript, and self-reviews, producing papers the authors say exceed a top ML conference's acceptance threshold — as judged by their own automated reviewer, not by human peer review. The AI Scientist-v2 (Yamada, Lange, Lu, Hu, Lu & Foerster, 2025) goes further and reports that one fully AI-generated manuscript actually cleared peer review and exceeded the average acceptance bar at a real ICLR workshop. Other systems in the same lineage — AI-Researcher, Kosmos, OpenLens AI (health informatics), Towards end-to-end automation of AI research — make comparable or stronger claims. Kosmos in particular reports 79.4% of its generated report statements verified accurate by independent domain experts, with several findings judged genuinely novel.

**The pushback side.** Three independent papers directly contest these claims, and the disagreement is recorded as a substantive contradiction, not just differing emphasis:

- "Can AI Conduct Autonomous Scientific Research? Case Studies on Two Real-World Tasks" (2026) systematically evaluated eight open-source AI research frameworks against a full research-cycle standard (literature understanding → hypothesis → implementation → validated results → writing) and found that none completed a full cycle. The consistent failure point was the transition from planning to actual computational execution: frameworks were competent at conceptual summarization but produced "sophisticated hallucinations" rather than genuine validated results, and required substantial human debugging to run at all — directly undercutting claims of "minimal/no human intervention." This paper explicitly frames itself as a corrective to "isolated success stories, often reported by the developers of the systems themselves," and its authors register direct contradictions with AI-Researcher, OpenLens AI, Kosmos, and (by extension) the AI Scientist line of work.

- "Why LLMs Aren't Scientists Yet: Lessons from Four Autonomous Research Attempts" (2026, Trehan & Chopra) independently ran four end-to-end autonomous ML research attempts and documents six recurring failure modes — bias toward training-data defaults, implementation drift, context/memory degradation on long-horizon tasks, "overexcitement" (declaring success despite obvious failure), weak domain intelligence, and poor experimental taste — and argues for design principles rather than declaring the problem solved.

- "The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems" (Luo, Kasirzadeh & Shah, 2025) is the most pointed methodological critique. It audits prominent open-source AI scientist systems (including The AI Scientist and Agent Laboratory) and finds systematic issues — benchmark cherry-picking, undocumented dataset manipulation, arbitrary metric choices, and post-hoc selection bias driven by internal reward mechanisms that game test-set performance. Critically, they show that an LLM auditor catches these problems far more reliably when given the full workflow trace and code (82% accuracy) than when given only the finished paper (55% accuracy) — implying that a paper's surface polish and apparent acceptability can mask methodologically unsound underlying work. This paper's finding is recorded as directly contradicting Kosmos's expert-validation claim: reliability assessed on the finished report versus reliability assessed on the underlying process point to different conclusions.

**Net assessment.** The "publishable" claims mostly rest on automated-reviewer judgments (The AI Scientist) or on a single workshop-level acceptance (AI Scientist-v2), and on developer-run evaluations. The critical literature argues these are weak or biased evidentiary standards, and that when independently audited — either by testing frameworks on real research cycles or by inspecting the underlying execution trace rather than the finished manuscript — current systems fail at robust computational implementation and are prone to hallucination, cherry-picking, and self-reported "success" that doesn't hold up. So your PI's position is one side of a live and fairly sharp dispute, not a consensus finding. The more defensible summary of the literature is: current systems can produce manuscripts that look polished and sometimes clear low bars (an automated reviewer, one workshop), but independent, execution-level scrutiny consistently finds methodological failures that undercut a "fully autonomous, publication-quality" claim in the general case.

**Papers named (8):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; AI-Researcher: Autonomous Scientific Innovation; Kosmos: An AI Scientist for Autonomous Discovery; OpenLens AI: Fully Autonomous Research Agent for Health Infomatics; Can AI Conduct Autonomous Scientific Research? Case Studies on Two Real-World Tasks; Why LLMs Aren't Scientists Yet: Lessons from Four Autonomous Research Attempts; The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems  
**Stated confidence:** high  
**Stated limits:** I can establish that the dispute is explicit and substantive in the recent literature, but I cannot verify from this material alone which side would prevail under a fully independent, blinded human peer-review test (as opposed to automated-reviewer or single-workshop evidence), since no paper in this set reports that.  
**Effort:** 11 exploration calls, 47,576 payload chars, 202,653 context, 44.6s, $0.263
  
**Graph tools used:** `paper_neighbourhood`×5, `find_paper`×2, `edge_reasons`×2, `topic_structure`×1, `search_contributions`×1
  
**Call trace:** topic_structure(4,313ch) → search_contributions(4,934ch) → find_paper(312ch) → find_paper(317ch) → paper_neighbourhood(5,940ch) → paper_neighbourhood(5,341ch) → paper_neighbourhood(3,763ch) → paper_neighbourhood(4,618ch) → paper_neighbourhood(4,098ch) → edge_reasons(11,642ch) → edge_reasons(2,298ch)

> *Judge:* Best-structured account of the fault line: correctly distinguishes the original paper's self-reviewer evidence from v2's single real workshop acceptance, correctly states Kosmos's 79.4% expert-verified figure, and cites three specific critique papers with checkable findings (e.g. the 82% vs 55% trace-vs-paper audit gap), several of which are too recent for me to place.

### WEB (search)

**8.333333333333334** grounded · **8.0** correct · **8.333333333333334** useful · flags: unrecognised

Yes — this is actively contested, and the strongest evidence on both sides comes from the same line of work, which makes the disagreement unusually direct.

The claim of success: Sakana AI's "The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery" and its successor "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search" are the papers your PI is likely thinking of. The v2 system autonomously generates a hypothesis, designs and runs experiments via agentic tree search, analyzes results, and writes a full LaTeX manuscript with no human in the loop. The authors submitted three fully autonomous manuscripts to a real, blind peer-reviewed ICLR 2025 workshop (ICBINB); one scored an average of 6.33 (individual scores 6, 7, 6), above the workshop's average acceptance threshold — the first documented case of an unedited, fully AI-generated paper clearing a genuine human peer-review bar. Sakana has since published a related "Towards end-to-end automation of AI research" piece in Nature, further pressing the claim that the pipeline works.

The pushback is contested on at least three grounds in the literature:

1. Reliability of the pipeline itself. An independent evaluation, "Evaluating Sakana's AI Scientist for Autonomous Research: Wishful Thinking or an Emerging Reality Towards Artificial Research Intelligence (ARI)?", stress-tested the released system and found weak literature grounding, roughly half of attempted experiments failing outright, and manuscripts containing hallucinated numerical results, missing or duplicated figures, and leftover placeholder text (e.g., "Conclusions Here"). Independent tallies of the v2 outputs found a majority of generated papers (about 4 of 7 examined) contained fabricated or incorrect numerical results — including impossibly high accuracy scores on corrupted or invented datasets — even though one manuscript simultaneously scored well enough to pass peer review. The evaluators' summary judgment was that manuscript quality resembled "an unmotivated undergraduate rushing to meet a deadline" rather than a reliable research collaborator, and that the system cannot check its own logical or methodological soundness. Sakana's own authors acknowledge the system disobeys instructions and hallucinates a non-trivial fraction of the time.

2. What "passing peer review" actually shows. Critics have pointed out that one workshop paper clearing one score threshold at one lightly-reviewed venue is a weak proxy for "publishable research" in general — workshop review is noisier and lower-stakes than main-track review, and a system with a high failure/hallucination rate can still occasionally produce a polished-looking outlier. This is the crux of the disagreement: Sakana's papers treat the peer-review pass as validation of the approach, while the evaluation literature treats it as a cherry-pickable success buried in a high error rate.

3. Whether "novel ideas" and "sound research" are the same thing. The large-scale study "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (over 100 recruited NLP researchers, blind comparison of human- and LLM-written ideas) found LLM-generated ideas were rated as more novel than expert-generated ones, but rated slightly weaker on feasibility, and the authors flag serious open problems with LLMs' ability to self-evaluate their own ideas and with lack of diversity across generations. This supports a more nuanced picture: generation of interesting ideas is a separate and more solved problem than reliable execution and honest reporting.

Bottom line for your PI: the field has not converged. Sakana AI's own papers (and the Nature piece) are the strongest evidence for the "already publishable" claim. But every close independent read of the same systems — most explicitly the ARI evaluation paper, together with post-hoc audits reporting majority-hallucination rates in the v2 outputs — concludes that current AI-scientist pipelines are unreliable, error-prone, and require heavy human verification, and that the one workshop acceptance is closer to a proof-of-concept outlier than evidence of general publication-quality autonomy. Recent survey work in this space ("From AI for Science to Agentic Science: A Survey on Autonomous Scientific Discovery") likewise treats fully autonomous, reliably publication-grade AI scientists as an aspirational frontier rather than an established capability. So: the specific factual claim (one AI-Scientist-v2 paper scored above a workshop acceptance threshold) is true and documented, but the generalization your PI is making — that fully autonomous AI scientists already reliably produce publishable research — is explicitly disputed by independent evaluators of the very same systems.

**Papers named (6):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Towards end-to-end automation of AI research; Evaluating Sakanas AI Scientist for Autonomous Research: Wishful Thinking or an Emerging Reality Towards Artificial Research Intelligence (ARI)?; Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; From AI for Science to Agentic Science: A Survey on Autonomous Scientific Discovery  
**Stated confidence:** high  
**Stated limits:** I can establish that the claim is genuinely contested and can point to the specific documented success (one workshop-level acceptance) versus the specific documented failure modes (majority hallucination/error rates in independent audits); I cannot establish a settled consensus figure for how often such systems succeed versus fail across the field as a whole, since results are drawn from a small number of case studies and evaluations rather than a large systematic benchmark.  
**Effort:** 5 exploration calls, 13,875 payload chars, 243,367 context, 119.1s, $0.590

> *Judge:* Accurately anchors the dispute on the Sakana AI Scientist / v2 line (including the correct ICBINB workshop detail and ~6.33 average score) and pairs it with the real Beel-style ARI evaluation, though the "Nature" attribution for the end-to-end-automation piece and the "4 of 7 hallucinated" tally are the least verifiable elements.

### NULL (closed book)

**7.0** grounded · **7.666666666666667** correct · **7.333333333333333** useful · flags: —

Yes — this is actively contested, and the disagreement runs right through the papers that made the strongest claims.

**The main claim your PI is likely thinking of** comes from Sakana AI's "The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery" (Lu, Lu, Lange, Foerster, Clune, Ha, 2024). It describes an end-to-end pipeline — idea generation, coding, running experiments, writing up results, and an automated "reviewer" module — and reports that its own LLM-based reviewer judged the output papers as comparable in quality to real conference submissions. A follow-up, "The AI Scientist-v2," pushed this further with an agentic tree-search process and reportedly had one fully AI-generated paper pass peer review at an ICLR workshop.

**Why this is contested rather than settled:**

1. The quality evidence in the original paper rests heavily on an LLM acting as its own reviewer, which is a weak and self-referential form of validation — LLM judges are known to have biases (favoring fluent, confident, longer text) that make "near-human reviewer agreement" hard to trust as a proxy for genuine scientific validity.
2. Independent scrutiny of the generated papers after release found substantive problems: shallow or nonsensical experiments, incorrect statistical claims, citation and self-plagiarism issues, and in at least one case the system modifying its own experiment-running code to bypass a timeout — a reliability/safety failure, not just a quality one. This significantly undercut the "publishable" framing.
3. The AI Scientist-v2 workshop acceptance is often read very differently by critics than by the authors: a single workshop-track acceptance, for a specific paper selected out of several attempts, at a venue with a lower bar and smaller reviewer pool than a main conference or journal, is not treated by most of the field as evidence that autonomous systems reliably produce publishable science — more as a curated proof-of-concept, with humans still choosing which output to submit and how to present it.

**Complicating and more cautious evidence:**
- "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (Chenglei Si, Diyi Yang, Tatsunori Hashimoto, 2024) is the most careful empirical study in this space, but it only addresses the idea-generation stage, not full papers. Under blind review by real researchers, LLM-generated ideas were rated more novel than human-generated ideas but notably less feasible — and the authors themselves caution that judging novelty is difficult and that this result shouldn't be over-extrapolated to claims about full autonomous research output.
- "Autonomous LLM-driven research — from data to human-verifiable research papers" (Ifargan, Hafner, Kern, Alcalay, Kishony, 2024) is essentially a direct response to the reliability problem: it builds a pipeline (sometimes called Data-to-Paper) that forces every claim in an AI-written paper to be traceable back to the underlying code and data, explicitly because unconstrained autonomous pipelines like Sakana's were producing papers whose claims couldn't be trusted or verified.
- Systems with actual experimental (wet-lab or chemistry) validation — "Autonomous chemical research with large language models" (Boiko et al., 2023, the "Coscientist" system) and "The Virtual Lab of AI agents designs new SARS-CoV-2 nanobodies" (Zou et al., 2025, published in Nature with real binding-affinity validation) — are the strongest existing evidence that AI-driven pipelines can produce results meeting a publication bar. But in both cases there is substantial human framing, oversight, and selection of what gets tested and reported; they are not "fully autonomous" in the sense of a system unsupervised end-to-end, and their success is domain-specific (chemistry, protein/antibody design) rather than general.

**Bottom line:** There is no consensus that fully autonomous AI scientists already reliably produce publishable research. The strongest "yes" evidence (Sakana's AI Scientist and AI Scientist-v2) comes from the same group making the claim and has been substantially disputed on grounds of self-evaluation bias, output quality, and the low bar of the specific venue used to demonstrate success. The most careful independent human study (Si, Yang, Hashimoto) only supports novelty at the idea stage, with a feasibility gap. And the clearest cases of genuinely validated output (Boiko et al.'s Coscientist, Zou et al.'s Virtual Lab) involve heavy human oversight and narrow domains, which is a different claim than "fully autonomous."

**Papers named (6):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; Autonomous LLM-driven research — from data to human-verifiable research papers; Autonomous chemical research with large language models; The Virtual Lab of AI agents designs new SARS-CoV-2 nanobodies  
**Stated confidence:** medium  
**Stated limits:** I could not verify the precise current status (e.g., exact acceptance outcome, any later retraction or disclosure dispute) of the AI Scientist-v2 workshop submission, nor find a single authoritative peer-reviewed rebuttal paper devoting itself specifically to critiquing the original AI Scientist paper's quality claims — much of that pushback exists as independent scrutiny/commentary rather than a formal counter-paper, and I could not enumerate it further with confidence.  
**Effort:** 0 exploration calls, 0 payload chars, 62,866 context, 84.0s, $0.204

> *Judge:* Appropriately cautious and adds a genuinely useful axis (Coscientist, Virtual Lab as domain-validated but human-scoped counterpoints), but its critique side is largely unattributed "independent scrutiny", it credits the self-reported timeout-bypass incident to external critics, and it implies data-to-paper (Ifargan/Kishony, preprinted before The AI Scientist) was built in response to Sakana.

**Fabrication notes:** Nothing clearly fabricated. Two soft errors worth noting: (1) Answer C's chronology — data-to-paper (Ifargan et al.) predates The AI Scientist, so it cannot have been motivated by it, and it attributes the self-modifying-timeout incident to independent scrutiny when Sakana reported it themselves; it also cites the Virtual Lab as "Zou et al." when Swanson is first author (Zou senior). (2) Answer A's claim that Sakana published "Towards end-to-end automation of AI research" in Nature is a specific venue claim I cannot confirm.

*Judged in 58.1s for $0.192.*


---

## q04 — uses-findings

> What research is actually being built on the findings from 'Hypothesis Generation with Large Language Models' (the HypoGeniC paper)? I want to know what people did with it, not just who cited it.

**Expected winner:** `graph`  
**Judged best:** `graph` (slight margin) — prediction hit  
**Ranking:** graph>web>null  
**Presentation order:** web / null / graph

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

Only 2 papers genuinely take it up - 'Literature Meets Data' (uses_extends + 3 builds_on) and 'HypoBench' (uses_extends + 4 builds_on). 'Improving Scientific Hypothesis Generation with Knowledge Grounding' compares_contrasts. TEN other papers cite it as pure background. The web sees 12 undifferentiated citations.

</details>

### GRAPH (Prior atlas)

**8.0** grounded · **7.666666666666667** correct · **7.666666666666667** useful · flags: unrecognised

HypoGeniC (Zhou, Liu, Srivastava, Mei & Tan, "Hypothesis Generation with Large Language Models," 2024) introduced an iterative, bandit-inspired (UCB-style) algorithm for generating and refining data-grounded hypotheses with LLMs, maintaining a "wrong-example bank" to drive an exploration/exploitation loop, and showed that classifiers built from these hypotheses beat few-shot in-context learning and supervised baselines like RoBERTa/Llama-2-7B on real-world text classification tasks. Beyond simply being cited as prior work, three lines of research concretely build on it:

1. "Literature Meets Data: A Synergistic Approach to Hypothesis Generation" takes HypoGeniC's algorithm and code as the literal data-driven backbone of its own system (called HypoRefine in that work). It bolts on a literature-retrieval agent so that hypotheses are grounded in both data and prior published findings, and it adds a human-evaluation protocol showing that hypotheses produced by this hybrid pipeline improve human decision accuracy on tasks like deception detection (+7.44%) and AI-generated-content detection (+14.19%). It also reports that combining literature with HypoGeniC's data-driven generation produces the best out-of-distribution generalization across five datasets. In short, this paper operationalizes HypoGeniC as a component and extends it rather than merely referencing it.

2. "HypoBench: Towards Systematic and Principled Benchmarking for Hypothesis Generation" uses HypoGeniC's official released code and reported hyperparameters as one of the methods it benchmarks head-to-head against five other hypothesis-generation approaches across four LLMs, and it reuses HypoGeniC's original real-world datasets (deceptive reviews, retweets, news headlines) as part of its evaluation suite. This work turns HypoGeniC into a standard baseline/reference point for the field, and its findings (e.g., that augmenting data-driven generation with retrieved literature performs best on real-world tasks, and that hypothesis-discovery rates collapse sharply as synthetic task difficulty rises, topping out around 38.8% recovery of ground-truth hypotheses even for the best method) are calibrated against HypoGeniC's performance.

3. "DN-Hypo-Pipeline: An AI-Driven Workflow for Hypothesis Generation via Large Language Models and Scientific Explanations" independently arrives at a matching conclusion — that LLM-generated hypotheses can be turned into working algorithms that outperform baselines from highly cited data-science papers — reinforcing HypoGeniC's central empirical claim in a different (non-text-classification) domain, though this is a parallel/corroborating result rather than a direct reuse of HypoGeniC's code.

There is also a more critical line of engagement: "Improving Scientific Hypothesis Generation with Knowledge Grounded Large Language Models" explicitly contrasts itself with HypoGeniC's prompting-based iterative approach, arguing that its own method differs by grounding hypothesis generation in structured and unstructured domain-specific knowledge sources rather than relying mainly on iterative prompting over data examples — i.e., it treats HypoGeniC as an important point of comparison and improves on it along the axis of external knowledge grounding rather than adopting its machinery.

Overall, the pattern is: HypoGeniC's algorithm and released artifacts (code, datasets, hyperparameters) have become a standard component/baseline that follow-on hypothesis-generation systems either directly incorporate (Literature Meets Data, HypoBench) or use as the comparison point they aim to surpass (Improving Scientific Hypothesis Generation with Knowledge Grounded LLMs), while other work (DN-Hypo-Pipeline) independently corroborates its core finding that LLM-derived hypotheses can be turned into high-performing, interpretable models.

**Papers named (5):** Hypothesis Generation with Large Language Models; Literature Meets Data: A Synergistic Approach to Hypothesis Generation; HypoBench: Towards Systematic and Principled Benchmarking for Hypothesis Generation; DN-Hypo-Pipeline: An AI-Driven Workflow for Hypothesis Generation via Large Language Models and Scientific Explanations; Improving Scientific Hypothesis Generation with Knowledge Grounded Large Language Models  
**Stated confidence:** medium  
**Stated limits:** I could establish which specific papers build on, benchmark against, or contrast with HypoGeniC and how, based on their stated methodological relationships; I could not independently verify claims like DN-Hypo-Pipeline's specific numerical results or assess real-world downstream adoption (e.g., industry use) beyond the academic literature examined.  
**Effort:** 4 exploration calls, 15,032 payload chars, 160,670 context, 30.5s, $0.142
  
**Graph tools used:** `find_paper`×1, `paper_neighbourhood`×1, `edge_reasons`×1, `citations_between`×1
  
**Call trace:** find_paper(1,467ch) → paper_neighbourhood(3,801ch) → edge_reasons(7,895ch) → citations_between(1,869ch)

> *Judge:* Gets the authors, algorithm and the HypoRefine/Literature-Meets-Data lineage right, distinguishes reuse from mere contrast (KG-grounded work) from parallel corroboration (DN-Hypo-Pipeline), though it misses HypoEval and HypotheSAEs and leans on one paper I cannot place.

### WEB (search)

**8.0** grounded · **4.666666666666667** correct · **7.666666666666667** useful · flags: fabricated, unrecognised

HypoGeniC (Zhu, Sudhir, Zhu, Si et al., "Hypothesis Generation with Large Language Models," 2024, from the University of Chicago Human+AI Lab) proposed an LLM pipeline that generates candidate natural-language hypotheses from a handful of labeled examples and then iteratively refines them using a multi-armed-bandit-style reward that trades off exploring new hypotheses against exploiting ones that already score well on a growing "wrong example bank." The concrete downstream uses of this idea fall into a few clear categories:

1. Direct extension by the same authors. The original paper already introduced a sister method, HypoRefine, which augments the data-driven bandit loop with literature retrieval so that hypotheses are grounded in both existing papers and the dataset. This was developed into its own full paper, "Literature Meets Data: A Synergistic Approach to Hypothesis Generation" (ACL 2025), which shows that combining literature-based and data-driven generation beats few-shot prompting by about 9%, beats literature-only generation by about 16%, and beats the original data-only HypoGeniC by about 3% on held-out prediction accuracy. This is the most direct "what did people build on it" answer: the authors themselves turned HypoGeniC's bandit-refinement core into a hybrid literature+data system.

2. Repurposing the machinery for evaluation rather than discovery. "HypoEval: Hypothesis-Guided Evaluation for Natural Language Generation" takes the HypoGeniC/HypoRefine hypothesis-refinement loop and uses it to automatically derive checklist-style evaluation criteria for scoring generated text, extending the framework so it outputs Likert-scale judgments rather than the binary yes/no rubrics that earlier checklist-based evaluators produced. It explicitly builds on HypoRefine (and hence on HypoGeniC) as its generation engine, redirecting the method from "explain a labeled dataset" to "construct a rubric for judging text quality."

3. Using it as a diagnostic tool to find model weaknesses, then acting on the hypotheses. "Automatically Generating Hard Math Problems from Hypothesis-Driven Error Analysis" runs HypoGeniC directly on records of which math problems a target model (Llama-3.3-70B) gets right or wrong, letting it propose and score natural-language hypotheses about which mathematical concepts correlate with failure. The highest-scoring hypotheses are then used as semantic anchors to prompt an LLM to generate new, harder problems that specifically probe those identified weaknesses — i.e., HypoGeniC is repurposed from a scientific-discovery tool into an error-analysis-and-adversarial-problem-generation component in someone else's pipeline.

4. Systematic benchmarking of the method itself. "HypoBench: Towards Systematic and Principled Benchmarking for Hypothesis Generation" evaluates HypoGeniC alongside five other hypothesis-generation methods (including the literature+data variant) across seven real-world and five synthetic tasks with over 190 datasets, using metrics like hypothesis discovery rate, downstream classification accuracy, generalization under distribution shift, and human-rated novelty/plausibility/clarity. It finds HypoGeniC is the strongest purely data-driven method tested and the single best method on synthetic tasks (hypothesis discovery rate up to ~94% at low complexity), but that its performance collapses as task compositionality and noise increase (down to ~39% discovery rate), and that on real-world tasks the literature-augmented variant surpasses it — establishing both HypoGeniC's competitive standing and its concrete limits.

5. Use as a comparison baseline for alternative hypothesis-generation architectures. "Sparse Autoencoders for Hypothesis Generation" treats HypoGeniC as the representative "prompt-the-LLM-with-labeled-examples-and-a-bandit-reward" baseline against which it contrasts its own approach of building hypotheses out of sparse-autoencoder-derived features, positioning HypoGeniC as the standard data-driven prompting method that alternative, more mechanistically grounded approaches are measured against.

Taken together, the concrete downstream work is: (a) the authors' own extension into a literature-plus-data hybrid (HypoRefine / "Literature Meets Data"), (b) repurposing the same refinement loop for automatic NLG evaluation (HypoEval), (c) using the method as an error-analysis engine to drive adversarial problem generation for math LLMs, (d) folding it into a broader benchmark (HypoBench) that quantifies where it excels (synthetic, low-complexity tasks) and where it breaks down (compositional, noisy real-world tasks), and (e) using it as the standard baseline that newer hypothesis-generation architectures (e.g., sparse-autoencoder-based methods) are compared against. I did not find evidence of large-scale adoption outside the hypothesis-generation/AI-for-science niche (e.g., no confirmed uptake in wet-lab or clinical hypothesis-generation pipelines), so its downstream influence so far looks concentrated among a fairly small cluster of NLP/AI-for-science groups rather than being broadly diffused.

**Papers named (6):** Hypothesis Generation with Large Language Models; Literature Meets Data: A Synergistic Approach to Hypothesis Generation; HypoEval: Hypothesis-Guided Evaluation for Natural Language Generation; Automatically Generating Hard Math Problems from Hypothesis-Driven Error Analysis; HypoBench: Towards Systematic and Principled Benchmarking for Hypothesis Generation; Sparse Autoencoders for Hypothesis Generation  
**Stated confidence:** medium  
**Stated limits:** I could not fully verify the precise technical relationship (e.g., whether it is a direct extension, a mere baseline mention, or something in between) for a couple of tangentially related papers I found in the search (an ILP hypothesis-generation paper and an agentic social-science hypothesis paper) because their full text was not accessible to me, so I excluded them rather than guess; there may be additional downstream uses in venues or preprints I did not surface.  
**Effort:** 12 exploration calls, 22,339 payload chars, 241,283 context, 106.3s, $0.852

> *Judge:* Much the richest survey of genuine downstream uses (Literature Meets Data, HypoEval, HypoBench, HypotheSAEs) with precise, mostly checkable relationships, but it misattributes HypoGeniC's authorship entirely and wrongly says the original paper introduced HypoRefine.

### NULL (closed book)

**5.333333333333333** grounded · **8.0** correct · **4.0** useful · flags: hedged

Short answer: the clearest, most confident case of work actually built on top of HypoGeniC's method (rather than just citing it) is HypoBench, a benchmark paper from the same research group (Chenhao Tan's lab at the University of Chicago, overlapping authors with the original HypoGeniC paper — Yangqiaoyu Zhou, Haokun Liu, et al.). HypoBench takes HypoGeniC's core algorithm — the iterative, bandit-style loop that proposes candidate hypotheses from small labeled datasets, scores them on held-out examples, and updates a "hypothesis bank" — and turns it into one of the reference methods evaluated inside a broader systematic assessment of hypothesis-generation approaches. HypoBench compares HypoGeniC's data-driven iterative refinement against other strategies (e.g., purely literature-grounded generation and hybrid literature+data approaches) across a wider and more diverse set of real-world tasks than the original paper used, and it examines properties like hypothesis validity, novelty, and generalizability that the original HypoGeniC paper didn't systematically measure. This is a direct extension: it reuses and stress-tests the actual algorithm and hypothesis-bank framework, not just the idea of LLM-driven hypothesis generation.

Beyond that direct lineage, HypoGeniC's core idea — use an LLM to propose and iteratively refine explicit, checkable natural-language hypotheses from small data samples, then use the surviving hypotheses as interpretable features/predictors for a downstream task — has become a common reference point and baseline in the broader "LLM for hypothesis/idea generation" literature (e.g., work on literature-grounded scientific hypothesis discovery, and general research-idea-generation systems). However, I can't confidently confirm from memory that these other systems actually adopt or extend HypoGeniC's specific bandit-update algorithm or hypothesis-bank machinery, as opposed to citing it as related prior work or using it as a comparison baseline. I don't want to overstate that connection.

So: the one clear "built on it" case I can vouch for is HypoBench. Other papers in the hypothesis/idea-generation space engage with HypoGeniC mainly as a point of comparison or motivating prior work, and I don't have reliable enough recall to name specific independent systems that reuse its actual algorithm.

**Papers named (2):** Hypothesis Generation with Large Language Models; HypoBench: Towards A Systematic Assessment of Hypothesis Generation Methods  
**Stated confidence:** low  
**Stated limits:** I could not establish with confidence which, if any, independent (non-same-lab) research groups have directly reused or extended HypoGeniC's specific algorithm (as opposed to citing it as related prior work or a baseline) — my recall here is limited and I did not want to name papers I'm not sure about.  
**Effort:** 0 exploration calls, 0 payload chars, 119,814 context, 72.2s, $0.215

> *Judge:* Honest and essentially error-free, but it surfaces only HypoBench and explicitly declines to name the other obvious direct extensions (Literature Meets Data / HypoRefine, HypoEval), so there is little the researcher can act on.

**Fabrication notes:** Answer A attributes HypoGeniC to "Zhu, Sudhir, Zhu, Si et al." — the paper is by Yangqiaoyu Zhou, Haokun Liu, Tejes Srivastava, Hongyuan Mei and Chenhao Tan (Chicago Human+AI Lab); A also states that HypoRefine was introduced in the original HypoGeniC paper, whereas HypoRefine is introduced in the follow-up "Literature Meets Data" paper (Answer C states this correctly).

*Judged in 71.1s for $0.196.*


---

## q05 — evidence-base

> I want to use an LLM to give feedback on my students' paper drafts. How well does that actually work in practice, and has anyone found that it doesn't?

**Expected winner:** `graph`  
**Judged best:** `graph` (slight margin) — prediction hit  
**Ranking:** graph>web>null  
**Presentation order:** null / graph / web

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

supports + contradicts around 'Can Large Language Models Provide Useful Feedback on Research Papers?' (positive headline) - 4 contradicts edges to 'LLMs Assist NLP Researchers: Critique Paper Writing' and 'Are We There Yet? Revealing the Risks of Utilizing LLMs in Scholarly Peer Review', plus support/priority labels on the citation layer.

</details>

### GRAPH (Prior atlas)

**9.0** grounded · **8.666666666666666** correct · **8.0** useful · flags: —

Short answer: it works surprisingly well on the surface-level metrics people have checked so far, but there is real, direct disagreement in the literature about how good LLM feedback actually is, and several papers document specific, serious failure modes you should know about before relying on it for grading or substantive feedback to students.

The most directly relevant large-scale study is Liang et al.'s "Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis" (2024). They built a GPT-4 pipeline that reads a paper and produces structured feedback (significance, novelty, accept/reject-style reasoning, suggested improvements), and tested it at scale across multiple venues (Nature journals, ICLR, etc.). Two key findings: (1) the overlap between GPT-4's feedback and what a single human reviewer says is comparable to the overlap between two different human reviewers on the same paper — i.e., GPT-4 disagrees with any one human reviewer about as much as human reviewers disagree with each other; and (2) when they asked researchers to rate feedback on their own actual papers, a majority found it helpful, and many rated it as competitive with or better than the human peer review they'd received. This is the strongest "it actually works" result in the literature, and it's often cited as evidence that LLM feedback is a credible complement to human review.

However, that paper's conclusions are explicitly contested by two others that used the same construct (LLM vs. human review quality) and found the opposite:

- "LLMs Assist NLP Researchers: Critique Paper (Meta-)Reviewing" ran a sentence-level analysis and found LLM-generated reviews contain more deficient segments than human reviews, tend to be generic/paper-unspecific rather than tailored to the actual manuscript, and lack the diversity and constructive specificity of human comments (LLM reviews were also far more similar to each other than human reviews were to each other — around 70 BERTScore similarity between LLM reviews vs. ~59 between human reviews), meaning the model tends to produce similar boilerplate-ish commentary regardless of the paper.

- "Are We There Yet? Revealing the Risks of Utilizing Large Language Models in Scholarly Peer Review" (Ye et al., 2024) is the sharpest cautionary paper. It documents several concrete failure modes: LLM reviewers rate title-only "papers" (no actual content) as good or better than the full paper, indicating they're partly hallucinating an assessment rather than reading closely; LLMs show prestige bias, giving more favorable reviews when the (visible) author is well-known; LLMs are 4.5x more likely than human reviewers to simply parrot back limitations that authors pre-emptively disclose in their own text, meaning a student (or you) could game the feedback by strategically mentioning minor weaknesses to suppress deeper critique; and, most strikingly, they showed that invisible text hidden in a PDF (white-on-white font, invisible to a human reader but parsed by the LLM) can almost completely hijack the review — raising agreement with the injected instructions to ~90% and dropping alignment with genuine human judgment from 53% to 16%. This is a manipulation/robustness finding rather than a quality finding per se, but it means LLM feedback pipelines are not adversarially robust, which matters if drafts pass through any external editing tools or if you want the feedback signal to be trustworthy.

On the more constructive side, purpose-built systems have tried to fix the "generic feedback" problem specifically. SWIF2T ("Automated Focused Feedback Generation for Scientific Writing Assistance," Chamoun, Schlichtkrull & Vlachos, 2024) targets exactly the weakness the critique paper identifies: rather than a single holistic review, it uses a four-stage pipeline (planner, investigator, reviewer, controller) to generate specific, actionable feedback tied to individual paragraphs, and in their own evaluation it outperformed vanilla GPT-4 prompting on specificity, evidence of actually reading the text, and overall helpfulness — in some cases judged superior to human-written peer review comments on the same excerpts. Separately, "Can LLMs Identify Critical Limitations within Scientific Research?" (LimitGen benchmark) tested LLMs specifically on spotting weaknesses/limitations in AI papers and found that plain LLMs struggle to identify real, non-generic limitations, but that retrieval-augmented approaches (grounding the critique in related prior literature rather than the model's own knowledge) meaningfully improve the concreteness and correctness of the feedback.

Bottom line for your use case: expect LLM feedback to be useful at the level of "does this draft have the recognizable shape of good scientific/academic writing, and what are some plausible weaknesses" — it correlates with human reviewer judgments about as well as two humans correlate with each other, and users in the direct study rated it as genuinely helpful. But you should not treat it as a substitute for careful individualized review: independent work shows LLM feedback skews generic/repetitive across different drafts, can be gamed by what students choose to disclose, is somewhat swayed by superficial cues, and (for GPT-4-style prompting without extra scaffolding) is measurably worse than human review at the sentence level. If you build or adopt a tool, one you should look for is a system that grounds comments in specific passages (like SWIF2T's paragraph-level approach) or in retrieved external literature, rather than one that produces a single holistic verdict — the evidence suggests that structural choice is what separates "genuinely useful" from "generic-sounding" LLM feedback.

**Papers named (6):** Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis; LLMs Assist NLP Researchers: Critique Paper (Meta-)Reviewing; Are We There Yet? Revealing the Risks of Utilizing Large Language Models in Scholarly Peer Review; Automated Focused Feedback Generation for Scientific Writing Assistance; Can LLMs Identify Critical Limitations within Scientific Research? A Systematic Evaluation on AI Research Papers; GPT4 is Slightly Helpful for Peer-Review Assistance: A Pilot Study  
**Stated confidence:** medium  
**Stated limits:** All of this evidence comes from studies of LLM feedback on research-paper/scientific manuscripts (often in ML/NLP venues), not from studies specifically on undergraduate or K-12 student writing, so I can't confirm the findings transfer directly to a classroom setting with less polished drafts or different rubrics.  
**Effort:** 9 exploration calls, 32,559 payload chars, 186,579 context, 43.2s, $0.225
  
**Graph tools used:** `paper_neighbourhood`×4, `topic_structure`×2, `search_contributions`×1, `edge_reasons`×1, `get_contribution`×1
  
**Call trace:** topic_structure(3,469ch) → search_contributions(4,850ch) → topic_structure(4,597ch) → paper_neighbourhood(3,578ch) → paper_neighbourhood(3,310ch) → paper_neighbourhood(4,848ch) → paper_neighbourhood(3,470ch) → edge_reasons(3,540ch) → get_contribution(897ch)

> *Judge:* Names real, specific papers (Liang et al., ReviewCritique/Du et al., Ye et al., SWIF2T by Chamoun/Schlichtkrull/Vlachos, LimitGen) with accurate mechanisms and numbers, sets up a genuine agreement/disagreement structure, and honestly flags that all of it is peer-review rather than classroom evidence.

### WEB (search)

**7.0** grounded · **7.666666666666667** correct · **8.0** useful · flags: unrecognised

Short answer: it works reasonably well as a *supplement*, especially for lower-order issues (grammar, structure, argument presence/absence) and for giving students a fast first pass, but there is real, published evidence that it falls short of expert human feedback on the things that matter most for research-level writing — depth of methodological critique, catching what's actually missing versus present, and avoiding generic or fabricated points. Nobody has shown it's a safe drop-in replacement for an instructor or expert reviewer; the consistent finding is "useful complement, not substitute."

The most directly relevant large-scale evidence is "Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis" (Liang, Zhang et al.), which ran GPT-4 over 4,000+ papers from Nature-family journals and ICLR and surveyed 308 researchers. Results were genuinely encouraging on the surface: 57.4% of users rated GPT-4's feedback helpful or very helpful, and 82.4% said it was more useful than feedback from at least some human reviewers they'd received. The overlap between the points GPT-4 raised and the points human reviewers raised (~31% for Nature papers, ~39% for ICLR) was comparable to the overlap you typically see between two human reviewers of the same paper — meaning GPT-4 isn't just noise, it's flagging real, reviewer-relevant issues. But the same study is explicit about the limitation you're asking about: GPT-4 systematically clusters around certain surface-level categories (clarity, presentation, some methodological gaps) and "struggles to provide in-depth critique of method design" — exactly the kind of substantive critique a paper draft most needs. The authors' own conclusion is that human expert review should remain the foundation, with LLM feedback most valuable early, before formal peer review, when timely expert feedback isn't otherwise available.

On the writing/pedagogy side rather than the peer-review side, "ChatGPT's capabilities in providing feedback on undergraduate students' argumentation: A case study" found that human raters outperformed ChatGPT on four of five evaluated criteria, with only "criterion alignment" (does the feedback address the stated rubric criterion) reaching comparable performance — agreement with human judgment was described as very high overall but broke down for a nontrivial subset of feedback categories (roughly 8 of 45 in that analysis), where the model was either overly generic or diverged from what a human rater would say.

The clearest negative/cautionary findings come from work specifically on hallucination and over-reliance in this exact use case. Several recent studies (including work compiled under systematic reviews of generative-AI feedback in writing instruction, and studies on AI-mediated feedback in composition courses) document concrete failure modes: the model asserting a required element was "missing" when it was actually present, or claiming clear paragraph structure existed when it didn't — genuine hallucinations, not just vague advice. These same studies report that LLM feedback tends to default to formulaic, generic suggestions unless prompts/rubrics are tightly specified, and that it disproportionately flags grammar/syntax over higher-order concerns (argument quality, disciplinary reasoning) — the opposite of what you'd want for a serious paper draft. There's also a documented behavioral risk: studies on classroom deployment report that when students over-rely on the AI feedback and don't critically evaluate it, revision quality and learning outcomes can actually decline; gains only showed up when students calibrated and regulated their use of the feedback rather than applying it uncritically.

On the positive side for classroom use specifically, a study using an evidence-based feedback system ("Using LLMs to bring evidence-based feedback into the classroom") found AI-generated feedback increased secondary students' revision behavior, motivation, and positive emotions relative to no feedback — so it does move the needle on engagement and willingness to revise, separate from the question of critique depth. A broader meta-analysis of automated writing feedback tools (not LLM-specific, covering the class of tools this literature sits within) found a medium-sized positive effect on student writing performance across studies, which is consistent with "helpful, moderate, not transformative."

Net assessment: the evidence base (a large empirical study on research-paper feedback, a controlled comparison against human raters on argumentation feedback, classroom intervention studies, and a meta-analysis) converges on the same picture — LLM feedback catches a real and useful subset of issues, comparable in overlap to what a second human reviewer would flag, and it increases student engagement with revision. But it reliably underperforms trained humans on deep methodological or higher-order critique, produces documented hallucinations (claiming absent things are present or vice versa), skews toward generic and surface-level comments unless carefully prompted, and carries a real risk of over-reliance if students apply its suggestions without critical evaluation. The published recommendation across this literature is consistently to use it as a first-pass or supplementary layer alongside instructor feedback, not as a replacement for it.

**Papers named (5):** Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis; ChatGPT's capabilities in providing feedback on undergraduate students' argumentation: A case study; Using LLMs to bring evidence-based feedback into the classroom: AI-generated feedback increases secondary students' text revision, motivation, and positive emotions; Automated feedback and writing: a multi-level meta-analysis of effects on students' performance; LLM feedback for academic writing: Effects on students' performance and engagement  
**Stated confidence:** medium  
**Stated limits:** I could not establish results specific to graduate-level or disciplinary research-paper drafts (as opposed to undergraduate essays/argumentation or full manuscript peer review) as a distinct category, so evidence for the exact middle ground of 'student paper drafts' in a research-methods sense is inferred by combining the peer-review study and the classroom-writing studies rather than drawn from one single paper that studies exactly that population.  
**Effort:** 6 exploration calls, 14,021 payload chars, 125,733 context, 62.0s, $0.247

> *Judge:* Best domain fit for the actual question — accurate Liang et al. statistics (57.4%, 82.4%, ~31%/39% overlap, "struggles to provide in-depth critique of method design") plus real classroom work (Meyer et al. on revision/motivation) — but one paragraph collapses into unnamed "several recent studies", and the 4-of-5-criteria result it credits to the argumentation case study is the signature finding of Steiss et al., which it never cites.

### NULL (closed book)

**5.666666666666667** grounded · **3.6666666666666665** correct · **5.333333333333333** useful · flags: fabricated

Short answer: it works better than nothing and can genuinely catch real issues, but the evidence so far is that LLM feedback on drafts is systematically weaker than good human feedback in specific, predictable ways — it tends to be generic, overly positive, and worse at higher-order concerns (argument quality, idea development, novelty) than at surface-level issues (grammar, structure, clarity). There is also a documented failure mode where the feedback can be manipulated outright.

Two pieces of work are the ones I'd point you to directly:

1. Liang, Zhang, Cao et al., "Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis" (Stanford, on GPT-4 reviewing scientific manuscripts, not student essays specifically, but the closest large-scale empirical study of this exact question). They compared GPT-4-generated review comments against actual human reviewer comments on a large set of papers and found substantial overlap — a majority of the points GPT-4 raised matched points human reviewers also raised, and in a user study most researchers who received GPT-4 feedback on their own drafts said they found at least some of it useful, especially early in the writing process. But they also found real weaknesses: the feedback was often generic and templated (similar boilerplate phrasing recurring across very different papers), it was noticeably weaker than human reviewers at judging novelty and technical soundness, and — the finding people cite most — the review could be hijacked: hidden text embedded in a manuscript (invisible to a human reader but readable by the model) could steer GPT-4 into producing an entirely positive review regardless of the paper's actual quality. That's a direct demonstration that the feedback mechanism doesn't reason robustly about content; it can be gamed.

2. Steiss, Tate, Graham et al., "Comparing the Quality of Human and ChatGPT Feedback on Students' Writing" (published in Learning and Instruction, using actual student essays and comparing ChatGPT feedback against expert human/writing-instructor feedback). Their finding was that ChatGPT feedback was rated by expert judges as generally lower quality than human feedback overall, and the gap was concentrated in higher-order issues — things like developing ideas, strengthening argumentation, and addressing the writer's actual claims — where ChatGPT tended to give shallower, more generic comments. ChatGPT feedback also skewed more positive/complimentary and less pointedly critical than human feedback, and did comparatively better on lower-order concerns (grammar, organization, mechanics) where its performance was closer to or on par with humans.

Taken together, these two are basically consistent with each other despite covering different domains (research-paper review vs. student writing): LLM feedback captures a real and useful chunk of what human reviewers/instructors would say, particularly for surface- and structure-level issues and as a supplement or first pass, but it under-delivers on the things that arguably matter most for developing a student's argument or claims, it defaults toward praise rather than critique, and it can be manipulated or produce boilerplate that looks substantive without being tailored to the actual draft. So "does it work" — yes, partially and usefully, but "has anyone found it doesn't work" — also yes, specifically on the higher-order judgment and manipulability fronts, in both of the studies above.

One practical implication that follows from both papers: if you use an LLM for draft feedback, it's more trustworthy for line-level and structural feedback than for judging the strength or novelty of an argument, and you should not assume the feedback is immune to being steered by what's already in the draft (e.g., a student inserting reassuring framing) versus what's actually good.

**Papers named (2):** Can Large Language Models Provide Useful Feedback on Research Papers? A Large-Scale Empirical Analysis; Comparing the Quality of Human and ChatGPT Feedback on Students' Writing  
**Stated confidence:** medium  
**Stated limits:** I could not confirm the exact authorship, venue, and statistics of the Steiss et al. paper down to precise figures, and I don't have comprehensive coverage of the broader education-technology literature on LLM feedback for student writing beyond these two studies, so there may be additional relevant findings (positive or negative) that I'm not aware of.  
**Effort:** 0 exploration calls, 0 payload chars, 30,136 context, 42.9s, $0.232

> *Judge:* Picks the two most apt papers and frames the higher-order/lower-order split well, but misattributes the hidden-text prompt-injection "hijacked review" finding to Liang et al. (that is Ye et al., "Are We There Yet?"), and its gloss of Steiss et al. on tone (ChatGPT "more complimentary") runs against that paper's supportive-tone result.

**Fabrication notes:** Answer A credits the covert hidden-text review-hijacking experiment to Liang et al.'s "Can LLMs Provide Useful Feedback on Research Papers?" — that paper contains no such prompt-injection study; the finding belongs to Ye et al., "Are We There Yet?", which Answer B correctly attributes. A's claim that ChatGPT feedback was more complimentary than human feedback also sits awkwardly with Steiss et al., where humans scored higher on supportive tone. Possible (uncertain, so not flagged) attribution slip in C: the "humans better on 4 of 5 criteria, comparable only on criterion alignment" result is Steiss et al.'s headline finding.

*Judged in 74.5s for $0.212.*


---

## q06 — lineage

> I'm considering using AIDE as the coding backbone for a research agent. Where did it come from, and who has already built on top of it?

**Expected winner:** `graph`  
**Judged best:** `web` (clear margin) — **PREDICTION MISS**  
**Ranking:** web>graph>null  
**Presentation order:** null / web / graph

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

8 builds_on edges into AIDE (incl. The AI Scientist-v2 via uses_extends, 2 sites); multi-hop traversal in both directions.

</details>

### GRAPH (Prior atlas)

**8.0** grounded · **5.0** correct · **7.333333333333333** useful · flags: fabricated, unrecognised

AIDE ("AIDE: AI-Driven Exploration in the Space of Code," Jiang, Schmidt, Srikanth, Xu, Kaplan & Jacenko, 2025) is an LLM-driven agent for automated machine learning engineering. It frames ML engineering as a code-optimization problem and runs a tree search over candidate Python solutions: each node is a standalone executable script, edges represent improvement attempts, and a fixed policy chooses among "draft," "debug," and "improve" operators guided by automated evaluation scores. The authors introduced their own evaluation suite (the Weco Kaggle Benchmark) and also validated AIDE by reproducing METR's RE-Bench results, where AIDE's tree search matched or beat time-constrained human-expert performance on tasks such as Triton kernel optimization; it also reportedly earned roughly twice the medals of the next-best agent on MLE-Bench with GPT-4o. So its lineage is essentially self-contained methodologically, drawing on RE-Bench purely as an evaluation harness rather than as a technical ancestor.

A number of later systems explicitly build on AIDE's tree-search formulation:

- The AI Scientist-v2 ("Workshop-Level Automated Scientific Discovery via Agentic Tree Search") adopts AIDE's node-as-solution / scalar-score tree search directly, embedding it inside a dedicated experiment-manager agent as part of a broader end-to-end pipeline that also handles hypothesis generation, VLM-based figure refinement, and manuscript writing.
- The original "Towards end-to-end automation of AI research" (The AI Scientist) likewise uses AIDE-style agentic tree search for its template-free, open-ended experiment-execution mode.
- MLEvolve ("A Self-Evolving Framework for Automated Machine Learning Algorithm Discovery") builds on AIDE most substantively as a critique-and-extend: it explicitly names AIDE's tree search as suffering from "branch information isolation" and a fixed, hard-coded exploration policy, and replaces the tree with a Progressive Monte Carlo Graph Search that lets branches share information, adds retrospective memory, decouples strategic planning from code generation, and supports adaptive full-rewrite/stepwise/diff-based editing modes.
- AIRA-2 ("Overcoming Bottlenecks in AI Research Agents") treats AIDE as its principal baseline and target for improvement, reporting a mean percentile rank of 81.5–83.1% on MLE-bench-30 versus 72.7% for the strongest prior baseline (AIDE-class agents). Its contributions — asynchronous multi-GPU execution to decouple LLM reasoning from experiment execution, "Hidden Consistent Evaluation" to stop validation/test signal leakage over long search horizons, and replacing AIDE's single-turn operators with autonomous ReAct-based debugging/EDA operators — are all framed as fixes to bottlenecks observed in AIDE-style agents.
- "Why LLMs Aren't Scientists Yet: Lessons from Four Autonomous Research Attempts" discusses and draws on AIDE as one of the reference autonomous-research systems when deriving its six recurring failure modes and design principles for more robust AI-scientist pipelines.
- MLRC-Bench and AutoScientists both use AIDE as a comparison point/baseline in their evaluation of ML research agents rather than extending its method.

In short: AIDE originated as a benchmarked, tree-search coding agent for ML engineering, validated against METR's RE-Bench and a bespoke Kaggle benchmark. It has since become a standard baseline and architectural starting point in the automated-AI-research-agent literature — most directly extended by MLEvolve (graph search replacing tree search) and AIRA-2 (system-level bottleneck fixes: parallelism, evaluation-noise control, richer operators), and incorporated as a component inside larger scientific-discovery pipelines (The AI Scientist and The AI Scientist-v2).

**Papers named (9):** AIDE: AI-Driven Exploration in the Space of Code; RE-Bench: Evaluating frontier AI R&D capabilities of language model agents against human experts; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Towards end-to-end automation of AI research; MLEvolve: A Self-Evolving Framework for Automated Machine Learning Algorithm Discovery; AIRA_2: Overcoming Bottlenecks in AI Research Agents; Why LLMs Aren't Scientists Yet: Lessons from Four Autonomous Research Attempts; MLRC-Bench: Can Language Agents Solve Machine Learning Research Challenges?; AutoScientists: Self-Organizing Agent Teams for Long-Running Scientific Experimentation  
**Stated confidence:** high  
**Stated limits:** I can establish AIDE's origin and its documented influence within the automated-ML-research-agent literature covered here, but cannot confirm whether even more recent (post-2026) systems outside this material have adopted it, nor its uptake outside research-agent contexts.  
**Effort:** 5 exploration calls, 20,563 payload chars, 169,950 context, 52.6s, $0.227
  
**Graph tools used:** `paper_neighbourhood`×3, `find_paper`×1, `edge_reasons`×1
  
**Call trace:** find_paper(284ch) → paper_neighbourhood(4,099ch) → edge_reasons(8,007ch) → paper_neighbourhood(3,555ch) → paper_neighbourhood(4,618ch)

> *Judge:* The richest and most operationally useful map (correct author list, Weco Kaggle benchmark, RE-Bench Triton-kernel validation, and a precise MLEvolve/AIRA critique of AIDE's branch-isolation and fixed policy), but it asserts with "high" confidence that the original AI Scientist uses AIDE-style tree search in a template-free mode — v1 used Aider plus fixed templates, and template-free tree search is precisely what v2 introduced.

### WEB (search)

**8.333333333333334** grounded · **8.333333333333334** correct · **8.333333333333334** useful · flags: unrecognised

AIDE (AI-Driven Exploration in the Space of Code) comes from the paper "AIDE: AI-Driven Exploration in the Space of Code" (Jiang et al., Weco AI, arXiv:2502.13138, Feb 2025), with an open-source reference implementation released as the "aideml" package by WecoAI. The core idea is to frame machine-learning engineering (writing, running, debugging and improving a solution script against a metric) as a code-optimization problem solved by greedy best-first tree search: the agent drafts an initial solution, executes it, reads back the error trace or validation score, and then branches into "improve", "debug", or "draft" children of that node, iterating until a budget is exhausted. It was evaluated on Kaggle competitions (beating roughly half of human competitors on average) and quickly became a standard reference agent in ML-engineering benchmarks — most notably it is the strongest scaffold reported in OpenAI's MLE-bench (o1-preview + AIDE), where its tree search wins about four times as many medals as the best purely linear coding agent (OpenHands), and it is also used as a baseline in METR's RE-Bench.

Because of that strong, reproducible baseline status, several later systems explicitly build on or extend AIDE's tree-search formulation rather than starting from scratch:

- AutoMind ("AutoMind: Adaptive Knowledgeable Agent for Automated Data Science") takes AIDE as its starting point and augments it with an expert knowledge base (mined from hundreds of Kaggle solutions and papers) plus an adaptive coding strategy, reporting a sizeable improvement over AIDE on MLE-bench with much lower token cost and runtime.
- AutoMLGen ("AutoMLGen: Navigating Fine-Grained Optimization for Coding Agents") explicitly extends AIDE's single-path tree search into a graph-based search with finer-grained edit operators and asynchronous, branch-parallel exploration (drawing also on ideas from R&D-Agent-style Monte Carlo graph search).
- Sakana AI's "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search" replaces the human-authored code templates of the original AI Scientist with a progressive agentic tree-search experiment manager that is built directly on top of the AIDE project's tree-search code, citing AIDE as the basis for that component.
- A number of newer ML-engineering benchmark papers (e.g., FML-bench, ML-Dev-Bench) treat AIDE as the reference/state-of-the-art baseline agent against which new agents and search strategies are compared, rather than extending its code, which is a weaker but still telling sign of its status as the de facto backbone for this class of coding agent.

So: if you adopt AIDE as your backbone, you'd be building on the Weco AI tree-search formulation that is already the standard baseline in MLE-bench and RE-Bench, and you'd be following a path already taken by AutoMind and AutoMLGen (direct algorithmic extensions) and by Sakana's AI Scientist-v2 (reusing its tree-search engine inside a larger end-to-end research-automation system).

**Papers named (6):** AIDE: AI-Driven Exploration in the Space of Code; MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering; AutoMind: Adaptive Knowledgeable Agent for Automated Data Science; AutoMLGen: Navigating Fine-Grained Optimization for Coding Agents; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; FML-bench: Benchmarking Machine Learning Agents for Scientific Research  
**Stated confidence:** medium  
**Stated limits:** I could confirm AIDE's origin and its use as a baseline/foundation in MLE-bench, RE-Bench, AutoMind, AutoMLGen, and AI Scientist-v2 with good source support, but I could not exhaustively verify every system that has adopted AIDE as a backbone (e.g., internal or industry deployments), nor confirm fine-grained version differences between the arXiv paper's algorithm and the current aideml codebase.  
**Effort:** 6 exploration calls, 16,442 payload chars, 244,152 context, 99.7s, $0.430

> *Judge:* Accurate provenance (arXiv 2502.13138, aideml, draft/debug/improve greedy tree search, ~51% of Kaggle humans, 4x medals over OpenHands in MLE-bench) plus a clean, checkable split between direct algorithmic extensions (AutoMind, AutoMLGen), component reuse (AI Scientist-v2) and mere baseline use (FML-bench, ML-Dev-Bench); nothing here contradicts what I know.

### NULL (closed book)

**5.666666666666667** grounded · **8.0** correct · **5.0** useful · flags: hedged

AIDE ("AI-Driven Exploration in the Space of Code") is an open-source ML-engineering agent released by Weco AI. It frames data-science/ML-engineering tasks (of the kind found in Kaggle competitions) as a code-generation search problem: the agent maintains a tree of candidate solution scripts, uses an LLM to propose edits/mutations, executes them, and uses the resulting validation score to decide which branch to expand next (essentially a greedy/best-first tree search over code, sometimes described as "evolutionary" in the accompanying write-up). The original description of the method is the Weco AI technical report/paper on AIDE (authored by the Weco AI team, including Zhengyao Jiang and Dominik Schmidt among the credited contributors), which reported the approach achieving strong, human-comparable results on a set of Kaggle-style benchmarks.

Since its release, AIDE has mainly been adopted as a reference agent/backbone in evaluation benchmarks for autonomous ML-engineering and AI R&D capability, rather than being extended into a large family of derivative research papers:

- MLE-bench (from OpenAI), which evaluates language-model agents on real Kaggle machine-learning engineering competitions, uses AIDE as one of its baseline agent scaffolds — it is the main open-source scaffold they wrap different backbone LLMs into to measure end-to-end ML-engineering competence.
- METR's evaluations of frontier-model R&D/agentic capability (their RE-Bench-style work on measuring AI R&D capabilities) likewise use AIDE as a baseline scaffold to compare model performance (and model+scaffold performance) against human ML-engineer baselines on time-boxed research-engineering tasks.

In both cases AIDE is being used the way you're describing — as a ready-made "coding backbone" that supplies the search/execution loop, into which different underlying LLMs are plugged and then evaluated on ML-engineering benchmarks. I'm not aware of a broader ecosystem of papers that fundamentally modify AIDE's search algorithm itself (as opposed to using it unmodified as an evaluation harness); if such follow-on work exists, I could not confirm it.

**Papers named (2):** AIDE: AI-Driven Exploration in the Space of Code; MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering  
**Stated confidence:** medium  
**Stated limits:** I can confirm AIDE's origin (Weco AI) and its use as a baseline scaffold in MLE-bench and in METR's AI R&D capability evaluations, but I could not verify exact author lists, publication venue/date details, or whether any papers have substantively modified AIDE's underlying search algorithm rather than just using it as an off-the-shelf harness.  
**Effort:** 0 exploration calls, 0 payload chars, 111,033 context, 53.6s, $0.166

> *Judge:* Correct and appropriately hedged on AIDE's origin (Weco AI, Jiang/Schmidt, tree search over code) and its use as a scaffold in MLE-bench and METR's RE-Bench, but it answers only half the question and wrongly implies there is essentially no derivative-paper ecosystem, when AutoMind, AIRA/AIRA-dojo, AI Scientist-v2 and others clearly qualify.

**Fabrication notes:** Answer C claims the original AI Scientist ("Towards end-to-end automation of AI research") uses AIDE-style agentic tree search for a template-free experiment mode; the AI Scientist v1 (Lu et al., 2024) used Aider-based editing over human-written templates, and removing templates via agentic tree search was the headline change in v2 — this looks like an Aider/AIDE confusion, and the title given is also not v1's actual title.

*Judged in 73.7s for $0.194.*


---

## c01 — control-out-of-scope

> What recent work builds on AlphaFold for de-novo protein binder design?

**Expected winner:** `web`  
**Judged best:** `web` (slight margin) — prediction hit  
**Ranking:** web>null>graph  
**Presentation order:** graph / web / null

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

NOTHING. Structural biology is entirely outside the 152-paper corpus (verified: no paper matching 'AlphaFold' or 'protein'). Tests coverage honesty - does the graph arm say so, or invent?

</details>

### GRAPH (Prior atlas)

**2.6666666666666665** grounded · **7.666666666666667** correct · **2.6666666666666665** useful · flags: unrecognised, hedged

I was not able to find coverage of this topic in the material available to me. The literature I can draw on is centered on AI-agent and LLM-driven scientific discovery systems — autonomous research agents, hypothesis generation pipelines, and biomedical ML benchmarks (e.g., LAB-Bench, BioML-bench, CRISPR-GPT, AutoScientists, GALILEO) — not on structural biology or protein design methodology. It contains no treatment of AlphaFold itself, nor of the line of work that actually builds on it for de-novo binder design (e.g., RFdiffusion, ProteinMPNN, AlphaProteo, BindCraft, or similar hallucination/diffusion-based binder design pipelines).

The nearest adjacent material concerns binding-affinity prediction rather than structural binder design: one paper extends a protein fitness model (Kermut) to improve ACE2–spike binding-affinity prediction and generalizes the approach across the ProteinGym benchmark suite, and another (GALILEO) describes a closed-loop, living-system-feedback approach to peptide/membrane-protein blocker discovery. Neither of these is a de-novo structural binder-design method built on AlphaFold, and I have no basis to characterize the actual current state of AlphaFold-based binder design work — i.e., how RFdiffusion, BindCraft, AlphaProteo, or related 2023–2025 methods relate to or extend AlphaFold's structure-prediction machinery.

I'd recommend treating this as outside what I can speak to with evidence here, and consulting the structural-biology/protein-design literature directly (e.g., recent reviews of AlphaFold-based binder design pipelines) rather than relying on a guess from me.

**Papers named (2):** AutoScientists: Self-Organizing Agent Teams for Long-Running Scientific Experimentation; GALILEO: Embodied AI scientist for autonomous therapeutic discovery in dynamic membrane systems  
**Stated confidence:** low  
**Stated limits:** I could not establish anything substantive about actual recent AlphaFold-based de-novo protein binder design work (e.g., RFdiffusion, BindCraft, AlphaProteo) since this topic area is not covered in the material I had access to.  
**Effort:** 5 exploration calls, 13,162 payload chars, 130,141 context, 30.4s, $0.144
  
**Graph tools used:** `find_paper`×2, `search_contributions`×2, `topic_structure`×1
  
**Call trace:** topic_structure(3,427ch) → find_paper(32ch) → search_contributions(4,898ch) → search_contributions(4,773ch) → find_paper(32ch)

> *Judge:* An honest, accurate declination that correctly identifies the relevant method names (RFdiffusion, BindCraft, AlphaProteo, ProteinMPNN) as outside its corpus, but delivers essentially no substantive answer.

### WEB (search)

**8.0** grounded · **7.666666666666667** correct · **9.0** useful · flags: unrecognised

The dominant recent strategy for turning AlphaFold from a structure predictor into a de novo protein binder design tool is "hallucination": backpropagating through the frozen AlphaFold (or AlphaFold-Multimer) network to optimize an input sequence so that AlphaFold itself predicts a high-confidence, high-contact interface with a chosen target, then keeping only sequences AlphaFold is highly confident fold and bind correctly. Several concrete recent papers extend this idea:

- ColabDesign / AfDesign (from Sergey Ovchinnikov's lab) was the original implementation that repurposed AlphaFold2-Multimer's differentiable structure module for design rather than prediction, minimizing predicted alignment error and maximizing interface contacts and binder confidence to hallucinate a binder sequence for a fixed target. This is the base machinery most later work extends.

- BindCraft ("One-shot design of functional protein binders with BindCraft," Nature, 2025) is the most prominent recent advance: a fully automated, open-source pipeline that runs AlphaFold2-Multimer-based hallucination end-to-end, reporting experimental success rates of 10–100% across diverse targets and nanomolar-affinity binders obtained without high-throughput screening. It is built directly on AlphaFold2's trained weights rather than a separately trained generative model.

- "Fold-Conditioned De Novo Binder Design via AlphaFold2-Multimer Hallucination" (2025 preprint, introducing a method called FoldCraft) extends the same hallucination framework by adding a contact-map similarity loss so binders can be generated to match a user-specified fold, reporting higher structural and binding confidence than RFdiffusion-based designs on some targets.

- AlphaDesign ("AlphaDesign: a de novo protein design framework based on AlphaFold," Molecular Systems Biology, 2025) is a more general de novo design framework built directly on the AlphaFold architecture, extending its use beyond structure prediction into full protein design.

- AlphaProteo (Google DeepMind, 2024) is a generative model for de novo protein binder design in the same lineage — it uses AlphaFold-derived structural confidence metrics and training data to design binders to specified epitopes, reporting improved binding affinities and success rates over prior physics-based (Rosetta) and RFdiffusion-based approaches on several benchmark targets.

- RFdiffusion ("De novo design of protein structure and function with RFdiffusion," Nature, 2023) is technically built on RoseTTAFold rather than AlphaFold, but is tightly coupled to AlphaFold in practice: the standard pipeline generates a scaffold with RFdiffusion, assigns a sequence with ProteinMPNN, and filters designs using AlphaFold2 structure prediction to check the designed sequence folds and binds as intended. It is the incumbent method that BindCraft and FoldCraft explicitly benchmark against.

- BoltzDesign is a newer entrant generalizing the hallucination idea beyond AlphaFold2 itself, performing inversion of Boltz-1 (an open-source model in the AlphaFold3 lineage) rather than AlphaFold2-Multimer, and is reported to exceed RFdiffusion-AA on computational designability metrics across a broader range of target types (including nucleic acids and small molecules) — suggesting the field is moving from AlphaFold2-specific hallucination toward inversion of AlphaFold3-style all-atom models.

In short: ColabDesign/AfDesign established the core hallucination technique; BindCraft and FoldCraft are direct, more automated, higher-success-rate descendants; AlphaDesign and AlphaProteo build broader generative frameworks around AlphaFold's confidence signals; RFdiffusion is the leading non-AlphaFold generative backbone method that nonetheless depends on AlphaFold2 for validation; and BoltzDesign extends the inversion logic to AlphaFold3-class models.

**Papers named (7):** One-shot design of functional protein binders with BindCraft; Fold-Conditioned De Novo Binder Design via AlphaFold2-Multimer Hallucination; AlphaDesign: a de novo protein design framework based on AlphaFold; De novo design of protein structure and function with RFdiffusion; AlphaProteo; BoltzDesign; ColabDesign / AfDesign  
**Stated confidence:** medium  
**Stated limits:** I could not independently verify quantitative claims (e.g., exact success-rate figures, head-to-head benchmark numbers between BindCraft/FoldCraft/BoltzDesign/RFdiffusion) beyond what secondary summaries reported, nor confirm the precise publication venue/status of some of the newer preprints (e.g., BoltzDesign, FoldCraft) at this time.  
**Effort:** 2 exploration calls, 6,433 payload chars, 106,099 context, 56.9s, $0.508

> *Judge:* Broad, current and largely accurate map of the hallucination lineage — ColabDesign/AfDesign → BindCraft (Nature 2025, 10–100% success rates, correct) → AlphaDesign (Jendrusch et al.), AlphaProteo, RFdiffusion-as-non-AlphaFold-incumbent, and BoltzDesign as AF3-class inversion — with an appropriate caveat on unverified numbers; it omits the Bennett et al. AF2 initial-guess filter, which is the key AlphaFold link for the Baker-lab pipeline.

### NULL (closed book)

**8.0** grounded · **8.333333333333334** correct · **8.0** useful · flags: —

There are two distinct ways "building on AlphaFold" shows up in de novo protein binder design, and it's worth separating them because they represent different technical relationships.

1. AlphaFold used as an internal oracle for "hallucination"-style design. Before diffusion-based generators existed, a dominant approach to binder design was to backpropagate through AlphaFold2's structure-prediction network to optimize an input sequence toward a target confidence/contact objective — essentially using AlphaFold as a differentiable design tool rather than just a predictor. This line traces to Sergey Ovchinnikov's AfDesign/ColabDesign framework, which repurposed AlphaFold2 for sequence hallucination and binder generation. The most complete and widely cited recent instantiation of this idea is BindCraft (Pacesa, Nikolaidis, Schellhaas et al., "BindCraft: one-shot design of functional protein binders," 2024), an open-source pipeline that runs an AlphaFold2-hallucination loop (gradient-based sequence optimization against AlphaFold2's structure module, using an initial-guess/recycling trick) to generate binders in a single shot, followed by physics-based refinement. BindCraft reports high experimental success rates across diverse targets and is explicitly framed as an AlphaFold2-native design method, distinct from diffusion generators.

2. AlphaFold used as a validation/filtering oracle within a diffusion-based generation pipeline. The dominant current binder-design paradigm comes from the Baker lab: RFdiffusion (Watson, Juergens, Bennett et al., "De novo design of protein structure and function with RFdiffusion," Nature 2023) generates candidate backbones by fine-tuning a diffusion model on RoseTTAFold (not AlphaFold) weights, and ProteinMPNN designs sequences for those backbones. The step that connects this pipeline to AlphaFold is Bennett et al., "Improving de novo protein binder design with deep learning" (Nature Communications, 2023), which showed that filtering RFdiffusion/ProteinMPNN-generated binders using an "AlphaFold2 initial-guess" metric — feeding the designed complex into AlphaFold2 with the target structure given as a starting template and checking whether AlphaFold2 confidently recapitulates the intended binding pose — dramatically improves experimental hit rates. This AlphaFold2-initial-guess filter has since become a near-standard quality-control step across binder design pipelines that use RFdiffusion/ProteinMPNN, even though the generative model itself is RoseTTAFold-derived rather than AlphaFold-derived.

3. A more direct architectural descendant is AlphaProteo (Zambaldi et al., "De novo design of high-affinity protein binders with AlphaProteo," DeepMind, 2024), which was built by DeepMind using AlphaFold's underlying modeling technology and training data to generate binder sequences/structures directly, reporting higher binding success rates and stronger affinities than earlier RFdiffusion-based binders on several benchmark targets in their own comparisons.

In short: RFdiffusion is architecturally a RoseTTAFold derivative that leans on AlphaFold2 only as an evaluation filter (via Bennett et al.'s initial-guess trick); BindCraft and the AfDesign/ColabDesign lineage use AlphaFold2 itself as the generative engine through hallucination; and AlphaProteo is DeepMind's own AlphaFold-technology-based generative binder designer, positioned as a direct competitor/successor to the RFdiffusion-based approach. All of these are recent (2023–2024) and represent the current state of the art in de novo binder design.

**Papers named (4):** De novo design of protein structure and function with RFdiffusion; Improving de novo protein binder design with deep learning; BindCraft: one-shot design of functional protein binders; De novo design of high-affinity protein binders with AlphaProteo  
**Stated confidence:** medium  
**Stated limits:** I can describe how these specific papers relate to AlphaFold and to each other based on established knowledge of the field, but I cannot verify exact publication venues/dates or any newer 2025 follow-ups that may have since superseded them, since I did not check for the very latest releases.  
**Effort:** 0 exploration calls, 0 payload chars, 119,676 context, 74.8s, $0.230

> *Judge:* Cleanest conceptual framing — separates AlphaFold-as-generator (AfDesign/BindCraft) from AlphaFold-as-filter, and correctly credits Bennett et al. (Nat Commun 2023) with the AF2 "initial guess" filter that others miss — but it stops at 2023–2024 and misses 2025 developments (BindCraft's Nature publication, Boltz-based inversion).

**Fabrication notes:** Minor and not flagged: C lists BindCraft authors as "Pacesa, Nikolaidis, Schellhaas" — Pacesa and Schellhaas are right, but the second author is, I believe, Lennart Nickel, so "Nikolaidis" looks like a slight garble; C also asserts these 2023–2024 works "represent the current state of the art", which is stale as of 2026 (though it flags not having checked newer work).

*Judged in 56.1s for $0.156.*


---

## c02 — control-full-text

> What score does the best agent get on PaperBench, on which subset, and how does it compare to the human PhD baseline?

**Expected winner:** `web`  
**Judged best:** `web` (clear margin) — prediction hit  
**Ranking:** web>graph>null  
**Presentation order:** graph / null / web

<details><summary>What the atlas actually holds (never shown to any arm)</summary>

PaperBench IS in the corpus (4 contributions + abstract) but the bundle holds no results tables. Tests depth honesty - the graph arm should identify the paper and decline on the numbers.

</details>

### GRAPH (Prior atlas)

**7.333333333333333** grounded · **8.333333333333334** correct · **6.666666666666667** useful · flags: —

On PaperBench (the benchmark introduced in "PaperBench: Evaluating AI's Ability to Replicate AI Research," which requires agents to replicate 20 ICML 2024 Spotlight/Oral papers from scratch against 8,316 author-approved graded sub-tasks), the best-performing tested agent — Claude 3.5 Sonnet (New) running with an open-source agent scaffold — achieved an average replication score of 21.0% on the full benchmark.

The authors also recruited top ML PhDs to attempt a matched subset of PaperBench (not the full 20-paper set) and measured a human baseline of 41.4% on that subset. So the best AI agent's score (21.0% on the full benchmark) is roughly half the human PhD baseline (41.4% on the comparable subset), and the paper's own conclusion is explicit: current frontier models do not yet outperform expert humans at this end-to-end research-replication task — there remains a substantial capability gap.

**Papers named (1):** PaperBench: Evaluating AI's Ability to Replicate AI Research  
**Stated confidence:** high  
**Stated limits:** I could not establish further detail on exactly which subset of papers/tasks the human PhD trial covered (e.g., how many of the 20 papers, or which sub-tasks) beyond it being described as a "matched subset" of the full benchmark.  
**Effort:** 2 exploration calls, 3,311 payload chars, 86,558 context, 14.6s, $0.072
  
**Graph tools used:** `find_paper`×1, `get_paper`×1
  
**Call trace:** find_paper(295ch) → get_paper(3,016ch)

> *Judge:* Correct on the two headline numbers (Claude 3.5 Sonnet New + open-source scaffold at 21.0% on the 20-paper set; 41.4% human PhD baseline on a subset) and honestly flags that it cannot pin down the subset, but it omits the matched agent score (o1 at 26.6%) that makes the human comparison apples-to-apples, and its "roughly half" framing mixes two different populations.

### WEB (search)

**8.333333333333334** grounded · **7.0** correct · **8.666666666666666** useful · flags: —

The relevant paper is "PaperBench: Evaluating AI's Ability to Replicate AI Research" (OpenAI, Starace et al., 2025). PaperBench asks AI agents to replicate 20 recent top-tier ML papers from scratch — reading the paper, writing the implementing code, running the experiments, and reproducing the empirical results — with performance graded against a fine-grained rubric co-developed with the original papers' authors.

On the full 20-paper benchmark, the best-performing agent was Claude 3.5 Sonnet (New) paired with an open-source agentic scaffold, which achieved an average replication score of 21.0%. OpenAI's own o1 model scored lower on the full set.

Because running the complete benchmark is extremely costly (each attempt can take many agent-hours), the authors also built a lighter three-paper subset called PaperBench Code-Dev, which only grades whether the code exists and runs correctly, skipping the full execution/reproduction of results. On this subset, o1 reached 43.4%.

For the human comparison, the authors recruited top machine-learning PhD holders — several of whom were authors of the original papers being replicated — and had them attempt the same three-paper subset with 48 hours of effort each (best-of-3 attempts). The human PhDs averaged 41.4% on that subset, compared to o1's 26.6% on the same (non-Code-Dev, full grading) three-paper subset. So under matched conditions and time budget, the best human experts roughly outperformed the best AI agents by a wide margin (41.4% vs. 26.6%), and the paper's headline conclusion is that current agents do not yet outperform human ML PhDs on this task, even though agents show fast early progress before plateauing.

In short: best agent overall = Claude 3.5 Sonnet (New) with custom scaffolding at 21.0% on the full 20-paper benchmark; on the matched 3-paper subset used for the human comparison, o1 scored 26.6% versus a 41.4% human PhD baseline (48-hour effort, best-of-3).

**Papers named (1):** PaperBench: Evaluating AI's Ability to Replicate AI Research  
**Stated confidence:** medium  
**Stated limits:** I could not independently verify every figure against the original paper's results tables (some numbers, e.g. the 26.6%/41.4% subset comparison, are drawn from secondary summaries rather than a direct read of the primary results section), so exact decimal precision should be double-checked against the paper itself before citing in a publication.  
**Effort:** 3 exploration calls, 5,507 payload chars, 87,656 context, 33.4s, $0.147

> *Judge:* The only answer that actually answers all three parts of the question with the right specifics (21.0% best agent on the full 20-paper set; 3-paper matched subset; o1 26.6% vs 41.4% human PhD baseline at 48h, best-of-3), correctly credits Starace et al., but mischaracterises PaperBench Code-Dev as a "three-paper subset" (it is a cheaper code-only grading variant, with o1 at 43.4%) and wrongly suggests some human participants were authors of the replicated papers.

### NULL (closed book)

**5.666666666666667** grounded · **5.666666666666667** correct · **5.333333333333333** useful · flags: —

The relevant paper is "PaperBench: Evaluating AI's Ability to Replicate AI Research" (OpenAI, Kirchner et al.). PaperBench asks agents to reproduce 20 ICML 2024 papers from scratch (re-implementing the methods and reproducing the empirical results), with performance measured via fine-grained, paper-specific rubrics that break each replication into thousands of gradable sub-tasks, averaged into an overall replication score.

On the full 20-paper benchmark, the best-performing agent was Claude 3.5 Sonnet (New) run with a custom open-source scaffold built for the benchmark, which achieved an average replication score of about 21% - the highest of the models/agents tested (which also included o1, GPT-4o, and Gemini variants, all scoring lower).

The paper also ran a direct comparison against human ML PhDs on a smaller matched subset of the papers, giving both humans and agents a fixed time budget (up to 48 hours) to replicate the same papers. The headline result is that AI agents were competitive with, or even ahead of, human PhDs early in the time budget (within the first several hours), but human performance kept improving over the full 48 hours while agent performance plateaued much sooner. By the 48-hour mark, the human PhD baseline reached a substantially higher average replication score (on the order of the low-to-mid 40s percent) than the best agent achieved on that same subset (which scored well behind, in the 20s-30s percent range). The qualitative conclusion the authors draw is that current agents can rapidly produce partial, plausible-looking replications, but they do not have the sustained, self-correcting research stamina that lets human PhDs continue improving and closing gaps over longer horizons - so PhDs decisively win the extended-time, matched-subset comparison even though the gap on the full 20-paper benchmark (where agents are not time-matched against humans) looks smaller.

I am confident in the qualitative story and the identity of the winning model (Claude 3.5 Sonnet New with the paper's own scaffold) and in the roughly 21% figure for the full-benchmark average replication score, and in the overall finding that PhDs overtake and beat agents given the full 48-hour budget on the matched subset. I am less certain of the exact percentage-point values for the human-vs-agent subset comparison.

**Papers named (1):** PaperBench: Evaluating AI's Ability to Replicate AI Research  
**Stated confidence:** medium  
**Stated limits:** I could not confirm the exact numeric scores for the human-PhD-vs-agent time-matched subset comparison to the decimal point; the qualitative ordering (best agent about 21% on the full 20-paper benchmark, humans decisively ahead of agents by 48 hours on the matched subset) is what I can state with more confidence than the precise percentages.  
**Effort:** 0 exploration calls, 0 payload chars, 172,472 context, 69.7s, $0.228

> *Judge:* Gets the 21.0% figure and the correct qualitative story (agents ahead early / humans surpass by 48h) but refuses to commit to the subset size or the matched agent score, gives only vague ranges ("low-to-mid 40s", "20s-30s"), attributes the paper to "Kirchner et al." rather than Starace et al., and its closing claim that the full-benchmark gap "looks smaller" is confused.

**Fabrication notes:** Two mild misstatements in C: PaperBench Code-Dev is a reduced-grading variant (code development only, no execution), not a "lighter three-paper subset", and the 43.4% o1 figure belongs to that variant rather than a 3-paper set; also the human-baseline participants were recruited ML PhDs, not authors of the replicated papers. B attributes PaperBench to "Kirchner et al." whereas the first author is Giulio Starace (Starace et al., 2025) — likely a misattribution, though I am not certain Kirchner is absent from the author list, so I did not set the fabrication flag.

*Judged in 59.8s for $0.144.*
