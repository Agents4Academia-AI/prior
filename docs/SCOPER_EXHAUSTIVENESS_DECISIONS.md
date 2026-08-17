# Scoper exhaustiveness decision ledger

Branch: `codex/scoper-exhaustiveness-2026-08-15`, based on Cartographer `dev`
at `eab740d`.

Goal: improve systematic-search recall without silently replacing explicit scope
criteria with broader topical relevance. Each item below is a decision point, not
yet an implementation commitment.

## Proposed order of decisions

| # | Current heuristic | How eligible work can be lost | Proposed direction | Status |
|---|---|---|---|---|
| 1 | Generate 6–10 unstructured keyword queries, then 4–8 title-informed follow-ups | Entire vocabularies, disciplines, named systems, venues, or study types may never become a branch | Bootstrap a provisional query map, then induce and revise auditable query families as the literature is discovered | accepted, revised |
| 2 | Retrieve only one relevance-ranked page per query/source (25 OpenAlex, 5 arXiv, 12 S2 by default) | Relevant records below a shallow rank cutoff are invisible | Progressive deepening per branch; stop branches by observed eligible yield and novelty rather than a fixed first page | accepted |
| 3 | Exclude reviews and records without abstracts during source retrieval | Reviews can expose terminology and citations; older or poorly indexed eligible works may lack abstracts | Keep them as retrieval-only bridge records; exclude them only from the final primary-study corpus | accepted |
| 4 | Use only OpenAlex, arXiv, and Semantic Scholar keyword search | Venue-native, domain-indexed, workshop, and technical-report records can be absent or poorly ranked | Add pluggable sources selected adaptively as the literature map develops | accepted |
| 5 | BM25 keeps roughly 30% plus candidates whose in-scope score exceeds out-of-scope score | Novel terminology and interdisciplinary records can be gated before semantic screening | Use lexical relevance only to prioritise screening; never treat the unreviewed tail as excluded | accepted |
| 6 | Binary LLM scope decision from title plus the first 320 abstract characters | Ambiguous abstracts, late-stated contributions, and false negatives are not rescued | Use evidence-grounded include/exclude/uncertain decisions, rescue uncertain cases, and audit exclusions | accepted |
| 7 | Feed up to 15 dropped titles back as “out of scope—don’t re-surface” | False-negative decisions become hard negative search guidance | Preserve exclusion evidence and categories, but never use exclusions as hard-negative search vocabulary | accepted |
| 8 | First citation hop uses at most 200 search results; later hops use top-cited plus recent seeds | Mid-cited bridge works and minority clusters may never seed expansion | Put every useful record into a traced, coverage-aware citation-expansion queue | accepted |
| 9 | Citation expansion is capped (typically 40 per direction), with forward results biased toward newest works | Older citing papers and long bibliographies/citation tails are truncated | Retrieve complete backward references and progressively traverse forward citations, merging independently traced citation sources | accepted |
| 10 | Stop when global eligible yield falls below 3% | A noisy large branch can trigger stopping while a small eligible cluster remains undiscovered | Treat stopping as a documented argument assembled from branch, coverage, queue, and source-health evidence | accepted |
| 11 | Source errors warn and the run continues | Rate-limited sources produce an apparently finished but incomplete corpus | Persist failed retrieval tasks for retry and prevent unresolved required tasks from being labelled complete | accepted |
| 12 | Deduplicate to a preferred source record and cache scope decisions by source ID | Richer manifestations can be discarded and stale decisions reused | Unify canonical work identity without discarding manifestations; reassess when evidence materially changes | accepted |
| 13 | Completeness uses capture–recapture on dependent search and snowball channels | The estimate can look reassuring despite correlated discovery mechanisms | Retain it only as a diagnostic and report a multidimensional, evidence-backed completeness profile | accepted |

## Evaluation rule

For each accepted change, run a frozen ablation against the 37 hidden eligible
works from the Awesome AI Scientist comparison and additional domain cases. Report:

- eligible-work recall and recovery path;
- manifestation-aware precision and screening load;
- source failures and unresolved identities;
- marginal recall per query, citation branch, and screening batch;
- whether the stopping rule would have stopped before each recovered work.

The target is not merely a larger corpus. It is a defensible claim that every
important search path was either exhausted, explicitly bounded, or recorded as
incomplete.

## Accepted decisions

### 1. Evolving, auditable query map

Do not require an exhaustive coverage rubric before seeing the literature. That
would privilege the investigators' initial vocabulary and can hide precisely the
communities and framings the search is intended to discover. Instead, replace the
one-shot request for a small number of diverse queries with a traced, evolving
map:

