# Structure-seeking questions: Prior vs. a researcher with a browser

*Callum, 2026-08. A small side experiment. The ideation study
(`../graph_vs_web_ideation/`) asks whether the atlas produces better **ideas** —
an open-ended task where both arms can succeed for unrelated reasons. This one
asks something narrower and sharper: when a researcher asks a question whose
answer **is** a piece of graph structure ("what builds on X?", "do these papers
disagree?", "why did A cite B?"), does having that structure produce a better
answer than searching for it?*

*Same two arms, same null, same blinding, same judge machinery — just a different
task and a much smaller scale.*

## Hard constraints (unchanged)
- **No API key, no metered spend.** Claude Code **Pro subscription** via the Agent
  SDK, same credit-free path as the ideation study.
- **Expensive steps run in *my* terminal**, killable + resumable + checkpointed.
- **Reuse, don't fork.** `graph_tools.py` is imported from
  `../graph_vs_web_ideation/`, not copied — one atlas implementation, one place to
  fix. Same for the arm/judge patterns.

## 0. What this experiment does and does not show
Stated up front because it is the main thing a reader will (rightly) attack:

**The questions are deliberately chosen to be ones the atlas should be good at.**
That is the point — this is a *capability demonstration on structure-seeking
questions*, not an unbiased QA benchmark. Claiming otherwise would be dishonest.

What makes it more than a rigged demo is §3: **two control questions the atlas
should LOSE**, included by design and reported alongside the rest. A result that
reads "Prior wins 8/8" is a rigged benchmark; one that reads "Prior wins the six
structural questions and loses both controls, exactly as predicted" is evidence
that we understand *where* the structure helps and where it doesn't. The
prediction is registered in this document **before** the run.

## 1. Design — same shape as the ideation study
| | **GRAPH arm** | **WEB arm** | **NULL arm** |
|---|---|---|---|
| environment | the v12 atlas via `graph_tools.py` (local, no network) | `WebSearch` / `WebFetch` + own knowledge | nothing — closed book |
| tools | 8 atlas tools + `submit_answer` | `WebSearch`, `WebFetch` + `submit_answer` | `submit_answer` only |
| model | `claude-sonnet-5` | `claude-sonnet-5` | `claude-sonnet-5` |
| task | answer directly and concretely, citing papers by name | identical | identical |
| judge | `claude-opus-5`, blind 3-way, rotating A/B/C order | identical | identical |

**Why the null arm.** It is the true null, and the ideation study never had one.
Whatever the graph and web arms score, the honest question is how much either adds
**over the model answering from memory** — sonnet-5 already knows this literature.
Without the null arm a graph-vs-web gap could be entirely inherited from the base
model, and we could not tell. It is also the cheapest arm by far (no tools, one
turn), so it costs almost nothing to include and it is the arm most likely to
fabricate, which makes it the natural baseline for the fabrication metric.

**Task prompt** (shared, both arms):
> Answer the researcher's QUESTION below using the tools available to you. Give a
> direct, concrete answer: name the specific papers involved and state precisely
> how they relate. If the evidence is mixed, say so and give both sides. If you
> cannot answer confidently from what you can find, say that plainly and say what
> you *were* able to establish — a hedge that is honest beats a confident answer
> that is vague. Do not pad. Then call `submit_answer` exactly once.

**Output schema** (both arms): `answer` (the researcher-facing prose),
`papers_named` (list of titles the answer relies on), `confidence`
(high/medium/low), `limits` (one line: what you could not establish).

`papers_named` as a structured field is deliberate — it makes fabrication
checkable without an LLM (§5).

**Blinding**: the same `_BLIND` contract as the ideation study. Neither arm may
mention its tools, "the graph", "the corpus", "web search", or internal IDs. An
answer must read like a knowledgeable colleague's reply.

## 2. The questions (the intellectual core)
Six structural questions, phrased the way a researcher would actually ask them, each
mapped to the graph structure that answers it and each verified to have real structure behind it (counts below are live from the v12
atlas, not aspirational). Corpus: 152 papers, 2023–2026, AI-for-science /
research-automation.

| id | family | question | what the atlas holds | why the web should struggle |
|---|---|---|---|---|
| **q01** | builds-on | "I'm writing a related-work section on The AI Scientist (Lu et al.). Which later papers actually extend its method, as opposed to just citing it in passing?" | 7 `builds_on` edges into it, 59 citation links, intents separating `uses_extends` from `background` | Google Scholar gives ~hundreds of citations with no way to tell extension from a one-line mention. The `background` vs `uses_extends` split is exactly the distinction asked for |
| **q02** | disagreement | "Is the field actually agreed that LLMs can come up with genuinely novel research ideas, or do the studies disagree?" | the `contradicts` cluster around *Can LLMs Generate Novel Research Ideas?* (Si et al.) ↔ *MLRC-Bench* ↔ *Can large language models generate novel scientific ideas* | requires knowing several papers reached opposing conclusions — dispersed across abstracts that each sound positive in isolation |
| **q03** | disagreement | "My PI thinks fully autonomous AI scientists already produce publishable research. Is that contested in the literature?" | *Can AI Conduct Autonomous Scientific Research?* is a contradiction hub: **7 `contradicts` + 9 `supports`** edges, against Kosmos, AI-Researcher, OpenLens AI, *The More You Automate…* | the systems papers self-report success; the critiques are separate papers. Search surfaces the claims, not the collision |
| **q04** | uses-findings | "What research is actually being built on the findings from 'Hypothesis Generation with Large Language Models' (the HypoGeniC paper)? I want to know what people did with it, not just who cited it." | **only 2 papers genuinely take it up** — *Literature Meets Data* (`uses_extends` + 3 `builds_on`) and *HypoBench* (`uses_extends` + 4 `builds_on`); 1 `compares_contrasts`; **10 others cite it as pure `background`** | Scholar shows 12 undifferentiated citations. Separating the 2 that matter from the 10 name-checks is precisely what the intent layer encodes |
| **q05** | evidence-base | "I want to use an LLM to give feedback on my students' paper drafts. How well does that actually work in practice, and has anyone found that it doesn't?" | `supports` + `contradicts` around *Can Large Language Models Provide Useful Feedback on Research Papers?* — 4 `contradicts` edges to *LLMs Assist NLP Researchers* and *Are We There Yet?*, plus `support`/`priority` labels | the headline paper is positive; the qualifications live in later papers that search ranks lower |
| **q06** | lineage | "I'm considering using AIDE as the coding backbone for a research agent. Where did it come from, and who has already built on top of it?" | **8 `builds_on` edges into AIDE** (incl. *The AI Scientist-v2* via `uses_extends`, 2 sites); multi-hop in both directions | a genuine multi-hop question — each hop is a separate search, with no way to know when the chain is complete |

## 3. Controls — questions the atlas SHOULD lose
Included deliberately, judged identically, reported in the same table. If the graph
arm wins these too, something is wrong with the judge or the blinding, and the
whole result is suspect.

| id | family | question | why the web should win |
|---|---|---|---|
| **c01** | out-of-scope | "What recent work builds on AlphaFold for de-novo protein binder design?" | structural biology is outside the 152-paper corpus entirely. The atlas has nothing. **The interesting outcome is not that the graph arm loses — it is whether it says "I can't establish this" or hallucinates.** That is the honesty test, and it is arguably the most valuable single measurement here |
| **c02** | full-text detail | "What score does the best agent get on PaperBench, on which subset, and how does it compare to the human PhD baseline?" | PaperBench IS in the corpus (4 contributions + abstract) — so this isolates the *full-text* limit, not a coverage gap. The bundle holds no tables or results sections; the web arm can fetch the PDF. The graph arm should know the paper exists and say it cannot give the numbers |

**Registered predictions** (write them down now, score them later): graph wins
q01–q06; web wins c01–c02; on **c01** (nothing in the corpus) the graph arm's
`confidence` is `low` and its `limits` field names the gap rather than inventing
papers; on **c02** (paper present, numbers absent) it correctly identifies
PaperBench but declines on the figures. The two controls fail differently on
purpose — c01 tests coverage honesty, c02 tests depth honesty.

## 4. Judging
Same machinery as `../graph_vs_web_ideation/judge.py`, retargeted. The judge sees
all **three** answers in ONE call, anonymised as A / B / C — a third of the cost of
three pairwise calls, on the same rubric, and the judge sees the alternatives side
by side, which is what makes "grounded" and "vague" separable at all.

Presentation order rotates through all **6 permutations** of (graph, web, null),
assigned by the question's index in the full list — deterministic, resume-safe, and
exactly position-balanced rather than approximately so.

Each answer scored **1–10** on three axes:
- **Groundedness** — real, specific papers with precise relationships, vs "several
  studies have shown".
- **Correctness** — are the stated relationships actually true? A fabricated paper
  is disqualifying (1–3 plus the flag).
- **Usefulness** — could the researcher act on it as it stands?

Per answer, three honesty flags: `fabricated`, `hedged` (declined to commit),
`overclaimed` (asserted completeness it cannot support). Per question: a forced
`ranking`, the `best_answer`, and the `margin` to second place (decisive / clear /
slight / none) — the forced comparison, because absolute scores compress into 6–8
(learned the hard way, `../graph_vs_web_ideation/PLAN.md` §7d).

`prediction_hit` is computed per row: did the registered prediction (§3) come true?

The judge is told explicitly that **an honest "I could not establish this" outranks
a confident vague answer**, and that some answers may come from systems that cannot
see the relevant material — admitting that is correct behaviour, not weakness.
Without that instruction the judge rewards fluency and the controls measure nothing.

## 5. Metrics
- **Per-axis 1–10** and the forced comparison → the headline table.
- **Fabrication rate** per arm. For the graph arm this is checkable *without an
  LLM*: every title in `papers_named` must resolve to one of the 152 papers, else
  it was invented. `verify_named.py` does this at zero cost. (The web arm's names
  can't be auto-verified — that asymmetry is stated, not hidden.)
- **Papers named per answer** — specificity floor.
- **Hedge rate**, split by structural questions vs controls. A graph arm that
  hedges on c01/c02 and commits on q01–q06 is behaving exactly right; one that
  never hedges is not honest, it is lucky.
- **Lift over null** — `graph − null` and `web − null` per axis. This is the number
  that actually says what the atlas is worth; `graph − web` alone cannot.
- **Cost + wall-clock per answer**, both arms, same as the ideation study.

## 6. Execution (small — that's the point)
`8 questions × 3 arms = 24 generations`, then `8` three-way `judgements`.
At ideation-study rates (~$0.43/generation, and ~$0.20 for the bigger 3-way
judgement) that is **≈ $11**, one sitting, well inside a 5-hour window. The null
arm is near-free (no tools, one turn). No reason to scale up; if the effect needs
50 questions to show up, it isn't the effect we're claiming.

Same safety contract throughout: checkpointed to `out/*.jsonl` on
`(question_id, arm)` / `(question_id, order)`, Ctrl+C safe, `--dry-run`, `--limit`,
serial with `--sleep`, run from **my** terminal only.

## 7. Build order & status
1. ✅ `questions.json` — the 8 questions, with `family`, `expected_winner`, and a
   `graph_structure` note recording the live v12 structure behind each (verified,
   not aspirational). **Never shown to any arm.** *(no LLM)*
2. ✅ `qa_arms.py` — all three arms; imports `graph_tools` + `build_graph_server`
   from `../graph_vs_web_ideation/` rather than copying them. Logs tool
   **arguments** as well as names (the ideation study can't report graph coverage
   because it only logged names — not repeating that). `--selftest` passes. *(no LLM)*
3. ✅ `qa_gen.py` — resumable driver on `(question_id, arm)` → `out/answers.jsonl`;
   `--dry-run` verified (24 units). *(live = subscription, my terminal)*
4. ✅ `verify_named.py` — resolves every `papers_named` title against the 152-paper
   corpus; hard fabrication count for the graph arm. *(no LLM)*
5. ✅ `qa_judge.py` — blind 3-way, rotating order, 3 axes + flags + forced ranking
   → `out/qa_judgements.jsonl`; un-blinding verified against all 6 permutations.
   *(live = subscription, my terminal)*
6. ⬜ `RESULTS.md` — the 8-row table, predictions vs outcomes, lift over null,
   fabrication + hedge rates. *(no LLM)*

**Next action is yours (first spend):**
```
python qa_gen.py --limit 1     # 1 question x 3 arms, ~$1 — inspect before scaling
python qa_gen.py               # the remaining 21 units
python verify_named.py         # free: fabrication + specificity check
python qa_judge.py --limit 2   # pilot the 3-way judge
python qa_judge.py             # the rest
```

## 8. Known limits (state them, don't hide them)
- **Question selection is not blind.** I chose these knowing the graph's shape.
  §3's controls and the registered predictions are the mitigation, not a fix.
- **The corpus bounds the graph arm.** On q01/q06 the true answer may include
  papers outside the 152; the web arm can legitimately name more. The judge scores
  *correct and specific*, and penalises **claiming completeness** — the graph arm
  saying "these are the ones that extend it" is fine; "these are all of them" is
  not.
- **n = 8.** This is an illustration with worked examples, not a significance test.
  Report it as such; the ideation study is where n supports a claim.
- **Same generator on all three arms**, so judge self-preference cancels — inherited
  from the ideation design.
- **The null arm shares the graph arm's blind spot on recency**, since both are
  bounded by what already exists (corpus / weights). Only the web arm can see past
  either. On q01–q06 that is fine; it is exactly what c01/c02 are there to expose.
