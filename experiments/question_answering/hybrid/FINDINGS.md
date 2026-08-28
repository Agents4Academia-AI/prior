# Findings — what happened when the agent had both

Read alongside [`RESULTS_HYBRID.md`](RESULTS_HYBRID.md) (generated: every score,
every answer, every judge reason) and [`PLAN_HYBRID.md`](PLAN_HYBRID.md) (the
predictions, registered first, and §8 for what changed mid-flight).

**4 questions × 2 hybrid variants, judged 3× each against the question's
three-arm winner. $2.47 generation + $2.45 judging.** A pilot, not a study.

---

## 1. The headline: it barely used the browser

| | q01 | q03 | q04 | q06 |
|---|---|---|---|---|
| **directed** opened with | `find_paper` | `topic_structure` | `find_paper` | `find_paper` |
| **hands-off** opened with | `find_paper` | `topic_structure` | `find_paper` | `find_paper` |
| web calls, directed | 0 | **1** | 0 | **1** |
| web calls, hands-off | **0** | **0** | **0** | **0** |

Eight runs. **Two web calls in total.** The hands-off arm — told only "you have
an atlas and a browser, use whichever you judge appropriate" — never opened the
browser once, on any question.

Registered prediction 3 was that the hands-off arm would *open* with a search on
at least 2 of 3 questions, on the reasoning that searching is the model's reflex
and entering the atlas costs a lookup first. It opened with the atlas **4 times
out of 4**. That prediction did not just miss, it inverted.

And the atlas entry point was chosen correctly without being told: `find_paper`
on the three questions that name a paper, `topic_structure` on q03, which does
not. Both variants made that switch independently.

Worth being straight about the confound, which was written down before the run:
**these questions were selected because the atlas is good at them.** The
controls — `c01` (outside the corpus entirely) and `c02` (numbers that live in a
results table) — are where a browser should look irresistible, and they were not
run. What this shows is narrower than "models prefer graphs": on questions the
atlas can answer, a model given both does not go wandering.

## 2. Where having both actually helped: q03

q03 is the only place a genuine hybrid answer appeared, and it produced **the
best scores in the entire batch**:

| q03 — *"is it contested that autonomous AI scientists produce publishable research?"* | G / C / U | won |
|---|---|---|
| **hybrid_directed** (12 atlas calls + 1 web) | **9.0 / 8.7 / 9.0** | **3/3** |
| hybrid_free (10 atlas calls, no web) | 8.3 / 8.0 / 8.7 | 0/3 |
| incumbent — graph arm | 8.0 / 8.7 / 8.0 | 0/3 |

The web call was `Kosmos AI Scientist autonomous discovery Edison Scientific
paper 2025` — issued **after twelve atlas calls**, targeting a paper the atlas
had already surfaced. Not a search for material; a check on *who built the thing
and what it actually is*, which is provenance the atlas does not carry.

The shape of that answer is the interesting part. The structure — that the
optimistic claims and the sceptical rebuttals are papers pointed at each other,
with named `contradicts` relationships — came entirely from the atlas, and that
is what neither the web arm nor closed-book could produce in the parent run. The
web call added identity for one system in the affirmative column. Structure from
the graph, identity from the browser, which is exactly the division of labour
the routing policy asked for.

**But do not over-read it.** hybrid_free also beat the incumbent on q03 with no
web call at all, and every margin the judge gave in this entire batch was
`slight` — 12 of 12. q03/directed is one answer.

## 3. The verification trigger fired, and fired at the wrong target

This is the sharpest result, and it is a failure of the thing I designed.

Trigger 3 of the routing policy was written specifically for the q06 alias — the
edge labeller calls the 2026 paper *Towards end-to-end automation of AI research*
by the system name "The AI Scientist" in 36 of its 42 edges, and the parent graph
arm inherited that and called it "the original"
([`../NOTES.md`](../NOTES.md) §1). The policy tells the arm to verify exactly
this kind of claim.

On q06, `hybrid_directed` **did** issue a verification search. It searched:

```
AIDE AI-Driven Exploration Space of Code Weco Jiang Schmidt arxiv
```

It verified **AIDE** — the paper the question is about, the one it was already
confident about, the one that was never in doubt. It did not verify the paper
where the alias lived. And so it wrote:

> "**The original** *Towards end-to-end automation of AI research* work (the AI
> Scientist line) cites AIDE when describing its template-free, open-ended
> tree-search mode…"

**Same alias, same error, after a web search aimed at the wrong paper.**

Meanwhile `hybrid_free`, which made no web calls at all, did **not** say "the
original", and correctly attributed the agentic tree search to *AI Scientist-v2*.
The arm without the fix got it right; the arm with the fix did not.

Registered prediction 1 — directed beats the incumbent on q06 correctness by ≥2
— came out at **+0.0**. It was declared in advance as engineered rather than
discovered, which is the only reason it is safe to report: the pre-registration
is doing its job when the engineered prediction is the one that fails.

