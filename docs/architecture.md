# Prior — agentic architecture & tutorial

How Prior is built as agents, what tools and skills it exposes, and how to run
it. Written so another team can pick it up and reuse the pieces.

## The idea in one paragraph

Prior turns primary literature into a queryable **atlas of claims** (a typed
graph) and answers questions from it — with citations, surfaced contradictions,
and an honest "not found". Three LLM agents do the work over one shared atlas;
each is exposed as a CLI **tool**, and the whole workflow is packaged as a
Claude Code **skill** so any agent (or person) can drive it.

```
topic ─▶ Sources (OpenAlex + arXiv)
              │
              ▼
          Reader  ──▶  Cartographer  ──▶  [ shared atlas: claims · typed edges ]  ──▶  Navigator
       paper→claims    claims→graph                                                   question→answer
```

## The three agents

Each agent is the same pattern: a **system prompt** + **structured output**. The
structured output is forced via a single tool whose schema is the shape we want
(`src/prior/llm.py: structured()`), so the model returns valid JSON, not prose.

| Agent | File | In → Out | How |
|-------|------|----------|-----|
| **Reader** | `reader.py` | one paper → atomic, typed claims (+ evidence span, confidence) | one structured call per paper |
| **Cartographer** | `cartographer.py` | claims → typed relations (supports/contradicts/refines/extends) | BM25 proposes candidate pairs; one structured call per claim labels them (avoids O(n²)) |
| **Navigator** | `navigator.py` | question + atlas → grounded answer | BM25 retrieves relevant claims; one call returns verdict + supporting/contradicting/open, or `not_found` |

(A fourth agent, **Auditor** — claim-fidelity + citation honesty — is designed
but deferred to Week 2; see `WEEK_2.md`.)

The shared **atlas** (`atlas.py`) is a property graph persisted as JSON
(`data/atlas/atlas.json`) — papers and claims are nodes; `stated_in`, `cites`,
and the four semantic relations are edges. That JSON is the **hand-off API**:
other teams load it and build on a grounded, structured corpus.

## Tools (the CLI)

Each command is a tool an agent or person can call:

```
prior build "<topic>" [--max-papers N] [--cite-hops N]   # ingest → read → map → atlas
prior ask "<question>"                                    # forward: state of evidence (cited)
prior origin "<concept>"                                  # backward: trace to origin
prior view [--contributions]                              # interactive HTML graph
prior info                                                # one-line atlas summary
# lower-level: prior ingest / read / map
```

## Skill (the agent artifact)

`.claude/skills/prior/SKILL.md` packages the above as a **Claude Code skill**:
when a user asks "has anyone shown X?" / "what's the evidence on X?", the agent
loads the skill and drives `build` → `ask` → `view` as tools. That's what makes
Prior an *agent capability*, not just a script.

## Pluggable backend — run on a subscription, not API credits

All model calls go through `src/prior/llm.py`, which has two backends
(`PRIOR_LLM_BACKEND`):

| Backend | Runs on | Cost |
|---------|---------|------|
| `api` (default) | Anthropic API (`ANTHROPIC_API_KEY`) | metered credits |
| `claude-code` | Claude Agent SDK → your Claude Code login (e.g. Max) | flat-rate, no API credits |

The whole Friday demo was built and run on `claude-code`.

## How to run (tutorial)

```bash
# 1. install
pip install -e .                 # or: pip install -r requirements.txt

# 2. pick a backend
export PRIOR_LLM_BACKEND=claude-code      # uses your Claude Code login …
#   … or:  export ANTHROPIC_API_KEY=sk-ant-...

# 3. build an atlas, then ask it things
python -m prior.cli build "retrieval augmented generation reduces hallucination" --max-papers 15
python -m prior.cli ask   "Does retrieval-augmented generation reduce hallucination?"
python -m prior.cli ask   "Has anyone used RAG for protein structure prediction?"   # honest "not_found"
python -m prior.cli view                  # open data/atlas/view.html
python -m prior.cli view --contributions  # contributions-only graph
```

A one-command runbook for the demo lives in `scripts/demo.sh`.

## Evals (`evals/`)

| Agent | Metric | Key-free? | Script |
|-------|--------|-----------|--------|
| Reader | groundedness (evidence span found in source) | yes | `groundedness.py` |
| Cartographer | graph stats (relations, contradictions, connectivity) | yes | `graph_stats.py` |
| Navigator (forward) | SciFact SUPPORT/CONTRADICT/NOINFO accuracy | wired | `scifact/` |
| Navigator (backward) | origin grounded in citation ancestry | yes | `origin_check.py` |
| — | Prior vs vanilla / web-search Claude | — | `baseline_vanilla.py`, `baseline_websearch.py` |

Real numbers: [`../evals/results.md`](../evals/results.md) ·
graph stats: [`graph_stats.md`](graph_stats.md).

## File map

```
src/prior/
  sources/{openalex,arxiv}.py   primary-source adapters (citation graph)
  reader.py cartographer.py navigator.py   the three agents
  atlas.py models.py            the graph + data types
  llm.py                        pluggable backend (api / claude-code)
  pipeline.py cli.py            orchestration + tools
  render_html.py                the web view
.claude/skills/prior/SKILL.md   the Claude Code skill
evals/                          per-agent evals + baselines
```
