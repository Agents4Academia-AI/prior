---
name: prior
description: >-
  Assess the state of the art on a research question, grounded in primary
  literature. Use when the user asks "has this been done?", "what's the evidence
  on X?", "find the contradictions in the literature on X", or wants a cited,
  honest answer (including an honest "no") instead of an ungrounded summary.
  Builds a queryable atlas of claims from OpenAlex + arXiv and reasons over it.
---

# Prior — literature-assessment skill

Prior turns primary literature into a queryable **atlas of claims** and answers
questions from it, with citations and an honest abstention path. You (the agent)
drive it through its CLI tools — that is what makes this an agent capability
rather than a one-shot prompt.

## When to use
- "Has anyone shown X?" / "What's the state of the evidence on X?"
- "What are the contradictions in the literature on X?"
- The user wants a **grounded, cited** answer and an honest "no" when the
  literature doesn't support the claim — not a confident guess.

## Tools (run from the repo root)

Set a backend once: `export ANTHROPIC_API_KEY=...` **or**
`export PRIOR_LLM_BACKEND=claude-code` (runs on the Claude Code login, no API key).

| Step | Command | What it does |
|------|---------|--------------|
| build | `python -m prior.cli build "<topic>" --max-papers 15` | ingest → read → map → `data/atlas/atlas.json` |
| ask | `python -m prior.cli ask "<question>"` | forward: supporting / contradicting / open, all cited; honest `not_found` |
| origin | `python -m prior.cli origin "<concept>"` | backward: trace a concept to its origin paper |
| contributions | `python -m prior.cli contributions` | each primary paper's self-declared, standalone contributions (full text) |
| view | `python -m prior.cli view [--contributions]` | render the atlas (or contributions) to an interactive HTML graph |
| info | `python -m prior.cli info` | one-line atlas summary |

(If installed with `pip install -e .`, `prior <cmd>` works too.)

## Workflow for "assess the state of the art on a question"
1. Pick a focused topic string from the user's question.
2. `build` the atlas for that topic (skip if `data/atlas/atlas.json` already
   covers it — check with `info`).
3. `ask` the user's exact question. Report the verdict, the supporting and
   contradicting evidence **with their citations**, and any open questions.
4. If the verdict is `not_found`, relay the honest "no": the closest work and the
   gap — do not fill the gap with ungrounded knowledge.
5. Offer `view` for an interactive graph, or `origin` to trace where an idea began.

## Rules
- Never answer from your own parametric knowledge when Prior returns claims —
  ground every statement in cited claims from the atlas.
- Preserve Prior's abstention: a graceful "no" is a correct answer, not a failure.
- One build per topic is enough; the atlas is cached and reusable.