- begin with several deliberately broad and complementary seed queries derived
  from the natural-language scope, explicitly labelled as provisional;
- infer candidate facets, disciplinary vocabularies, named systems, study types,
  and missing communities from retrieved records, citation neighbourhoods, and
  retrieval-only bridge documents;
- create new labelled query branches in response to that evidence and retain the
  parent evidence that motivated each branch;
- allow facets to split, merge, or be rejected as the map develops;
- expose the current map for optional human correction without requiring the
  human to know the field's complete vocabulary in advance;
- freeze the final query map, its revisions, and branch-level stopping evidence
  as the reproducible review protocol;
- never treat unaudited exclusions as hard-negative vocabulary.

Use the search ledger to compare this adaptive map against the existing free-form
query generator with scope, source availability, result depth, screening policy,
and hidden targets held fixed. Attribute recall, unique eligible discoveries,
rediscoveries, candidates screened, and source/API cost to individual branches
and emergent facet families. Measure not only final recall but when a useful new
vocabulary or community was discovered, what evidence caused the expansion, and
whether that expansion recovered otherwise hidden eligible works. Report areas
that remain weakly explored and branches that failed or were bounded, rather than
claiming that a predetermined matrix was complete.

### 2. Adaptive retrieval depth

Remove fixed per-query retrieval depth as a stopping rule. Search each
query/source branch through paginated, traceable batches and decide whether to
continue using branch-specific evidence. The system should:

- preserve source rank, page or cursor, query, and retrieval time for every hit;
- measure new canonical works, newly eligible works, rediscoveries, unresolved
  candidates, and new vocabulary or citation communities per page;
- continue through temporary zero-yield pages when later relevant results remain
  plausible, using a configurable patience rule rather than stopping after one
  empty page;
- distinguish semantic saturation from source exhaustion, API failure, and a
  user-imposed resource ceiling;
- revisit or deepen branches whose facet remains weakly covered, even if their
  immediate eligible yield is lower than that of mainstream branches;
- keep operational ceilings as safety controls, but label any branch stopped by
  one as bounded/incomplete rather than saturated.

Use traced depth curves to learn sensible patience policies for each source and
query family. Compare the former fixed depths with progressively deeper runs at
the level of canonical eligible-work recall, marginal screening load, and the
rank/page at which every additional hidden target was recovered. Do not assume a
single universal depth or yield threshold across OpenAlex, arXiv, and Semantic
Scholar because their ranking and pagination behaviour differ.

### 3. Separate discovery graph from eligible evidence corpus

Do not discard a record during retrieval merely because it is a review,
perspective, editorial, protocol, dataset description, or lacks an abstract.
Instead, assign records distinct roles:

- `eligible`: satisfies the review criteria and may enter synthesis;
- `retrieval_only`: ineligible for synthesis but useful for terminology, citation,
  author, venue, system, or community discovery;
- `unresolved`: insufficient metadata or text for a defensible decision;
- `excluded`: neither eligible nor presently useful for retrieval, with a recorded
  reason.

Retrieval-only records may generate query branches and citation expansion but
must never be counted as included evidence without a separate eligibility
decision. Preserve provenance from each navigation record to the eligible works
it helps recover, so its discovery value can be evaluated empirically.

Treat a missing abstract as missing evidence rather than exclusion evidence.
Attempt manifestation resolution, metadata repair, repository or publisher text,
and—where lawful and available—full-text retrieval. Keep unresolved records in a
repair queue and expose their status in completeness reporting.

### 4. Adaptive, pluggable source coverage

Keep broad scholarly indexes as a general discovery layer, but do not treat
OpenAlex, Semantic Scholar, and arXiv as a universally sufficient source set.
Support independently traced source adapters in layers:

- broad metadata and discovery indexes, such as OpenAlex, Semantic Scholar, and
  Crossref;
- repository and venue-native sources, such as arXiv, OpenReview, or ACL
  Anthology;
- domain databases and registries selected when the emerging literature map
  indicates their relevance;
- web, project, and code discovery as lead-generation channels whose results are
  subsequently resolved to stable scholarly manifestations where possible.

The system may recommend or activate an additional source when retrieved records
reveal a publication community, artifact type, or vocabulary that is poorly
represented in active sources. Record the evidence motivating that source, its
queries and failures, and its unique eligible contribution. Do not require every
adapter for every review, and do not claim source completeness when a relevant
adapter is unavailable or bounded.

### 5. Relevance ranking is scheduling, not exclusion

Remove BM25 as a hard eligibility gate in exhaustive mode. Lexical, embedding,
and other inexpensive relevance scores may order screening work, but candidates
remain in the ledger until screened, resolved as duplicates, or explicitly left
unscreened because of a declared operational bound.

