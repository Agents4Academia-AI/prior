# Research Gap Atlas prototype

`build_gap_atlas.py` converts graph-grounded gap-generation outputs into a
reviewable survey artifact. Each card keeps three layers separate:

1. source evidence: paper identity, contribution, supporting quotation and the
   typed graph relation that caused the packet to be sampled;
2. model hypothesis: the proposed gap, missing evidence and smallest resolving
   study;
3. human verification: explicit fields for source sufficiency, gap confirmation,
   disputes, omitted papers and reviewer provenance.

The initial snapshot uses the 20 motif-balanced, three-paper packets. It is a
demonstration of the workflow, not a validated list of field gaps: every card
starts as `draft_unverified`. A gap can become `gap_confirmed` only after its
quotes and relation are checked and a fresh high-recall search fails to find an
existing resolution.

Generate a snapshot with:

```bash
python3 experiments/graph_ideation/build_gap_atlas.py \
  --input experiments/graph_ideation/out_motif_balanced \
  --out experiments/graph_ideation/gap_atlas_snapshot
```

The JSON is the machine/agent-facing representation; the Markdown is a dated,
read-only human review view. This dual export is the compact demonstration of
Prior serving humans and research agents from the same evidence substrate.
