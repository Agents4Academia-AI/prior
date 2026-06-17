# Prior

> An open-source, three-agent system — **Reader**, **Cartographer**, **Navigator** —
> that turns scientific literature into a queryable **atlas of claims**. It answers
> *"has this been done?"* **forward** (current state of evidence) and **backward**
> (origins of an idea), grounded in primary sources rather than black-box web search.

**Team 6** (merged with Team 4): Klara · Harit · Iacopo · Elle · Arya · Luke

**Hackathon:** [Agents4Academia](https://agents4academia.github.io), 14–26 Jun 2026

Most "research agents" answer literature questions by Googling and summarising
snippets — a black box you can't audit. Prior instead builds a transparent graph
of *claims* extracted from primary sources (OpenAlex + arXiv), each carrying its
provenance and citation links, and reasons over that graph. The built atlas is a
clean **hand-off API**: a structured, grounded corpus that verification and
baseline teams can build on directly.

```
topic ─▶ Sources (OpenAlex + arXiv)
              │  papers + citation edges
              ▼
          Reader        paper            ─▶ structured, typed claims (+ evidence)
              │
              ▼
        Cartographer    claims + citations ─▶ atlas graph
              │          stated_in · cites · supports/contradicts/refines/extends
              ▼
         Navigator      question + atlas ─▶ grounded answer
                         forward : supporting / contradicting / open questions
                         backward: trace a concept to its origin paper
```

## Day-5 demo targets (Fri 19 Jun)

1. **Forward** — run `build` on a topic we know well, then `ask` a question and
   get supporting evidence, contradicting evidence, and open questions, all cited.
2. **Graceful "no"** — `ask` something the literature hasn't settled and get an
   honest *not_found*: closest work X, gap Y — instead of a confident hallucination.
3. **Backward** — `origin` traces a concept to its earliest/foundational paper
   along real citation edges.
4. **Hand-off + evals** — `atlas.json` as a structured corpus for verification
   teams, plus per-agent eval numbers (`evals/`).

## How to run

```bash
pip install -e .                 # or: pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export PRIOR_CONTACT_EMAIL=you@university.edu   # polite OpenAlex access (optional)

prior build "retrieval augmented generation reduces hallucination"
prior ask    "Does retrieval-augmented generation reduce hallucination?"
prior origin "retrieval-augmented generation"
prior info
```

Stages are cached and independently re-runnable (`ingest` is network-bound;
`read`/`map` are the LLM-bound, expensive part):

```bash
prior ingest "<topic>" --max-papers 30   # papers  -> data/raw/papers.jsonl
prior read                               # claims  -> data/atlas/claims.jsonl
prior map                                # atlas   -> data/atlas/atlas.json
prior map --no-relate                    # fast pass: citations + provenance only
```

## What's in here

| Path | What |
|------|------|
| `src/prior/sources/` | Primary-source adapters: `openalex.py` (citation graph), `arxiv.py` |
| `src/prior/reader.py` | Reader: paper → structured claims |
| `src/prior/cartographer.py` | Cartographer: claims → atlas graph (BM25 candidates + LLM labels) |
| `src/prior/navigator.py` | Navigator: forward (`ask`) and backward (`origin`) |
| `src/prior/atlas.py` | Atlas store + graph + JSON persistence (the hand-off API) |
| `src/prior/pipeline.py` | Orchestration with per-stage caching |
| `evals/` | Per-agent evaluation harness |
| `AGENTS.md` | What Claude Code reads at session start |
| `claude-progress.md` | Session continuity log |

## Configuration

Environment variables (all optional except the API key):

| Var | Default | Purpose |
|-----|---------|---------|
| `ANTHROPIC_API_KEY` | — | required for Reader/Cartographer/Navigator |
| `PRIOR_CONTACT_EMAIL` | — | OpenAlex polite-pool access |
| `PRIOR_READER_MODEL` | `claude-sonnet-4-6` | extraction (high-volume) |
| `PRIOR_CARTOGRAPHER_MODEL` | `claude-sonnet-4-6` | relation labelling |
| `PRIOR_NAVIGATOR_MODEL` | `claude-opus-4-8` | user-facing reasoning |
| `PRIOR_MAX_PAPERS` | `25` | papers per topic |
| `PRIOR_RELATION_NEIGHBORS` | `6` | candidate neighbours per claim |

## Acknowledgements

Built during [Agents4Academia](https://github.com/Agents4Academia-AI), 14–26 June 2026.
Released under the MIT License.
