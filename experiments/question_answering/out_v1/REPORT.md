# QA experiment — answers and judgements in full

*Generated from `out/answers.jsonl` + `out/qa_judgements.jsonl`. 2 of 8 questions answered, 2 judged. Design + registered predictions: [PLAN.md](../PLAN.md).*

> ⚠️ **Blinding leak — these rows are not safely judgeable and should be regenerated, then re-judged:**  
> `q01` [graph]: schema_label=['"background"', '"compares_contrasts"', 'citation intent']  

## Scoreboard

Scores are groundedness / correctness / usefulness, each 1-10.

| q | expected | best | margin | prediction | GRAPH | WEB | NULL |
|---|---|---|---|---|---|---|---|
| **q01** | graph | **graph** | slight | ✅ hit | 9/8/9 | 8/8/8 | 7/8/7 |
| **q02** | graph | **graph** | slight | ✅ hit | 9/8/9 | 8/9/8 | 5/8/6 |

### Mean scores so far

| arm | groundedness | correctness | usefulness | fabricated | hedged | overclaimed |
|---|---|---|---|---|---|---|
| GRAPH (Prior atlas) | 9.0 | 8.0 | 9.0 | 0/2 | 0/2 | 0/2 |
| WEB (search) | 8.0 | 8.5 | 8.0 | 0/2 | 0/2 | 0/2 |
| NULL (closed book) | 6.0 | 8.0 | 6.5 | 0/2 | 0/2 | 0/2 |

**Lift over the null arm** (the number that says what each environment is worth):

| arm | Δ groundedness | Δ correctness | Δ usefulness |
|---|---|---|---|
| GRAPH (Prior atlas) | +3.0 | +0.0 | +2.5 |
| WEB (search) | +2.0 | +0.5 | +1.5 |

## Cost and effort

| q | arm | explore calls | seconds | cost | papers named | confidence |
|---|---|---|---|---|---|---|
| q01 | graph | 15 | 109.5 | $0.523 | 10 | medium |
| q01 | web | 4 | 94.6 | $0.416 | 7 | medium |
| q01 | null | 0 | 67.7 | $0.208 | 8 | medium |
| q02 | graph | 11 | 87.9 | $0.413 | 17 | high |
| q02 | web | 2 | 78.9 | $0.280 | 3 | medium |
| q02 | null | 0 | 105.6 | $0.306 | 2 | medium |

Generation total: **$2.15** (graph $0.94, web $0.70, null $0.51). Judging total: **$0.65**.


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

**9** grounded · **8** correct · **9** useful · flags: —

Short answer: only a handful of the ~50+ papers that cite The AI Scientist (Lu et al., 2024) actually extend its method. Most citations are "background" mentions (used to motivate a benchmark, a risk study, or a peer-review evaluation) or "compares_contrasts" mentions (used as one baseline among several). The papers that genuinely build on its pipeline/artifacts are:

**Direct, high-confidence extensions**

1. **The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search** (2025) — this is the explicit successor. It gives a feature-by-feature comparison table against v1, keeps the same idea→experiment→manuscript loop, and replaces the specific components v1 was criticized for: human-authored code templates are dropped in favor of an agentic tree-search "experiment manager" agent, and VLM feedback is added for iterative figure refinement. This is the closest thing to a canonical "v2 extends v1" relationship in the literature.

2. **Towards end-to-end automation of AI research** (Nature, 2026) — written by the same author team as the original (Chris Lu, Cong Lu, R. T. Lange, Yutaro Yamada, Shengran Hu, Jakob Foerster). It's effectively the journal-length follow-up: it keeps the original template-based system but adds a template-free, open-ended mode using agentic search, and reports the headline new result that an AI-Scientist-generated manuscript passed the first round of peer review at a workshop of a top-tier ML conference. This is a direct methodological extension by the original authors, not a third-party citation.

3. **AI-Researcher: Autonomous Scientific Innovation** (2025) — explicitly describes The AI Scientist as having "pioneered this field" and as "the first system for automated scientific discovery," and adopts the same idea-generation → experiment-execution → paper-writing pipeline structure while adding a multi-agent architecture and its own benchmark (Scientist-Bench). This is a genuine methodological build, not a passing mention.

