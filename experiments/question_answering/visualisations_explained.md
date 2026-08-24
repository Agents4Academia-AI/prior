# How to read the exploration figures

One figure per question, produced by `trace.py` into `out/traces/`. They show
**what the graph arm did on the Prior atlas** while answering that question.

Nothing here is drawn by hand or by a model. `trace.py` takes the tool calls that
were logged during generation (`out/answers.jsonl`, field `tool_args`) and
re-issues them against the atlas. The atlas is deterministic, so the same
arguments return the same rows they returned at the time. **It is a replay, not a
reconstruction** — that is what makes the figure evidence rather than
illustration.

---

## 1. In twenty seconds

- **Rings = how hard the agent engaged.** Big and numbered in the middle: papers
  it *chose*. Middle ring: papers whose *evidence text* it read. Faint outer ring:
  papers that merely appeared in a list.
- **Coloured lines = typed relations** from the graph, in the poster palette.
  Solid means the agent read that edge's justification; dashed means it only saw
  the label.
- **Gold halo = the paper made it into the final answer.**
- **The ribbon underneath** is the call sequence in order, then the two keys.

---

## 2. What the three engagement levels actually mean

This is the part worth being precise about, because it is the whole point of the
figure. Engagement is defined by **which tool call the paper appeared in**, not by
anything softer.

| ring | label | earned by |
|---|---|---|
| inner, large, numbered | **focus** — *it chose this* | the paper was named as an **argument** to a call |
| middle | **read** — *it read the evidence* | the paper came back from a call that returns **full justification prose** |
| outer, small, faint | **listed** — *delivered, not read* | the paper only appeared in a **returned list** |

Mapped onto the actual tool surface:

| tool call | what the agent was doing | what it puts on the figure |
|---|---|---|
| `find_paper(query)` | looking a paper up by name | a **query pill**; the hits become **listed** |
| `search_contributions(query)` | keyword search over contribution statements | a **query pill**; hits **listed** |
| `topic_structure(query)` | search + the relations round the hits, in one call | a **query pill**; hits **listed**, and their typed relations drawn **dashed** |
| `paper_neighbourhood(paper_id, …)` | *"show me how this paper connects"* | that paper becomes **focus**; its typed relations are drawn **dashed** (labels only — no justification was returned); the papers citing / cited by it become **listed** |
| `edge_reasons(paper_id, others=…, relation=…)` | *"give me the justification behind these specific edges"* | that paper **focus**; every paper on a returned edge becomes **read**; those edges are drawn **solid** |
| `citations_between(a, b)` | *"why exactly does a cite b?"* — returns the citation-site prose | `a` **focus**, `b` **read**; the citation edge **solid** |
| `get_paper(paper_id)` | the abstract and contribution list | **focus** |
| `get_contribution(contribution_id)` | one contribution in full | **focus** |

**Why the read/listed split is meaningful at all.** The v3 tool surface was
deliberately built so that `paper_neighbourhood` returns edge *labels* and
`edge_reasons` returns the *justifications*, batched and only on request (PLAN
§2a). Under the earlier surface every justification shipped with the listing,
truncated, whether wanted or not — so "read" and "listed" were the same thing and
no honest trace was possible. The figure and the tool design stand or fall
together.

**Focus outranks read.** If the agent pulled justifications for a paper it had
already chosen, it stays on the focus ring. That is why q02 reports `4 read in
depth` as 0 — the two papers whose justifications it pulled were already focus
nodes.

---

## 3. Every mark on the figure

**Nodes**

| mark | meaning |
|---|---|
| black disc in a white ring | focus — the agent chose this paper |
| numbered badge beside it | the call it was chosen on; matches the ribbon |
| hollow grey ring | read — its evidence text was delivered |
| small grey dot | listed — it appeared in a list only |
| **gold halo** | the paper is named in the final answer |

**Edges** — colours come from `REL_COLOR` in `trace.py`, the poster palette:
darker and higher contrast than the app's own so the relations survive being
printed at A0 and read from a metre away.

| colour | hex | relation | arrow? |
|---|---|---|---|
| deep red | `#ae2012` | `contradicts` | no — recorded **symmetric** |
| orange | `#ca6702` | `refines` | yes |
| slate blue | `#5b8fb0` | `builds_on` | yes |
| teal | `#0a9396` | `supports` | no — recorded **symmetric** |
| black | `#000000` | citation layer (`cites`) | yes — citing → cited |

- **Solid, thick** = the justification behind that edge was read.
- **Dashed, faint** = the edge label was listed, nothing more.

**Arrowheads are drawn only where the graph records a direction**, taken from the
canonical edges' own `direction` field rather than assumed: `supports` is
`symmetric` on all 203 edges and `contradicts` on all 27, while `builds_on` (109)
and `refines` (10) carry `a_to_b`/`b_to_a`.

One subtlety, in case anyone asks: `a_to_b`/`b_to_a` refers to the A/B roles the
labeller saw, and those were **not** preserved in the stored `src`/`dst`. Checked
against the citation layer, `src` is the citing (later) paper in **104 of 104**
directed edges that have a citation, whereas reading `a_to_b` as `src → dst`
agrees only **39 of 104** — a coin flip. So the arrow follows `src → dst`, and
`direction` is used only to decide *whether* an arrow is drawn.

**Query pills** (the rounded grey boxes at the edge)

- A pill is a **search string the agent typed**. Dotted lines run from it to the
  papers it returned.
