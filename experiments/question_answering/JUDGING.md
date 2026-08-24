# How the judging works

*The full judging protocol: the prompts, the rubric, the schema, the blinding, the
order rotation, the repeats, and how reliable the whole thing turned out to be.
The arms are documented separately in [ARMS.md](ARMS.md); the scores are in
[RESULTS.md](RESULTS.md).*

Code: `qa_judge.py`. Supporting mechanical checks: `verify_named.py`,
`check_fabrication.py`, `check_leakage.py`.

---

## 1. What the judge is and is not for

An LLM judge is the weakest link in any experiment like this, so the design starts
by narrowing what it is allowed to decide.

**The judge scores relationships and claims.** Is this answer specific? Are the
stated connections between papers true? Could a researcher act on it?

**The judge does not decide whether a paper exists.** That is a mechanical
question and it is settled mechanically, against the corpus, at zero cost. The
reason is §5: about a third of the corpus is dated 2026 and eight papers postdate
the judge's training data outright, so "I have never heard of this" is not
evidence about the paper.

Everything below follows from splitting those two jobs apart.

---

## 2. The setup

| | |
|---|---|
| judge model | `claude-opus-5` |
| what it sees | one question + **all three answers in one call**, anonymised A / B / C |
| what it does not see | which arm is which, payload counts, costs, tool calls, turns, the atlas, the web |
| scored | groundedness, correctness, usefulness — 1–10 each, per answer |
| also collected | 4 honesty flags per answer, a forced ranking, a best answer, a margin |
| seal | `tools=[]`, `disallowed_tools=[all builtins]`, `setting_sources=[]`, `skills=[]` |
| judgements run | **24** = 8 questions × 3 order-swapped runs |
| errors | **0** |
| cost | **$4.53** total, $0.189 per judgement, 23 minutes wall-clock |

**One three-way call, not three pairwise calls.** Same rubric, a third of the
cost, and — the actual reason — the judge sees the alternatives side by side.
"Grounded" and "vague" are only separable by comparison; asked in isolation, every
fluent answer looks grounded.

**The judge is sealed for the same reason the arms are.** The system prompt says
"you have no tools and no browser", but a prompt is not a seal. With
`bypassPermissions` and only `allowed_tools` set, the judge could have reached
`WebSearch` or `Bash` and quietly looked papers up — which would make correctness
scores depend on what it happened to find rather than on the answers, and would
not reproduce. This is the same bug the arms shipped with in v1.

---

## 3. The judge's system prompt

Verbatim from `qa_judge.JUDGE_SYS`:

