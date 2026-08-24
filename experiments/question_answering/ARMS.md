# How the three arms actually worked

*Everything a reader needs to reconstruct or attack the generation half of the
experiment: what each arm could see, the exact prompts, the exact tools, the files
those tools read, and what each arm did with them. Judging is a separate document
([JUDGING.md](JUDGING.md)); the results are in [RESULTS.md](RESULTS.md).*

Code: `qa_arms.py` (the arms), `qa_gen.py` (the runner). Nothing here is a
paraphrase — every prompt below is quoted verbatim from `qa_arms.py`, and
`python check_docs.py` re-checks that on demand.

---

## 1. The three arms at a glance

| | **GRAPH** | **WEB** | **NULL** |
|---|---|---|---|
| what it can see | Prior's v12 atlas, in-process, no network | `WebSearch` + `WebFetch` | nothing |
| tools | 12 atlas tools + `submit_answer` | `WebSearch`, `WebFetch` + `submit_answer` | `submit_answer` only |
| generator | `claude-sonnet-5` | `claude-sonnet-5` | `claude-sonnet-5` |
| task prompt | identical | identical | identical |
| blinding contract | identical | identical | identical |
| answers produced | 8 | 8 | 8 |
| exploration calls / answer | 6.8 | 5.8 | 0 |
| payload chars / answer | 24,533 | 14,314 | 0 |
| papers named / answer | 7.1 | 5.5 | 3.1 |
| cost / answer | $0.236 | $0.447 | $0.220 |

**Why a null arm exists.** Sonnet-5 already knows this literature. Without a
closed-book arm, a graph-vs-web gap could be entirely inherited from the base
model and we would not be able to tell. It is also the arm most likely to
fabricate, which makes it the natural baseline for the honesty metrics. It costs
almost nothing to run — no tools, one or two turns.

---

## 2. What all three arms share

The only difference between arms is the **environment**. Model, task, output
schema, blinding, nudging and budget are identical, which is what licenses
comparing them at all.

### 2.1 The task prompt

Sent as the first user message to every arm, with `{question}` substituted.
Verbatim from `qa_arms.TASK`:

> A researcher asks you the QUESTION below. Answer it.
>
> Give a direct, concrete answer: name the specific papers involved and state
> precisely how they relate to each other and to the question. If the evidence is
> mixed, say so and give both sides. If you cannot answer confidently, say that
> plainly and say what you WERE able to establish — an honest 'I can't establish
> this' is a better answer than a confident vague one, and inventing a plausible
> paper is the worst possible answer. Do not pad; a researcher wants the substance.
>
> Work efficiently: reach for the broadest tool that answers the question before
> drilling into specifics, and stop EXPLORING once you have what you need.
>
> You deliver the answer by calling `submit_answer` EXACTLY ONCE with: `answer`
> (your reply to the researcher); `papers_named` (the exact titles of the papers
> your answer relies on); `confidence` (high / medium / low); `limits` (one line
> on what you could not establish).
>
> *…the blinding contract, §2.2, is appended here…*
>
> QUESTION: {question}
>
> Do not write your reply as ordinary text — text is discarded. The ONLY way to
> deliver it is the `submit_answer` tool call. Make that call now.

That last paragraph is scar tissue. The first v2 run explored perfectly, wrote its
answer as ordinary prose, and ended the turn — the unit was lost.

### 2.2 The blinding contract

Appended to the task prompt for all three arms. Without it the judge could tell
the arms apart from a single phrase ("I searched for…", "the graph shows…") and
the blinding would be theatre. Verbatim from `qa_arms._BLIND`:

