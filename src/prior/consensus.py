"""Consensus scoring for global (contribution↔contribution) edges.

The v0.2 graph stamps each cross-paper relation with a `trust` score and an
`agreement.tier` saying how many independent signals back it. Klara's original
corpus-wide scorer isn't in the repo, so we reproduce the *shape* with a
transparent, documented formula: two LLM passes (Sonnet + Opus) independently
label the relation and embedding similarity is a third signal. Opus is the
arbiter — an edge survives only if Opus asserts it (mirrors v0.2, which has an
`opus_only` tier but no `sonnet_only`).

  tier  = triple    — Opus + Sonnet agree on the relation, and similarity is high
          double    — Opus + exactly one other signal
          opus_only — Opus alone
  trust = 0.4·conf_opus + 0.4·conf_sonnet(if they agree) + 0.2·similarity

(With the credit-free claude-cli backend both passes may resolve to the same
model; the two independent labelings + similarity still add signal, and the API
backend gives a genuine two-model vote.)
"""

from __future__ import annotations

from typing import Optional

from . import cartographer, config
from .models import Contribution

SIM_THRESHOLD = 0.5


def relate(source: Contribution, cands: list[Contribution],
           sim_by_id: dict[str, float], cited: set[str], *,
           sonnet_model: Optional[str] = None,
           opus_model: Optional[str] = None) -> list[dict]:
    """Return consensus-scored global edges (as dicts ready for graph.add_edge)."""
    sonnet_model = sonnet_model or config.CARTOGRAPHER_MODEL
    opus_model = opus_model or config.NAVIGATOR_MODEL
    s_edges = {e.dst: e for e in cartographer._label(source, cands, cited, sonnet_model)}
    o_edges = {e.dst: e for e in cartographer._label(source, cands, cited, opus_model)}

    out: list[dict] = []
    for dst, oe in o_edges.items():            # Opus is the gate
        se = s_edges.get(dst)
        agree = bool(se and se.relation == oe.relation)
        sim = float(sim_by_id.get(dst, 0.0))
        c_o = float(oe.confidence)
        c_s = float(se.confidence) if agree else 0.0
        signals = 1 + int(agree) + int(sim >= SIM_THRESHOLD)
        tier = "triple" if signals == 3 else "double" if signals == 2 else "opus_only"
        trust = round(0.4 * c_o + 0.4 * c_s + 0.2 * sim, 2)
        out.append({
            "src": source.id, "dst": dst, "relation": oe.relation,
            "evidence": oe.evidence, "confidence": c_o, "source": oe.source,
            "trust": trust, "tier": tier, "similarity": round(sim, 3),
        })
    return out
