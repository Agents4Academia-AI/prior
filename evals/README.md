# Evals

Per-agent evaluation. The headline metrics here run **without an API key** —
they check the *outputs* already cached on disk, so they're cheap to re-run and
hard to game.

| Agent | Metric | Needs key? | Script |
|-------|--------|-----------|--------|
| Reader | **groundedness** — fraction of claims whose evidence span actually appears in the source text | no | `groundedness.py` |
| Reader | claim-type distribution, claims/paper | no | `groundedness.py` |
| Cartographer | graph stats: relations found, density, contradiction rate | no | `graph_stats.py` |
| Navigator (forward) | **citation validity** — every id a Navigator answer cites exists in the atlas (no fabricated citations) | for live runs | `citation_check.py` |
| Navigator (forward) | **SciFact** — SUPPORT/CONTRADICT/NOINFO accuracy + abstention | for live runs | `scifact/` |
| Navigator (backward) | **origin grounding** — is a traced origin a real citation ancestor of the matched papers? | for live runs | `origin_check.py` |

Results template for the Friday slide: [`results.md`](results.md).

```bash
# After `prior build "<topic>"`:
python evals/groundedness.py
python evals/graph_stats.py
python evals/citation_check.py "Does RAG reduce hallucination?"   # needs key
```

`groundedness` is the load-bearing Reader metric: an extractor that paraphrases
or invents claims scores low even if the prose looks plausible. `citation_check`
is the load-bearing Navigator metric: it catches the failure mode that motivates
Prior — confident answers grounded in nothing.

## SciFact — the headline Navigator eval (`scifact/`)

SciFact labels claims SUPPORT / CONTRADICT / NOINFO against a corpus of
abstracts — a near-direct mirror of Prior's forward output (supporting /
contradicting / abstain), and the only public source of contradiction labels the
Cartographer can be scored against. Per claim we BM25-retrieve the top-k
abstracts, run Navigator over a small atlas built from them, and map its verdict
to a label. We report 3-way accuracy, macro-F1, and the NOINFO (abstention) row.

```bash
# one-off: fetch SciFact
python evals/scifact/run.py --data data/scifact --download --mock   # downloads, then a free dry-run

# validate the whole harness with ZERO API calls / ZERO credits:
python evals/scifact/run.py --data data/scifact --mock

# cheap real dev slice; --cache makes reruns free:
python evals/scifact/run.py --data data/scifact --limit 20 --cache data/scifact/preds.jsonl

# full run:
python evals/scifact/run.py --data data/scifact
```

## Not burning credits: the LLM backend

The Prior pipeline calls the model through `prior.llm`, which has two backends
(`PRIOR_LLM_BACKEND`, or `--backend` on the SciFact runner):

| Backend | Runs on | Cost |
|---------|---------|------|
| `api` (default) | Anthropic API (`ANTHROPIC_API_KEY`) | metered API credits |
| `claude-code` | the Claude Agent SDK → your Claude Code login (e.g. Max plan) | flat-rate subscription, **no** API credits |

So to develop the evals without spending the hackathon's API credits: use
`--mock` for plumbing (no model at all), then `--backend claude-code` for real
runs on a Max subscription. `claude-code` needs `pip install claude-agent-sdk`,
Claude Code installed and logged in, and `ANTHROPIC_API_KEY` **unset** (otherwise
the SDK may fall back to the metered API).