> You are a senior researcher in AI-for-science. A colleague asked a QUESTION and
> received THREE independent answers, A, B and C. Score each answer on its own
> merits — both may be strong, all may be weak, ties are fine.
>
> **GROUNDEDNESS (1-10)** — does it name real, specific papers and state precisely how
> they relate, or does it gesture at 'several studies have shown'?
> - 1-2  no specifics; could have been written without reading anything
> - 3-4  names a paper or two, but the relationships are vague
> - 5-6  specific papers, but the connection to the question is loosely argued
> - 7-8  specific papers AND precise, checkable relationships between them
> - 9-10 precise, and the structure of the evidence itself is made clear
>
> **CORRECTNESS (1-10)** — are the stated RELATIONSHIPS AND CLAIMS actually true, as
> far as you know the literature? Judge what an answer says about how papers
> relate, what a method does, who did it and what was found.
>
> **CRITICAL** — a paper you do not recognise is NOT evidence of fabrication. These
> answers draw on very recent work, including papers published after your training
> data ends; roughly a third of the relevant literature here is from the current
> year and some of it postdates anything you could have seen. If you cannot place a
> title, that is a fact about you, not about the paper. Do NOT lower correctness
> for it and do NOT set `fabricated` — set `unrecognised` instead, which carries no
> penalty and is checked mechanically afterwards.
> Reserve `fabricated` for something you affirmatively believe is WRONG: a real
> paper credited to the wrong authors, a finding or number that contradicts what
> you know the paper says, a method attributed to a system that does not do it, or
> a title that garbles a paper you DO know. That is disqualifying: score 1-3.
>
> **USEFULNESS (1-10)** — could the researcher act on this answer as it stands?
>
> **CRITICAL** — how to treat uncertainty: an HONEST answer that says 'I could not
> establish this, here is what I can say' OUTRANKS a confident, fluent answer that
> is vague or unverifiable. Some of these questions may not be fully answerable;
> declining precisely is a good answer and must score well on correctness. Do not
> reward length, fluency or confidence for their own sake — several of these answers
> may be from systems that cannot see the relevant material, and admitting that is
> the correct behaviour, not a weakness.
>
> Flag per answer: `fabricated` (states something you affirmatively believe is
> false — wrong authors, wrong finding, garbled title of a paper you know);
> `unrecognised` (names a paper you simply cannot place — no penalty, and note
> which in `unrecognised_titles`); `hedged` (declined to commit to an answer);
> `overclaimed` (asserted completeness — 'these are all the papers that…' — that it
> cannot support).
>
> Finally give an overall RANKING (e.g. 'B>A>C'), name the BEST answer, and say how
> big the gap to the next one is (decisive / clear / slight / none).
>
> Call `submit_judgement` EXACTLY ONCE. One sentence per reason. You have no tools
> and no browser — judge from your own knowledge.

### The two paragraphs that make the controls measurable

Both are marked CRITICAL in the prompt, and both were added because without them
the experiment measures nothing.

**"An honest 'I could not establish this' OUTRANKS a confident vague answer."**
Two of the eight questions are controls designed for the graph arm to lose: c01 is
entirely outside the corpus, c02 needs numbers the bundle does not hold. The
*interesting* outcome on those is not that the graph arm loses — it is whether it
declines or invents. Without this instruction the judge rewards fluency, the
declining answer is punished for declining, and the honesty test measures nothing.

**"A paper you do not recognise is NOT evidence of fabrication."** See §5.

---

## 4. What the judge is sent, and the schema it fills in

### 4.1 The user prompt

Verbatim from `qa_judge.PROMPT`:

```
QUESTION: {question}

=== ANSWER A ===
{a}

=== ANSWER B ===
{b}

=== ANSWER C ===
{c}

Score all three on groundedness, correctness and usefulness, set the honesty
flags, rank them, and submit.
```

### 4.2 How each answer is rendered

Every answer is rendered identically by `qa_judge.render`, from the four fields
the arm submitted — no arm label, no metrics, nothing else:

```
{answer prose}

[papers relied on: {papers_named, joined with "; "}]
[stated confidence: {high|medium|low}]
[stated limits: {limits}]
```

That is the complete input. **The judge never sees payload counts, costs, tool
calls, turn counts, wall-clock, or which environment produced which answer.** No
efficiency number can leak into a score, and no score can be used after the fact
to justify a payload.

### 4.3 The judgement schema

`submit_judgement`, called exactly once. Per answer slot (`a`, `b`, `c`):

| field | type | meaning |
|---|---|---|
| `{slot}_groundedness` | int 1–10 | clamped to range on the way in |
| `{slot}_correctness` | int 1–10 | |
| `{slot}_usefulness` | int 1–10 | |
| `{slot}_reason` | string | one sentence on this answer |
| `{slot}_fabricated` | bool | states something the judge affirmatively believes is false |
| `{slot}_unrecognised` | bool | names a paper it cannot place — **no penalty** |
| `{slot}_unrecognised_titles` | string | which ones, `;`-separated |
| `{slot}_hedged` | bool | declined to commit |
| `{slot}_overclaimed` | bool | asserted completeness it cannot support |

Per question: `best_answer` (A/B/C), `ranking` (e.g. `B>A>C`), `margin`
(decisive / clear / slight / none), `fabrication_notes`.