**Why it probably happened.** A model verifies what feels *salient*, not what is
*fragile*. AIDE is the subject of the question, so AIDE is what got checked. The
alias arrived inside a recorded justification written in confident prose, indexed
under a correct relationship, on a paper that was peripheral to the question — it
never presented as a claim needing support. The policy said "check load-bearing
characterisations you took from justification prose", and the model could not
tell which of its beliefs that described. If this is right, the fix is not a
better prompt but a **marker in the data**: `edge_reasons` output would have to
say *which* paper id a name in the prose refers to, so the collision is visible
rather than something the model has to suspect. That is
[`../NOTES.md`](../NOTES.md) §1's third suggested fix, and this pilot is evidence
for it over the prompt-level one.

## 4. Neither hybrid ever left the corpus

`verify_named.py` on all eight answers: **92 titles named, 0 unresolved.** Every
paper either hybrid cited is one of the 152. For comparison, the parent web arm
was 45% in-corpus.

So the browser did not broaden coverage — it was used twice, both times to
confirm the identity of a paper the atlas had already produced. Given that the
subset excludes the out-of-corpus control, that is about what should be expected,
but it means the pilot has **no evidence at all** on the coverage question the
hybrid was mainly supposed to solve.

## 5. Cost — the hybrid is the graph arm plus a bit

Means over the same four questions:

| arm | payload chars | calls | USD | seconds |
|---|---:|---:|---:|---:|
| hybrid_directed | 31,435 | 8.5 | 0.344 | 64 |
| hybrid_free | 31,183 | 7.8 | 0.275 | 60 |
| graph (parent) | 27,275 | 6.5 | 0.296 | 54 |
| web (parent) | 18,939 | 7.8 | **0.594** | 112 |
| null (parent) | 0 | 0.0 | 0.206 | 65 |

Adding a browser costs about **15% more payload and 30% more calls** than the
graph arm, and most of that is extra atlas traffic, not web traffic — the arms
explored the graph *more*, not less, for having an alternative. Registered
prediction 4 (payload goes up) held, as the parent experiment's compactness
finding said it would ([`../ARMS.md` §6](../ARMS.md#6-why-the-compactness-prediction-failed)).

The web arm remains the expensive one at nearly double the cost for the thinnest
payload.

## 6. Scoreboard, with the caveat first

**Every margin in all 12 judgements was `slight`.** Nothing here is decisive and
the win counts should not be quoted without that sentence attached.

| question | incumbent | winner (of 3 runs) |
|---|---|---|
| q01 builds-on | graph | **incumbent 2/3**, directed 1/3 |
| q03 disagreement | graph | **directed 3/3** |
| q04 uses-findings | graph | **free 3/3** |
| q06 lineage | web | **free 2/3**, directed 1/3 |

A hybrid took 10 of 12 judgements, but on q01 the plain graph arm was still
best — handing the model a browser it then ignored cost it a little (7.7/7.3/8.0
and 7.7/7.7/7.7 against the incumbent's 8.0/7.7/8.3). The most likely reason is
just the longer system prompt and a slightly more diffuse answer; the call
sequences for q01 were **byte-identical** between the two variants, so nothing
about the exploration differed.

Prediction scorecard: **2 held, 3 missed** (1, 3, and 5 — where 5 failed on a
boundary, q04's gain being exactly +1.0 against a "<1" threshold). Full table in
[`RESULTS_HYBRID.md`](RESULTS_HYBRID.md).

---

## Conclusions

1. **Given both, the model stays in the graph.** Four questions, two variants,
   two web calls. The hands-off arm never searched. Whatever else this pilot
   shows, it does not show a model reaching for search when structured relations
   are available and sufficient.

2. **The one clear hybrid win was structure-plus-identity, not
   structure-plus-coverage.** q03's best-in-batch answer used the atlas for the
   disagreement structure and the browser for one system's provenance. If there
   is a hybrid design worth pursuing, that division — *the graph says what
   relates to what, the browser says what things are* — is the one the data
   points at.

3. **Prompting a model to verify does not tell it what to doubt.** The
   verification trigger fired on q06 and checked the wrong paper, and the arm
   with no policy at all avoided the error. Alias collisions should be marked in
   the `edge_reasons` payload, not left to the model to suspect.

4. **The pilot cannot speak to coverage**, which was the hybrid's main
   motivation. Nothing here touched the out-of-corpus control. The obvious next
   step is **c01 and c02 with both variants** — c01 is where the graph arm
   scored 2.7 groundedness and a browser is the only thing that can help, and
   c02 is where the numbers live in a results table the bundle does not hold. If
   the hands-off arm does not search on c01 either, that is a much stronger and
   much stranger result than anything in this document.

5. **This is four questions with every margin `slight`.** It is a routing study
   that happens to carry scores, not a scoring study. The routing is the part
   that is not noise-limited, and the routing is what it should be reported for.

*2026-08-27. Regenerate the numbers with `python routing.py` and
`python hybrid_report.py` — both free.*
