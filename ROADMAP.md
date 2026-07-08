# Roadmap

Where Prior goes next, grouped by what each cluster improves. (Summary in the
[README](README.md#roadmap); contributions welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).)

## Trust & calibration — make the graph trustworthy

- **Evidence-weighted confidence (the headline).** Today confidence answers *"was this
  faithfully extracted, and do the models agree?"* — a per-node extraction score plus
  `triple`/`double`/`opus_only` model-agreement tiers, self-audited for calibration. It is
  **not yet** *"how strong is the evidence?"*. Next: calibrate a claim by the *strength and
  agreement of its evidence* (the IPCC/IPBES scheme, Mastrandrea et al. 2010), not just how
  many model runs concur.
- **Decompose relation extraction (the easiest win).** Relations are the weak link (21–53%).
  The Cartographer labels a contribution against ~6 candidates in one call; that batching
  raises the *relational complexity*, where LLMs degrade and don't recover with scale
  ([Fesser et al. 2026, *REL*](https://arxiv.org/abs/2604.12176)). Split into lower-arity
  calls — *is there a relation? · what type? · which direction?* — pairwise for the hard
  cases, and keep anchoring direction to publication year.
- **Contradiction as its own agent** — lift precision past the ~50% floor: the "significance
  everywhere vs. nowhere" selection problem, head-on.
- **Eval as a gate** — make the key-free eval scorecard a *blocking* CI check, so a PR that
  regresses faithfulness / grounding / relation numbers fails and quality only ratchets up.
- **Citation verification integration** — firstly port c-v's reference resolution into the ingestion of prior, and then run similiar support checks to them on our edges,(check that the evidence actually supports asserted relation between contribution quotes) giving each edge a stamp in the procsess. Then apply c-v's support judgement to the 525 mined contexts and classify each before relation labelling, feeding this in as a prior on edge type. Finally measure and hope for a precision lift.

## Coverage & sources — what's in the graph

- **Beyond papers** — generalise the `Paper` node to a typed `Source` (talk, blog, video,
  thread, preprint) with credibility-weighted provenance, so the atlas reflects the whole
  scholarly conversation, not just the archived record.
- **Negative & null results** — give each claim a polarity (positive / negative / null /
  mixed) so the atlas captures what *didn't* work, countering publication bias.
- **Citation-aware Cartographer** — once the citation graph is backfilled, use real citations
  to set relation direction and to check model-guessed edges.

## Structure & synthesis — the higher-level shape of a field

- **Contribution roll-up + establishedness** — surface the latent claim hierarchy (distinct
  leaves → broader synthesized claims), non-destructively, and compute a graph-derived
  *establishedness* from independent support (the ontology-trap risk is real — specced
  separately, staged and human-approvable).
- **Gap surfacing — a coverage view, not the graph.** Absence is invisible in a node-link
  layout; a method × task (or community × claim-type) matrix makes under-studied cells pop,
  plus a Navigator "what's under-supported?" query.

## Distribution — get it to people and agents

- **Hosted demo** — a public, STORM-style instance to try Prior without installing.
- **MCP server — Prior as an agent tool.** Expose the atlas over MCP so other agents can build
  and query it — the graph as agent-queryable long-term memory, not just a human UI.
