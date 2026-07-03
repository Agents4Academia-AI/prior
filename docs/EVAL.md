# Prior — evaluation

How we measure whether the system is doing well. The scorecard is computed by
`src/prior/eval_suite.py` (`prior eval`), written to `data/eval/results.json`, and
shown live in the web app's **Eval** tab (`/api/eval`).

## The three gates

A green system is **Faithful + Honest + Useful**:

1. **Faithful** — extraction and edges are grounded; nothing is hallucinated.
   *(the floor — if this fails, nothing downstream is trustworthy)*
2. **Honest** — abstains when the graph doesn't cover a question, and doesn't
   *over*-abstain when it does. *(the differentiator vs a confident LLM)*
3. **Useful** — the headline novelty/"has this been solved?" task is correct, and
   beats baselines. *(the payoff)*

## The scorecard

| Metric | Gate | How measured | Target | Cost |
|--------|------|--------------|--------|------|
| Extraction faithfulness | Faithful | % claims whose evidence span is in the source | ≥ 95% | key-free |
| Global-edge precision | Faithful | LLM-judge a sample of global edges — does the relation hold? | ≥ 80% | LLM |
| Grounding (no hallucination) | Faithful | every cited claim id in an answer exists as a node | 100% | LLM |
| Abstention (off-topic) | Honest | off-topic questions → `not_found` | ≥ 95% | LLM |
| In-scope coverage | Honest | in-scope questions are *not* falsely `not_found` | ≥ 90% | LLM |
| Verdict calibration (ECE) | Honest | confidence vs holdout truth (reliability) | ≤ 0.10 | pending |
| Novelty recall | Useful | `has_been_solved` surfaces related work (no false `not_addressed`) | ≥ 80% | LLM |
| Novelty vs temporal holdout | Useful | see below — chronology = ground truth | F1 ≥ 0.70 | pending |

Plus live, key-free **distributions** for the dashboard: global-edge provenance
(`text` vs `both`), global/local relation types, claim types.

## The headline eval — temporal holdout (retrodiction)

The strongest, label-free test of novelty/gap-finding:

1. Take a paper **P** (year **Y**) that claims novelty X and lists prior art (its
   citations).
2. Build the graph from papers **< Y only**.
3. Ask `has_been_solved(X)` / "is X novel?"
4. **Ground truth from chronology + P's citations:** if real prior work exists, the
   system must surface it (not say "novel"); if X was genuinely new, it should say so.

Metrics: precision/recall on "prior work exists," recall of P's actual cited
precedents, and the false-novelty rate. A variant — hide the citation edges and
check the system still links P to its precedents via the **text** hybrid — directly
measures the "finds uncited parallel work" claim. (Harness: `evals/temporal_holdout.py`,
run offline; expensive because each case rebuilds a graph.)

## Honest caveats

- **Scale.** At tens of papers the numbers are *signals*, not measurements. Real
  scores need a few hundred papers + a held-out labeled slice.
- **The irreducible part.** Edge precision, extraction recall, and novelty ultimately
  need a small **human gold set** (~20 papers / ~50–100 claims+edges) to anchor the
  LLM-judge. Everything else calibrates against it.
- **Bonus, label-free:** the continuous design enables **predictive validity** — do
  the gaps the system flags get filled by papers that arrive later?

## Baselines

Same questions to a vanilla LLM and web-search RAG vs Prior (see `evals/` on the
ingestion branches): the win condition is **Prior cites real prior work / abstains
correctly where the baselines confabulate**.

## Running it

```bash
prior eval                          # full scorecard (LLM metrics, ~10 min on claude-cli)
prior eval --no-llm                 # key-free metrics + distributions only (instant)
prior eval --data /path/to/reading  # cached reading dir for faithfulness
```
Results render in the web app's **Eval** tab.
