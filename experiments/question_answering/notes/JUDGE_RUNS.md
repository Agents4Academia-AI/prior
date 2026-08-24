# The three order-swapped judge runs

> **Superseded by [../JUDGING.md](../JUDGING.md)**, which absorbs this and adds the
> prompts, the rubric and the schema. Kept as the contemporaneous record of the
> 2026-08-22 run.

*Callum, 2026-08-22. Every question was judged three times, each time with the arms
presented in a different order. This records what was actually run and what came out,
because it was only ever described as a design in [PLAN.md](../PLAN.md) §4 and never written
up. Everything here is recomputed from `out/qa_judgements.jsonl`, not copied from
`../RESULTS.md`.*

---

## 0. What was run

| | |
|---|---|
| judgements | **24** = 8 questions × 3 runs |
| judge | `claude-opus-5`, blind, sealed (`tools=[]`, `setting_sources=[]`, `skills=[]`) |
| what it sees | all three answers in one call, anonymised A / B / C |
| scored | groundedness, correctness, usefulness, 1-10 each, plus flags and a forced ranking |
| errors | **0** |
| checkpoint key | `(question_id, run)`, so a partly-judged question resumes into only its missing runs |
| cost | **$4.53** for all 24 |

Run 0 predates the `--repeats` flag and carries no `run` field, which `report.py` treats as
run 0. Runs 1 and 2 came from `qa_judge.py --repeats 3`.

## 1. The order swap, and why it is exactly balanced

The base presentation order for a question is one of the 6 permutations of
(graph, web, null), assigned by the question's index in the list. Each repeat then
**rotates that base**, rather than drawing a fresh permutation. At 3 repeats that makes
every arm appear in every slot exactly once per question:

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

Counted over all 24 judgements, arm × slot is **8 / 8 / 8 for every arm**:

| arm | slot A | slot B | slot C |
|---|---|---|---|
| graph | 8 | 8 | 8 |
| web | 8 | 8 | 8 |
| null | 8 | 8 | 8 |

That is the point of rotating rather than resampling. A position effect cannot ride along
with one arm, either within a question or across the set.

## 2. Per question, mean of the three runs

Groundedness / correctness / usefulness.

| q | expected | GRAPH | WEB | NULL | winner (vote) | margin |
|---|---|---|---|---|---|---|
| q01 | graph | **9.0** / 8.0 / **9.0** | 8.0 / 7.7 / 8.0 | 7.0 / 7.7 / 5.7 | graph 3/0/0 | slight |
| q02 | graph | **8.7** / 8.0 / **8.7** | 8.0 / **9.0** / 8.0 | 6.0 / 8.0 / 6.0 | graph 3/0/0 | slight |
| q03 | graph | **9.0** / 8.0 / **9.0** | 8.3 / 8.0 / 8.3 | 7.0 / 7.7 / 7.3 | graph 3/0/0 | slight |
| q04 | graph | 8.0 / **7.7** / 7.7 | 8.0 / 4.7 / 7.7 | 5.3 / 8.0 / 4.0 | graph 3/0/0 | slight |
| q05 | graph | **9.0** / **8.7** / 8.0 | 7.0 / 7.7 / 8.0 | 5.7 / 3.7 / 5.3 | graph 3/0/0 | slight |
| q06 | graph | 8.0 / 5.0 / 7.3 | **8.3** / **8.3** / **8.3** | 5.7 / 8.0 / 5.0 | **web** 0/3/0 | clear |
| c01 | web | 2.7 / 7.7 / 2.7 | **8.0** / 7.7 / **9.0** | 8.0 / **8.3** / 8.0 | web 0/3/0 | slight |
| c02 | web | 7.3 / **8.3** / 6.7 | **8.3** / 7.0 / **8.7** | 5.7 / 5.7 / 5.3 | web 0/3/0 | clear |

**Set means** (mean over runs, then over questions). Controls are never pooled with the
structural set, for the reason in PLAN §5.