> Write the answer as a SELF-CONTAINED reply a colleague could read with no idea
> how you produced it. Name prior work by paper title or author, never by an
> internal ID. Do NOT mention your tools, your search or exploration process, 'the
> graph', 'the corpus', a database, 'web search', node/edge IDs, or how you arrived
> at the answer. In `limits`, describe what you could not ESTABLISH about the
> question itself — never what tools or sources you did or did not have. Do not
> invent papers, findings, or numbers.
>
> Write in ordinary scholarly English. Never quote or name a classification label
> from any system you consulted — words like 'background', 'uses_extends',
> 'compares_contrasts', 'builds_on', 'contradicts', 'citation intent', 'edge' or
> 'relation type' as TECHNICAL TERMS are forbidden, and so is any underscored_token.
> Say what is true in plain prose ('cites it only in passing', 'genuinely extends
> it', 'reaches the opposite conclusion') — a colleague would never say a paper was
> tagged compares_contrasts.

Two carve-outs are load-bearing:

- **`limits` is about the question, never about the tooling.** "I had no way to
  search" would identify the null arm instantly.
- **The relation vocabulary is banned as jargon, not as content.** The graph arm
  must say "reaches the opposite conclusion", not "is tagged `contradicts`".
  Otherwise the graph arm is identifiable from its own vocabulary.

This is enforced, not just requested. `check_leakage.py` scans every answer for
tool names, process language and relation tokens; `report.py` runs it and prints
the verdict at the top of [RESULTS.md](RESULTS.md). The gate is currently **clean
on all 24 answers**.

### 2.3 The output schema

Every arm delivers via one MCP tool, `submit_answer`:

| field | type | why |
|---|---|---|
| `answer` | string | the researcher-facing prose — this is what the judge scores |
| `papers_named` | list of strings | exact titles the answer relies on |
| `confidence` | high / medium / low | self-report, used for the honesty analysis |
| `limits` | string | one line on what could not be established |

`papers_named` being a **structured field rather than prose** is the single
design choice that makes fabrication checkable without an LLM. `verify_named.py`
resolves each title against the 152-paper corpus at zero cost. For the graph arm
an unresolved title *is* a fabrication — it could only ever have seen those 152
papers. That check is unavailable for web and null, and the asymmetry runs
against the graph arm, not for it.

`submit_answer` keeps the **first complete** submission and archives every attempt.
This too is scar tissue: 14 of 24 rows called it more than once and two called it
eleven times, degrading the payload on each retry. Under the original last-wins
rule, `q04/graph` stored an 823-char stub with `limits="test"` while its real
answer sat in a discarded earlier attempt — and that stub is what the judge scored.
"Complete" means prose *and* at least one paper named; a later attempt can only
replace an incomplete one.

### 2.4 The nudge

If a model ends a turn without calling `submit_answer`, it gets one identical
message (`qa_arms.NUDGE`), up to twice, inside the same session so its exploration
context survives:

> You have not called `submit_answer`, so nothing has been recorded and the
> researcher has received nothing. Call `submit_answer` now with your answer,
> `papers_named`, `confidence` and `limits`. If you were unable to establish an
> answer, submit that honestly — say what you could and could not establish, with
> `confidence` set to low. Do not explore further and do not reply in prose.

Nudges are counted on every row as `n_nudges`, so they cannot quietly advantage
one environment. Across the whole run: **1 nudge total**, on `q03/web`.

### 2.5 The seal

The arms are sealed at the SDK level, and this is the part that has already gone
wrong once, so it is worth stating precisely.

**`allowed_tools` is a permission allowlist, not a tool-surface restriction.** The
surface restriction is the separate `tools=` field. v1 set only the former and ran
`permission_mode="bypassPermissions"`, so every default Claude Code tool was live
in every arm. It bit us: the v1 `q02` GRAPH run opened with `Skill(prior)` and
`Bash(python -m prior.cli info)`, and the NULL arm had `WebSearch` available
throughout (it happened not to call it). Those rows are archived in `out_v1/` and
are **not valid for scoring**.

What is set now, per arm:

```python
ClaudeAgentOptions(
    system_prompt=SYS[arm],
    mcp_servers=mcp,
    allowed_tools=allowed,
    tools=builtin,            # THE surface restriction: [] for graph and null,
                              #   ["WebSearch","WebFetch"] for web
    disallowed_tools=[...],   # every other builtin, belt and braces
    setting_sources=[],       # no project CLAUDE.md, no settings
    skills=[],                # no repo skills (v1 leaked Skill(prior))
    max_turns=14, model="claude-sonnet-5",
    permission_mode="bypassPermissions", max_budget_usd=1.20,
)
```

Three independent defences, because one of them silently failed before:

1. `tools=` — the real restriction.
2. `disallowed_tools` — names every real builtin the arm must never see. They have
   to be *real* tool names or the CLI warns "deny rule matches no known tool" on
   every call.
3. **The canary.** `run_one` records `off_arm_tools` on every row: any tool call
   observed that is not in that arm's allowlist. A non-empty value means the row
   is **discarded, not patched**. `report.py` surfaces it at the top of
   RESULTS.md so a breach can never be quietly read past.

Result: `off_arm_tools` is empty on all 24 rows. `python qa_arms.py --selftest`
re-asserts the whole wiring with no model call and zero cost.

> ⚠️ The same sealing bug is still live in `../graph_vs_web_ideation/arms.py`.
> That experiment is parked; fix it there before it is ever re-run.

---

## 3. The GRAPH arm

### 3.1 What it read

The atlas is built by `graph_tools.GraphAtlas`, imported from
`../graph_vs_web_ideation/graph_tools.py` — **imported, never forked**, so there
is one atlas implementation and one place to fix it. It loads five files:

| file | what it contributes |
|---|---|
| `experiments/edge_quality/out/canonical_semantic_candidates_enriched_evidence_v12.json` | the canonical typed edges between contributions, each with a `relation`, a `direction` and a recorded `reason` |
| `experiments/edge_quality/out/citations_intent.json` | citation links with an intent (`background` / `uses_extends` / `compares_contrasts`) and a justification per site |
| `experiments/edge_quality/out/citations_typed.json` | support / priority labels on those same citation links |
| `experiments/edge_quality/out/citations_intent_incoming_v12_new.json` | the additional incoming citation sites added in the v12 pass |
| `data/prior-core-v0.2/papers_core.jsonl` | the 152 papers: title, year, authors, abstract |

Live sizes, as loaded:

- **152 papers**, 2023–2026, AI-for-science / research automation. About a third
  are dated 2026.
- **581 contributions** — atomic claims, methods and findings extracted per paper.
- **989 typed edges** between contributions. Of these the four evaluative
  relations the tools expose as filters are **203 `supports`, 109 `builds_on`,
  27 `contradicts`, 10 `refines`**; the remaining 640 are `related`/`none`.
- **643 directed citation links** between papers, each carrying an intent and
  per-site justifications.

Everything is local and deterministic. There is no network call anywhere in this
arm — which is also what makes the exploration replayable (§7).

### 3.2 The system prompt

Verbatim from `qa_arms.GRAPH_SYS`:

> You have a structured research atlas to consult, covering ~150 papers. Two
> coupled layers:
> • CONTRIBUTIONS — atomic claims / methods / findings.
> • RELATIONS — how they connect: typed semantic edges (builds_on, refines,
> supports, contradicts — all four matter equally), each with a stated REASON, plus
> the CITATIONS between papers, each tagged with an intent (background /
> uses-and-extends / compares-and-contrasts) and a justification for why one paper
> cited another. The semantic edges were derived from those citations.
>
> HOW TO USE IT — get the SHAPE first, then read the evidence you need:
> 1. If the question names a paper: `find_paper`, then `paper_neighbourhood`. That
> one call gives you its contributions, the typed relations touching them, its
> citations ranked by intent, and every count.
> 2. If the question is about a topic rather than a named paper,
> `topic_structure` searches and returns the relations around the best hits in the
> same call.
> 3. Those calls give edge LABELS, not justifications. Decide which relations
> actually bear on the question, then call `edge_reasons` ONCE with all of them
> (`relation=` to filter by type, or `others=[...]` to name specific papers) and
> read the full evidence. One batched call, not one per edge.
> 4. Narrow filters beat second calls: `paper_neighbourhood(paper_id,
> relation='contradicts')` or `intent='uses_extends'` answers a pointed question
> directly.
> 5. Only then drill further if something is still missing: `get_edges`,
> `citations_between` for site-level citation justifications, `get_paper` for an
> abstract, `get_contribution` for detail. `overview` is orientation only.
>
> Read the COUNTS before the lists — they are often the answer on their own. A
> paper cited 53 times as background and 3 times as uses-and-extends has three
> papers building on it, not fifty-six. The listing deliberately omits routine
> background citations; the count is still there, and `intent='background'`
> enumerates them if you genuinely need the names.
>
> Answer from what the structure actually says, and be straight about what it does
> not cover: if the question falls outside this material, say so plainly rather
> than guessing. Present the answer as ordinary scholarly knowledge, citing papers
> by name; reveal nothing about this atlas.

Two sentences in there do real work. *"all four matter equally"* stops the model
treating `contradicts` as an exception to be mentioned in passing. *"be straight
about what it does not cover"* is what the c01 control tests — and it held.

### 3.3 The twelve tools

Four broad, paper-shaped entry points, then eight narrow drill-downs retained from
the v1 surface. **Filters are arguments, not tools**: `relation='contradicts'`,
`intent='uses_extends'`. There is deliberately no `papers_building_on` endpoint —
a tool named after the shape of q01 would be a question-shaped API, and the same
filter serves "what contradicts X" and "what refines X" without encoding anything
about these eight questions.

**Entry points**

| tool | arguments | returns |
|---|---|---|
| `find_paper` | `query` | up to 5 papers matched by title / author / venue. Refuses below a coverage threshold — this is what makes c01 work |
| `paper_neighbourhood` | `paper_id`, optional `relation`, optional `intent` | one call: the paper's contributions, the typed relations touching them as **labels**, its citations ranked by intent, and every count precomputed |
| `edge_reasons` | `paper_id`, optional `others[]`, optional `relation`, `max_items` (default 6) | the **full recorded justification** behind specific typed edges, batched — six edges cost one call |
| `topic_structure` | `query` | search *and* the typed relations around the best-matching contributions, in one call. For questions about an area rather than a named paper |

**Drill-downs**

| tool | arguments | returns |
|---|---|---|
| `overview` | — | sizes, relation-type counts, intent counts, most-connected contributions. Orientation only |
| `search_contributions` | `query` | keyword search over the 581 contribution statements, best 8 |
| `get_paper` | `paper_id` | identity, abstract, contribution list |
| `get_contribution` | `contribution_id` | statement, kind, grounding quote, paper |
| `get_edges` | `contribution_id` | full typed relationships around one contribution — relation, direction, reason, intent |
| `get_neighbors` | `contribution_id` | adjacency list, typed edges only. Cheaper than `get_edges` |
| `get_citations` | `paper_id` | every citation link touching a paper, with intent, support/priority, site count |
| `citations_between` | `paper_id_a`, `paper_id_b` | site-level citation detail: the justifications and the passages |

### 3.4 The four rules the surface obeys

The v3 surface is an **envelope** change: same graph, same edges, same intents,
same counts, fewer characters. The line that keeps it honest is between *rendering
the data model faithfully and compactly* (engineering) and *reshaping what the tool
returns until the metric improves* (tuning). The test is whether the rules can be
stated from the data model alone, without reference to the outcome. They were, and
they were committed before the re-run:

1. **The envelope is not data.** A list row is one line, not a JSON object
   re-spelling `title` / `year` / `intents` / `n_sites` / `paper_id` on every row.
   Measured on The AI Scientist node: 190 chars/row → 58.
2. **Abstracts are not part of the graph.** The contribution statements *are* the
   distilled claim; shipping both pays twice for one thing. Still one `get_paper`
   call away. (−1,919 chars on that node.)
3. **Edges carry labels; justifications are fetched on request, batched.** v2
   truncated *every* reason to 320 chars — the median reason is 1,095 — and
   shipped them all whether wanted or not. v3 ships labels, and `edge_reasons`
   returns the full text for the edges that matter. Fewer characters *and* more
   evidence where it counts.
4. **Counts before lists.** Every count covers all links. Only the *enumeration*
   of routine `background` citations is deferred; `intent='background'` lists
   them. Nothing is hidden — the number is right there.

Measured offline, zero cost:

| | v2 | v3 | |
|---|---:|---:|---|
| `paper_neighbourhood` (The AI Scientist) | 19,390 | 5,756 | 3.4× |
| `topic_structure` (q02's query) | 9,709 | 3,995 | 2.4× |
| q01's whole trace, same exploration shape | 47,843 | 23,819 | 2.0× |

Rule 3 has a side effect worth more than the bytes: **the exploration trace
becomes meaningful.** Under v2 a paper "touched" by the graph arm might merely
have been one of 40 rows dumped into context — q01 touched 60 of 152 papers that
way. Under v3 a node was either *listed* or *deliberately read* (its justification
requested by id), and the log distinguishes them. That distinction is the entire
basis of the trace figures; see [visualisations_explained.md](visualisations_explained.md).

### 3.5 What it actually did

54 calls over 8 questions. Payload by tool, across the whole run:

| tool | calls | total chars | mean |
|---|---:|---:|---:|
| `paper_neighbourhood` | 19 | 81,376 | 4,282 |
| `edge_reasons` | 7 | 48,513 | 6,930 |
| `search_contributions` | 5 | 24,098 | 4,819 |
| `topic_structure` | 5 | 19,515 | 3,903 |
| `citations_between` | 4 | 12,111 | 3,027 |
| `find_paper` | 12 | 6,739 | 561 |
| `get_paper` | 1 | 3,016 | 3,016 |
| `get_contribution` | 1 | 897 | 897 |
| **total** | **54** | **196,265** | |

Per question, in order, with the characters each call returned:

| q | trace |
|---|---|
| q01 | `find_paper`(1,361) → `paper_neighbourhood`(5,940) → `edge_reasons`(8,386) → `citations_between`(6,662) → `citations_between`(1,756) → `citations_between`(1,824) |
| q02 | `topic_structure`(3,709) → `search_contributions`(4,643) → `find_paper`×3 (1,524) → `paper_neighbourhood`×4 (16,681) → `edge_reasons`(6,745) → `find_paper`(1,115) → `paper_neighbourhood`(3,716) |
| q03 | `topic_structure`(4,313) → `search_contributions`(4,934) → `find_paper`×2 (629) → `paper_neighbourhood`×5 (23,760) → `edge_reasons`(11,642) → `edge_reasons`(2,298) |
| q04 | `find_paper`(1,467) → `paper_neighbourhood`(3,801) → `edge_reasons`(7,895) → `citations_between`(1,869) |
| q05 | `topic_structure`(3,469) → `search_contributions`(4,850) → `topic_structure`(4,597) → `paper_neighbourhood`×4 (15,206) → `edge_reasons`(3,540) → `get_contribution`(897) |
| q06 | `find_paper`(284) → `paper_neighbourhood`(4,099) → `edge_reasons`(8,007) → `paper_neighbourhood`(3,555) → `paper_neighbourhood`(4,618) |
| c01 | `topic_structure`(3,427) → **`find_paper`(32)** → `search_contributions`(4,898) → `search_contributions`(4,773) → **`find_paper`(32)** |
| c02 | `find_paper`(295) → `get_paper`(3,016) |

Three things to read off that table.

**q01 and q04 are the intended v3 shape**, exactly as the system prompt describes:
locate, get the shape, then one batched evidence pull. q01 then spent three
`citations_between` calls checking specific citation links at site level — one
call over the registered prediction, and a real miss, but defensible behaviour
rather than thrashing.

**The two 32-character `find_paper` results on c01 are the control working.**
That is the corpus refusing a query — AlphaFold and protein binder design are
entirely outside the 152 papers. The arm then tried two contribution searches,
found nothing relevant, named two corpus papers as the nearest adjacent work with
`confidence: low`, and declined. It did not invent a structural-biology
literature. That is the single most valuable measurement in the experiment, and it
is why the graph arm's c01 groundedness of 2.7 is a *pass*, not a failure.

**c02 is depth honesty, in two calls.** PaperBench *is* in the corpus, so
`find_paper` resolved it and `get_paper` returned the abstract and contributions —
but the bundle holds no results tables. The arm identified the paper, gave what
the abstract supports, and declined on the numbers.

---

## 4. The WEB arm

### 4.1 The system prompt

Deliberately thin. The graph arm needs an explanation of an atlas it has never
seen; a browser needs no such thing, and padding the web prompt to match length
would be handicapping it in the other direction. Verbatim from `qa_arms.WEB_SYS`:

> You are a researcher with a web browser: use WebSearch/WebFetch and your own
> knowledge to answer the question and ground it in real papers. When you write the
> answer, cite the papers by name and reveal nothing about your search process.

### 4.2 What it read

`WebSearch` and `WebFetch`, Claude Code's built-in tools, live network. Nothing
else — same seal as everything else, `off_arm_tools` empty on all 8 rows.

| tool | calls | total chars | mean |
|---|---:|---:|---:|
| `WebSearch` | 33 | 100,905 | 3,058 |
| `WebFetch` | 13 | 13,607 | 1,047 |
| **total** | **46** | **114,512** | |

That second row matters for §6. Across the whole experiment the web arm fetched
thirteen pages and got about a thousand characters back from each. **88% of what
this arm read was search-result snippets**, not papers. It is steering parametric
memory with titles, dates and one-line summaries — which is a perfectly good way
to answer these questions, and is exactly what a researcher with a browser does in
five minutes, but it is not "reading the literature".

---

## 5. The NULL arm

One MCP tool, `submit_answer`. No graph, no browser, nothing. Verbatim from
`qa_arms.NULL_SYS`:

> Answer the researcher's question from your own knowledge of the literature. Cite
> the papers by name. Be precise about what you actually know versus what you are
> inferring, and do not invent papers, findings or numbers to fill a gap.

It reads 0 payload chars by construction, and it still scores **6.11 groundedness
and 7.17 correctness** on the structural set. Hold onto that number — it is the
one that reframes the whole efficiency question.

---

## 6. Why the compactness prediction failed

*The registered prediction (PLAN §3): the graph arm's ingestion drops below the
web arm's on q01–q06, and it makes fewer tool calls on the paper-named questions.
Both were written down before the run.*

**Outcome: falsified, twice, on two successive tool surfaces.**

| | GRAPH | WEB | |
|---|---:|---:|---|
| payload chars / answer | 24,533 | 14,314 | graph **1.71× more** |
| exploration calls / answer | 6.8 | 5.8 | graph **more** |
| cost / answer | $0.236 | $0.447 | graph **half** |
| papers named / answer | 7.1 | 5.5 | graph more |

The compactness claim failed. The *efficiency* claim — fewer turns, lower cost —
held. Those are different claims and were registered separately, which is the only
reason it is possible to say cleanly which one broke.

### 6.1 Three reasons it failed

**(a) The gap is mostly the evidence we deliberately added.** `edge_reasons`
accounts for **48,513 of the graph arm's 196,265 characters — 25% of everything
it read**. That is full recorded justification prose, median 1,095 characters per
edge, for edges the model chose by id. The web arm has no counterpart: its 13
`WebFetch` calls returned 13,607 characters *in total*. Strip `edge_reasons` and
the graph arm sits at **18,469 chars/answer against web's 14,314 — 1.29×, not
1.71×**. Most of the "excess" is the one thing v3 was built to deliver.

Which exposes the flaw in the metric: `payload_chars` counts bytes, and bytes are
not evidence. A 6,930-character `edge_reasons` result and a 6,930-character page
of search snippets are the same number and not remotely the same thing.

**(b) The prediction assumed one neighbourhood call per question. The model made
2.4.** 19 `paper_neighbourhood` calls over 8 questions; q03 alone opened five
neighbourhoods before reading a single justification. That is legitimate — it is
what a researcher does when the graph keeps surfacing adjacent papers — but it
means payload scales with **how interesting the structure is**, not with how well
it is serialised. A compact API does not make a model incurious. The v2 estimate
of "12 calls / 89,201 chars for all 8 questions" was wrong for exactly this
reason, and the v3 pilot missed its call-count target by one for the same reason.

**(c) The web arm reads less because search delivers less, not because search is
compact.** This is the point the null arm settles. The null arm reads **zero**
characters and still scores 6.11 groundedness. The web arm reads 14,314 and scores
7.94. So roughly speaking, web's entire payload buys +1.83 groundedness over what
the model already knew, and 88% of that payload is snippets. "Fewer characters" is
here a symptom of a thinner environment, not evidence of a denser one.

### 6.2 So is Prior a compact representation?

Two claims were tangled together and need separating.

**Compact per byte returned to the model — no, and this experiment says so
plainly.** v3 made the envelope 2.0–3.4× smaller and the arm spent the savings on
more calls and more evidence. If the claim is "Prior sends less into context than
a web search does", the claim is false on this evidence, and it should be dropped
rather than defended.

**Compact per fact established — yes, and it is demonstrable, but this experiment
did not pre-register it and so cannot claim it cleanly.** q01 is the sharpest
case: 25,929 characters separated **7 genuine methodological extensions from 53
routine background citations** on a paper with 59 citation links, and every one of
the 19 titles it named resolves to the corpus. The web arm spent a comparable
23,099 characters, named 8 papers, and its own `limits` field admits it "could not
exhaustively verify every paper that cites The AI Scientist… this should be
treated as a well-supported list of the clearest cases rather than a complete
census". Those two payloads are the same size and answer different questions: one
of them has a denominator.

**The honest summary: the atlas is a higher-yield environment, not a
lower-volume one.** The pre-registered claim was about volume. It was the wrong
claim to register — volume was measurable, so it got measured, and specificity per
byte is what actually mattered. That is a real methodological error, and stating
it is more useful than the finding it replaced.

### 6.3 What broke in the measurement itself

Two instrument failures, both found and both kept in the record rather than
quietly dropped.

**`tokens_in` was demoted from headline metric.** It was pre-registered as *the*
efficiency number and it broke on the first v3 row. On q01/graph, v2→v3:
`payload_chars` fell 47,843 → 25,929 (about 5,500 tokens less material) while
`cache_creation` **rose by 27,345 tokens**. A 27k rise cannot be caused by
ingesting 5.5k fewer tokens, so `tokens_in` is not measuring ingestion — it is
charging cache *writes*, which track how the conversation prefix was re-chunked
across turns. v2 pulled one 20k blob early and coasted on cheap cache reads; v3
pulled six medium results, so the growing prefix was re-committed more often.

Three metrics are now reported for every row, in descending order of
trustworthiness, and **all three appear in RESULTS.md including the one that
broke**:

| metric | computed by | what can move it for the wrong reason |
|---|---|---|
| **`payload_chars`** *(headline)* | our own `run_one`, summing what the tools returned | nothing in the harness |
| `context_total` | harness usage: input + cache_creation + cache_read | nothing much — it is the total the model processed |
| `tokens_in` *(retained, not headline)* | harness usage: input + cache_creation | caching: it charges cache writes, which track prefix re-chunking, not ingestion |

This is the second time an efficiency metric moved against the graph arm and was
then revisited, which is a pattern to be suspicious of. What separates it from
motivated reasoning: the disqualifying evidence is an **internal contradiction in
the instrument** (payload down, cache_creation up five times more than payload
fell), not a preference about the result; and the demoted metric stays in the
table with this explanation attached.

**A per-query usage bug under-counted every nudged row.** `ResultMessage.usage`
and `total_cost_usd` are **per-query**, not session-cumulative — proved by
`q03/web`, which made four search calls yet whose last `ResultMessage` reports
`web_search_requests: 0`, because those happened in the first query. `run_one` now
sums usage across queries and takes the max for `num_turns`.

### 6.4 The judging side of the cost story

Efficiency and judging are deliberately disconnected, and it is worth being
explicit about that because it is what stops the two contaminating each other.

**The judge sees none of this.** It receives the question and three anonymised
answers with their `papers_named`, `confidence` and `limits` — and nothing else.
No payload counts, no costs, no tool call counts, no turn counts, no arm labels.
So no efficiency metric can leak into a score, and equally, a good score can never
be used to retrospectively justify a payload. See [JUDGING.md](JUDGING.md).

**But the judge is where the *budget* prediction failed.** PLAN §6 registered
≈$11 for "24 generations and 8 judgements". Generation came in near estimate at
$7.23. Judging came in at **$4.53 — because there were 24 judgements, not 8.**
The judge was tripled after an accidental replication showed 7 of 27 axis scores
moving by a point on unchanged answers and one winner of three flipping. Measuring
the instrument's own noise was worth three times the judging budget; the whole
experiment still landed at $11.76 against an ≈$11 estimate.

One reporting bug came out of that change: `report.py` summed judging cost over
the **consensus** rows, of which there is one per question, so it counted one run
in three and printed $1.62 where the truth was $4.53. Fixed. Cost never supports a
claim here, so nothing else moved.

**And cost moves opposite to payload, which is the last reason not to conflate
them.** The graph arm reads the most and costs the least ($0.236/answer against
web's $0.447). Atlas calls are local, in-process and cached; `WebSearch` and
`WebFetch` carry a server-side charge per call. Any argument that uses one of
these numbers as a proxy for the other is broken in this dataset, in both
directions.

---

## 7. Replaying what the graph arm did

Because the atlas is local and deterministic, **re-issuing the logged `tool_args`
returns exactly the rows the agent saw** — a replay, not a reconstruction. That is
what makes the trace figures evidence rather than illustration, and it is
available at zero cost after the fact:

```bash
python trace.py                       # all 8 questions -> out/traces/*.svg|json|md
python trace.py --questions q01 --png # one, plus a PNG
```

`out/traces/<qid>.md` is the call-by-call narrative including the **full
justification text of every edge the arm actually read** — the document to open
when someone asks whether `contradicts` means anything. How to read the figures:
[visualisations_explained.md](visualisations_explained.md).

---

## 8. Reproducing the generation half

Costs subscription credit — **run it in your own terminal**, never from an agent.
Checkpointed on `(question_id, arm)`, Ctrl+C safe, resumes into only what is
missing.

```bash
python qa_arms.py --selftest   # free: asserts the wiring and the seal, no model call
python qa_gen.py --dry-run     # free: prints the assembled prompts and the plan
python qa_gen.py --limit 1     # one question, all three arms (~$0.90)
python qa_gen.py               # all 24 units (~$7.20)
```

Useful flags: `--arm graph|web|null`, `--questions q01,q03`, `--budget` (per-answer
cap, default $1.20 — a runaway guard, not a target), `--sleep`, `--prune` (move
no-answer rows out of the checkpoint so they re-run), `--drop q04:graph` (archive a
completed-but-unusable row to `out/dropped.jsonl` so it re-runs).

To ask your own question instead of the eight, see `ask.py` and the
[README](README.md).