- A **red dashed pill reading "no match"** is a search the corpus **refused**.
  `find_paper` will not return the nearest thing in a 152-paper corpus below its
  coverage threshold. This is the whole story of the `c01` control: five searches,
  two refusals, nothing chosen, nothing read, and an answer that declined.
- Pills are shown when there are at most three of them, or whenever the agent
  never committed to a paper (then the searches *are* the trace). Force it either
  way with `--queries on|off`.

**The ribbon**

- **WHAT IT DID, IN ORDER** — one numbered chip per graph call, in sequence.
  Chips are dark when the call *chose* something (a paper named as an argument)
  and grey when it was a search.
- **HOW THE AGENT ENGAGED** and **RELATION** — the two keys. The relation key
  always lists all five relations, used in that figure or not, so two figures side
  by side on the poster read with the same legend.

**The caption** — `N graph calls · N papers chosen · N read in depth · N listed ·
N typed edges · N papers in the answer`. "Papers in the answer" counts the
`papers_named` field of the submitted answer, matched back to the corpus by title.

---

## 4. What the figure does *not* show

Worth knowing before someone asks at the poster.

- **The outer ring is a sample, not the full list.** It is capped at
  `--max-listed` (default 14), ranked answer-cited first, then most-touched. q01's
  focus paper actually had **56** citing papers; the figure shows the top slice.
  The caption's "listed" count is the number *drawn*, and the pruned count is
  printed to the terminal when you run `trace.py`.
- **Routine `background` citations were never enumerated.**
  `paper_neighbourhood` counts every citation but only lists the substantive ones,
  deferring the routine `background` ones unless asked for with
  `intent='background'`. Papers that only cite in passing therefore do not appear
  as nodes — by design, and it is the reason the graph arm's payload is small.
- **Nodes are papers; the graph's edges are between contributions.** Several
  contributions of the same paper collapse into one node in the figure. The
  `.json` export keeps the contribution-level structure.
- **Layout carries no meaning beyond the rings.** Angular position comes from a
  small force pass that puts connected papers near each other, then equal
  arc-length spacing round the ellipse so labels do not collide. Distance within a
  ring means nothing.

---

## 5. The other two files per question

`trace.py` writes three files for each question:

- **`<qid>.svg`** — the figure. Vector, white background, Arial. PowerPoint takes
  it directly (*Insert → Pictures → This Device*) and keeps it as editable vector
  shapes. `--png` also writes a raster copy via headless Chrome if something
  cannot take an SVG.
- **`<qid>.json`** — the same subgraph in Prior's `GlobalGraph {nodes, edges}`
  shape, for the app's own viewer (`frontend/src/components/ClaimGraph.tsx`).
  Contribution-level, as that type requires, with additive `trace_engagement`,
  `trace_steps` and `trace_in_answer` fields. Citation-layer edges attach to each
  paper's first contribution and are flagged `paper_level`.
- **`<qid>.md`** — the call-by-call narrative, including **the full justification
  text of every edge the agent actually read**. This is the supervisor-conversation
  document: it is where you can show that "contradicts" is backed by a paragraph
  of reasoning, not a label.

---

## 6. Regenerating and tuning

```bash
python trace.py                                  # all eight questions
python trace.py --questions q01,q03 --png        # just these, plus 2x PNGs
python trace.py --questions q01 --max-listed 8   # thin the outer ring
python trace.py --questions q03 --drop "MLR-Copilot,Chain of Ideas"
```

Zero cost — no model is called.

| flag | effect |
|---|---|
| `--max-listed N` | cap the faint outer ring (default 14) |
| `--drop "a,b"` / `--keep "a,b"` | prune by title or paper-id substring |
| `--queries on\|off\|auto` | show the search pills |
| `--no-citations` | drop the citation layer, leaving only typed edges |
| `--font-scale F` | scale all type together (default 1.1) |
| `--aspect F` | squash the rings into ellipses (default 0.62) |
| `--spread F` | multiply ring radii (default 0.92) |
| `--layout below\|side` | key underneath (default) or in a right-hand column |
| `--width N` | nominal width in px (default 1900; it is vector, so this only sets the aspect maths) |

**Sizing for the poster.** Each figure is a landscape band, roughly 1.2–1.4:1.
Height is what the type size competes with, which is why the rings are squashed
into ellipses and why ring radii are driven by node counts and label widths rather
than by font size — so raising `--font-scale` really does make the type bigger
relative to the figure. At a quarter of an A0 sheet (297mm tall) the current
defaults put body text near **11pt** and paper titles near **15pt**. `--layout
side` buys back roughly a quarter of the height if you ever need type larger still.

---

## 7. Suggested figures

- **q01 (`builds-on`)** — the cleanest "what does a typed edge buy you" figure.
  One paper chosen, seven `builds_on` justifications read, then three specific
  citation links checked. Every blue arrow points *into* The AI Scientist: these
  are the papers that extend it, separated from the 56 that merely cite it.
- **q03 (`disagreement`)** — five neighbourhoods, then two batched `contradicts`
  pulls. The red structure through the middle is a live disagreement in the
  literature, and the numbered badges let you narrate the order it worked in.
- **c01 (`control-out-of-scope`)** — the control, and a good companion panel. Two
  name lookups refused, three searches landing on the same irrelevant cluster,
  nothing chosen, nothing read. The empty centre *is* the finding: asked about
  something outside the corpus, the arm did not manufacture an answer.