4. **Kosmos: An AI Scientist for Autonomous Discovery** (2025) — uses The AI Scientist as an explicit baseline/comparison point and positions its main contribution (running roughly 8× more discovery cycles, with reported value scaling with cycle count) as an advance on the iteration budget that limited earlier systems including The AI Scientist. It's a build on the *problem framing* more than a direct reuse of the original codebase.

5. **AIGS / Baby-AIGS: Generating Science from AI-Powered Automated Falsification** (2024) — explicitly contrasts its DSL-based approach against "the coding language adopted in previous work (Lu et al., 2024)" and frames its FalsificationAgent as filling a gap "absent in prior systems (Lu et al., 2024)." It builds on The AI Scientist's end-to-end framing while adding an explicit falsification stage.

6. **Chain of Ideas: Revolutionizing Research Via Novel Idea Development with LLM Agents** (2025) — a partial/mixed case worth flagging: it explicitly says it follows "the previous practice (Wang et al. 2023; Lu et al. 2024)" of using a novelty-check agent, and it adopts Lu et al.'s idea-collection assessment scale — genuine methodological reuse. At the same time it also uses The AI Scientist as a baseline it benchmarks against and critiques (it argues Lu et al.'s method for organizing literature in the prompt is unstructured, motivating its own chain-structured approach). So it both extends specific components and contrasts itself against the whole system.

**Cited but not extended (background/comparison only)**

The large majority of the citing literature falls here: benchmark and evaluation papers such as MLGym, ScienceAgentBench, Curie, CORE-Bench, MLR-Bench, EXP-Bench, AstaBench, MLRC-Bench, RE-Bench, and ResearcherBench cite The AI Scientist as one of the systems being evaluated or as motivating context, without adopting or modifying its method. Risk/critique papers — The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems, and Jr. AI Scientist and Its Risk Report — cite it only as background (grouped with other "several works" and critiqued for producing "undirected discoveries" from small-scale code), and Jr. AI Scientist proposes a deliberately different, mentor-guided problem framing rather than extending the original pipeline. Automated peer-review papers (DeepReview, ReviewRL, TreeReview, OpenReviewer, MARG, CycleResearcher) cite it only for the peer-review component in passing. Other end-to-end systems — SciAgents, Towards an AI co-scientist, AgentRxiv, Denario, Robin — cite it as prior art in the "AI scientist" space but come from distinct architectural lineages (e.g., AgentRxiv builds on Schmidgall's Agent Laboratory, not on Lu et al.'s pipeline) and don't reuse its specific methods.

**Bottom line for a related-work section**: cite The AI Scientist-v2 and the Nature "Towards end-to-end automation of AI research" paper as direct successors/extensions from the same lineage; cite AI-Researcher, Kosmos, AIGS/Baby-AIGS, and Chain of Ideas as third-party systems that adopt or explicitly build on specific components of its method; treat everything else in the citing set (benchmarks, peer-review studies, risk reports, and competing end-to-end frameworks) as comparison or background citations rather than extensions.

**Papers named (10):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Towards end-to-end automation of AI research; AI-Researcher: Autonomous Scientific Innovation; Kosmos: An AI Scientist for Autonomous Discovery; AIGS: Generating Science from AI-Powered Automated Falsification; Chain of Ideas: Revolutionizing Research Via Novel Idea Development with LLM Agents; Jr. AI Scientist and Its Risk Report: Autonomous Scientific Exploration from a Baseline Paper; The More You Automate, the Less You See: Hidden Pitfalls of AI Scientist Systems; AgentRxiv: Towards Collaborative Autonomous Research  
**Stated confidence:** medium  
**Stated limits:** I could not verify the full text of every one of the ~50 citing papers individually (e.g. AI Scientist via Synthetic Task Scaling, EvoScientist, Robin), so a small number of borderline cases classified here as "background/comparison" based on citation intent labels might, on closer reading of their methods sections, turn out to reuse more of the original pipeline than the citation context alone indicates.  
**Effort:** 15 exploration calls, 109.5s, $0.523
  
**Graph tools used:** `get_edges`×7, `get_paper`×4, `citations_between`×2, `ToolSearch`×1, `search_contributions`×1, `get_citations`×1

