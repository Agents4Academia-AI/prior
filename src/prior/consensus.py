"""Consensus scoring for global (contribution↔contribution) edges.

The v0.2 graph stamps each cross-paper relation with a `trust` score and an
`agreement.tier` saying how many independent signals back it. Klara's original
corpus-wide scorer isn't in the repo, so we reproduce the *shape* with a
transparent, documented formula.

Default (fast — one LLM pass): the relation is labelled once (Sonnet) and
combined with embedding similarity:
  trust = 0.7·confidence + 0.3·similarity
  tier  = triple  (confidence and similarity both strong)
          double  (one of them strong)
          single  (weak — kept but flagged)

Opt-in two-model arbiter (PRIOR_CONSENSUS_OPUS=1 — slower, higher quality): Opus
labels the relation too and acts as the gate (an edge survives only if Opus
asserts it; mirrors v0.2's `opus_only` tier with no `sonnet_only`):
  trust = 0.4·conf_opus + 0.4·conf_sonnet(if they agree) + 0.2·similarity
  tier  = triple / double / opus_only by how many signals fire.

Both produce the same edge schema, so the viewer treats them uniformly.
"""

from __future__ import annotations

import os
from typing import Optional

from . import cartographer, config
from .models import Contribution

SIM_THRESHOLD = 0.5


def _use_opus() -> bool:
    return os.environ.get("PRIOR_CONSENSUS_OPUS", "").lower() in ("1", "true", "yes")


def _single(source: Contribution, cands: list[Contribution],
            sim_by_id: dict[str, float], cited: set[str], model: str) -> list[dict]:
    out: list[dict] = []
    for e in cartographer._label(source, cands, cited, model):
        sim = float(sim_by_id.get(e.dst, 0.0))
        c = float(e.confidence)
        strong_c, strong_s = c >= 0.65, sim >= SIM_THRESHOLD
        tier = "triple" if strong_c and strong_s else "double" if strong_c or strong_s else "single"
        out.append({
            "src": e.src, "dst": e.dst, "relation": e.relation, "evidence": e.evidence,
            "confidence": c, "source": e.source,
            "trust": round(0.7 * c + 0.3 * sim, 2), "tier": tier, "similarity": round(sim, 3),
        })
    return out


def _arbiter(source: Contribution, cands: list[Contribution],
             sim_by_id: dict[str, float], cited: set[str],
             sonnet_model: str, opus_model: str) -> list[dict]:
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
        out.append({
            "src": source.id, "dst": dst, "relation": oe.relation,
            "evidence": oe.evidence, "confidence": c_o, "source": oe.source,
            "trust": round(0.4 * c_o + 0.4 * c_s + 0.2 * sim, 2),
            "tier": tier, "similarity": round(sim, 3),
        })
    return out


def relate(source: Contribution, cands: list[Contribution],
           sim_by_id: dict[str, float], cited: set[str], *,
           sonnet_model: Optional[str] = None,
           opus_model: Optional[str] = None) -> list[dict]:
    """Consensus-scored global edges (dicts ready for graph.add_edge). One-pass by
    default; two-model Opus arbiter when PRIOR_CONSENSUS_OPUS is set."""
    sonnet_model = sonnet_model or config.CARTOGRAPHER_MODEL
    if _use_opus():
        return _arbiter(source, cands, sim_by_id, cited,
                        sonnet_model, opus_model or config.NAVIGATOR_MODEL)
    return _single(source, cands, sim_by_id, cited, sonnet_model)
