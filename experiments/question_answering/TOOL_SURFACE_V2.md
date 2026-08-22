# Why the graph arm cost as much as web search — diagnosis and redesign

*Written 2026-08-21, after the v1 pilot (q01, q02 × 3 arms). Prompted by a fair
challenge: if Prior is a compact representation of the literature, why did the
graph arm not cost less than a web search? The short answer is that it should
have, it didn't, and the reason was in our tool surface rather than in Prior.*

---

## 1. What v1 actually measured

| run | turns | **new tokens into context** | cache-read | output | $ | $/turn |
|---|---|---|---|---|---|---|
| q01 graph | 19 | **43,443** | 407,594 | 10,169 | 0.523 | 0.028 |
| q01 web | 9 | **25,366** | 191,331 | 7,244 | 0.416 | 0.046 |
| q01 null | 4 | 16,577 | 87,273 | 6,143 | 0.208 | 0.052 |
| q02 graph | 16 | **40,010** | 263,140 | 7,126 | 0.413 | 0.026 |
| q02 web | 6 | **19,396** | 119,882 | 6,048 | 0.280 | 0.047 |
| q02 null | 6 | 20,648 | 149,214 | 6,048 | 0.306 | 0.051 |

Two facts worth stating plainly:

- **The graph arm pulled ~1.7–2× more tokens into context than web search did.**
  On the metric that actually tests "compact representation", v1 showed the
  opposite of the claim.
- **Cost per turn was *lower* for the graph arm** ($0.026–0.028 vs $0.046 web,
  $0.051 null). Per-turn context was ~21k for every arm. So cost here is close to
  linear in turn count, and the graph arm lost purely by taking 2–3× more turns.

The supervisor's intuition was right, and the number that shows it is
`tokens_in`, not dollars. Dollars are a notional API-equivalent price we never
pay on the subscription; they also fold in output verbosity. `tokens_in` =
`input_tokens + cache_creation_input_tokens` is the honest measure of how much
material an arm had to ingest, and it is now recorded on every row.

## 2. Where the turns went

Replaying q01's logged calls against the atlas offline (zero cost):

```
q01 graph — 59,374 chars of payload across 15 calls
  search_contributions ->  4,458
  get_citations        -> 13,884     56 citing papers, flat and unranked
  get_edges            -> 11,292
  get_edges            ->      2     EMPTY
  get_edges            ->      2     EMPTY
  ... + 4x get_paper, 2x citations_between, 4x more get_edges
```

Three faults, all ours:

**(a) Granularity mismatch.** Every question in `questions.json` is *paper*-level
("which papers build on X?"). Every v1 traversal tool was *contribution*-level —
`get_edges(contribution_id)`. A paper has 3–5 contributions, so covering one
paper's relations meant `get_paper` to enumerate the IDs, then N× `get_edges`.
Two of the six `get_edges` calls returned `[]` because the agent guessed
contribution IDs with no typed edges. Those wasted turns were structural, not
bad luck.

**(b) No aggregation.** `get_citations` returned all 56 citing papers as an
unsorted flat list with every intent weighted equally. The entire answer to q01
is four numbers — 53 background, 14 compares_contrasts, 3 uses_extends, 7
`builds_on` — but the tool made the model re-derive them by reading 13.9k chars.
**That is precisely the work Prior claims to have already done.** Handing back
raw rows and asking the model to count them throws the value away at the door.

**(c) No cheap-then-detailed path.** `get_edges` always returned the full
neighbour statement, full reason and nested citation object — no projection for
deciding *where to go* before pulling detail.

## 3. A second, more serious problem: the arms were not sealed

`ClaudeAgentOptions.allowed_tools` is a **permission allowlist**, not a
tool-surface restriction. The surface is the separate `tools=` field, which v1
never set. Combined with `permission_mode="bypassPermissions"`, every default
Claude Code tool was live in every arm. Confirmed in the SDK's CLI wiring:
`tools` → `--tools`, `allowed_tools` → `--allowedTools`.

It bit us. The first two calls of the v1 q02 **graph** run:

```json
{"tool":"Skill","args":{"skill":"prior","args":"Is the field actually agreed..."}}
{"tool":"Bash","args":{"command":"cd .../prior; python -m prior.cli info"}}
```

`.claude/skills/prior/SKILL.md` exists in this repo, so on q02 the "graph" arm
was graph + Prior's own skill + shell access to the working tree. And the **null**
arm had `WebSearch` available throughout — it never called it, so it was
closed-book by luck, not by construction.

Both v1 questions are therefore invalid for scoring. They are archived in
`out_v1/` with this note, and their token accounting is retained as the
efficiency baseline.

> The same bug exists in `../graph_vs_web_ideation/arms.py`, which is parked.
> Fix it there before that experiment is re-run.

## 4. The v2 redesign

### Sealing (`qa_arms.py`)

```python
tools=builtin,                                    # THE surface restriction
disallowed_tools=[t for t in _BUILTINS if t not in builtin],
setting_sources=[],                               # no project CLAUDE.md / settings
skills=[],                                        # no repo skills
```

`graph` → `tools=[]` + graph MCP server. `web` → `tools=["WebSearch","WebFetch"]`.
`null` → `tools=[]` and exactly one MCP tool, `submit_answer`. `_selftest`
asserts all of it, and every generated row now carries an `off_arm_tools` canary
that `qa_gen.py` shouts about if it is ever non-empty.

### Paper-shaped tools (`graph_tools.py`, additive)

