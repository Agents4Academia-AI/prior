# Prior — core graph (v0.2)

A queryable, auditable graph of the **primary LLM-agent / AI-scientist literature**:
self-declared *contributions* grounded in their source text, linked by cross-model
*relations*. Built by [Prior](https://github.com/Agents4Academia-AI/prior)
(Agents4Academia).

## Contents
| file | what |
|---|---|
| `contributions_core_grounded.json` | 581 contributions over 152 papers, each with a verbatim source span |
| `contributions_core_consensus.json` | 989 relation edges (consensus, with trust tiers) |
| `papers_core.jsonl` | metadata for the 152 core papers (incl. `date` / `date_precision`) |
| `core_exclusions.json` | papers dropped as non-primary (perspective/position/review) + why |

## Nodes — `contributions_core_grounded.json`
Each contribution: `{id, paper_id, statement, kind, quote, quote_verbatim,
quote_offsets, grounding}`.
- `statement` — standalone, source-agnostic claim of the contribution.
- `quote_verbatim` + `quote_offsets` — the **verbatim span** in the source text it
  was aligned to (char offsets), recovered deterministically.
- `grounding` — [0,1] support score. Distribution: {'verbatim ≥0.90': 487, 'paraphrase 0.60–0.90': 83, 'weak <0.60': 6}
  (mean **0.953**). Only the few `weak <0.60` need review.

## Edges — `contributions_core_consensus.json`
Relation graph, **claude-opus-4-8**-anchored, each edge annotated with
cross-model agreement (`claude-sonnet-4-6, claude-haiku-4-5-20251001`):
`{src, dst, relation, confidence, trust, agreement:{tier, confirmed_by, dissent}}`.
- `relation` ∈ supports / contradicts / builds_on / refines.
- `directed` / `precedence` — `builds_on`/`refines` point **newer→older by publication
  date** (`src` = deriver, `dst` = antecedent); same-date pairs are `directed:false`
  (`precedence:ambiguous`). supports/contradicts are symmetric.
- `tier` — `triple` (all 3 models agree) / `double` / `opus_only`; `trust` blends
  Opus confidence with agreement. `contradicts` is the most-corroborated relation.

## Changed since v0.1
- **Primary-only**: 3 non-primary papers (perspective/position) removed — see
  `core_exclusions.json`.
- **Relations rebuilt**: fixed spurious-`contradicts` (soft-distance candidates +
  an `unrelated` escape + real confidence), then a cross-model consensus.
- **Verbatim provenance** added (the `quote_verbatim`/`grounding` fields above).
- **Publication dates + edge direction**: every paper carries `date` (month-level
  or better for 100% of core); `builds_on`/`refines` are now oriented by chronology
  (previously ~67% backwards) with same-date pairs left undirected.

## Not included — raw full text
Publisher TDM licenses permit *mining*, not redistribution (per Bodleian guidance).
Reproduce full text locally with your own entitlement via
`scripts/get_fulltext.py --ids <dois>`; the graph here is derived/transformative.

_Generated 2026-06-24T13:58:36+00:00._
