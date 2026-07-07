# Prior as the shared substrate — and why it's a graph, not a map

**Thesis (one line for the slide):** Prior is the *connective tissue* of the
hackathon — a single typed **claim graph** that every other agent reads from and
writes back to, and from which a human-readable **IP-X assessment report** is
rendered.

---

## 1. It's a graph, not a map

"Atlas" / "map" is the metaphor; the thing we actually build is a **directed,
typed, multi-relational knowledge graph**. The distinction matters:

| "Map" (what we're *not* building) | **Graph (what we are)** |
|-----------------------------------|--------------------------|
| A 2-D layout you browse / zoom | Nodes + **typed edges** you *traverse and query* |
| Position carries meaning | **Relations** carry meaning (supports, contradicts, …) |
| One picture | A queryable database: "show the contradiction subgraph", "trace this claim to its origin", "what extends X?" |
| Read-only artifact | A **shared state** agents read *and write* |

A map is the *rendering*; the graph is the *substrate*. The IP-X report is one
view rendered from the graph — like a chapter printed from a database.

---

## 2. The data model — how claims link together

Two kinds of node, several kinds of edge. Edges and nodes both carry attributes
(a *property graph*).

**Nodes**
- **Claim** — one atomic, calibrated assertion. Attributes: text, evidence span,
  `evidence_level × agreement_level → confidence` (IPCC calibration), likelihood,
  scope, `contested`, audit status.
- **Paper** — a primary source (OpenAlex / arXiv). Attributes: title, year,
  citation count.

**Edges**
| Edge | From → To | Meaning | Powers |
|------|-----------|---------|--------|
| `stated_in` | Claim → Paper | provenance — where the claim is made | grounding, citation honesty |
| `cites` | Paper → Paper | bibliographic citation (from OpenAlex) | **backward / origin tracing** |
| `supports` | Claim → Claim | evidence agrees | state-of-evidence, confidence |
| `contradicts` | Claim → Claim | evidence conflicts | **contradiction surfacing** |
| `refines` | Claim → Claim | adds conditions / narrows scope | nuance, scope |
| `extends` | Claim → Claim | builds further on | lineage, novelty |

```mermaid
flowchart LR
  P1["Paper · Lewis 2020 (RAG)"]:::paper
  P2["Paper · Jiang 2023 (Active RAG)"]:::paper
  P3["Paper · Chen 2024 (RAG benchmark)"]:::paper

  C1["Claim · RAG reduces hallucination in QA<br/>(robust × high → HIGH confidence)"]:::claim
  C2["Claim · active retrieval reduces it further"]:::claim
  C3["Claim · retrieval adds latency"]:::claim

  C1 -->|stated_in| P1
  C2 -->|stated_in| P2
  C3 -->|stated_in| P3
  P2 -->|cites| P1
  P3 -->|cites| P1
  C2 -->|extends| C1
  C3 -->|refines| C1
  classDef claim fill:#e7f0ff,stroke:#2b6cb0,color:#000;
  classDef paper fill:#f3f3f3,stroke:#888,color:#000;
```

ASCII fallback (same graph):

```
        extends                 refines
   C2 ───────────▶ C1 ◀─────────────── C3
   │               │                    │
   │stated_in      │stated_in           │stated_in
   ▼               ▼                    ▼
   P2 ───cites────▶ P1 ◀────cites────── P3

   C1  RAG reduces hallucination in QA      (robust × high  → HIGH confidence)
   C2  active retrieval reduces it further  (extends C1)
   C3  retrieval adds latency               (refines C1: scope/cost caveat)
```

The point: a "claim" is never a floating sentence — it is **anchored** to a
source (`stated_in`), **situated** among other claims (`supports / contradicts /
refines / extends`), and **dated** through the paper citation graph (`cites`),
which is what lets us walk *backward* to an idea's origin.

---

## 3. Prior as the shared substrate the cohort plugs into

Luke's observation: the teams are each building a *different agent over the same
underlying object* — claims, contributions, citations, and their relations. Make
that object a shared graph and the agents **compose instead of duplicating**.
They sort into two roles around the atlas:

- **Enrichers** — *write* verification stamps onto claims (each team = one stamp).
- **Consumers** — *read* the atlas (query, surface, review).

```mermaid
flowchart TB
  SRC["Primary sources<br/>OpenAlex + arXiv"] -->|Reader · Cartographer · Contributor| ATLAS
  ATLAS(["PRIOR shared atlas<br/>claims · contributions · relations<br/>+ open VERIFICATION SLOTS per claim"])

  subgraph ENRICH["Enrichers — write verification stamps"]
    CITE["Citation verification<br/>→ real / relevant / fair"]
    CLAIMV["Claim verification<br/>→ claim faithfully supported"]
    EMP["Paper / empirical verification<br/>→ result reproduces"]
  end
  subgraph CONSUME["Consumers — read the atlas"]
    PKM["Personal knowledge management<br/>store / query / surface by interest"]
    REV["Auto-review<br/>contradictions + gaps → feedback"]
  end

  ENRICH -->|stamp claims| ATLAS
  ATLAS -->|read| CONSUME
  ATLAS --> ASSESS["Assessor → calibrated assessment<br/>weights evidence by VERIFICATION depth"]
  ASSESS --> SURVEY["Survey: AI that autonomously<br/>produces papers (Luke + ALL)"]
```

ASCII fallback:

```
  ENRICHERS (write verification stamps)         CONSUMERS (read)
  ───────────────────────────────────          ────────────────
  Citation verification → real/relevant/fair    Personal knowledge mgmt → query / surface
  Claim verification    → faithfully supported  Auto-review            → contradictions+gaps
  Paper/empirical verif → result reproduces
            │  stamp                                        ▲  read
            ▼                                               │
   sources ─▶┌──────────────────────────────────────────┐──┘
   (OA+arXiv)│  PRIOR atlas: claims · contributions ·    │
             │  relations  + open VERIFICATION SLOTS     │──▶ Assessor (weights by verification)
             └──────────────────────────────────────────┘        └─▶ IP-X report ─▶ survey
```

**Why this is the right shape.** Today each agent re-reads PDFs and re-extracts
its own private claims. With a shared graph, **extraction happens once**; everyone
else stamps or reads the same object. And the payoff compounds: each team's stamp
is a verification in the stack, so Prior's **Assessor weights evidence by
*verification depth*, not citations** — the calibrated confidence is literally
aggregated from the cohort's verification work. Prior's job is to expose the
**interface** (the verification slots + a query API); the teams fill the stack.
See the verification-stamp schema in [`WEEK_2.md`](project/WEEK_2.md).

---

## 4. The link to Luke's survey paper

The cohort already has a meta-goal: *a survey on using AI to autonomously produce
publishable papers (Luke + ALL).* Prior connects to it two ways:

1. **As an instance.** An IP-X report *is* an autonomously produced assessment /
   mini-survey, with calibrated confidence and traceable evidence — a concrete
   data point for the survey.
2. **As the organizing framework.** The survey can use Prior's graph as its
   taxonomy: each agent type (extract / verify citations / verify claims /
   review / judge novelty / synthesize) maps to a **node or edge operation** on
   the claim graph. That gives the survey a single coherent backbone instead of
   a loose list of tools — "here is the shared object; here is each agent as an
   operation on it."

**Slide takeaway:** *Prior turns the hackathon's parallel agents into one
pipeline over a shared claim graph — and that same graph is the backbone for the
survey.*
