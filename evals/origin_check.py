"""Navigator backward / origin eval — grounded in real citation edges.

There's no off-the-shelf benchmark for origin tracing, but Prior's atlas already
carries OpenAlex `cites` edges, so we can self-validate: a good "origin" for a
concept should be a citation **ancestor** of (or among) the papers whose claims
match that concept — i.e. older work they build on, reachable by following
citation edges.

This module is key-free except the optional `--navigator` path:
  * `structural_origin` — a no-LLM baseline: the most foundational matching paper
    (most-cited within the atlas, then earliest, then most globally cited).
  * `score_traced` — does a traced origin land on an ancestor/member of the
    matched frontier? Reusable to score a live Navigator answer.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prior import config, navigator  # noqa: E402
from prior.atlas import Atlas  # noqa: E402

_ID = re.compile(r"\[([a-zA-Z]+:[^\]\s]+)\]")


def cited_ids(text: str) -> list[str]:
    """Pull `[openalex:W..]` / `[arxiv:..]` ids out of free text."""
    return _ID.findall(text or "")


def cites_graph(atlas: Atlas) -> nx.DiGraph:
    """Edge src→dst means src cites dst (dst is the older, cited work)."""
    g = nx.DiGraph()
    for e in atlas.edges:
        if e.relation == "cites":
            g.add_edge(e.src, e.dst)
    return g


def ancestors(atlas: Atlas, paper_id: str, g: nx.DiGraph | None = None) -> set[str]:
    """Papers reachable by following citations from `paper_id` — the works it
    (transitively) builds on."""
    g = g if g is not None else cites_graph(atlas)
    return nx.descendants(g, paper_id) if paper_id in g else set()


def matching_papers(atlas: Atlas, concept: str, k: int = 15) -> list[str]:
    """Papers whose claims best match the concept (BM25, no LLM)."""
    hits = navigator._retrieve(atlas, concept, k)
    return list(dict.fromkeys(c.paper_id for c, _ in hits))


def structural_origin(atlas: Atlas, concept: str, k: int = 15) -> str | None:
    papers = matching_papers(atlas, concept, k)
    if not papers:
        return None
    g = cites_graph(atlas)
    def in_atlas_cites(pid: str) -> int:
        return g.in_degree(pid) if pid in g else 0
    return sorted(
        papers,
        key=lambda p: (-in_atlas_cites(p), atlas.papers[p].year or 9999,
                       -atlas.papers[p].cited_by_count),
    )[0]


def score_traced(atlas: Atlas, concept: str, traced_ids: list[str],
                 k: int = 15) -> dict:
    """A traced origin is 'grounded' if it is an ancestor of, or a member of, the
    matched frontier — i.e. it's reachable along real citation edges."""
    frontier = set(matching_papers(atlas, concept, k))
    g = cites_graph(atlas)
    anc: set[str] = set()
    for p in frontier:
        anc |= ancestors(atlas, p, g)
    valid = frontier | anc
    hits = [t for t in traced_ids if t in valid]
    return {
        "traced": traced_ids,
        "grounded": bool(hits),
        "grounded_ids": hits,
        "frontier_size": len(frontier),
        "ancestor_pool": len(anc),
    }


def _fmt(atlas: Atlas, pid: str | None) -> str:
    if not pid or pid not in atlas.papers:
        return str(pid)
    p = atlas.papers[pid]
    return f"{pid}  {p.short_cite()} — {p.title[:70]}"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Origin-tracing eval over the atlas.")
    ap.add_argument("concept")
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--navigator", action="store_true",
                    help="also run Navigator.origin (uses the LLM) and score it")
    args = ap.parse_args()

    atlas = Atlas.load(config.ATLAS / "atlas.json")
    print("── Origin eval (backward) ──")
    base = structural_origin(atlas, args.concept, args.k)
    print(f"structural origin (no-LLM baseline):\n  {_fmt(atlas, base)}")

    if args.navigator:
        ans = navigator.origin(atlas, args.concept)
        traced = cited_ids(" ".join([ans.origin_paper, ans.account, *ans.lineage]))
        r = score_traced(atlas, args.concept, traced, args.k)
        print(f"\nNavigator traced origin: {ans.origin_paper}")
        print(f"  cited ids: {traced or '(none — answer used no [id] citations)'}")
        print(f"  grounded in citation graph: {r['grounded']}  "
              f"(frontier={r['frontier_size']}, ancestors={r['ancestor_pool']})")
        agree = base in traced if base else False
        print(f"  agrees with structural baseline: {agree}")
