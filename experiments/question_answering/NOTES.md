# Notes: post-hoc investigations

Short write-ups of things worth understanding after the fact. Not part of the
design record ([PLAN.md](PLAN.md)) and not part of the results
([RESULTS.md](RESULTS.md)) — this is where a specific finding gets chased down.

---

## 1. Why the graph arm got q06 wrong: an alias in the edge justifications

**The error.** q06 asked where AIDE came from and who has built on it. The graph
arm answered well — correct authorship, correct descendants, a precise account of
MLEvolve's and AIRA-2's critiques — and then wrote one wrong sentence:

> The original "Towards end-to-end automation of AI research" (The AI Scientist)
> likewise uses AIDE-style agentic tree search for its template-free, open-ended
> experiment-execution mode.

The AI Scientist **v1** (Lu et al., 2024) used Aider plus human-written experiment
templates. Agentic tree search was **v2's** headline change. The judge caught it
all three runs, and it cost the graph arm the question — correctness 4 / 5 / 6,
the lowest any arm scored on a structural question, and the only one of the eight
registered predictions to miss.

### It was not invented. It was inherited.

Replaying the trace (`python trace.py --questions q06`) shows exactly five calls
and no room for the agent to have made this up:

```
find_paper("AIDE") → paper_neighbourhood(AIDE) → edge_reasons(AIDE, others=[7 edges])
                   → paper_neighbourhood(AIRA_2) → paper_neighbourhood(Why LLMs Aren't Scientists Yet)
```

`paper_neighbourhood` returned this edge label, which is **correct**:

```
<- builds_on | Towards end-to-end automation of AI research | openalex:W7140287209::k01
```

Then `edge_reasons` returned the recorded justification behind it, and here is the
problem, verbatim from the atlas:

> **"B (The AI Scientist)** explicitly cites A (AIDE) when describing its
> template-free, open-ended mode that uses agentic tree search for code
> optimization. […] B builds on A's tree-search-based code optimization approach
> by incorporating it as a component in a broader autonomous research pipeline"

The justification **glosses `Towards end-to-end automation of AI research` as "The
AI Scientist"** — the *system* name, not the paper title. Everything the graph arm
then wrote is a faithful restatement of that sentence. The single word it added
from its own knowledge was **"The original"**, because it knows "The AI Scientist"
means Lu et al. 2024. That word is where the claim became false.

So the failure is: **a correct relation, attached to a correctly identified paper,
carrying a justification that names the paper by a system alias which the corpus
also assigns to a different paper.**

### The alias is systematic, not a one-off

`Towards end-to-end automation of AI research` (`openalex:W7140287209`, 2026) has
42 typed edges. **36 of them describe it as "The AI Scientist" in their
justification prose.** One goes further and asserts the identification outright:

> "Contribution B (The AI Scientist, **Nature 2026**) is **the original system**
> that generated and submitted the workshop paper…"

Meanwhile the corpus separately holds `openalex:W4402952666` — *"The AI Scientist:
Towards Fully Automated Open-Ended Scientific Discovery"*, 2024, the actual
original. Eleven corpus papers have "AI Scientist" in the title. The edge labeller
was using a system name where only a paper id disambiguates.

### Four things that let it through

1. **The labeller wrote prose for a human reader, and prose gets read as fact.**
   Under the v3 surface, `edge_reasons` returns those justifications **in full and
   unedited** — which is the whole point of the redesign, and is why the graph arm
   scored so well elsewhere. The same channel that carries the evidence carries
   the labeller's mistakes, at full confidence, with no marker distinguishing the
   two.

2. **The typed-relation lines carry no year.** `paper_neighbourhood` prints
   `cited_by` rows with years — `AIRA_2: … (2026)` — but `typed_relations` rows
   have none. Had the line read `Towards end-to-end automation of AI research
   (2026)`, a paper the answer calls "the original" being dated two years after
   the thing it supposedly preceded is a contradiction the model would very likely
   have caught.

3. **The arm never touched the real v1 node.** q06's five calls never reach
   `openalex:W4402952666`. There was no in-atlas contradiction available to it —
   only the alias, unopposed.

4. **Nothing downstream could catch it.** `verify_named.py` checks that named
   titles *exist* in the corpus; every title in this answer does, including
   `Towards end-to-end automation of AI research`. There is no check that an
   answer's *characterisation* of a paper matches the paper. That is exactly the
   gap the judge is for, and here the judge worked — it caught it three times out
   of three.

### What this is evidence of

It is the honest counterweight to the q01 result. The atlas's advantage is that it
ships recorded justifications rather than adjacency, and the graph arm reads them
carefully — which is why it wins the structural questions. The cost of that
advantage is that **the arm inherits the labeller's errors as confidently as it
inherits the labeller's insights**, and it has no way to tell them apart. On the
poster framing: Prior does not make a model correct, it makes a model
*checkable* — the error is traceable to one recorded sentence in one edge, which
is more than can be said for the web arm's mistakes.

### Cheap fixes, roughly in order of value

- **Put the year on the typed-relation lines**, as `cited_by` already does. One
  line in `graph_tools.paper_neighbourhood`; would very likely have prevented this
  specific error and costs about 6 characters per row.
- **Flag alias collisions at build time.** A paper whose justifications repeatedly
  name it by a string that is a substring of a *different* corpus paper's title is
  a detectable condition. 36 of 42 edges is not subtle.
- **Consider prefixing paper mentions in `edge_reasons` output with the paper id**
  the reason actually refers to, so an alias in the prose can be resolved against
  the graph rather than against the model's memory.
- **Do not "fix" this by re-labelling and re-running q06.** The registered
  prediction missed and the miss is reported. Correcting the corpus after seeing
  which question it lost would be a fourth post-hoc revision, and PLAN §8 already
  has three.

*Investigated 2026-08-24. Reproduce with:*
`python trace.py --questions q06` *(free), then read* `out/traces/q06.md` *for the
full justification text of every edge the arm read.*
