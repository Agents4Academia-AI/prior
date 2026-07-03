# Contributing to Prior

Thanks for your interest. Prior reads primary literature and builds an *auditable* graph of
a field — contributions and typed relations (**supports · builds_on · refines · contradicts**),
every claim traceable to its source. Contributions of all sizes are welcome.

## Setup

```bash
git clone https://github.com/Agents4Academia-AI/prior.git && cd prior
python -m venv .venv && source .venv/bin/activate
pip install -e ".[graph]"              # core + local embeddings (add ,web for the API/UI)
export PRIOR_LLM_BACKEND=claude-cli    # runs on your Claude Code login; or set ANTHROPIC_API_KEY
pytest -q                              # key-free, no Neo4j required
```

Build an atlas and view it with **no database**:

```bash
prior build "your topic here"
prior view --open                      # one self-contained HTML file
```

## Workflow

- **Fork → branch → PR.** Keep PRs small and focused; every change should move a number or fix
  a specific thing. Say what and why.
- **Tests stay key-free.** `pytest -q` must pass with no API key and no running Neo4j. Add tests
  for new behaviour.
- **Match the surrounding code** — naming, comment density, idioms. No new dependencies without a
  reason.
- **Never commit secrets.** `data/users.json` is local/gitignored — use `data/users.json.example`.
  No API keys, no full-text dumps.

## Architecture (where things live)

`Scoper → Contributor → Cartographer → Navigator` — find papers → extract contributions + claims
→ link across papers → query / render. CLI entry points: `prior build / view / serve`. See
`README.md` and `docs/RUNNING.md`.

## Good first areas

- **The citation layer** — give papers their real references and use them to set relation
  direction (well-scoped and measurable; start from the citation checks in `evals/`).
- **Evals** — extend the groundedness / calibration scorecards.
- **Rendering** — improvements to the self-contained `prior view` output.

## Reporting issues

Open an issue with what you did, what you expected, and what happened (plus the atlas / collection
if relevant). For anything security-sensitive, contact the maintainers directly rather than filing
a public issue.
