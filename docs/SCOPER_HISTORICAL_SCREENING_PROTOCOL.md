# Historical Scoper screening protocol

This note records the actual criteria and implementation used to create the
255-paper Scoper corpus in the original Elicit comparison. It must be distinguished
from later experimental screening protocols and from the 152-paper downstream
Prior v0.2 atlas bundle.

## Two-stage scope

The historical pipeline first used the broad natural-language protocol in
`evals/scoper_monkeys/workshop_inputs/scoper-original-input-v1.txt` for discovery
and query generation. It then rescreened the candidate pool using the stricter
core criteria in
`evals/scoper_monkeys/workshop_inputs/historical-strict-core-scope-v1.txt`.

The strict-screen artifacts remain at:

- `data_hackathon/atlas/core_scope.json`: 255 kept, 873 dropped;
- `data_hackathon/atlas/scope_strict_cache.jsonl`: 1,128 binary decisions;
- `experiments/scoper_vs_elicit/out/scoper_ai-scientist.json`: the exported
  255-paper comparison corpus.

The strict criteria are copied byte-for-byte from `scripts/tighten.py` and the
immutable replay artifact `strict-core-scope.txt`.

## Historical screening instruction

The system instruction in `src/prior/scoper.py` was:

> You are the Scoper. Decide whether each candidate paper is IN SCOPE for the
> given topic, judging only from its title + abstract. Honour the topic's
> inclusion and exclusion criteria exactly. Be strict: a paper that is merely
> adjacent — same buzzwords, neighbouring subfield, a tool that just mentions
> the terms — is OUT of scope.
>
> PRIMARY SOURCES ONLY. Reject papers whose own framing is a perspective,
> position, opinion, survey, review, roadmap, or viewpoint — judge this by
> CONTENT, not by metadata or article-type flags. Out-of-scope tells (from the
> title/abstract's own words): "this perspective / this position paper", "we
> argue", "we advocate", "we call for", "a survey of", "systematic review",
> "a review of", "roadmap". Keep primary empirical/methodological work that
> introduces a method, system, dataset, benchmark, or finding. CRUCIAL: a paper
> whose topic is peer review (e.g. an agent that reviews papers, a peer-review
> benchmark) is still PRIMARY — do not confuse "about reviewing" with "a review
> article".
>
> For each candidate return in_scope (true/false) and a one-line reason.

Implementation details:

- evidence: title plus the first 320 abstract characters;
- output: binary `in_scope` plus one-line reason;
- batch size in `scripts/tighten.py`: 20;
- cache: paper source identifier (`id`), with one decision per record;
- no BM25 prefilter in the strict rescreen;
- missing or failed LLM decisions were conservatively kept for review by the
  historical `scope` function;
- model/backend were provided by the run environment; the script documents the
  Claude Code backend but the old cache does not record an immutable model ID.

## Later artifacts are different

The packaged Prior v0.2 atlas contains 152 papers. It is a later downstream
materialized corpus produced after the original search and a documented
primary-only audit removing three non-primary pieces from a 155-paper intermediate
set. Its coverage was constrained by the historical search heuristics (including
shallow retrieval and limited expansion), so it is useful as a retrospective
regression set but is neither the original 255-paper strict-screen output nor an
independent or complete gold standard.

For the workshop comparison, use:

- the broad protocol as the matched initial product input;
- the historical strict criteria and primary-source instruction as the common
  eligibility screen;
- modern work-level identity resolution and full available abstracts as a
  separately labelled methodological improvement, with a sensitivity analysis
  reproducing the historical 320-character evidence window.
