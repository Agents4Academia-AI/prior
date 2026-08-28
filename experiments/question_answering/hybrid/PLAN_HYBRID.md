# Hybrid arm: atlas + browser — a pilot

**An add-on to [`../README.md`](../README.md), not a revision of it.** Nothing in
the parent folder is modified. The three-arm experiment, its answers, its
judgements and its write-ups stay exactly as they were; this directory adds a
fourth environment and tests it on three of the eight questions.

**Registered before any model was called.** Predictions in §4 are written first
and left as written, whatever happens. The parent experiment already carries
three post-hoc design revisions ([`../PLAN.md`](../PLAN.md) §8) and that is the
main thing an examiner attacks; this one gets to be clean.

> **§8 records everything that changed after the first batch ran** — a harness
> bug that destroyed two answers, a routing-classifier fix, and the addition of
> q03. Sections 1–7 are left exactly as they were written beforehand.

---

## 1. The question

The three-arm result says the atlas wins where the answer *is* a piece of graph
structure, and loses where the answer is outside the corpus or inside a paper's
full text. Those are complementary failures, not a ranking. So: does an agent
with **both** the atlas and a browser beat the better of the two on its own?

### Where the headroom actually is

Mean judge scores over 3 runs, from [`../RESULTS.md`](../RESULTS.md):

| qid | family | graph G/C/U | web G/C/U | winner |
|---|---|---|---|---|
| q01 | builds-on | **9.0** / 8.0 / 9.0 | 8.0 / 7.7 / 8.0 | graph |
| q02 | disagreement | **8.7** / 8.0 / 8.7 | 8.0 / 9.0 / 8.0 | graph |
| q03 | disagreement | **9.0** / 8.0 / 9.0 | 8.3 / 8.0 / 8.3 | graph |
| q04 | uses-findings | 8.0 / **7.7** / 7.7 | 8.0 / **4.7** / 7.7 | graph |
| q05 | evidence-base | **9.0** / 8.7 / 8.0 | 7.0 / 7.7 / 8.0 | graph |
| q06 | lineage | 8.0 / **5.0** / 7.3 | 8.3 / 8.3 / 8.3 | web |

The graph arm already sits at 8.0–9.0 groundedness on the structural questions,
and the judge's own run-to-run spread is about 1 point
([`../JUDGING.md`](../JUDGING.md) §9). **On q02, q03 and q05 there is less
headroom than there is noise.** A hybrid tested there could not show anything
even if it worked perfectly. The subset is therefore chosen for diagnostic
value, and that choice is stated here rather than defended later.

---

## 2. The two hybrid variants

Both get **all 12 atlas tools plus `WebSearch` and `WebFetch`**, the same
`TASK`, the same blinding contract, the same seal, the same
`off_arm_tools` canary. They differ only in the system prompt.

| arm | system prompt |
|---|---|
| `hybrid_directed` | **`GRAPH_SYS` verbatim**, plus a routing policy appended after it. |
| `hybrid_free` | The atlas *description* from `GRAPH_SYS` (the two-layer paragraph, verbatim), a sentence saying a browser also exists, and nothing else. No procedure, no ordering, no triggers. |

Constructing both from the live `qa_arms.GRAPH_SYS` rather than retyping it
means `hybrid_directed` is exactly *the graph arm's prompt plus a documented
delta*, and `hybrid_free` is exactly *the same description minus the procedure*.
The comparison is therefore about the policy and not about incidental wording.
`hybrid_arms.py --show-prompt` prints both in full and
`--selftest` asserts they still derive from `GRAPH_SYS` by exact substring.

### The routing policy (`hybrid_directed`)

Atlas first: establish the structure of the answer before searching, because the
atlas is the only thing that can distinguish genuinely extending a paper from
citing it in passing. Then reach for the browser in exactly three situations:

1. **Coverage** — the question falls outside the ~150 papers. Search rather than
   guess or decline.
2. **Detail** — something the atlas does not hold: a number from a results
   table, an experimental setting, the wording of a claim in the full text.
3. **Verification** — the answer is about to rest on a characterisation of *what
   a paper does* or *when it appeared* that came from a recorded justification.
   Those justifications are written automatically; they are reliable about the
   relationship they describe and can be unreliable about identity, sometimes
   naming a paper by a **system name** that belongs to a different paper or a
   different version of it.

And a tie-break: the atlas decides what relates to what, the browser confirms
what things are. If they disagree, say so in the answer rather than silently
picking one.

### Trigger 3 is engineered from a known failure, and that is declared

Trigger 3 is the generalisable rule that came out of the q06 post-mortem
([`../NOTES.md`](../NOTES.md) §1): the graph arm inherited a system-name alias
from an edge justification — 36 of that paper's 42 edges call it "The AI
Scientist" — and asserted that the 2026 paper was "the original". The policy
names no paper, no system and no question, but it was unquestionably **written
after seeing q06 fail**.

So an improvement on q06 is *engineered, not discovered*, and this document says
so before the run. The informative outcomes are the ones trigger 3 was **not**
tuned for: whether q01 and q04 regress, and what the routing traces show.