| tool | what it does |
|---|---|
| `find_paper(query)` | Look a paper up **by name**. v1 had no such tool at all — an agent asked about "The AI Scientist (Lu et al.)" had to hope a keyword search over contribution *statements* surfaced it. |
| `paper_neighbourhood(paper_id)` | Everything about how one paper connects, in **one call**: contributions, every typed relation touching them with reasons, every citation in/out **ranked by intent**, with counts precomputed. |
| `topic_structure(query)` | The topic-shaped counterpart: search, and return the typed relations around the best hits in the same call — so "is this disputed?" is one call, not a search plus N× `get_edges`. |

The eight v1 tools are retained for drill-down; the system prompt now orders the
surface explicitly (broad first, drill second) and tells the model to **read the
counts before the lists**.

Two supporting fixes to retrieval, both of which were latent v1 bugs:

- `search_contributions` now scores by **idf-weighted** overlap and indexes the
  **paper title**. v1 used a raw count of shared tokens over statements only, so
  *"are there disagreements about whether LLMs produce novel ideas"* scored
  partly on `about`, `are`, `there`.
- `find_paper` penalises long titles and **refuses below a coverage floor**.
  Without the floor it answered `"AlphaFold de novo protein binder design"` with
  an unrelated paper — manufacturing exactly the false positive the c01 control
  exists to detect. Verified behaviour:

  ```
  'The AI Scientist'                          -> The AI Scientist: Towards Fully Automated...
  'Hypothesis Generation with Large Language Models' -> exact match (v1 ranked a longer
                                                 title above it)
  'AIDE'                                      -> AIDE: AI-Driven Exploration in the Space of Code
  'AlphaFold de novo protein binder design'   -> (no match — refused)
  'protein structure prediction'              -> (no match — refused)
  ```

## 5. Projected efficiency, computed offline before the run

The intended v2 path for each question, measured against the real atlas at zero
cost:

| q | shape | calls | payload chars | entry resolved to |
|---|---|---|---|---|
| q01 | paper | 2 | 20,566 | The AI Scientist |
| q02 | topic | 1 | 10,524 | contradicts 2, supports 6, builds_on 1, refines 2 |
| q03 | topic | 1 | 7,563 | supports 7 |
| q04 | paper | 2 | 12,645 | Hypothesis Generation with Large Language Models |
| q05 | topic | 1 | 12,749 | builds_on 4, supports 6, refines 2, contradicts 2 |
| q06 | paper | 2 | 11,110 | AIDE |
| c01 | paper | 1 | 2 | **refused — correct** |
| c02 | paper | 2 | 14,042 | PaperBench |

**All 8 questions: 12 calls, 89,201 chars.** v1 needed 24 calls and 98,433 chars
for **two**. Per question: **1.5 calls / 11.2k chars, against 12 calls / 49.2k
chars** — ~8× fewer calls and ~4.4× less payload.

That is a projection of the intended path, not a promise: the agent chooses its
own route and may still wander. What it establishes is that the atlas *can*
answer these questions compactly, so if v2 still ingests more than web search,
the finding is about the agent's search behaviour and not about the tool surface.

## 6. The honest caveat

The questions were chosen to favour the atlas. Shaping the tools around them as
well risks making a graph win unfalsifiable. Three things keep it honest, and
they should be stated in any write-up:

1. The new tools are **generic** — lookup by name, one-paper neighbourhood,
   topic neighbourhood. None encodes anything specific to these eight questions.
2. The controls stay, and c01 is now *harder*: `find_paper` refuses rather than
   returning the nearest paper, so a c01 fabrication would be the model's, not
   the tool's.
3. The efficiency prediction is registered in `PLAN.md` **before** the run, with
   the numbers above behind it.

The cleanest framing for the write-up is that this is itself a result: **the same
underlying representation, ~4× less material into context, because the index does
the aggregation instead of the model.** Compactness is a property of the
interface, not only of the data.

---

# 7. v3 — the envelope, 2026-08-21

v2 fixed the seal and the granularity but **not** the compactness problem. On the
three clean triples the graph arm still pulled 1.27× more `tokens_in` and 1.79×
more payload than web search, so the §3 efficiency prediction was falsified. See
PLAN.md §3 for the scored table.

Decomposing a single `paper_neighbourhood` payload located the cost precisely —
and it was not the graph:

| part of the 19,390-char payload | chars | what it is |
|---|---:|---|
| `typed_relations` | 7,390 | **9 edges**, ~820 chars each — mostly a 320-char truncated `reason` plus three duplicated ids |
| `cited_by` | 7,584 | **40 rows**, ~190 chars each, re-spelling five JSON keys per row |
| `abstract` | 1,919 | not part of the graph; the contribution statements already carry the claim |
| `contributions` | 1,182 | **the actual node content** |
| `counts` | 265 | **the whole answer to q01** |

The agent paid 19,390 characters to obtain a 265-character `counts` block, four
times over. The four v3 rules and the measured effect are in **PLAN.md §2a** — they
change serialisation, not content, and `paper_neighbourhood(pid, verbose=True)` /
`topic_structure(q, verbose=True)` still reproduce the v2 payload so the surfaces
can be compared at zero cost.

Two things fell out of the same change:

- **`edge_reasons` delivers MORE evidence, not less.** v2 truncated every
  justification to 320 chars (median reason: 1,095) and shipped them all whether
  wanted or not. v3 ships the full text for the edges the model asked for.
- **The exploration trace becomes honest.** Under v2, q01 "touched" 60 of 152
  papers — but 56 of those were rows dumped into context, not nodes considered.
  v3 distinguishes *listed* from *deliberately read* (an edge whose reason was
  requested by id), which is what the poster figure needs.

**Still outstanding from §6:** the same sealing bug remains in
`../graph_vs_web_ideation/arms.py`. `qa_judge.py` had it too and has now been
fixed; the ideation arms have not.
