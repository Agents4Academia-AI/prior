# Prior — demo script (~5 min)

## SETUP (run once, before you present)
```bash
cd ~/Desktop/hackathon/prior
export PRIOR_LLM_BACKEND=claude-code          # or: export ANTHROPIC_API_KEY=sk-ant-...
# open the deck + the centerpiece view:
open docs/slides.html
open data/atlas/view_evolution.html
```
Have a terminal + the browser tab side by side. **Do NOT live-build** — the atlas is cached.
Backup answers (if a live `ask` is slow) are in `/tmp/demo_q*.txt`.

---

## BEAT 0 — what it is (15s)
> "Prior turns scientific literature into a queryable, **auditable graph of claims** —
> grounded in primary sources, not web search. Three agents: **Reader** extracts
> claims, **Cartographer** relates them, **Navigator** answers."

## BEAT 1 — the artifact (90s)  ← the centerpiece
Show `view_evolution.html`. Click the stage buttons **1 → 2 → 3**:
> "Watch the atlas build. **Stage 1: papers.** **Stage 2:** each paper decomposes into
> its *self-declared contributions*. **Stage 3:** cross-paper relations connect them —
> supports, extends, refines."

Click one contribution node:
> "Every node is traceable — here's the contribution, the exact quote from the paper,
> the full citation. This structured graph is the artifact other teams plug into."

*(Numbers for this view: 12 papers · 39 contributions · 17 cross-paper relations.)*

## BEAT 2 — use case (a): grounded assessment (90s)
```bash
PYTHONPATH=src python3 -m prior.cli ask "Does retrieval-augmented generation reduce hallucination?" --contributions
```
> "Verdict **ESTABLISHED** — but look: it surfaces *supporting* evidence (Shuster's
> >60% reduction), *contradicting/limiting* notes, and open questions — that the
> strongest quantified result is a single study. Every statement cites a specific
> paper. Calibrated and honest, not a confident blob."

## BEAT 3 — the graceful "no" (45s)
```bash
PYTHONPATH=src python3 -m prior.cli ask "Has anyone used retrieval-augmented generation for protein structure prediction?" --contributions
```
> "Verdict **NOT_FOUND**. When the evidence isn't in the corpus, it says so — names
> the closest work and the exact gap — instead of fabricating. Vanilla Claude, asked
> this, invents specific papers. Prior abstains. That honesty is the point."

## BEAT 4 — differentiation + vision (60s)
> "Versus an ungrounded LLM: Prior **won't hallucinate citations**. Versus web search:
> we trade breadth for **structure, provenance, and a reusable auditable graph**.
>
> The bigger picture: medicine has GRADE, climate has IPCC, biodiversity has IPBES —
> every field has a **calibrated evidence-assessment** system. **ML has none.** Prior
> is that, for ML. And it's the **shared substrate** the cohort plugs into — citation
> verification, benchmark replication, reviewers all enrich and read one graph. We
> have a concrete eval plan with **real labels** (SciFact) to prove the calibration."

## CLOSE (15s)
> "Open source, runs on a Claude Code subscription, hand-off API ready. That's Prior."

---

## GUARDRAILS (don't get caught overclaiming)
- **Talk only about the contributions graph** — 12 papers · 39 contributions ·
  17 relations. Don't bring up the raw claims graph (it's messier and not the point).
- **Don't** say calibration is *done* — it's the direction + an eval plan.
- **Don't** say "better than web search" on answers — we trade breadth for structure/auditability.
- If asked about contradictions: the relations are supports/extends/refines —
  *"at the contribution level papers mostly propose and build on each other."*

## IF SOMETHING HANGS
- A live `ask` slow? Read the captured output from `/tmp/demo_q1.txt` / `q2`.
- Browser shows stale view? Hard-refresh `Cmd+Shift+R`.