---

## 3. What gets run

### Subset — q01, q04, q06

| qid | why it is in |
|---|---|
| **q06** | The graph arm's only structural loss and the one the hybrid exists to fix. Correctness 5.0 against web's 8.3, and the correcting fact is one search away. If the hybrid cannot repair q06, the idea does not work. |
| **q04** | The mirror image: web's worst correctness (4.7) against graph's 7.7 at equal groundedness. Tests that adding a browser does not pull graph's correctness down toward web's. |
| **q01** | The flagship builds-on question and a clean graph win (9.0 / 8.0 / 9.0). Pure regression check: does handing the model a browser dilute a structural answer it was already getting right? |

Optional fourth: **c02** (control-full-text), the textbook complementary case —
the atlas holds the structure, the numbers live in a results table only the
browser can fetch, and the graph arm lost it 7.3 to 8.3. It is the one question
where a hybrid should beat *both* incumbents rather than matching one. Included
only if budget allows; excluded from the primary analysis either way.

### Judging — three-way, reusing the existing judge unmodified

For each question the judge sees **`hybrid_directed`, `hybrid_free`, and that
question's incumbent winner** (graph for q01/q04, web for q06). Three answers,
so `qa_judge.py`'s existing three-way call, rubric, schema and six-permutation
rotation are reused **as imports, with no edits** — same `JUDGE_SYS`, same
`JUDGEMENT_SCHEMA`, same `render()`, same `judge_one()`. Only the row-building
is new, because that is the part coupled to the arm names.

A pairwise fight would have needed a new rubric and a new prompt for strictly
less information. Three questions × three repeats = nine judgements, which the
rotation balances to exactly 3/3/3 on arm × slot.

The incumbent answers are read from `../out/answers.jsonl` **read-only**. Nothing
in this directory writes to the parent's `out/`.

### Mechanical checks — no new code

`../verify_named.py` and `../check_leakage.py` both already take `--file`, so
they point straight at `hybrid/out/answers.jsonl`.

- **`verify_named`** — the graph arm scored 0 of 57 unresolvable titles because
  it could only name corpus papers. A hybrid can name anything. The expected
  in-corpus rate drops; the number worth watching is whether the *out*-of-corpus
  titles it adds are real.
