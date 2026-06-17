"""The atlas: papers + claims + a typed graph over them, with persistence.

Graph nodes are papers and claims; edges are:
  stated_in   claim  -> paper   (provenance; every claim has exactly one)
  cites       paper  -> paper   (from OpenAlex referenced_works)
  supports / contradicts / refines / extends   claim -> claim

The on-disk JSON is the hand-off API: a verification or baseline team can load
`atlas.json` and get a fully grounded corpus of claims with provenance.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from . import config
from .models import Claim, Edge, Paper


class Atlas:
    def __init__(self) -> None:
        self.papers: dict[str, Paper] = {}
        self.claims: dict[str, Claim] = {}
        self.edges: list[Edge] = []
        self.topic: str = ""

    # ── building ────────────────────────────────────────────────────────────
    def add_paper(self, p: Paper) -> None:
        self.papers[p.id] = p

    def add_claim(self, c: Claim) -> None:
        self.claims[c.id] = c
        self.edges.append(Edge(c.id, c.paper_id, "stated_in", confidence=1.0))

    def add_edge(self, e: Edge) -> None:
        self.edges.append(e)

    def link_citations(self) -> int:
        """Add `cites` edges between papers we actually hold. Returns count."""
        n = 0
        have = set(self.papers)
        for p in self.papers.values():
            for ref in p.referenced_works:
                if ref in have:
                    self.edges.append(Edge(p.id, ref, "cites", confidence=1.0))
                    n += 1
        return n

    # ── graph view ──────────────────────────────────────────────────────────
    def graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for p in self.papers.values():
            g.add_node(p.id, kind="paper", title=p.title, year=p.year,
                       cited_by=p.cited_by_count)
        for c in self.claims.values():
            g.add_node(c.id, kind="claim", text=c.text, claim_type=c.claim_type)
        for e in self.edges:
            g.add_edge(e.src, e.dst, relation=e.relation,
                       evidence=e.evidence, confidence=e.confidence)
        return g

    def claims_for(self, paper_id: str) -> list[Claim]:
        return [c for c in self.claims.values() if c.paper_id == paper_id]

    def relations_of(self, claim_id: str) -> list[Edge]:
        rels = {"supports", "contradicts", "refines", "extends"}
        return [e for e in self.edges
                if e.relation in rels and (e.src == claim_id or e.dst == claim_id)]

    # ── persistence ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "papers": [p.to_dict() for p in self.papers.values()],
            "claims": [c.to_dict() for c in self.claims.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def save(self, path: Path | None = None) -> Path:
        config.ensure_dirs()
        path = path or (config.ATLAS / "atlas.json")
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "Atlas":
        path = path or (config.ATLAS / "atlas.json")
        d = json.loads(Path(path).read_text())
        a = cls()
        a.topic = d.get("topic", "")
        for pd in d.get("papers", []):
            a.papers[pd["id"]] = Paper.from_dict(pd)
        for cd in d.get("claims", []):
            a.claims[cd["id"]] = Claim.from_dict(cd)
        a.edges = [Edge.from_dict(ed) for ed in d.get("edges", [])]
        return a

    def summary(self) -> str:
        rel = sum(1 for e in self.edges if e.relation in
                  {"supports", "contradicts", "refines", "extends"})
        cit = sum(1 for e in self.edges if e.relation == "cites")
        return (f"atlas[{self.topic!r}]: {len(self.papers)} papers, "
                f"{len(self.claims)} claims, {rel} claim-relations, {cit} citations")
