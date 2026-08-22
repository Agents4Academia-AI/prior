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

> **v2 — 2026-08-21.** The v1 pilot (q01, q02) is archived in `out_v1/` and is
> **not valid for scoring**. Two problems, both ours, both fixed:
> (1) the arms were never sealed — `allowed_tools` is a permission allowlist, not
> a tool-surface restriction, so every default Claude Code tool was live in every
> arm and the v1 q02 *graph* run opened with `Skill(prior)` and `Bash`;
> (2) the graph tool surface was contribution-level while every question is
> paper-level, so the graph arm ingested **1.7–2× more tokens than web search** —
> the opposite of the compactness claim. Full diagnosis, measurements and
> redesign: **[TOOL_SURFACE_V2.md](TOOL_SURFACE_V2.md)**.
>
> **v3 — 2026-08-21.** v2 fixed the seal but *not* the compactness problem: across
> the three clean triples the graph arm still pulled **1.27× more `tokens_in` and
> 1.79× more payload than web search**, falsifying the v2 efficiency prediction
> (§3). Decomposing one `paper_neighbourhood` call showed why — of 19,390
> characters, the *graph* (contribution statements + counts) was ~1,450; the rest
> was JSON envelope re-spelled on every list row, an abstract nobody asked for,
> and a truncated justification stub on every edge whether wanted or not. The v3
> surface fixes the **serialisation**, not the content, under four rules fixed
> from the data model *before* measuring (§2a). The five v2 graph rows are
> archived in `out_v2_graph/` with their numbers, and the two surfaces are
> reported side by side — `verbose=True` still reproduces the v2 payload, so the
> comparison costs nothing. **The web and null rows were not re-run**: nothing
> about those arms changed.

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
| tools | 12 atlas tools + `submit_answer` | `WebSearch`, `WebFetch` + `submit_answer` | `submit_answer` only |
| seal | `tools=[]`, `setting_sources=[]`, `skills=[]`, everything else in `disallowed_tools` | `tools=["WebSearch","WebFetch"]`, same seal otherwise | `tools=[]`, one MCP tool total |
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

## 2a. The graph tool surface — rules fixed from the data model

The v2→v3 change is an **envelope** change: same graph, same edges, same intents,
same counts, fewer characters. The distinction that keeps this honest is between
*rendering the data model faithfully and compactly* (engineering) and *reshaping
what the tool returns until the metric improves* (tuning). The test is whether the
rules can be stated from the data model alone, without reference to the outcome —
so they are stated here, and they were committed before the re-run.

1. **The envelope is not data.** A list row is one line, not a JSON object
   re-spelling `title`/`year`/`intents`/`n_sites`/`paper_id` on every row. Measured
   on the AI Scientist node: 190 chars/row → 58.
2. **Abstracts are not part of the graph.** The contribution statements *are* the
   distilled claim; shipping both pays twice for one thing. Still one `get_paper`
   call away. (−1,919 chars on that node.)
3. **Edges carry labels; justifications are fetched on request, batched.**
   `paper_neighbourhood` returns `<- builds_on | AI-Researcher | arxiv:…::k00`;
   `edge_reasons(paper_id, others=[…], relation=…)` returns the **full**
   justification for the edges that matter — v2 truncated *every* reason to 320
   chars (median reason is 1,095) and shipped them all regardless. Fewer characters
   *and* more evidence where it counts.
4. **Counts before lists.** Every count covers all links. Only the *enumeration* of
   routine `background` citations is deferred — `intent='background'` lists them.
   Nothing is hidden; the number is right there.

**Filters are arguments, not tools.** `relation='contradicts'` /
`intent='uses_extends'` on the existing surface, deliberately *not* a
`papers_building_on` endpoint — a tool named after the shape of q01 and q04 would
be a question-shaped API, and the same filter serves "what contradicts X" and
"what refines X" without encoding anything about these eight questions.

**Measured effect, offline, zero cost:**