- **`check_leakage`** — the blinding contract now has two systems to conceal
  instead of one, so the risk of a tell ("search results indicate…", "the atlas
  shows…") is higher than in any previous arm. Clean on 24/24 before; must be
  clean here too or the judgements are void.

---

## 4. Predictions — registered before the run

1. **`hybrid_directed` beats the incumbent on q06 correctness by ≥ 2 points.**
   Expected, not discovered — see §2. A *failure* here would be the real news,
   because it would mean the browser cannot correct an inherited alias even when
   explicitly told to look for one.
2. **`hybrid_directed` does not regress on q01 or q04**: groundedness within
   1 point of the graph incumbent on both.
3. **`hybrid_free` opens with a web search on ≥ 2 of the 3 questions.** Searching
   is the model's reflex and entering the atlas costs a `find_paper` lookup
   first. If this holds, the ordering policy is load-bearing and that is the
   finding of the pilot.
4. **Both hybrids pull more payload than the graph arm alone** (graph averaged
   24,533 chars/answer). Compactness gets worse again; saying so in advance this
   time — see [`../ARMS.md` §6](../ARMS.md#6-why-the-compactness-prediction-failed).
5. **Neither hybrid's groundedness *gain* over the graph incumbent clears judge
   noise on q01/q04.** If the hybrid has value it should appear in correctness
   and coverage, not in groundedness, which the graph arm has already maxed.

---

## 5. What this pilot cannot show

Three questions is not a result. With judge spread near 1 point, **the scores
are decoration**; they cannot separate two hybrids or establish that a hybrid
beats an incumbent. What is *not* noise-limited is the logged routing, which is
free to extract and is the actual deliverable:

- **Which tool did each variant reach for first**, per question.
- **Did the browser verify or substitute?** A search that targets a claim the
  atlas has already produced is verification. A search that re-derives what
  `paper_neighbourhood` already returned is substitution, and means the model is
  paying twice for one answer.
- **Was the q06 alias actually caught**, and by which call.

Anything from this directory should be reported as *a pilot that tells us where
to look*, never as a fourth arm of the main experiment. It is not sealed against
the main result's question selection, it shares that result's judge, and it
reuses answers generated weeks earlier as its comparison baseline.

---

## 6. Files

```
hybrid/
  PLAN_HYBRID.md     this file — predictions registered before spending
  hybrid_arms.py     the two variants          (--selftest, --show-prompt: free)
  hybrid_gen.py      $  -> hybrid/out/answers.jsonl
  hybrid_judge.py    $  -> hybrid/out/judgements.jsonl
  routing.py         free — the call-routing trace, the real deliverable
  hybrid_report.py   free -> hybrid/RESULTS_HYBRID.md
```

`hybrid_arms.py` imports `qa_arms` and wraps `build_options` with a delegating
shim, so `qa_arms.run_one` — whose usage accounting is subtle and has been
debugged three times — stays the single source of truth instead of being
copy-pasted. The shim lives in memory; `qa_arms.py` on disk is untouched, and
`--selftest` asserts the original three arms come back through the wrap with an
identical configuration signature.

---

## 7. Budget

| step | |
|---|---|
| 2 variants × 3 questions, cap $1.00/run | ≈ $3.00–4.50 |
| 3 questions × 3 judge repeats | ≈ $1.70 |
| checks, routing, report | free |
| **total** | **≈ $5–6, about 20 minutes** |

Same contract as the parent experiment: everything marked **$** runs in the
user's own terminal, never spawned by an agent, checkpointed, Ctrl+C safe,
resumable into only what is missing.

---

## 8. Amendments after the first batch — 2026-08-26

The first batch (q01/q04/q06 × 2 arms, $2.04 generation + $1.58 judging) ran
before these changes. Everything below is recorded here rather than edited into
the sections above, so the pre-registration stays readable as written.

### 8.1 A harness bug destroyed two answers

`qa_arms._submit_tool` is first-complete-wins, and it calls a submission
"complete" if the prose is non-blank and at least one paper is named. Two models
probed the tool before committing —

```
answer="Test", papers_named=["Test Paper"], confidence="high", limits="test"
```

— which satisfies that test, so the probe was locked in, the real answer that
followed was discarded, and the tool replied *"your first complete answer is the
one that counts and it is safely stored"*, which is why the model then stopped.
The judge scored the resulting one-word answers **1/1/1**, three runs out of
three, on `q01/hybrid_free` and `q06/hybrid_directed`.

This is the same root cause as the parent's own last-wins bug ([`../PLAN.md`](../PLAN.md),
`_submit_tool` docstring): **the ordering was never the problem, the completeness
predicate is.** First-wins loses when the junk arrives first; last-wins loses
when it arrives last.

Fixed **in this directory only**, by overriding the submit tool in
`hybrid_arms.py`: keep every attempt and store the *best* — clears a probe bar
(≥900 chars, papers named, non-placeholder limits), then longest. A probe now
gets told the slot is still open instead of being told it succeeded.
`--selftest` asserts both orderings land on the real answer.

**The parent's published run is unaffected** — checked directly: no row in
`../out/answers.jsonl` is probe-shaped or has `n_submits > 1`. The bug is
nonetheless still live in `../qa_arms.py` and would bite a re-run.

**Recovery, not a do-over.** Every attempt was already logged on the row as
`submissions`, before any of this was known. `repair.py` re-applies the fixed
rule to that log and stores what the fixed harness would have stored — the same
deterministic rule the live code now runs, which can only pick the fullest
submission, never a nicer one. `q01/hybrid_free` is recovered that way (4 chars →
4,428, 19 papers). `q06/hybrid_directed`'s best logged submission is *also* a
probe, so it is genuinely lost and gets re-run rather than patched.

Judgements for q01 and q06 were made with a 1/1/1 answer in the lineup, which
changes both the ranking and the contrast the other two answers are read
against, so they are dropped and re-judged. **q04 was never affected and its
judgements stand.**

### 8.2 The routing classifier was too strict

Matching a surfaced title against a web query by substring mis-filed the batch's
only web call. The agent searched `AIDE "AI-Driven Exploration" Jiang Schmidt
Weco …` for a paper the atlas had already handed it as `AIDE: AI-Driven
Exploration in the Space of Code` — the same paper, and plainly a check of
something it had already been told, but not a substring. It was filed COVERAGE
when it is VERIFICATION. `routing.py` now matches on content-word overlap (≥60%
of a title's distinctive words present in the query), and that call reclassifies
correctly.

### 8.3 q03 added to the subset

Added **after** seeing the first batch, and therefore declared: the registered
predictions in §4 are scored on **q01/q04/q06 only**, and `hybrid_report.py`
enforces that in code — q03 appears in the tables and in brackets beside
prediction 3, but cannot move a verdict.

The reason it earns its place: **q01, q04 and q06 all name a paper**, so every
run in the first batch could open with `find_paper`, and every one did. q03 is a
*topic* question with no paper to look up, which is the routing case the subset
was missing — if a browser is ever going to look attractive to the hands-off
arm, it is when there is no name to enter the atlas with. Its headroom is poor
(§1: graph already 9.0/8.0/9.0), so it is a routing probe, not a scoring test.

### 8.4 Prediction 3 missed, badly, and that is the finding so far

Registered: *"hands-off opens with a web search on ≥2 of 3."* Observed: **0 of
3.** Every run of both variants opened with `find_paper`, and across all six
runs there was exactly **one** web call in total — `hybrid_free` made **none**.
On q01 the two variants produced byte-identical call sequences.

Handed both environments on questions about a named paper, the model goes to the
atlas essentially unprompted, and the routing policy barely changes what it does.
The obvious confound is stated in §1 and stands: these questions were chosen
because the atlas is good at them. q03 tests one edge of it; the controls
(c01/c02) would test the other and have not been run.