| set | arm | groundedness | correctness | usefulness |
|---|---|---|---|---|
| structural, n=6 | GRAPH | **8.61** | 7.56 | **8.28** |
| | WEB | 7.94 | 7.56 | 8.06 |
| | NULL | 6.11 | 7.17 | 5.56 |
| controls, n=2 | GRAPH | 5.00 | 8.00 | 4.67 |
| | WEB | **8.17** | 7.33 | **8.83** |
| | NULL | 6.83 | 7.00 | 6.67 |

**Lift over the closed-book arm, structural only.** This is the number that says what each
environment is worth, and `graph − web` alone cannot.

| arm | Δ groundedness | Δ correctness | Δ usefulness |
|---|---|---|---|
| GRAPH | **+2.50** | +0.39 | **+2.72** |
| WEB | +1.83 | +0.39 | +2.50 |

## 3. How stable the judge actually is

This is the whole reason for running three times, and it is the part that should govern how
hard anyone leans on the scores.

| q | widest single-axis spread across the 3 runs | winner unanimous? |
|---|---|---|
| q01 | 1 pt (web correctness 7-8) | yes |
| q02 | 1 pt (graph groundedness 8-9) | yes |
| q03 | 1 pt (web groundedness 8-9) | yes |
| q04 | 1 pt (graph correctness 7-8) | yes |
| q05 | 2 pt (web usefulness 7-9) | yes |
| q06 | 2 pt (graph correctness 4-6) | yes |
| c01 | 1 pt (graph groundedness 2-3) | yes |
| c02 | 3 pt (null correctness 4-7) | yes |

- **8 of 8 questions had a unanimous winner.** No question needed the `split` verdict.
- **Median widest spread is 1 pt.** Worst is 3 pt, on the null arm's correctness for c02.
- The judge called **19 of 24** margins `slight` and 5 `clear`.

**What that licenses.** The winner is stable: three independent presentations, three times
the same answer, on every question. What is *not* stable at the 1-point level is the gap
between graph and web on the structural set, which is 0.67 on groundedness and 0.22 on
usefulness. Both sit at or below the noise floor. So the defensible reading is the **lift
over null** (+2.50 against +1.83, comfortably above 1 pt) and the **direction of the
result**, not a graph-minus-web score.

`prediction_hit` is true on **21 of 24** rows. All three misses are q06, where the atlas
was predicted to win and web won all three times, on a content error: the graph arm claimed
The AI Scientist v1 used AIDE-style tree search, when v1 used Aider plus fixed templates.
Its correctness mean is 5.0 there, the lowest score any arm received on a structural
question.

## 4. Honesty flags, by majority of the three runs

A flag counts only if at least 2 of the 3 runs set it. Counts are out of 8 questions.

| flag | GRAPH | WEB | NULL |
|---|---|---|---|
| `fabricated` | 1 | 1 | 1 |
| `unrecognised` | 6 | 6 | 0 |
| `hedged` | 1 | 0 | 2 |
| `overclaimed` | 0 | 0 | 0 |

`unrecognised` carries no penalty by design (PLAN §4): 32% of the corpus is dated 2026 and
eight papers postdate the judge's training data, so "I have not heard of this" is not
evidence that a paper does not exist. Existence is settled mechanically instead:
`verify_named.py` resolves every title the graph arm named against the 152-paper corpus and
**0 of 57 failed** *(this file originally said 62; the correct denominator from `verify_named.py` is 57 — see ../JUDGING.md §10)*. That check is not available for web or null, and the asymmetry runs
*against* the graph arm rather than for it.

## 5. A reporting bug found while writing this up

`report.py` prints `Judging total` by summing `total_cost_usd` over the **consensus** rows,
of which there is one per question, so it counted one run in three. It reported **$1.62**
where the true figure across all 24 judgements is **$4.53**. Fixed. Cost is a footnote and
never supports a claim here (PLAN §5), so nothing else moves.

## 6. Where the data is

| | |
|---|---|
| raw judgements | `out/qa_judgements.jsonl`, 24 rows, one per (question, run) |
| rendered report | `../RESULTS.md`, means and majority winners |
| judge v1 rubric | `out_judge_v1/qa_judgements_v1.jsonl`, kept for comparison (PLAN §4) |
| re-run | `python qa_judge.py --repeats 3`, checkpointed on `(question_id, run)` |

Everything in this file was recomputed from the raw jsonl, so it can be regenerated
independently of `report.py`.
