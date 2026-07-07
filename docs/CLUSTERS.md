# Communities in the atlas — how they're computed, and how good they are

The **communities** lens in the viewer (and the per-community knowledge-frontier
view) comes from a deterministic clustering of the contribution graph. This page
documents the method, the shipped assignment, and two independent checks of
whether the communities are real structure or artefacts.

## Method

- Build an **unweighted, undirected** graph over contributions from the consensus
  relation edges (all types, equal weight).
- Run greedy modularity maximisation (networkx
  `greedy_modularity_communities`), with nodes and edges sorted first so the
  result is deterministic and input-order independent.
- Keep communities with **≥ 8 members** (at most 9); everything smaller is
  `-1` — *unclustered / isolated*.
- **Labels are keyword-assigned**, by a greedy one-to-one vote of each
  community's member statements against a fixed keyword table
  (`scripts/cluster_core.py`). Read them as navigation aids, not as a claimed
  taxonomy of the field.
- Greedy modularity is tie-order sensitive, so re-clustering in two interfaces
  can disagree at the margins. We therefore **cluster once and ship the
  canonical assignment**: `clusters.json` (contribution → community) and
  `graph.json` (a turnkey render payload with `comm` already on every node).
  Interfaces consume the assignment; they don't re-derive it.

Reproduce with:

```bash
python3 scripts/cluster_core.py <bundle_dir>   # writes clusters.json + graph.json
```

## The flagship atlas's communities

581 contributions · 989 consensus edges · **modularity 0.72**:

| community | contributions |
|---|---|
| Peer review | 82 |
| Autonomous systems | 70 |
| Hypothesis generation | 55 |
| Benchmarks & eval | 52 |
| Multi-agent orchestration | 50 |
| Domain-science agents | 28 |
| Idea novelty / eval | 27 |
| RAG / literature-QA | 27 |
| Safety / risk | 25 |
| *unclustered / isolated* | *165* |

28% of contributions are unclustered — mostly contributions with no cross-paper
relation yet ("known · not yet connected" in the viewer), which is honest
sparsity rather than a rendering artefact.

## Are the communities real?

Two checks that don't rely on the model grading itself:

- **Citation enrichment.** Edges *inside* a community connect papers that cite
  each other **29%** of the time, vs **18%** for cross-community edges and ~6%
  for random paper pairs in the corpus (citation graph mined independently from
  the papers' own LaTeX bibliographies). Communities concentrate structure the
  citation record separately confirms.
- **Stability under a different edge set.** Re-deriving communities from an
  independently built relation graph (pairwise, citation-aware relabelling of
  the same contributions) reproduces the partition well above chance
  (adjusted Rand index 0.32) with near-identical community labels.

One caveat worth knowing: the community layer is more robust than the individual
edges underneath it. Relation-*type* errors documented in the eval mostly connect
work in the same neighbourhood with the wrong label — they blur edge semantics,
not community boundaries. So trust the neighbourhoods; verify the individual
edges (every edge carries its evidence for exactly that reason).
