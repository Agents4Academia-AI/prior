# Week 2 — deferred (do NOT build before the Friday demo)

Captured so they're not lost. None of these are in the Friday MVP.

## Evaluation: IPBES-style evidence-status assessment (the *right* eval)
Prior's benefit is NOT answering broad questions better than web search — it
abstains on recall (see the QA round). The benefit is **calibrated assessment of
whether a finding is established / contested / emerging / unsupported** — the
IPCC/IPBES task, which is exactly what Navigator's forward verdict already emits.
Crucially, this is evaluable because **true labels exist** (unlike open Q&A).

- **Task.** Given a scientific claim, Prior builds/queries an atlas and returns a
  verdict (established / contested / emerging / not_found) + confidence. Score
  against the claim's ground-truth evidential status.
- **Why it's the right eval.** Tests the actual differentiator (calibrated
  evidence assessment + honest abstention), not recall; matches the system's
  design and the IPCC/IPBES framing. Reframes Prior as an *automated IPBES-style
  assessor* — a claim worth making only if measured against real labels.
- **Sources of true labels.**
  - **SciFact / SciFact-Open** (already wired, `evals/scifact/`): claim →
    SUPPORT / CONTRADICT / NOINFO + evidence sentences. Maps directly to the
    verdict — the headline starting point.
  - **PubMedQA / BioASQ** — yes / no / **maybe**; the "maybe" class tests
    calibrated abstention.
  - **Consensus / replication datasets** — replicated vs. failed-to-replicate
    findings, meta-analysed claims, retracted/overturned results → ground-truth
    "established vs. contested/overturned."
  - **IPCC / IPBES assessment findings themselves** — each finding carries a
    calibrated confidence (very low → very high): a gold standard for the task.
- **Metrics.** Verdict accuracy (4-way); abstention calibration (does not_found
  fire only when evidence is genuinely insufficient?); **confidence calibration**
  (does Prior's confidence track true evidential strength? — reliability diagram / ECE).
- **Weekend run plan.** Start with SciFact over a freshly built atlas per claim;
  then a small hand-labelled set of established-vs-contested findings in an area
  we know; report per-verdict accuracy + calibration. (Needs: build atlas per
  claim's topic — full-text + reviews-as-evidence decisions from below apply.)

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
   - Full text de-risked. **HTML-first**: `arxiv.org/html/<id>` (→ `ar5iv.org`
     fallback) gives clean text and surfaces the explicit contribution list
     verbatim ("The contributions of our work can be summarized as follows: • We
     propose …") — no PDF parsing. Fall back to PDF (`pypdf`) only for non-arXiv
     OA sources (ACL/MDPI), via OpenAlex `best_oa_location.pdf_url`. Add a
     `fulltext` field/fetch to `Paper`; focus the agent on abstract + intro.
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

**Agent granularity** (the "merge step = its own agent?" question):
- **Merge / Canonicalize = its own agent.** Decides *equivalence* and collapses
  contributions across papers into canonical nodes (collapses nodes, not labels
  edges) — genuinely distinct.
- **Relate (supports/extends/contradicts between contributions) = reuse
  Cartographer**, not a new agent — same task it does for claims.
- **Novelty = its own agent** (judges new-vs-overstated using merge + chronology).

This implies a **two-tier roster**:
- *Local / per-paper:* Reader (claims), Contributor (contributions).
- *Global / per-graph, iterative:* Cartographer (relate), Merge (canonicalize),
  Novelty (assess), Auditor (verify), Navigator (query) — run over the whole
  atlas and re-run as it grows.
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
