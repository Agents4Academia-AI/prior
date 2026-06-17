# Evals

Per-agent evaluation. The headline metrics here run **without an API key** —
they check the *outputs* already cached on disk, so they're cheap to re-run and
hard to game.

| Agent | Metric | Needs key? | Script |
|-------|--------|-----------|--------|
| Reader | **groundedness** — fraction of claims whose evidence span actually appears in the source text | no | `groundedness.py` |
| Reader | claim-type distribution, claims/paper | no | `groundedness.py` |
| Cartographer | graph stats: relations found, density, contradiction rate | no | `graph_stats.py` |
| Navigator | **citation validity** — every id a Navigator answer cites exists in the atlas (no fabricated citations) | for live runs | `citation_check.py` |

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
