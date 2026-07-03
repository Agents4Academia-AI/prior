# Contributions & retrospective

## Contributions

- **Klara Kaleb** — project lead + editorial direction; the core pipeline — **Scoper**
  (scoping, recall→precision, citation snowball), **Contributor** (contribution/claim
  extraction), **Cartographer** (cross-paper atlas + consensus edges) — the atlas viewer,
  groundedness / SciFact evals, and the writeup.
- **Harit Vishwakarma** — the web application (nav rail, Papers, agentic **Ask**,
  **Report**, streaming chat across model backends), the self-auditing **Eval** system
  (multi-judge scorecard, cross-judge agreement, calibration), the D3 graph viz +
  collections UI, ingestion / dedup, a fast headless LLM backend, and deployment.
- **Yee Whye Teh** — whole-paper Markdown rendering (LaTeX math + figures), Scoper
  abstract-repair (recovering foundational papers), method-comparison tooling and tests.
- **Claude (Claude Code — primarily Claude Opus 4.8, with Sonnet 4.6 and Haiku 4.5)** —
  most of the implementation grunt-work under human direction: pipeline code, the
  `prior view` CLI, scripts, docs and the writeup, research synthesis, and the release
  engineering.

## How we worked — a candid retrospective

Prior was built **human-in-the-lead, Claude-in-the-loop** over a two-week sprint. Because
the Anthropic brief is about *model behaviour on agentic-research tasks* — and because
Prior's whole point is honesty — here's a frank account of how the collaboration actually
went: what Claude (via Claude Code) did well, and where it needed a human hand.

### What Claude did well

- **Implementation volume.** The bulk of the pipeline, the `prior view` CLI, the scripts,
  the docs, and the writeup — drafted fast and iterated on.
- **Release engineering.** Scrubbing secrets from git history, squashing to a clean public
  commit, archiving the full history privately *first*, and verifying every step via fresh
  clones — with deliberate pauses before each irreversible force-push.
- **Research synthesis.** Reading and situating related work (decision-reason extraction in
  PNAS, relational-reasoning limits, the Papers-with-Code revival) and turning it into
  strategy and outreach notes.
- **Reconciling messy numbers.** Catching that ~half the usage-log lines were duplicates and
  re-deriving the token accounting from scratch.
- **Executing cleanly once a problem was named** — e.g. excising an institutional-access
  fetch path from both the code *and* the history.

### Where it needed steering

- **Over- and under-claiming.** It called a real limitation "model noise, don't trust it"
  (an overstatement — corrected), and it initially *under*-sold a key PNAS result as "just
  extracting categories" until pushed to re-read it properly.
- **Framing "out of nowhere."** It introduced motifs the writeup hadn't earned — a
  Nature-based-Solutions aside, IPCC/IPBES, a whole "Vision" section — each cut or properly
  motivated on review.
- **Facts and names.** It mis-read a Google Drive signal and reported that a researcher had
  "shared his deck with you" when he'd simply tweeted it publicly; it wrote "Eureka" for a
  sister project actually named **UReKA**.
- **Visuals.** Its first screenshot was of the *old* UI; its first GIFs were zoomed in too
  far with the legend covering the graph — both redone.
- **Editorial judgment.** What to cut, how to group sections, what to keep private, where the
  Quickstart belongs — the curation was consistently the human's; Claude produced material,
  the human shaped it.
- **Proactivity.** The compliance risk above was **caught by the human**, not surfaced by the
  model — it had built the path earlier without flagging it as a problem.

## The pattern

The division of labour that worked: the **human owns direction, taste, ground truth, and
ethics**; **Claude owns volume, synthesis, and mechanics**. The failures cluster exactly
where the model lacked ground truth (what's public, what a thing is called, what the team
values) or where curation was needed — which is precisely where keeping a human in the loop
earns its keep.