> *Judge:* By far the widest and most checkable coverage — it separates extension from background with named quoted relationships (AIGS's "the coding language adopted in previous work (Lu et al., 2024)", CoI's novelty-check reuse) and an accurate roll-call of the benchmark/peer-review/risk citing set (MLGym, ScienceAgentBench, RE-Bench, MLRC-Bench, Jr. AI Scientist, "The More You Automate…", AgentRxiv-builds-on-Agent-Laboratory), though the Kosmos "≈8× more discovery cycles" figure and the Nature 2026 follow-up are the shakiest items, and it misses Dolphin, the clearest third-party extension.

### WEB (search)

**8** grounded · **8** correct · **8** useful · flags: —

Three papers actually extend The AI Scientist's method rather than just citing it; a couple more are close enough to be worth flagging as "parallel/borderline"; and there's at least one paper that engages closely with it but as critique rather than extension.

**Direct method extensions:**

1. **The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search** (Yamada et al., Sakana AI, 2025). This is the literal sequel, same lab. It explicitly replaces v1's biggest weakness — reliance on a human-authored starter code template per research domain — with a "progressive agentic tree search" run by a dedicated experiment-manager agent, so it generalizes across ML domains instead of being locked to a template. It also adds VLM-based feedback during experiments and during the automated review/manuscript stage. Worth noting for your related-work section: the authors themselves report v2 doesn't always beat v1 on paper quality, especially when a good template exists for v1 — so it's an extension with a real, stated trade-off, not a strict improvement.

2. **Dolphin: Moving Towards Closed-loop Auto-research through Thinking, Practice, and Feedback** (Yuan et al., Fudan University / Shanghai AI Lab, ACL 2025). This one explicitly names the gap in AI Scientist as its starting point: AI Scientist's idea-generation stage doesn't receive feedback from experimental results, and its experimental validation runs on simple, self-constructed datasets. Dolphin keeps the same broad shape (generate idea → implement via code template → run experiment → analyze results) but closes the loop by feeding experiment outcomes back into the next round of idea generation, and adds exception-traceback-guided debugging of the generated code. This is a genuine architectural extension of the same idea→code→experiment loop, not a different paradigm.

3. **AI-Researcher: Autonomous Scientific Innovation** (Tang, Xia, Li, Huang; NeurIPS 2025). Positions itself explicitly against both AI Scientist-v1 and v2, targeting the hallucination/correctness problem in the experiment-implementation stage. Its contribution is a multi-agent architecture that maintains bidirectional mappings between mathematical formulations and code, plus a mentor/student-style iterative refinement loop between agents — a direct attempt to fix a failure mode of the AI Scientist code-generation approach.

**Borderline — related pipelines, not direct extensions of the method itself:**

- **Agent Laboratory: Using LLM Agents as Research Assistants** (Schmidgall et al., 2025) covers the same broad territory (literature review → experimentation → report writing) and is frequently discussed alongside AI Scientist, but it's built around a human-in-the-loop research assistant framing rather than extending AI Scientist's specific pipeline or code — treat it as convergent, independently-designed work rather than a technical extension.
- **Curie: Toward Rigorous and Automated Scientific Experimentation with AI Agents** — focused on rigor and reproducibility of the experimentation stage broadly; it references AI Scientist as prior art in the space but its contribution (reliability/reproducibility guarantees) isn't framed as building on AI Scientist's architecture specifically.

**Critique rather than extension:**

- **"Evaluating Sakana's AI Scientist: Bold Claims, Mixed Results, and a Promising Future?"** — this is a replication/evaluation study of AI Scientist's actual output quality and claims, useful for a related-work section's "limitations of the original" paragraph, but it doesn't propose a method extension.

For a related-work section, I'd frame it as: v2 is the direct lineage extension (same team, template→tree-search), Dolphin is the "closes the feedback loop" extension, and AI-Researcher is the "fixes the code-hallucination problem" extension — those three are the ones that modify or replace a specific mechanism from the original paper rather than adopting its framing.

