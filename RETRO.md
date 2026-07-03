# Prior — contributions & a candid retrospective

For anyone curious how Prior was actually built: **who did what**, and **an honest account of
the human + Claude collaboration** — what the AI did well, and where it needed a human hand.
The Anthropic brief is about model behaviour on agentic-research tasks, and honesty is Prior's
whole point, so it felt worth writing down.

## Who did what

- **Klara Kaleb** — project lead and editorial direction; the core pipeline (**Scoper**:
  scoping, recall→precision, snowball; **Contributor**: contribution/claim extraction;
  **Cartographer**: cross-paper atlas + consensus edges), the atlas viewer, groundedness /
  SciFact evals, and the writeup.
- **Harit Vishwakarma** — the web application (nav rail, Papers, agentic **Ask**, **Report**,
  streaming chat across model backends), the self-auditing **Eval** system (multi-judge
  scorecard, cross-judge agreement, calibration), the D3 graph viz + collections UI,
  ingestion / dedup, a fast headless LLM backend, and deployment.
- **Yee Whye Teh** — whole-paper Markdown rendering (LaTeX math + figures), Scoper
  abstract-repair (recovering foundational papers), method-comparison tooling and tests.
- **Claude (Claude Code, mostly Opus 4.8)** — most of the implementation under human
  direction: pipeline code, the `prior view` CLI, scripts, docs and this writeup, research
  synthesis, and the release engineering.

## How it went

Prior was built **human-in-the-lead, Claude-in-the-loop**. Klara owned the direction and every
judgement call; Claude did most of the typing — code, docs, research, and the git/release
plumbing. Over a two-week sprint a clear division of labour emerged.

**Claude was strong at volume and mechanics.** It drafted the bulk of the pipeline, the CLI,
and the docs quickly, and iterated well on feedback. It was reliable at fiddly, high-stakes
plumbing — scrubbing secrets from git history, squashing to a clean public commit, archiving
the full history privately first, always verifying via a fresh clone and pausing before
anything irreversible. And it was good at synthesis: reading and situating related work, and
catching that half the token-usage logs were duplicated, then re-deriving the numbers.

**It needed a human wherever ground truth or taste came in.** Left alone it both *over-* and
*under-*claimed — it called a real limitation "model noise, don't trust it" (too strong), then
first dismissed a key result as "just extracting categories" until pushed to read it properly.
It introduced framing the writeup hadn't earned (a Nature-based-Solutions aside, a whole
"Vision" section), each cut on review. It got facts and names wrong — treating a publicly
tweeted deck as a private share, writing "Eureka" for a project actually named *UReKA*. Its
first screenshot was of the old UI and its first GIFs zoomed in too far. And, tellingly, a
compliance problem — an institutional-access scraper it had built earlier — was **caught by
the human, not surfaced by the model.** Throughout, the editorial calls (what to cut, how to
structure, what to keep private) were the human's.

## The takeaway

The split that worked: **the human owns direction, taste, ground truth, and ethics; Claude
owns volume, synthesis, and mechanics.** The failures clustered exactly where the model lacked
ground truth — what's public, what a thing is called, what the team values — or where curation
was needed. Which is precisely where keeping a human in the loop earns its keep.
