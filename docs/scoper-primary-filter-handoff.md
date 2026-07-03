# Handoff: tighten the primary-only filter (Scoper)

Non-primary literature is leaking into the corpus, against the `principles.md`
"primary sources only" rule. Found while auditing the AI-scientist consensus graph.

## The leak
- **Confirmed:** `arxiv:2602.13855v1` — *"From Fluent to Verifiable: Claim-Level Auditability for Deep Research Agents"* (Rasheed) self-describes as **"This perspective proposes…"** → a position/perspective paper. Should be excluded.
- Likely others (position/critique pieces, e.g. "Stop Automating Peer Review…", "Are We There Yet?…").

## Why the current filter misses it
- **`is_review` and the OpenAlex `type` veto are unreliable here.** On the 155-paper core: `is_review=True` for 11 — but almost all are **peer-review-*topic* primary papers** (DeepReview, ReviewRL, AgentReview…), not review *articles*. The flag conflates "review article" with "about reviewing." It both **misses** arXiv perspectives and **false-positives** on the whole peer-review cluster.
- A naive title/`review` keyword filter over-flags ~16% for the same reason. **Don't filter on `is_review` or bare "review".**

## What works (use this signal)
Judge the paper's **nature by content**, not metadata:
- the work's own framing: *"this perspective / this position / position paper / we argue / we advocate / we call for / a survey of / systematic review / we review the…"*
- unambiguous article-type titles: *perspective, position paper, a survey, survey of, systematic review, a review of, roadmap, viewpoint, primer* — **but not** bare "review" / "peer review".

## Recommended fix
1. **Scope step (you):** add a one-line rubric to the LLM relevance/scope filter — *"reject perspective / position / survey / review articles; keep primary empirical/methodological contributions (incl. papers whose **topic** is peer review)."* This is a content judgment the model can make; metadata can't.
2. **Interim QA gate:** `scripts/atlas_review.py` now emits `non_primary_candidate` flags (content-framing + safe title types, human-confirmed — never auto-drop). Run it post-Cartographer; review the flags.
3. **Now:** drop `arxiv:2602.13855v1` from the core.

Cross-ref: `principles.md` (primary-only), `atlas_review.py` (the linter), the ontology-trap staging discipline (human-confirm, don't auto-mutate).
