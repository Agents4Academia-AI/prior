# Scoper ledger gap analysis

Date: 12 August 2026

Scope: Scoper corpus construction only. Cartographer and the separate survey
repository are out of scope. This document records no confidential source,
identity, wording, or implementation detail.

## Shipped implementation versus required evidence

| Evidence requirement | Before this change | Status after this change |
|---|---|---|
| Frozen scope and criteria | Topic path only in the evaluation manifest | Scope text plus SHA-256 fingerprint |
| Database, timestamp, API parameters | Sources implied; no event timestamps | UTC timestamps plus query-level source requests and limits |
| Model, prompt, code versions | Optional model argument only | Model argument and git revision; prompt identity/version remains open |
| Proposed/selected/rejected/stopped coverage hypotheses | Follow-up queries only, no hypothesis objects | Still open; no new agent behavior was added |
| Every query and motivating observation | Initial queries embedded in the manifest; follow-ups absent | Explicit probe and reformulation events with compact motivation |
| Every candidate, source rank, deduplication, discovery channel | Candidates and broad channel logged | Query/branch, source rank, channel, and cross-source dedup decisions recorded |
| Screening decision, confidence, evidence, correction | Decision and short reason logged | Confidence, evidence locators, and correction history remain open |
| Citation expansion path | Citation candidates labelled by channel | Exact seed, direction, and edge path remain open |
| Marginal yield and stopping rationale | Snapshot yield and threshold reason logged | Present, but unresolved facets and considered-not-run branches remain open |
| Source/API failures and fallback | Console text only | Structured failure and continuation policy recorded; internal retries remain source-adapter behavior |
| Frozen bibliographic records | Candidate records embedded in JSONL | Present for returned candidates; source-response snapshots/checksums remain open |
| Machine-readable contract | Ad hoc JSONL consumed permissively | Versioned envelope and fail-fast validation |

## Smallest coherent improvement

The existing Scoper viability collector was the narrowest truthful place to add a
ledger contract: it already observes candidates, screening decisions, yields, and
stopping. `prior.scoper-ledger/1.0` now gives every event a stable run envelope,
freezes the natural-language scope, records code/run provenance, makes probe and
reformulation decisions explicit, and validates the trace before scoring.

This does not claim that the production `explore()` console trace is now fully
auditable. It also does not introduce coverage-hypothesis branching. The next
compatible increment should capture query-level source requests/responses and
deduplication, followed by citation seed/direction paths and source failures.

The next increment adds query-level retrieval requests/results, source ranks,
cross-source deduplication decisions, and failures. Query branches also emit growth
snapshots: returned unique records, first-observed globally new records,
rediscoveries, newly included records, eligible yield, and cumulative corpus size.
First-observed attribution prevents overlapping queries from double-counting growth.
The underlying result events preserve overlap for later Shapley-style or shared
attribution if that becomes scientifically useful.

`evals/scoper_monkeys/viewer.html` provides a read-only Three.js projection of
these records. It derives branch and paper nodes solely from the ledger and shows
the underlying provenance on selection; it is an audit aid, not an additional
record or evaluation result.

## Reproducibility boundary

- Procedural: improved by the declared schema and parameters, not yet complete.
- Decision: improved for query reformulations; branch alternatives remain absent.
- Corpus: candidate bibliographic records are frozen in the ledger, but raw source
  responses and index snapshot versions are not.
- Outcome robustness: requires dated reruns and comparison; this change provides
  identifiers and provenance needed to conduct that evaluation but no result.