**Papers named (7):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; Dolphin: Moving Towards Closed-loop Auto-research through Thinking, Practice, and Feedback; AI-Researcher: Autonomous Scientific Innovation; Agent Laboratory: Using LLM Agents as Research Assistants; Curie: Toward Rigorous and Automated Scientific Experimentation with AI Agents; Evaluating Sakana's AI Scientist: Bold Claims, Mixed Results, and a Promising Future?  
**Stated confidence:** medium  
**Stated limits:** I could not establish a complete/exhaustive list of every paper extending the method (the auto-research space is moving fast, and other 2025-2026 systems exist), nor confirm each paper's own related-work framing of "extends vs. cites" beyond what's summarized above from their stated contributions.  
**Effort:** 4 exploration calls, 94.6s, $0.416

> *Judge:* The only answer to surface Dolphin (Yuan et al., Shanghai AI Lab), which is genuinely the paper that names AI Scientist's no-feedback-to-ideation gap and closes that loop, and the only one to note v2's own admission that it does not always beat v1 when a good template exists — but its AI-Researcher mechanism description ("bidirectional mappings between mathematical formulations and code", mentor/student refinement) and the NeurIPS 2025 venue attribution are stated more confidently than I can support, and its overall coverage is much thinner than A's.

### NULL (closed book)

**7** grounded · **8** correct · **7** useful · flags: —

Most papers that cite "The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery" (Lu, Lange, Foerster, Clune, Ha et al., Sakana AI, 2024) do so as motivating background for "automated end-to-end research" — very few actually build on or modify its pipeline (idea generation → aider-driven code/experiment execution → paper writing → LLM-based automated peer review). Here's how I'd split the field:

**Direct, unambiguous extension (same lineage):**
- **"The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search"** (Yamada, Lange, Lu, Hu, Lu, Krishnamurthy, Ha, Clune, Foerster — Sakana AI, 2025). This is a genuine method extension, not just a citation: it explicitly replaces v1's fixed, human-written experiment templates with an agentic tree-search procedure for exploring the experiment space, generalizes the pipeline to work without domain-specific scaffolding, and reports that one of its generated papers passed peer review at an ICLR workshop. This is the paper you'd cite as the direct successor.

**Papers that extend a specific stage of the pipeline, with explicit reference to Lu et al.'s architecture:**
- **CycleResearcher / CycleReviewer** (Weng et al., 2024) — takes the "LLM generates paper → LLM reviews it" loop from AI Scientist and turns it into a closed training loop, using reinforcement learning against an automated reviewer model to iteratively improve a research-generation LLM, rather than relying on prompting alone. This extends the paper-writing/review-feedback component specifically.
- **"Chain of Ideas" / CoI-Agent** (Li et al., 2024) — focuses narrowly on the idea-generation stage, proposing a chain-structured literature organization to improve novelty/quality of generated research ideas; positions itself as improving on AI Scientist's (and similar systems') idea-generation step rather than the full pipeline.
- **Curie** (2025) — targets the experiment-execution stage, arguing AI Scientist-style pipelines lack methodological rigor, and proposes a framework aimed at more reliable, reproducible automated experimentation. I'm less certain of its exact mechanism than the two above, so treat this one as a "likely relevant, verify before citing" case.

**Parallel/competing systems that cite AI Scientist as related work but do not extend its method:**
- **Agent Laboratory** (Schmidgall et al., AMD/Johns Hopkins, 2025) — an alternative human-in-the-loop research-agent pipeline (literature review → experimentation → report). It's frequently discussed alongside AI Scientist and addresses the same problem, but it's an independently designed architecture, not a modification of Lu et al.'s method.
- **Google's AI co-scientist** (2025) — a multi-agent hypothesis-generation system for biomedical research built on Gemini; conceptually adjacent but architecturally unrelated to AI Scientist's code-experiment-paper loop.
- **Robin** (Ghareeb et al., FutureHouse, 2025) — automated a real wet-lab biomedical discovery; cites automated-science precedents like AI Scientist but its method (literature agents + lab-in-the-loop) is unrelated to Lu et al.'s ML-paper-generation pipeline.

For a related-work section, I'd cite AI Scientist-v2 as "extends," CycleResearcher/CycleReviewer and CoI-Agent as "extends a component of," and Agent Laboratory / AI co-scientist / Robin as "addresses the same problem space but independently."