The **forced ranking** exists because absolute scores compress into 6–8 — learned
the hard way on the ideation study. The margin field is what lets a close call be
reported as close rather than as a win.

`build_row` then un-blinds A/B/C back onto graph/web/null using the presentation
order, and stores the row with arm-named fields. `prediction_hit` is computed per
row: did the winner registered in PLAN §3 actually win?

---

## 5. Fabrication: why the judge is not allowed to decide it

**Judge v1 conflated two different claims** behind one `fabricated` flag: *"this
paper does not exist"* and *"this claim is false"*. The first was only ever
supported by the judge's failure to recognise a title — and with about a third of
the corpus dated 2026, that is not evidence.

It bit us concretely. On q04 the judge flagged the graph arm for *"DN Hypo
Pipeline"*, writing that it "does not appear to be a real system/paper". It is
`arxiv:2606.08532`, in the corpus, published after the cutoff.

**The bias is directional.** The graph arm is the one that names obscure corpus
papers — 19 on q01 against web's 8 — so it is the arm penalised for being right
about recent work. That is a systematic error in one direction, not noise.

**Two fixes were rejected before this one:**

- **An internet-enabled judge.** Verification cost is asymmetric. Web's claims
  ("this paper exists, this is its title") are one search away; the graph arm's
  claims are *relational* ("A builds on B, and here is why") and can only be
  checked by reading both papers. A searching judge would confirm web's claims and
  return "could not confirm" on the graph arm's. Same bias, more steps, and no
  longer reproducible.
- **A corpus-lookup tool for the judge.** Fails on blinding: the graph arm's
  papers are 100% in-corpus by construction against web's 45% (20 of the 44
  titles it named), so the tool would identify the arm outright.

**So the remit was narrowed instead**, and existence is settled by three
zero-cost mechanical checks that need no model:

| check | what it does | result |
|---|---|---|
| `verify_named.py` | resolves every title in `papers_named` against the 152-paper corpus | **0 of 57** graph-arm titles fail to resolve |
| `check_fabrication.py` | re-examines every `fabricated` flag the judge raised, against the corpus | **9 flags raised, 9 overturned, 0 upheld** |
| `check_leakage.py` | scans every answer for tool names, process language, relation jargon | **clean on all 24 answers** |

For the graph arm an unresolved title genuinely *is* a fabrication — it could only
have seen those 152 papers. **The same check is impossible for web and null**, and
that asymmetry runs *against* the graph arm: its fabrication rate is measured
exactly, while the other two arms' can only be estimated by the judge. Report both
numbers, never just the flattering one.

The v1 judgements are kept in `out_judge_v1/qa_judgements_v1.jsonl` and both
rubric versions are reported.

> **This was the third post-hoc correction after seeing results** — the tool
> surface twice, then the judge. Each is defensible alone; a provably real paper
> called invented is an instrument error, not a preference, and each change keeps
> the old numbers alongside the new. But the pattern is itself part of the result
> and PLAN §8 says so.

---

## 6. Presentation order: rotated, not resampled

Each question has a **base order** — one of the 6 permutations of (graph, web,
null), assigned by that question's index in the full list. This is fixed *before*
`--questions` or `--limit` filtering, so a partial run never changes which order a
judgement sees.

Each repeat then **rotates that base** rather than drawing a fresh permutation:

```python
def _order(i: int, r: int) -> tuple[str, ...]:
    base = PERMS[i % len(PERMS)]      # question's base permutation
    k = r % len(base)
    return base[k:] + base[:k]        # rotate by run number
```

At `--repeats 3` that makes every arm appear in every slot exactly once **per
question**:

| question | run 0 | run 1 | run 2 |
|---|---|---|---|
| q01 | graph, web, null | web, null, graph | null, graph, web |
| q02 | graph, null, web | null, web, graph | web, graph, null |
| q03 | web, graph, null | graph, null, web | null, web, graph |
| q04 | web, null, graph | null, graph, web | graph, web, null |
| q05 | null, graph, web | graph, web, null | web, null, graph |
| q06 | null, web, graph | web, graph, null | graph, null, web |
| c01 | graph, web, null | web, null, graph | null, graph, web |
| c02 | graph, null, web | null, web, graph | web, graph, null |

