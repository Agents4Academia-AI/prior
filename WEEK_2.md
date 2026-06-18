# Week 2 — deferred (do NOT build before the Friday demo)

Captured so they're not lost. None of these are in the Friday MVP.

## Agent decomposition: relations / use cases as agents & skills
Split agents by **task**, not by edge label.
- Keep ONE relation-classifier agent for `supports` / `refines` / `extends`
  (same NLI-style judgment over the same candidate pairs — don't fragment).
- Elevate **contradiction detection** to its own agent/skill: higher-stakes,
  a distinct task (real logical conflict vs. scope difference), benefits from
  verification, maps to use case (c) and to Team 2.
- `cites` / `stated_in` are structural (OpenAlex / Reader) — not agents.
- The real wins are **analysis agents over the graph**, matching the use cases:
  - **(b) novelty/gap agent** — find under-supported or missing regions.
  - **(c) contradiction-impact agent** — find a contradiction, then walk
    `cites`/`extends` to see which follow-up works inherited it (a traversal,
    not an edge type).
- Frame each as an *operation on the shared graph*; other teams' agents slot in.

## Contribution agent (the global-graph node extractor)
A dedicated agent — distinct task from Reader. Reader extracts *all* claims
(incl. background, definitions, surveys of open problems, others' work, future
directions). The **Contribution agent** isolates a paper's *own novel,
self-declared* offering.
- **Key signal:** papers name their contributions explicitly ("we propose /
  introduce / present", "our contributions are", "in this work we …"). Anchor on
  that self-declaration — high precision — rather than inferring from claim_type
  (the type heuristic produced false positives, e.g. a "four open challenges"
  survey claim slipping into the contributions view).
- **Output:** 1–4 contributions per paper, each linked to supporting claim(s)
  via `contributes_to`. These are the **global graph's nodes** ("global graph
  lists contributions, not claims").
- **Caveat:** the explicit contribution list is usually in the intro; abstract-
  only ingestion catches most but not all → full-text ingestion raises recall.
- Until then, `prior view --contributions` uses a claim_type heuristic (drops
  definitional) — a rough proxy, not real contribution extraction.

## Other deferred items (from the team scope decision)
- Auditor agent + its two modes (claim-fidelity, citation real/relevant/fair) —
  Team 2 folds in.
- IPCC schema migration on `Claim` (evidence_level / agreement_level /
  derived confidence / likelihood / scope / contested fields).
- IP-X prose report rendering.
- Local-vs-global schema refactor in code (the README diagram holds the
  distinction; the single atlas is fine for the demo).
- Cross-field equivalence detection; supersession edges.
- OKF / Open Knowledge Format exporter; ORKG / NCG dataset ingestion.
- Backward-genealogy improvements beyond current `prior origin`.
