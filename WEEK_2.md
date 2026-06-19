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

- **Other evidence-calibration frameworks & label sources (optional).** Every
  serious evidence field has reinvented IPCC-style calibration — useful as both
  framing ("not niche") and label sources:
  - **GRADE** (evidence-based medicine): certainty High/Moderate/Low/Very-Low —
    the IPCC of medicine. **Cochrane** Summary-of-Findings tables = thousands of
    gold certainty labels. Best label source after SciFact.
  - **Replication labels:** DARPA **SCORE** / **Replication Markets** (confidence
    + actual replication outcome), Reproducibility Projects (Psych, Cancer Bio).
  - **Fact-verification datasets (FEVER family):** FEVER, **Climate-FEVER**
    (on-theme), HealthVer, PubHealth, COVID-Fact, SciTab — Supported/Refuted/NEI.
  - **scite.ai Smart Citations:** supporting/contrasting/mentioning at scale
    (structurally = Prior's supports/contradicts edges).
  - Other frameworks: USPSTF grades, Oxford CEBM levels, IUCN Red List
    (biodiversity), ICD-203 / Words of Estimative Probability (intelligence),
    ENFSI likelihood ratios (forensics), Evidence-Based Software Engineering.
  - **ML-specific (this is mostly a GAP Prior could fill):** no GRADE/IPCC
    equivalent exists for ML. But label material does: **ML Reproducibility
    Challenge / ReScience** (did it reproduce?), **Papers with Code** leaderboards
    (SOTA corroborated vs. superseded), "reality-check" meta-eval papers (curated
    contested findings, e.g. metric-learning / GAN / deep-RL reproducibility
    critiques), **rliable** (stratified-bootstrap CIs — statistical calibration
    tooling), **OpenReview** (reviewer confidence + accept/reject + later
    citations). ML also owns the *calibration machinery* itself (model
    calibration: ECE, reliability diagrams, temperature scaling) — reuse it to
    score Prior's confidence.

## Assessor agent (the calibrated-evidence-assessment core)
Replaces Navigator's *holistic* verdict with a *derived, inspectable* one. This
is the piece that turns Prior into a calibrated assessor; the rest is plumbing
we already have.

Input: a target claim + the atlas. Per claim:
1. Gather bearing claims/contributions (supports/contradicts/refines edges +
   semantic match).
2. Classify each: stance (support/contradict/refine); **evidence quality**
   (measured-empirical ≫ asserted ≫ theoretical — use claim type); **independence**
   (distinct papers/groups; discount mutual-citation clusters via the citation graph).
3. **evidence_level** (limited/medium/robust) = f(independent count × quality).
4. **agreement_level** (low/medium/high) = f(support-vs-contradict balance, weighted).
5. **confidence** = Mastrandrea(evidence_level, agreement_level).
Output: {claim, confidence, evidence_level, agreement_level, supporting[],
contradicting[], gaps[]} — *derived*, not vibed.

ML wrinkles: up-weight reproduced / benchmarked / statistically-significant
results (rliable-style CIs); down-weight **superseded** claims (recency via
`cites`); independence is sneaky (shared codebases/benchmarks ≠ independent).

## Calibration harness (weekend — `evals/calibration/`)
"Calibrated" is an empirical claim, so this loop is what earns the word.
- **Gold set:** claims with known status. Start with SciFact (wired) + Climate-FEVER;
  add a small hand-labelled **ML** set with a spread: established (e.g. "residual
  connections enable training very deep nets"), **contested/overturned** (e.g.
  "batch norm works by reducing internal covariate shift" — refuted by Santurkar
  et al.), emerging/thin.
- **Per claim:** build a *representative* atlas (multi-seed queries + `--cite-hops`),
  run the Assessor, map confidence/verdict → the gold label.
- **Metrics:** verdict accuracy; abstention calibration; **confidence calibration**
  (reliability diagram / ECE).
- **MVP first:** just the 3–5 known ML claims. If the batch-norm-via-ICS claim
  comes out **contested** (Santurkar's contribution contradicts Ioffe-Szegedy's),
  that's the first real evidence the assessment works on a case we *know* — a far
  stronger result than the open-QA comparison.

## Verification-stamp schema (the interface for the cohort)
Prior is the shared substrate; the other teams are enrichers (write stamps) and
consumers (read). Prior's job is to expose the **interface**, not build every
verifier. Each claim/contribution carries an **open set of verification stamps**,
one per enricher. (See `docs/shared-substrate.md` for the team mapping.)

Claim record gains:
```
verifications: {
  extraction_fidelity:  {verdict, score, by, evidence, ts}   # Prior/groundedness — HAVE
  citation_honesty:     {verdict, real, relevant, fair, by, ts}   # Team 2
  reproducibility:      {verdict, by, ts, link}              # Team 1 (benchmark replicator)
  internal_consistency: {verdict, by, ts}                    # Wittgenstein / Reviewer #2
  novelty:              {verdict, by, ts}                    # Reviewer-0
  ...open: a team registers a new check type; Prior need not know each
}
```
Each **stamp** = `{check, verdict (pass/fail/uncertain), confidence, by (agent/team
id), evidence/notes, timestamp, link?}`. Generalises the already-specced Auditor
fields (`audited`, `citation_check_pass`, `method_attribution_check_pass`).

API (formalise `atlas.json`):
- **read** — get a claim + its stamps; **write** — append a stamp (idempotent per
  check×agent); **query** — claims by topic / verification status / stance.

The **Assessor** reads the stamps: evidence weight = base quality × **verification
depth** (which checks passed, by whom). So the calibrated confidence is aggregated
from the cohort's verification work — not citations.

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