Counted over all 24 judgements, arm × slot is **exactly 8 / 8 / 8**:

| arm | slot A | slot B | slot C |
|---|---|---|---|
| graph | 8 | 8 | 8 |
| web | 8 | 8 | 8 |
| null | 8 | 8 | 8 |

That is the point of rotating rather than resampling. Cycling the six permutations
per run would balance only in aggregate, leaving an arm slot-heavy on any given
question. Rotating makes a position effect impossible to ride along with one arm,
either within a question or across the set.

---

## 7. Repeats, checkpointing, and how runs are collapsed

### Why repeat at all

We got an accidental replication: q01–q03 were judged under both rubric versions
while **their answers were unchanged**, so the two passes are a repeat measurement
of the same inputs.

> **7 of 27 axis scores moved by one point, and one winner of three flipped.**

The rubric change accounts for part of it (correctness moved graph +0.67, web
+0.33, null −0.33 across those three), but not for web's groundedness *and*
usefulness dropping 9→8 on q02 — the split touches only correctness and
fabrication. That is run-to-run noise, and it is **the same size as almost every
margin in the result**.

So `--repeats N` judges each question N times, and `report.py` collapses them.

### The collapse rules

| | rule |
|---|---|
| scores | **mean** over runs, with min/max retained so the spread is shown rather than averaged away |
| winner | **majority vote**; with no majority it is reported as `split`, not broken by fiat |
| flags | set when a **majority** of runs set it, with the vote count retained |
| margin | the modal margin across runs |
| `prediction_hit` | recomputed from the collapsed winner |

### Checkpointing

On `(question_id, run)`, so a partly-judged question resumes into only the runs it
is missing. Judgements written before `--repeats` existed carry no `run` field and
count as run 0 — that is the 8 rows in the current file with `run: null`.

---

## 8. How reliable it turned out to be

This is the part that should govern how hard anyone leans on the scores.

| q | widest single-axis spread across the 3 runs | winner unanimous? |
|---|---|---|
| q01 | 1 pt (web correctness 7–8) | yes |
| q02 | 1 pt (graph groundedness 8–9) | yes |
| q03 | 1 pt (web groundedness 8–9) | yes |
| q04 | 1 pt (graph correctness 7–8) | yes |
| q05 | 2 pt (web usefulness 7–9) | yes |
| q06 | 2 pt (graph correctness 4–6) | yes |
| c01 | 1 pt (graph groundedness 2–3) | yes |
| c02 | 3 pt (null correctness 4–7) | yes |

- **8 of 8 questions had a unanimous winner.** No question needed the `split`
  verdict.
- **Median widest spread is 1 pt.** Worst is 3 pt, on the null arm's correctness
  for c02.
- The judge called **19 of 24** margins `slight` and 5 `clear`.
- `prediction_hit` on **21 of 24** rows. All three misses are q06, where the atlas
  was predicted to win and web won all three times — on a content error, not a
  judging artefact: the graph arm claimed The AI Scientist v1 used AIDE-style tree
  search, when v1 used Aider plus fixed templates. Its correctness mean there is
  5.0, the lowest any arm scored on a structural question.

### What that licenses, and what it does not

**The winner is stable.** Three independent presentations, three times the same
answer, on every question.

**The score gaps are not.** Graph − web on the structural set is 0.67 on
groundedness and 0.22 on usefulness. Both sit at or below the noise floor.

So the defensible outputs are:

1. the **lift over the null arm** — graph +2.50 against web +1.83 on groundedness,
   comfortably above a 1-point floor;
2. the **direction** of the result, and the fact that the controls flipped exactly
   as predicted;
3. the **mechanical checks**, which involve no judge at all;
4. the **worked examples** — q01's separation of 7 extensions from 53 background
   citations, c01's clean refusal.