Prioritisation should combine more than topical lexical similarity. Citation
provenance, source uniqueness, novel vocabulary, manifestation quality, and
membership in an under-covered cluster may raise a candidate's priority. A low
lexical score from a credible bridge path can be evidence of a useful new framing
rather than evidence of irrelevance.

If resources prevent complete screening, audit stratified samples throughout the
low-ranked tail and estimate missed eligible yield with uncertainty. Label the
remaining records `unscreened`, never `excluded`, and reflect them in the run's
completeness status.

### 6. Staged, evidence-grounded scope screening

Replace binary screening from a truncated abstract with a staged protocol:

1. Screen the complete available title and abstract into `include`, `exclude`, or
   `uncertain`.
2. Require each decision to identify the applicable scope criterion and the
   supporting evidence; absence of sufficient evidence produces `uncertain`, not
   exclusion.
3. Rescue uncertain records through manifestation resolution, metadata repair,
   additional text, or lawful full-text retrieval.
4. Reassess rescued cases independently while preserving disagreements and the
   evidence available to each assessment.
5. Audit a stratified sample of exclusions, with strata informed by source,
   query branch, model confidence, citation provenance, novelty, and cluster.
6. Increase audit intensity adaptively where false negatives concentrate.

Key decision caches by canonical work identity, scope version, screening protocol
and prompt version, model, and evidence version. New evidence or a changed scope
must invalidate or explicitly supersede an earlier decision rather than silently
reusing it.

### 7. Exclusions do not become search prohibitions

Do not describe a small set of excluded titles to the query generator as material
that must not re-surface. Record and expose the actual exclusion category,
applicable scope criterion, evidence, certainty, and audit status. Distinguish at
least topical irrelevance, explicit boundary exclusion, retrieval-only/non-primary
material, uncertain evidence, duplicate, and alternate manifestation.

Use canonical identity and prior adjudication to avoid paying to screen the same
work repeatedly. Do not suppress its terminology or prevent an adjacent or
retrieval-only record from motivating a new branch. Trace every case in which an
excluded or retrieval-only record influences reformulation, including the
eligible works subsequently recovered through that path.

### 8. Coverage-aware citation-expansion queue

Remove fixed first-hop seed counts and the later restriction to highly cited or
recent papers. Every eligible record, unresolved candidate, and useful
retrieval-only bridge record should enter a citation-expansion queue.

Prioritise that queue using evidence such as under-covered vocabulary or
clusters, unique references, novel authors or venues, graph position,
uncertainty, likely neighbourhood overlap, citation count, and recency. Citation
count and recency may affect order but must not determine whether expansion is
permitted.

Each seed must eventually have a visible terminal state: expanded in each
available direction/source, source-exhausted, duplicate neighbourhood, explicitly
bounded, failed and awaiting retry, or pending. Low priority must never silently
mean omitted. Preserve which seed, manifestation, source, and direction produced
every recovered candidate.

### 9. Progressive citation-neighbourhood traversal

Remove fixed per-seed/per-direction citation-result caps as stopping rules.
Retrieve complete backward reference lists where sources permit it. Traverse
forward citation results through source pagination while preserving rank or
ordering, cursor/page, direction, manifestation, and retrieval time.

Merge but do not conflate citation evidence from OpenAlex, Semantic Scholar, and
Cartographer's parsed bibliography/full-text evidence. Preserve source
disagreements and manifestation resolution so missing links in one provider can
be recovered from another.

For exceptionally large forward neighbourhoods, prioritise or stratify traversal
across time, relevance, and citing communities. If operational limits prevent
complete traversal, retain the known total where available and label the branch
as bounded with its sampling policy and unretrieved remainder. Never describe a
sampled citation neighbourhood as exhausted.

### 10. Evidence-based stopping argument

Remove the global eligible-yield threshold as the run-level stopping rule. A run
may be described as saturated only when its trace supports a documented argument
covering all active discovery mechanisms. At minimum:

- every query and citation branch has an explicit terminal state;
- newly induced vocabularies, communities, and retrieval-only bridge paths have
  been searched, rejected with evidence, or declared bounded;
- screening, identity-resolution, evidence-repair, and source-retry queues are
  empty or explicitly reported as incomplete;
- branch-specific depth shows sustained absence of unique eligible recovery and
  meaningful literature-map expansion under a documented patience policy;
- independent routes increasingly rediscover known canonical works;
- source health and operational bounds do not masquerade as saturation.

