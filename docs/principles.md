# Prior — design principles

> Treat LLM output as fallible normal-tech: build for verification, provenance, and
> oversight. Make *verification* the product, not the extraction. (2026-06-23)

- **Verification is the product.** LLM extraction is the cheap middle; the value is at the ends — scoping + verifying. Ungoverned extraction = "vibe coding" for graphs. So we invest in audit/review, not a fancier extractor. *(SWE essay; normal-tech)*
- **A spectrum of control**, not human-in-loop vs autonomy *(normal-tech)*:
  - Audit (point-in-time) — `atlas_review.py` checks. *(shipped, PR #4)*
  - Monitor (over time) — per-run quality scorecard + drift. *(planned)*
  - Circuit breakers — `EVAL.md` gates pause/flag on threshold. *(gates exist; wiring planned)*
  - Least privilege — agent touches the graph only via `graph.py`. *(shipped)*
- **Reversibility & legibility** *(normal-tech)*:
  - Edit mode never mutates source — it exports resolutions. *(shipped, PR #4)*
  - Provenance stamps (`both`/`text`) + evidence quotes + citations. *(shipped)*
  - Navigator returns honest `not_found`, never fabricates. *(shipped)*
- **A task-specific tool, not a chatbot.** Graph + typed queries are the interface; `ask` is one narrow entry point. *(chatbot paper; normal-tech)*
- **Provenance/reliability over size.** Node counts & "% LLM-generated" are vanity. Track provenance ratio, groundedness, relation-mix drift, confidence. *(normal-tech; SWE essay)*
- **Build oversight tooling now, train models later (if ever).** Bottleneck is verified labels + oversight, not model capability. Revisit training once the review loop yields labels at volume. *(Ellf; normal-tech)*

## Sources
- AI as normal technology — Narayanan & Kapoor — https://www.normaltech.ai/p/ai-as-normal-technology
- Why AI hasn't replaced software engineers — Narayanan & Kapoor — https://www.normaltech.ai/p/why-ai-hasnt-replaced-software-engineers
- What if AI systems weren't chatbots? — Ghosh et al. — https://arxiv.org/abs/2605.07896
- Ellf — virtual NLP engineer — Explosion (spaCy/Prodigy) — https://beta.ellf.ai/