| | v2 | v3 | |
|---|---:|---:|---|
| `paper_neighbourhood` (AI Scientist) | 19,390 | 5,756 | 3.4× |
| `topic_structure` (q02's query) | 9,709 | 3,995 | 2.4× |
| q01's whole trace, same exploration shape | 47,843 | 23,819 | 2.0× |

The q01 projection *includes* a `edge_reasons` call returning all seven
`builds_on` justifications in full (9,295 chars) — evidence v2 never delivered.

**Side effect worth having: the exploration trace becomes meaningful.** Under v2,
a paper "touched" by the graph arm might merely have been one of 40 rows dumped
into context — q01 touched 60 of 152 papers that way, which would overclaim badly
if drawn as "what the agent explored". Under v3 a node is either *listed* or
*deliberately read* (its edge justification was requested by id), and the two are
distinguishable in the log. That is what makes the poster figure honest.

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

**Registered efficiency prediction** (added v2, before the re-run — this is the
one the supervisor's challenge is about). Measured offline against the real atlas,
the intended v2 path answers all 8 questions in **12 calls / 89,201 chars**, where
v1 needed 24 calls / 98,433 chars for **two** (per question: 1.5 calls / 11.2k
chars vs 12 calls / 49.2k chars; see TOOL_SURFACE_V2.md §5). So I predict:

- the graph arm's **`tokens_in` is now BELOW the web arm's** on q01–q06 — this is
  the compactness claim, and v1 falsified it;
- the graph arm makes **fewer tool calls than the web arm** on the paper-named
  questions (q01, q04, q06);
- **`off_arm_tools` is empty on all 24 rows.** If it is not, the seal failed again
  and the affected rows are discarded, not patched;
- on **c01** `find_paper` returns nothing and the graph arm says so, rather than
  naming the nearest paper in the corpus.

A miss here is a real result, not a bug to be fixed after the fact: it would mean
the agent wanders regardless of how the atlas is shaped, which is worth knowing.

### Outcome of the v2 efficiency prediction: **FALSIFIED** (2026-08-21)

Scored on the three complete triples that ran before the session limit (q01, q02,
q04; q03's web row is excluded — its metrics were under-counted by an aggregation
bug, see below).

| | graph | web | |
|---|---:|---:|---|
| `tokens_in` | 68,791 | 54,321 | graph **1.27× worse** |
| payload chars | 104,392 | 58,234 | graph **1.79× worse** |
| cost | $0.82 | $1.66 | graph **half** |
| turns | 21 | 32 | graph fewer |
| tool calls | 12 | 24 | graph half |

So the compactness claim failed and the *efficiency* claim held, for a reason worth
stating plainly: atlas calls are cheap and cached, `WebSearch`/`WebFetch` carry
server-side cost, and the graph arm needed fewer turns. `payload_chars` — which has
no cache-prefix confound — moves the same way as `tokens_in`, so this was a real
result and not a measurement artefact. The v2 prediction of "12 calls / 89,201
chars for all 8" was also far too optimistic: it assumed one neighbourhood call per
question, and the model legitimately pulled three or four.

**Registered v3 efficiency prediction** (before the re-run):

- the graph arm's **`payload_chars` at least halves** versus its own v2 rows on the
  same questions — this is the near-certain one, since it is mostly arithmetic on
  the serialisation, and it is scored against `out_v2_graph/`;
- the graph arm's **`tokens_in` drops below the web arm's** on q01–q06. This is the
  claim that actually failed in v2 and it is the one to watch;
- **turns do not inflate.** Splitting justifications into a second call risks
  re-creating v1's failure mode (v1 died on 15 calls, not on payload). Predict the
  graph arm stays **at or below its v2 call count** on each question, because
  `edge_reasons` is batched and the filters remove follow-up calls. If calls rise
  materially, the split was the wrong trade and that gets reported;
- **`off_arm_tools` empty on all rows**, unchanged;
- on **c01** `find_paper` still refuses, unchanged by v3.

### Scored on the v3 pilot (q01/graph, 2026-08-21)

Against the archived v2 row for the same question. Turns identical at 10.

| prediction | outcome | |
|---|---|---|
| `payload_chars` at least halves | 47,843 → **25,929** (1.85×) | ✅ |
| calls at or below v2's | 5 → **6** | ❌ (by one) |
| `off_arm_tools` empty | empty | ✅ |
| `tokens_in` below web's | 32,019 → **59,320** vs web's 22,208 | ❌ — **but the metric was disqualified**, see §5 |

The call-count miss is real and stands as a miss: the arm spent its extra call on
three `citations_between` lookups for site-level evidence, which is defensible
behaviour but is not what was predicted. Its trace was otherwise exactly the
intended v3 shape — `find_paper` → `paper_neighbourhood` → **one batched**
`edge_reasons(relation='builds_on')`.

`tokens_in` is scored as a failure of the *instrument*, not of the arm, and the
reasoning for that call — plus the number that disqualifies it — is set out in §5
rather than here, so a reader can reject it and still read the table.

**A metrics bug found and fixed at the same time.** `ResultMessage.usage` and
`total_cost_usd` are **per-query**, not session-cumulative — proved by `q03/web`,
which made four `WebSearch`/`WebFetch` calls yet whose last `ResultMessage` reports
`server_tool_use.web_search_requests: 0`, because those happened in the first
query. An earlier build read only the last message and under-counted every nudged
row. `run_one` now sums usage across queries, takes the max for `num_turns`, and
stores each query's own numbers in `finals_meta`. Exactly one completed row was
affected (`q03/web`, one nudge); it should be re-run rather than trusted.

## 4. Judging

> **judge v2 — 2026-08-21. `fabricated` is split from `unrecognised`.** The judge
> is sealed (no browser) and scores from its own knowledge, which is right for
> reproducibility and has one hard edge: **32% of the corpus is dated 2026 and
> eight papers postdate the judge's training data outright.** A paper it has never
> heard of is indistinguishable from one that does not exist.
>
> This is not hypothetical. On q04 the judge set `fabricated` on the graph arm for
> *"DN Hypo Pipeline"*, writing that it "does not appear to be a real
> system/paper". It is `arxiv:2606.08532`, in the corpus, published after the
> cutoff. The bias is **directional**: the graph arm is the one that names obscure
> corpus papers (19 on q01 against web's 8), so it is the one penalised for being
> right about recent work.
>
> Two options were rejected before this one. **An internet-enabled judge** fails
> because verification cost is asymmetric: web's claims ("this paper exists, this
> is its title") are one search away, whereas the graph arm's claims are
> *relational* ("A builds on B, and here is why") and can only be checked by
> reading both papers — so a searching judge would confirm web's claims and return
> "could not confirm" on the graph arm's. Same bias, more steps, and no longer
> reproducible. **A corpus-lookup tool for the judge** fails on blinding: graph's
> papers are 100% in-corpus by construction against web's ~64%, so the tool would
> identify the arm.
>
> So the judge's remit is narrowed instead. Existence is a *mechanical* question
> and is settled mechanically (`verify_named.py`, `check_fabrication.py`); the
> judge scores the **relationships and claims**, flags what it cannot place as
> `unrecognised` (explicitly no penalty), and reserves `fabricated` for what it
> affirmatively believes is false — wrong authors, wrong finding, a garbled title
> of a paper it does know. The v1 judgements are kept in `out_judge_v1/` and both
> are reported.
>
> **This is the third post-hoc correction after seeing results** (tool surface
> twice, now the judge). Each is defensible alone — a provably real paper called
> invented is an instrument error, not a preference — and each keeps the old
> numbers alongside the new. But the pattern is now part of the result, and §8
> says so.

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

### Judge reliability — measured, not assumed

We got an accidental replication: q01–q03 were judged under both rubric versions
while their **answers were unchanged**, so the two passes are a repeat measurement
of the same inputs.

> **7 of 27 axis scores moved by one point, and one winner of three flipped.**

The rubric change itself accounts for part of it (correctness: graph +0.67, web
+0.33, null −0.33 across those three questions), but not for web's groundedness
and usefulness dropping 9→8 on q02 — the split touches only correctness and
fabrication. That is run-to-run noise, and it is **the same size as almost every
margin in the result**: the judge called six of eight comparisons `slight`.

So `qa_judge.py --repeats N` judges each question N times and `report.py` collapses
the runs:

- **Scores are means** over runs, with min/max kept so the spread is shown rather
  than averaged away.
- **Winner is a majority vote**; with no majority it is reported as `split`, not
  broken by fiat.
- **A flag is set when a majority of runs set it**, with the vote count retained.
- **Presentation order rotates within a question.** Across questions the base
  order cycles all 6 permutations; each repeat rotates that base, so at
  `--repeats 3` **every arm appears in every slot exactly once per question** — a
  position effect cannot ride along with one arm across its repeats. Verified:
  arm × slot counts are 8/8/8 over 24 judgements.
- Checkpointing is on `(question_id, run)`, so a partly-judged question resumes
  into only the runs it is missing. Judgements written before repeats existed
  carry no `run` and count as run 0.

**Consequence for reporting: do not lean on win counts.** With margins at the
noise floor, the defensible outputs are the per-axis means with their spread, the
mechanical checks, and the worked examples.

### Two objections this design has to answer

**"If `unrecognised` carries no penalty, can the judge still judge correctness?"**
Yes, because the old flag conflated two claims. *"This paper does not exist"* was
only ever supported by absence of recognition, which — with 32% of the corpus
dated 2026 — is not evidence, and was wrong 3 times out of 3. *"This claim is
false"* is still fully penalised, and demonstrably discriminates: correctness ran
4–9 in the first full batch, with the low scores all going to content errors (q06
graph 4, for claiming AI Scientist v1 used AIDE-style tree search when v1 used
Aider plus fixed templates; c02 web 7, for mischaracterising PaperBench Code-Dev;
c02 null 6, for attributing the paper to "Kirchner et al.").

The residual hole is real and worth stating: an arm that invents a plausible paper
the judge has never heard of now escapes the judge. For the **graph arm that hole
is closed** by `verify_named.py`, which is stricter than the judge could be — it
can only name papers from the 152, and 0 of 62 named titles failed to resolve. For
**web and null it is not closed**. That asymmetry runs *against* the graph arm's
apparent advantage: the other two arms can now invent unpenalised, so a graph
advantage measured under this rubric is understated, not inflated.

**"The judge's `best_answer` sometimes disagrees with the highest axis total."**
It happened once in eight, and the shape matters: **the judge never picked an
answer that another beat on all three axes.** The one exception, q02, is *weak*
dominance — graph 8/8/8 against web 8/9/8, tied on groundedness and usefulness,
one point apart on correctness. The missing factor is identifiable from the
judge's own reason: it credited graph with "the broadest and most structured map
of the disagreement", and **breadth is not one of the three axes** — groundedness
measures specificity and precision, not coverage.

Both `best_answer` and the axis sum are compressions of the same three numbers,
weighted differently; the sum's equal weighting is no less arbitrary than the
judge's implicit one. So neither is privileged and **neither is the headline**:
report the three axis means, and the ranking as a separate qualitative signal.
`report.py` prints both win counts side by side for exactly this reason.

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
- **Efficiency — `payload_chars` is the headline** (revised 2026-08-21, reason
  below). Three numbers are reported for every row, in descending order of how far
  they can be trusted, and *all three appear in RESULTS.md* — including the one
  that broke:

  | metric | computed by | what can move it for the wrong reason |
  |---|---|---|
  | **`payload_chars`** *(headline)* | **our own `run_one`**, summing what the tools returned | nothing in the harness |
  | `context_total` | harness usage: input + cache_creation + cache_read | nothing much — it is the total the model processed |
  | `tokens_in` *(retained, not headline)* | harness usage: input + cache_creation | **caching**: it charges cache *writes*, which track prefix re-chunking, not ingestion |

  **Why `tokens_in` was demoted.** It was the pre-registered headline and it broke
  on the very first v3 row. q01/graph v2→v3: `payload_chars` fell 47,843→25,929
  (≈5,500 tokens less material) while `cache_creation` **rose by 27,345 tokens**. A
  27k rise cannot be caused by ingesting 5.5k fewer tokens, so `tokens_in` is not
  measuring ingestion. Mechanically: v2 pulled one 20k blob early and then coasted
  on cheap cache reads; v3 pulled six medium results, so the growing prefix was
  re-committed more often, moving tokens from the read bucket into the write bucket
  — which is also the entire cost difference ($0.415→$0.554, of which +$0.164 is
  cache writes and −$0.031 is cache reads). On the metric that survives, v3 read
  **1.85× less payload** and processed **1.32× less total context** (308,771 →
  234,120) than v2.

  This is the second time an efficiency metric has moved against the graph arm and
  been revisited, which is a pattern to be suspicious of. What separates it from
  motivated reasoning: the disqualifying evidence is an *internal contradiction in
  the instrument* (payload down, cache_creation up five times more than payload
  fell), not a preference about the result; and the demoted metric stays in the
  table with this explanation attached rather than being dropped.

- **Cost is a footnote, not a result.** On the subscription, dollars are a notional
  API-equivalent price we never pay, and — as above — they are dominated by
  cache-write accounting, i.e. by turn structure rather than by how much the arm
  read. Reported for completeness; never used to support a claim.
- Reported alongside: **tool calls to answer**, turns, wall-clock.
- **Controls are NEVER pooled with the structural questions.** c01/c02 are
  designed for the graph arm to lose — c01 has nothing in the corpus at all — so
  averaging them in drags the graph mean down by construction and makes the
  headline meaningless in both directions. Pooled, graph's groundedness read 7.6;
  split, it is **8.5 on the six structural questions and 5.0 on the two controls**,
  which is the intended pattern and the more informative report. Lift over null is
  structural-only for the same reason.
- **Seal integrity** — `off_arm_tools` must be empty on every row. Non-empty means
  the arm reached outside its environment and the row is discarded.
- **Exploration trace** — for the graph arm, the logged tool arguments replay
  exactly against the local atlas (it is deterministic), so the explored subgraph
  is recoverable at zero cost, including *after* the fact. Nodes split into
  *listed* and *deliberately read* (§2a).

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
2. ✅ `qa_arms.py` **(v3)** — all three arms, **sealed** (`tools=`,
   `setting_sources=[]`, `skills=[]`, `disallowed_tools`), asserted by
   `--selftest`. Graph surface is paper-shaped and lean: `find_paper`,
   `paper_neighbourhood` (with `relation` / `intent` filters), `edge_reasons`
   (batched justifications) and `topic_structure` in front of the eight v1
   drill-down tools. Logs tool **arguments and result sizes**, plus the
   `off_arm_tools` canary and per-query `finals_meta`. `graph_tools.py` is still
   imported from `../graph_vs_web_ideation/`, never copied — the new methods were
   added there and are additive, so the parked ideation environment stays frozen
   (`arms.py --selftest` still shows its original 8 tools). *(no LLM)*
3. ✅ `qa_gen.py` — resumable driver on `(question_id, arm)` → `out/answers.jsonl`;
   `--dry-run` verified (24 units). *(live = subscription, my terminal)*
4. ✅ `verify_named.py` — resolves every `papers_named` title against the 152-paper
   corpus; hard fabrication count for the graph arm. *(no LLM)*
5. ✅ `qa_judge.py` — blind 3-way, rotating order, 3 axes + flags + forced ranking,
   **`--repeats N`** for mean-and-spread scoring (§4), checkpointed on
   `(question_id, run)`
   → `out/qa_judgements.jsonl`; un-blinding verified against all 6 permutations.
   **Now sealed too** (`tools=[]`, `setting_sources=[]`, `skills=[]`): it had the
   same v1 bug the arms had — the system prompt said "you have no tools and no
   browser", but with `bypassPermissions` a prompt is not a seal, and a judge that
   quietly looked papers up would make correctness scores depend on what it found
   rather than on the answers. *(live = subscription, my terminal)*
6. ✅ `TOOL_SURFACE_V2.md` — the cost diagnosis, the seal bug, the redesign, and
   the offline efficiency projection. *(no LLM)*
7. ✅ `check_fabrication.py` — resolves every judge `fabricated` / `unrecognised`
   title against the 152 papers and reports overturned vs upheld, so a flag on a
   real-but-recent paper cannot silently become a fabrication statistic. *(no LLM)*
8. ✅ `trace.py` — replays the logged graph-arm tool arguments against the atlas
   (deterministic, so this is a **replay, not a reconstruction**) and writes, per
   question, `out/traces/<qid>.{svg,json,md}`: a white-background poster figure, a
   Prior `GlobalGraph {nodes, edges}` for the app's own viewer, and the
   call-by-call narrative. *(no LLM, no cost)*

   The figure's primary channel is **engagement, not adjacency** — concentric
   rings:

   | ring | meaning | earned by |
   |---|---|---|
   | **focus** (inner, numbered by call) | the agent *chose* this paper | named as an argument to a call |
   | **read** (middle) | the agent read its *evidence text* | returned by `edge_reasons` or `citations_between` |
   | **listed** (outer, faint) | merely delivered | appeared in a returned list |

   That split is only measurable **because of the v3 redesign** (§2a): labels in
   `paper_neighbourhood`, justifications on request in `edge_reasons`. Under v2,
   where every truncated justification shipped with the listing, "read" and
   "listed" were the same thing and no honest trace existed. The figure is
   therefore evidence for the tool-surface argument, not just decoration for it.

   Edge colour is Prior's own palette (`frontend/src/lib/colors.ts`); solid =
   read, dashed = listed; a gold halo marks papers named in the final answer.

   **Arrowheads are drawn only where the graph records a direction**, read off the
   canonical edges' own `direction` field rather than asserted: `supports` is
   `symmetric` on all 203 edges and `contradicts` on all 27, while `builds_on`
   (109) and `refines` (10) carry `a_to_b`/`b_to_a`; citation-layer edges are
   directed by construction (citing -> cited). One trap worth recording:
   **`a_to_b`/`b_to_a` refers to the A/B roles the labeller saw, and those were
   NOT preserved in `src`/`dst`.** Checked against the citation layer, `src` is
   the citing (later) paper in **104 of 104** directed edges that have a citation,
   whereas reading `a_to_b` as `src -> dst` agrees only **39 of 104** — a coin
   flip. So the arrow follows `src -> dst`, and `direction` decides only *whether*
   to draw one.

   **Poster candidates.** `q01` (one paper chosen, 7 `builds_on` justifications
   read, then three specific citation links checked — the cleanest "what does
   `builds_on` buy you" figure) and `q03` (five neighbourhoods, then two batched
   `contradicts` pulls, giving a red disagreement structure through the middle).
   `c01` is worth keeping as the control panel: two name lookups **refused** by
   the corpus (drawn red), nothing chosen, nothing read — the empty centre is the
   finding.

   **Sized for the poster.** Each figure is a landscape band (~1.7:1) for about a
   quarter of the height of an A0 sheet. Height is the binding constraint — at
   297mm tall a square figure is only ~300mm wide and the labels land at 7pt — so
   the key and the call sequence are a right-hand *column*, not a strip
   underneath, and the type is set large relative to the graph (ring radii come
   from node counts, not font size, so large type is nearly free vertically). At
   a quarter of A0 that puts body text near 13pt and paper titles near 17pt.
   Everything is Arial.

   Tuning for the two hero figures: `--max-listed`, `--drop`/`--keep`,
   `--queries`, `--spread`, `--width`, `--font-scale`, `--layout below`,
   `--no-timeline`. `--png` renders via headless Chrome if PowerPoint's SVG
   import is not wanted.
9. ⬜ `RESULTS.md` — the 8-row table, predictions vs outcomes, lift over null,
   fabrication + hedge rates, **the efficiency table** (§5), and the **v2 vs v3
   tool-surface comparison** scored against `out_v2_graph/`. *(no LLM)*

**State on 2026-08-21.** The overnight run stopped at unit 13 on the Claude
session limit (`"You've hit your session limit · resets 5am"` — recorded verbatim
in `out/failures.jsonl`). Nothing else failed: the limited units cost $0.00, went
to `failures.jsonl` rather than the checkpoint, and will re-run. `out/answers.jsonl`
holds **8 valid web + null rows** (q01–q04, minus `q03/web` which needs re-running
for the metrics bug above). The five v2 graph rows are in `out_v2_graph/`.

Remaining: 5 graph rows under v3 + 11 units never reached + `q03/web` = **17 units,
≈ $5**, then 8 judgements ≈ $2.80.

```
python qa_arms.py --selftest                  # free: confirms the seal + 12 tools
python qa_gen.py --questions q01 --arm graph  # ~$0.30 — the v3 pilot, inspect it
python check_leakage.py                       # free: blinding gate
python qa_gen.py --questions q03 --arm web    # ~$0.30 — re-run for the metrics fix
python qa_gen.py                              # the rest (~$4.50)
python verify_named.py                        # free: fabrication + specificity
python qa_judge.py --limit 2                  # pilot the 3-way judge
python qa_judge.py                            # the rest
python report.py                              # free: renders out/REPORT.md
```

On the v3 pilot, check three things before scaling, all on the graph row:
`payload=` should be roughly **half** q01's archived 47,843; `calls=` should be
**at or below** 5; and there should be no **SEAL BREACH** line. If `calls=` jumps,
the label/justification split cost more turns than it saved — say so and report it
rather than tuning it away.

## 8. Known limits (state them, don't hide them)
- **Question selection is not blind.** I chose these knowing the graph's shape.
  §3's controls and the registered predictions are the mitigation, not a fix.
- **The tool surface was revised after seeing v1 fail.** That is a second degree
  of freedom on top of question selection, and pretending otherwise would be
  dishonest. Three things bound it: the new tools are generic (lookup by name,
  one-paper neighbourhood, topic neighbourhood) and encode nothing about these
  eight questions; c01 got *harder*, because `find_paper` now refuses rather than
  returning the nearest paper; and the efficiency prediction was registered with
  its numbers before the re-run. The defensible claim is about the interface, not
  a score: *the same representation, less material into context, because the index
  aggregates instead of the model*.
- **The tool surface was then revised a SECOND time**, after v2's efficiency
  prediction failed. This is the weakest point in the design and it should be
  stated first, not buried. What separates it from tuning: the v3 rules were fixed
  from the data model and written down before measuring (§2a); they change
  *serialisation*, not content, so no evidence was added or removed; the change was
  argued from a decomposition of one payload (1,450 chars of graph inside 19,390
  chars of envelope) rather than from the metric; the deliberately question-shaped
  option (`papers_building_on`) was rejected precisely because it would have
  encoded these questions; and the v2 rows are kept and reported beside the v3 ones
  rather than replaced. A reader who still discounts the efficiency numbers as
  tuned is entitled to — which is why the fabrication, groundedness and honesty
  results, none of which the serialisation touches, carry the actual argument.
- **The corpus bounds the graph arm.** On q01/q06 the true answer may include
  papers outside the 152; the web arm can legitimately name more. The judge scores
  *correct and specific*, and penalises **claiming completeness** — the graph arm
  saying "these are the ones that extend it" is fine; "these are all of them" is
  not.
- **The judge cannot see the recent third of the corpus.** 32% of the 152 papers
  are dated 2026 and eight postdate the judge's training data. Judge v2 (§4)
  removes the penalty and `check_fabrication.py` adjudicates what is left, but the
  judge still cannot *positively* confirm a recent paper's content — so on
  questions turning on 2026 work, its correctness scores are weaker evidence than
  they look. Report fabrication as **judge-flagged, then corpus-adjudicated, both
  numbers**, never one alone.
- **Two harness bugs contaminated rows before they were caught**, and both are
  worth stating because they are the kind that look like results. (1) The v1 arms
  were unsealed. (2) `submit_answer` was last-wins, so a model that retried its
  submission had its *degraded* attempt stored: 14 of 24 rows submitted more than
  once and two submitted eleven times, ending in an 823-char stub with
  `limits="test"` that the judge then scored. Fixed to first-complete-wins with
  every attempt retained and `n_submits` on the row; the two affected rows
  (`q04/graph`, `q05/null`) were re-generated.
- **The method is now three post-hoc corrections deep** — tool surface v2, tool
  surface v3, judge v2 — each made after seeing a result move against the graph
  arm. The mitigations are consistent (rules fixed from the data model before
  measuring; old numbers archived and reported beside the new; the disqualifying
  evidence in each case an internal contradiction rather than a preference), but a
  reader is entitled to discount the efficiency and judge-score results on this
  basis. **The results that no correction touches are the fabrication check
  (`verify_named.py`: 0 unresolved titles across every paper the graph arm named),
  the specificity count, and the author-attribution errors in the other arms.**
  Those carry the argument.
- **The judge is noisier than the effect.** Measured, not assumed: a repeat pass
  on unchanged answers moved 7 of 27 axis scores by a point and flipped one winner
  of three, against margins the judge itself called `slight` in six of eight
  comparisons. `--repeats` gives a spread; it does not make n=6 into a result.
  Report per-axis means with their spread, and **do not report a win rate**.
- **c02 is a weaker control than designed.** It was meant to isolate the full-text
  limit — PaperBench is in the corpus but the results tables are not. In fact
  **PaperBench's abstract carries the headline numbers (21.0%, 41.4%)**, which the
  graph arm read via `get_paper`. It scored the *highest* correctness of the three
  arms (9) while honestly declining on the subset detail, and lost on usefulness
  because the web arm could fetch the PDF. So c02 measured "correct and bounded vs
  complete and slightly wrong", not coverage depth. c01 remains a clean control and
  behaved exactly as registered: `find_paper` refused, the graph arm said it could
  not establish the topic, confidence `low`, and it ranked last.
- **n = 8.** This is an illustration with worked examples, not a significance test.
  Report it as such; the ideation study is where n supports a claim.
- **Same generator on all three arms**, so judge self-preference cancels — inherited
  from the ideation design.
- **The null arm shares the graph arm's blind spot on recency**, since both are
  bounded by what already exists (corpus / weights). Only the web arm can see past
  either. On q01–q06 that is fine; it is exactly what c01/c02 are there to expose.