**Papers named (8):** The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery; The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search; CycleResearcher: Improving Automated Research via Automated Review; Chain of Ideas: Revolutionizing Research Via Novel Idea Development with LLM Agents; Curie: Toward Rigorous and Automated Scientific Experimentation with AI Agents; Agent Laboratory: Using LLM Agents as Research Assistants; Towards an AI Co-Scientist; Robin: A multi-agent system for automating scientific discovery  
**Stated confidence:** medium  
**Stated limits:** I'm highly confident about AI Scientist-v2 as a direct extension (same authors, explicit successor); for CycleResearcher, CoI-Agent, and Curie I'm confident on their general positioning relative to Lu et al. but not on precise implementation details or exact result numbers, so those should be checked against the papers themselves before being characterized in detail; I could not establish whether any other, less prominent papers with genuine architectural extensions exist beyond this set.</limits>
</invoke>
  
**Effort:** 0 exploration calls, 67.7s, $0.208

> *Judge:* Correct on everything it commits to (v2's template→tree-search replacement, CycleResearcher's RL-against-an-automated-reviewer loop, CoI-Agent's idea-generation focus, Agent Laboratory / co-scientist / Robin as convergent-not-derived) and admirably explicit about which items to verify before citing, but it covers the smallest slice of the citing literature and its "extends a stage" grouping is loosely argued — CycleResearcher is arguably an independent training paradigm rather than an extension of Lu et al.'s pipeline.

**Fabrication notes:** No clear fabrications in any answer; all named systems (AI Scientist-v2, Dolphin, AI-Researcher, AIGS/Baby-AIGS, CoI-Agent, CycleResearcher, Curie, Agent Laboratory, Kosmos, Robin, AgentRxiv, Jr. AI Scientist, and A's benchmark list) exist. Unverified/soft items rather than fabrications: A's Nature 2026 "Towards end-to-end automation of AI research" (plausible successor by the same team but I cannot confirm it) and its Kosmos "≈8× more discovery cycles" number; B's NeurIPS 2025 venue for AI-Researcher, its ACL 2025 venue for Dolphin, its slightly-off Dolphin title variant, and its AI-Researcher mechanism description; C's Curie claim, which it correctly flags as needing verification.

*Judged in 81.9s for $0.408.*


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

**9** grounded · **8** correct · **9** useful · flags: —

No, the field is not settled — the literature disagrees at two levels: on the underlying capability, and on whether we can even trust the evaluations used to measure it.

**The headline "yes" result.** The most-cited data point is Si et al., "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (2024): in a blind review by 100+ NLP researchers, LLM-generated ideas were rated significantly more novel than human-expert-written ideas (p<0.05), though somewhat weaker on feasibility — billed as the first statistically significant result on this question. Several other studies independently converge on the same qualified-positive answer: "Can Large Language Models Unlock Novel Scientific Research Ideas?" found GPT-4/Gemini/Claude-2/GPT-3.5 generate ideas that are novel, relevant and feasible "to a meaningful degree" across five disciplines (660 ideas rated); a social-psychology hypothesis-generation study found GPT-4 hypotheses rated above human ones on originality and quality; MOOSE-Chem argued LLMs encode latent chemistry knowledge associations enabling genuinely unseen hypothesis rediscovery; and a 2026 astronomy-domain study reported LLM ideas matching or exceeding human ideas on novelty and feasibility. A cluster of ideation frameworks (Chain-of-Ideas, ResearchAgent, NOVA, VIRSCI, EvoScientist) built retrieval-, planning-, and multi-agent-based systems specifically to push novelty scores higher, implicitly treating the capability as real and improvable.

**The direct contradiction.** MLGym ("A New Framework and Benchmark for Advancing AI Research Agents") tested frontier models (Claude-3.5-Sonnet, Llama-3.1-405B, GPT-4o, o1-preview, Gemini-1.5 Pro) on open-ended AI research tasks and found they improve baselines mainly through hyperparameter tuning and do *not* generate novel hypotheses, algorithms, or architectures — a finding explicitly flagged as being in tension with the "Can Large Language Models Unlock Novel Scientific Research Ideas?" result, since it covers overlapping models but reaches the opposite conclusion. Separately, "All That Glitters is Not Novel: Plagiarism in AI Generated Research" went back and audited the actual proposals from the Si et al. study (among others) and found 24% were plagiarized or closely paraphrased from prior work without attribution — directly undercutting the "more novel than humans" conclusion by showing some of that apparent novelty is an artifact of undetected copying.

**The deeper, arguably more important disagreement is about measurement.** A large share of the recent literature is really arguing about whether novelty ratings (human or LLM-judged) mean anything. MLRC-Bench found LLM-judged idea novelty is poorly correlated with actual empirical effectiveness on ML research problems. SCI-IDEA found LLM-as-judge scores for open-ended ideation systematically exceed PhD-expert ratings by 3–4 points on a 10-point scale with near-zero inter-rater correlation (r=0.02–0.17) — and this finding was flagged as directly contradicting three other papers that claimed LLM judges track expert opinion well: MLR-Bench's "MLR-Judge" (claims LLM-human agreement statistically indistinguishable from human-human agreement), ResearchAgent's reviewing-agent module, and "Interesting Scientific Idea Generation using Knowledge Graphs and LLMs" (claims zero-shot LLM ranking predicts expert interest). NovBench similarly reports current LLMs have limited understanding of scientific novelty with a substantial gap versus human novelty judgments. Even Si et al.'s own study reports, alongside its headline novelty result, two systematic failure modes: lack of diversity across generated ideas and unreliable self-evaluation of idea quality.

**Bottom line:** there is real, well-evidenced support for LLMs producing ideas that human reviewers rate as novel in several domains, but there is equally direct, paper-level contradiction of that claim (MLGym; the plagiarism audit) and an active, unresolved dispute over whether the novelty scores driving the optimistic conclusions are even measuring what they claim to measure. This is not a settled consensus — it's an open and actively contested question, with the disagreement concentrated as much in "how do we evaluate novelty" as in "can LLMs produce it."

**Papers named (17):** Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; Can Large Language Models Unlock Novel Scientific Research Ideas?; Machine-assisted social psychology hypothesis generation.; MOOSE-Chem: Large Language Models for Rediscovering Unseen Chemistry Scientific Hypotheses; Can large language models generate novel scientific ideas? A comprehensive study on data-driven astronomy; Chain of Ideas: Revolutionizing Research Via Novel Idea Development with LLM Agents; ResearchAgent: Iterative Research Idea Generation over Scientific Literature with Large Language Models; NOVA: An Iterative Planning Framework for Enhancing Scientific Innovation with Large Language Models; Many Heads Are Better Than One: Improved Scientific Idea Generation by A LLM-Based Multi-Agent System; EvoScientist: Towards Multi-Agent Evolving AI Scientists for End-to-End Scientific Discovery; MLGym: A New Framework and Benchmark for Advancing AI Research Agents; All That Glitters is Not Novel: Plagiarism in AI Generated Research; MLRC-Bench: Can Language Agents Solve Machine Learning Research Challenges?; SCI-IDEA: Context-Aware Scientific Ideation Using Token and Sentence Embeddings; MLR-Bench: Evaluating AI Agents on Open-Ended Machine Learning Research; Interesting Scientific Idea Generation using Knowledge Graphs and LLMs: Evaluations with 100 Research Group Leaders; NovBench: Evaluating Large Language Models on Academic Paper Novelty Assessment  
**Stated confidence:** high  
**Stated limits:** I could not establish a resolution to the dispute (e.g., a follow-up replication or meta-analysis that adjudicates between the positive and negative findings) — the literature as surveyed leaves the question open rather than settled in either direction.  
**Effort:** 11 exploration calls, 87.9s, $0.413
  
**Graph tools used:** `get_edges`×5, `search_contributions`×4, `ToolSearch`×2, `Skill`×1, `Bash`×1

> *Judge:* Maps the disagreement at two levels — capability (Si et al. vs MLGym vs the Gupta/Pruthi plagiarism audit) and, more valuably, measurement validity (MLRC-Bench, SCI-IDEA vs MLR-Judge/ResearchAgent/Gu-Krenn, NovBench) — with named, overwhelmingly real papers and checkable pairwise relations; minor risk sits in unverifiable specifics (SCI-IDEA's 3–4 point gap and r=0.02–0.17, "NovBench", the 2026 astronomy study) and it oddly omits the single most direct rebuttal, the same authors' Ideation-Execution Gap.

### WEB (search)

**8** grounded · **9** correct · **8** useful · flags: —

No, there isn't agreement — and the disagreement is unusually well-documented because the same research group produced both the optimistic finding and the walk-back.

**The optimistic result:** Chenglei Si, Diyi Yang, and Tatsunori Hashimoto's "Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers" (ICLR 2025) had over 100 expert NLP researchers write research ideas and separately blind-review a mix of human-written and LLM-generated ideas on the same prompts. LLM ideas were judged significantly more novel than the human experts' ideas (statistically significant), though rated somewhat less feasible. This result got a lot of attention as evidence LLMs could produce genuinely novel ideas, at least by the yardstick of blind expert judgment of idea statements.

**The direct rebuttal from the same authors:** A follow-up, "The Ideation-Execution Gap: Execution Outcomes of LLM-Generated versus Human Research Ideas" (Si, Hashimoto et al., 2025), tested whether that novelty edge survives actually doing the research. They recruited 43 expert researchers, each randomly assigned an idea (LLM-generated or human-written) to execute — over 100 hours per person, producing a short paper. Result: the LLM-generated ideas' scores dropped significantly more than the human ideas' scores once executed, on every evaluation metric, closing the gap seen at the ideation stage. In other words, "novel-sounding" LLM ideas often don't hold up as novel or good once someone tries to build and run them — the effect looks like it was partly an artifact of judging idea descriptions in isolation rather than judging research outcomes.

**Independent evidence pointing the same skeptical direction:** An independent evaluation of Sakana AI's "The AI Scientist" system — "Evaluating Sakana's AI Scientist for Autonomous Research: Wishful Thinking or an Emerging Reality Towards 'Artificial Research Intelligence'?" — found the system's novelty claims were frequently wrong in the other direction: it misclassified well-established techniques (e.g., micro-batching for SGD) as novel because its literature review relied on shallow keyword search rather than real synthesis. On top of that, about 42% of its automatically-run experiments failed outright due to coding errors, and several "successful" runs produced misleading results (e.g., claiming an energy-efficiency improvement while actually using more compute). This suggests that end-to-end automated "novel discovery" pipelines are currently not reliable arbiters of novelty either.

**Bottom line:** the field does not agree. There is one well-cited human study showing LLM-generated ideas are rated more novel than expert ideas in blind review, but the same authors' own execution follow-up shows that advantage largely evaporates when ideas are actually carried out, and independent scrutiny of autonomous "AI scientist" pipelines shows their novelty judgments are often unreliable (both over- and under-crediting existing work) and their executed experiments frequently flawed. The honest summary is: LLMs can generate ideas that look novel to human judges reading short descriptions, but there is active, credible pushback on whether that reflects genuine research novelty once you follow the idea through to execution.</answer_end_placeholder>

**Papers named (3):** Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; The Ideation-Execution Gap: Execution Outcomes of LLM-Generated versus Human Research Ideas; Evaluating Sakana's AI Scientist for Autonomous Research: Wishful Thinking or an Emerging Reality Towards 'Artificial Research Intelligence' (ARI)?  
**Stated confidence:** medium  
**Stated limits:** I could not establish a broad, systematic survey across the full literature (e.g., domains outside NLP/ML, or older idea-generation work like SciMON/MOOSE-style literature-grounded hypothesis systems) — the disagreement described here is well-grounded for the specific ideation-vs-execution debate in NLP/ML research-idea generation, but I can't say how representative it is of the field's view as a whole across all scientific domains.</limits>
</invoke>
  
**Effort:** 2 exploration calls, 78.9s, $0.280

> *Judge:* Correctly identifies the sharpest structure in this debate — the same group's own Ideation-Execution Gap (43 executors, 100+ hours, LLM ideas dropping more on every metric) rebutting their ICLR 2025 result — plus Beel et al.'s independent Sakana audit with accurate details (micro-batching misjudged as novel, ~42% experiment failure), and it scopes its own limits honestly to NLP/ML; narrower coverage than A and it misses the evaluation-validity literature entirely.

### NULL (closed book)

**5** grounded · **8** correct · **6** useful · flags: —

No, there isn't consensus — the evidence is genuinely mixed, and even the strongest pro-novelty result comes with caveats its own authors raise.

The key data point on the 'yes' side is Chenglei Si, Diyi Yang, and Tatsunori Hashimoto's paper 'Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers' (2024). This is the most rigorous study in the space: they recruited 100+ NLP researchers to both write research ideas and blind-review a mix of LLM-generated and human-expert-generated ideas on the same topics. LLM ideas were judged as more novel than the human experts' ideas, and the difference was statistically significant. This result gets cited constantly as evidence that LLMs can produce novel ideas.

But the same paper undercuts a simple 'yes' reading in three ways: (1) LLM ideas were rated as less feasible than human ideas, so novelty came with a practicality tradeoff; (2) the authors explicitly flag a diversity/mode-collapse problem — when you sample many ideas from an LLM, they cluster around a small number of underlying concepts, which is in tension with 'genuine' novelty at scale rather than one-off lucky outputs; (3) novelty here was judged from written proposals by human reviewers, not from completed research — it's an evaluation of idea statements, not of the actual scientific contribution once pursued. There is follow-on work from the same line of research specifically examining what happens when ideas are actually executed into full projects (an ideation-vs-execution gap), and the reported pattern is that the novelty edge for AI-generated ideas is harder to sustain once you look at completed work rather than proposals — I'm less certain of that paper's exact title/authorship, so treat that specific claim as a weaker, secondary point rather than a settled finding.

On the skeptical side, Sakana AI's paper 'The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery' (2024), which claims a fully automated pipeline from idea generation through experiment execution and paper writing, was met with substantial community pushback — critics pointed to superficial or incremental novelty, hallucinated results and citations, and papers that didn't hold up to real reviewer scrutiny. That controversy is widely seen as evidence against the strong claim that current systems produce genuinely novel, execution-ready science end-to-end.

There's also a standing methodological worry across this literature: human novelty ratings of LLM-written proposals may be partly confounded by writing style (AI text tends to be longer, more structured, and more confidently hedged), rather than purely reflecting the underlying idea's originality. This is a concern raised in discussion of the Si/Yang/Hashimoto results themselves, not a refutation of them, but it means 'reviewers rated it more novel' isn't the same as 'it is more novel' in a deeper conceptual sense.

Bottom line: the single best-designed human study (Si, Yang, Hashimoto) found LLM ideas rated more novel than expert human ideas at the proposal stage — a real and notable result — but feasibility trade-offs, diversity collapse under repeated sampling, unresolved questions about whether that novelty survives execution, and the broader controversy around fully autonomous systems like The AI Scientist mean the field has not converged on 'yes, LLMs generate genuinely novel research ideas.' It's closer to one strong result under specific conditions, contested on what it actually demonstrates.

**Papers named (2):** Can LLMs Generate Novel Research Ideas? A Large-Scale Human Study with 100+ NLP Researchers; The AI Scientist: Towards Fully Automated Open-Ended Scientific Discovery  
**Stated confidence:** medium  
**Stated limits:** I could not establish the exact title or authorship of the specific follow-up study examining whether LLM idea novelty survives full execution into completed projects, so that point is flagged as lower-confidence rather than a firmly cited finding.  
**Effort:** 0 exploration calls, 105.6s, $0.306

> *Judge:* Accurate on Si/Yang/Hashimoto (novelty edge, feasibility trade-off, diversity collapse, self-eval unreliability) and honest in flagging that it could not name the execution follow-up — which is exactly the right behaviour — but it rests on only two named papers, substitutes community controversy over The AI Scientist for actual counter-evidence, and so gives the researcher little to chase.

**Fabrication notes:** None confidently fabricated. Watch-items in A: the exact SCI-IDEA numbers (3–4 point LLM-judge inflation, r=0.02–0.17), "NovBench: Evaluating Large Language Models on Academic Paper Novelty Assessment" (plausible but I cannot confirm the title; related work such as SchNovel/NoveltyBench exists and could be conflated), and the "2026 astronomy" study's date/title. B's unnamed execution follow-up is real (Si, Yang, Hashimoto, "The Ideation-Execution Gap", 2025) and B was right to flag rather than guess it. C's three papers all check out, including Beel et al.'s Sakana evaluation.

*Judged in 71.9s for $0.237.*