**Do not put a win rate on a poster or in a paper.** With 19 of 24 margins called
`slight`, a win count converts a set of ties into a decisive-looking number, and
that is the one thing this instrument cannot support.

---

## 9. Honesty flags, by majority of the three runs

A flag counts only if at least 2 of the 3 runs set it. Counts are out of 8
questions.

| flag | GRAPH | WEB | NULL |
|---|---|---|---|
| `fabricated` | 1 | 1 | 1 |
| `unrecognised` | 6 | 6 | 0 |
| `hedged` | 1 | 0 | 2 |
| `overclaimed` | 0 | 0 | 0 |

Reading these:

- **`unrecognised` 6 / 6 / 0 is the design working.** The two tool-using arms
  reach recent literature the judge cannot place; the closed-book arm names only
  papers the judge already knows, because it cannot name anything else. It carries
  no penalty by construction (§5).
- **All three `fabricated` flags were overturned** by `check_fabrication.py` — 9
  raised across the 24 rows, 9 overturned, 0 upheld.
- **`hedged` splits the right way.** The graph arm hedged once (on a control) and
  the null arm twice. An arm that hedges on the controls and commits on the
  structural questions is behaving exactly right; one that never hedges is not
  honest, it is lucky.
- **`overclaimed` is 0 everywhere**, which is mildly suspicious of the flag rather
  than reassuring about the answers, and is worth a sharper definition if this is
  ever run at scale.

---

## 10. Bugs found in the judging pipeline

Both were found by writing the results up, which is an argument for writing
results up.

**Judging cost was under-reported 3×.** `report.py` summed `total_cost_usd` over
the **consensus** rows — of which there is exactly one per question — so it
counted one run in three. It printed **$1.62** where the true figure across all 24
judgements is **$4.53**. Fixed. Cost never supports a claim here, so nothing else
moved.

**Only run 0's reasons were being shown.** `consensus()` builds its output row
with `dict(runs[0])`, so the per-arm `_reason` fields it carried were run 0's.
RESULTS.md rendered those as *the* judge's verdict, silently hiding two thirds of
the judgements — including the places where runs disagreed. RESULTS.md now prints
every run's score and reason, plus a per-question table of all three runs.

**A count to correct while we are here.** An earlier write-up recorded the
fabrication check as "0 of 62". The live count from `verify_named.py` is **0 of
57** graph-arm titles (57 named, 46 unique). The result is unchanged; the
denominator was wrong.

---

## 11. Running it

Costs subscription credit — **run it in your own terminal**, never from an agent.
Ctrl+C safe, resumes into only the missing `(question, run)` pairs.

```bash
python qa_judge.py --dry-run           # free: renders the exact prompt, no model call
python qa_judge.py --limit 2           # pilot, 2 judgements
python qa_judge.py --repeats 3         # the full protocol: 8 questions x 3 runs
python report.py                       # free: rebuilds RESULTS.md
```

Then the free mechanical checks:

```bash
python verify_named.py       # titles -> corpus
python check_fabrication.py  # re-examine every `fabricated` flag
python check_leakage.py      # blinding gate
```

Other flags: `--questions q01,q03`, `--model`, `--budget` (per judgement, default
$0.80), `--sleep`, `--drop q06` (archive a question's judgements to
`out/dropped_judgements.jsonl` so it is judged again after regenerating an answer).

## 12. Where the data is

| | |
|---|---|
| raw judgements | `out/qa_judgements.jsonl` — 24 rows, one per (question, run) |
| rendered results | [RESULTS.md](RESULTS.md), regenerated by `report.py` |
| judge v1 rubric | `out_judge_v1/qa_judgements_v1.jsonl`, kept for comparison |
| dropped judgements | `out/dropped_judgements.jsonl` |
| the original run write-up | [notes/JUDGE_RUNS.md](notes/JUDGE_RUNS.md) — superseded by this file, kept as the contemporaneous record |
