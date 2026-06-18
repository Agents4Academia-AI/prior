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

## Contribution + Novelty pipeline (atlas-aware, iterative)
Not a per-paper classifier — self-declared contributions ≠ true contributions,
because papers overstate novelty. True novelty is only judged against the atlas.
Four stages:

1. **Extract** (per paper, FULL TEXT). The paper's *self-declared* contributions,
   anchored on intro language ("we propose / introduce / present", "our
   contributions are", "in this work we …"). High precision; distinct task from
   Reader (which extracts ALL claims incl. background/survey/future-work).
   - Full text de-risked: OpenAlex exposes OA PDFs (`best_oa_location.pdf_url`;
     ACL/arXiv/MDPI all worked), arXiv via `arxiv.org/pdf/<id>`, extract with
     `pypdf`. Add `pdf_url` to `Paper`; focus the agent on abstract + intro.
2. **Merge / canonicalize** (atlas-wide). Cluster equivalent claims across papers
   into **canonical nodes** (similarity via embeddings or an LLM judge). The
   canonical claim is the node; papers attach as evidence. THIS is "global graph
   lists contributions, not claims."
3. **Assess novelty** (atlas + chronology). For each self-declared contribution,
   check whether an equivalent canonical claim already existed in an *earlier*
   paper → overstated novelty; no match → genuinely new. Catches overstatement.
4. **Iterative.** Novelty is relative to the current atlas, so re-merge and
   re-assess as it grows (more papers, `--cite-hops`).

This is the IDEAS-deck **Reviewer-0 / Novelty Due Diligence** idea; serves use
case (b) novelty/gaps and (c) duplicate/competing claims.
- **Caveats:** novelty is corpus-bounded ("novel relative to what we ingested");
  chronology is messy (preprint v1 vs publication dates).
- **Until built:** `prior view --contributions` uses a claim_type heuristic
  (drops definitional) — a rough proxy, with known false positives.

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