Learn source- and branch-specific patience policies retrospectively from traced
depth curves and hidden-target recovery. Preserve individual signals—eligible
yield, rediscovery, novelty, cluster coverage, and unresolved work—rather than
collapsing them prematurely into one scalar. Permit a run to terminate as
`incomplete` or `bounded`; completion and saturation are stronger claims.

### 11. Persistent source-task and retry state

Represent every planned query page, identifier lookup, and citation expansion as
a traceable retrieval task. A failed call must retain its branch, source,
parameters, cursor/page, attempt history, and failure category in a persistent
`pending_retry` state rather than becoming an empty result.

Retry transient failures with bounded backoff that respects provider policies,
and support pause/resume without losing task state. Distinguish rate limiting,
quota exhaustion, authentication/configuration failure, source rejection,
malformed responses, and genuine empty results.

A run with unresolved required retrieval tasks cannot be labelled complete or
saturated. Permit explicit waivers, but record who or what waived the task, why,
which branches and coverage areas are affected, and the resulting degraded-run
status. Compare evaluation runs only under equivalent source availability or
report degraded-source results separately.

### 12. Canonical works with preserved manifestations

Represent each source record as a manifestation and resolve manifestations into
canonical scholarly works without deleting their source-specific evidence. Merge
metadata field by field, retain conflicting titles, dates, author lists,
publication types, identifiers, abstracts, and citation links, and distinguish a
true later extension from an alternate version of the same contribution.

Measure corpus recall and synthesis inclusion at the canonical-work level while
retaining manifestation-level provenance for retrieval and audit. Identity
resolution should expose confidence and unresolved conflicts rather than forcing
uncertain merges.

Key screening decisions by canonical work, scope version, screening protocol and
prompt version, model, and an evidence fingerprint. A materially richer or
conflicting manifestation must trigger reassessment or explicit confirmation;
it must not inherit a stale decision made from weaker evidence. Deduplication
unifies identity—it does not discard evidence.

### 13. Multidimensional completeness evidence

Do not present capture–recapture overlap between search and snowball channels as
a calibrated percentage of literature recovered. Those channels are dependent:
snowballing is seeded from search, reformulation learns from retrieved records,
and providers share underlying metadata. Retain the statistic only as one clearly
labelled convergence diagnostic.

Report a completeness profile containing branch and source terminal states,
retrieval-depth and marginal-yield curves, canonical-work rediscovery across
routes, evolving map coverage, unscreened and unresolved records, failed and
bounded tasks, hidden-target recovery, and disagreements with independently
assembled external collections. Preserve the evidence behind each component.

Validate proposed stopping signals retrospectively across multiple review
domains. Prefer the defensible claim that no known gap remains under a declared
protocol, with limitations exposed, over an unknowable percentage-complete
claim.

### 14. Select semantic geometry on the downstream discovery task

Do not let whichever embedding model happens to run locally determine the
evolving query map. Bibliographic evidence repair and citation-topology
expansion remain model-independent. Export useful records with their roles,
screening evidence, and provenance, then compare embedding models on a GPU
machine.

The comparison must include a scientific-document model, a strong general
retrieval model, and a lexical baseline. Select using blinded neighbour audits,
stability, preservation of minority communities, novel eligible yield from
induced query branches, and stopping-curve sensitivity. Freeze the selected
model and its proposed branches before joining hidden recovery targets. Cluster
appearance alone is not a selection criterion.

## Implementation dependency order

1. **State and provenance substrate:** canonical works/manifestations, durable
   retrieval tasks, branch/source/direction/page events, evidence-versioned
   decisions, and explicit incomplete/bounded states (decisions 11–12).
2. **Lossless candidate flow:** discovery versus evidence roles, no hard BM25
   gate, full candidate preservation, and staged screening/repair queues
   (decisions 3, 5–7).
3. **Adaptive retrieval engines:** paginated keyword retrieval, citation-expansion
   queue, complete/progressive citation traversal, and pluggable sources
   (decisions 2, 4, 8–9).
4. **Evolving search controller:** provisional seed queries, evidence-motivated
   reformulation, emergent map revision, and coverage-aware scheduling
   (decision 1).
5. **Stopping and evaluation:** evidence-backed terminal-state checks,
   multidimensional completeness reporting, hidden-target ablations, and
   cross-domain calibration (decisions 10 and 13).
6. **Semantic-map model selection:** portable corpus export, GPU embedding
   comparison, branch freeze, then leakage-safe downstream recovery evaluation
   (decision 14).

Build vertical slices through this order so every new retrieval behaviour is
traceable and evaluable when introduced. Do not first broaden retrieval and add
provenance afterwards.
