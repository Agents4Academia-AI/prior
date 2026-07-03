"""The atlas: papers + contributions + claims + a typed two-level graph, with
persistence.

Graph nodes are papers, contributions (global) and claims (local); edges are:
  stated_in        claim        -> paper         (provenance; one per claim)
  supports_contrib claim        -> contribution  (local→global bridge)
  cites            paper        -> paper          (from OpenAlex referenced_works)
  LOCAL_RELATIONS  claim        -> claim          (within-paper story)
  GLOBAL_RELATIONS contribution -> contribution   (cross-paper lineage)

The on-disk JSON is the hand-off API: a verification or baseline team can load
`atlas.json` and get a fully grounded corpus with provenance.
"""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from . import config
from .models import GLOBAL_RELATIONS, LOCAL_RELATIONS, Claim, Contribution, Edge, Paper


class Atlas:
    def __init__(self) -> None:
        self.papers: dict[str, Paper] = {}
        self.contributions: dict[str, Contribution] = {}
        self.claims: dict[str, Claim] = {}
        self.edges: list[Edge] = []
        self.topic: str = ""

    # ── building ────────────────────────────────────────────────────────────
    def add_paper(self, p: Paper) -> None:
        self.papers[p.id] = p

    def add_contribution(self, k: Contribution) -> None:
        self.contributions[k.id] = k

    def add_claim(self, c: Claim) -> None:
        self.claims[c.id] = c
        self.edges.append(Edge(c.id, c.paper_id, "stated_in", confidence=1.0, level="meta"))
        if c.contribution_id:
            self.edges.append(Edge(c.id, c.contribution_id, "supports_contrib",
                                   confidence=1.0, level="meta"))

    def add_edge(self, e: Edge) -> None:
        self.edges.append(e)

    def link_citations(self) -> int:
        """Add `cites` edges between papers we actually hold. Returns count."""
        n = 0
        have = set(self.papers)
        for p in self.papers.values():
            for ref in p.referenced_works:
                if ref in have:
                    self.edges.append(Edge(p.id, ref, "cites", confidence=1.0, level="meta"))
                    n += 1
        return n

    # ── graph view ──────────────────────────────────────────────────────────
    def graph(self) -> nx.DiGraph:
        g = nx.DiGraph()
        for p in self.papers.values():
            g.add_node(p.id, kind="paper", title=p.title, year=p.year,
                       cited_by=p.cited_by_count)
        for k in self.contributions.values():
            g.add_node(k.id, kind="contribution", paper_id=k.paper_id,
                       problem=k.problem, method=k.method, result=k.result)
        for c in self.claims.values():
            g.add_node(c.id, kind="claim", text=c.text, claim_type=c.claim_type)
        for e in self.edges:
            g.add_edge(e.src, e.dst, relation=e.relation,
                       evidence=e.evidence, confidence=e.confidence, source=e.source)
        return g

    def claims_for(self, paper_id: str) -> list[Claim]:
        return [c for c in self.claims.values() if c.paper_id == paper_id]

    def contributions_for(self, paper_id: str) -> list[Contribution]:
        return [k for k in self.contributions.values() if k.paper_id == paper_id]

    def local_relations_of(self, claim_id: str) -> list[Edge]:
        return [e for e in self.edges
                if e.level == "local" and (e.src == claim_id or e.dst == claim_id)]

    def global_relations_of(self, contrib_id: str) -> list[Edge]:
        return [e for e in self.edges
                if e.level == "global" and (e.src == contrib_id or e.dst == contrib_id)]

    # ── persistence ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "papers": [p.to_dict() for p in self.papers.values()],
            "contributions": [k.to_dict() for k in self.contributions.values()],
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
        for kd in d.get("contributions", []):
            a.contributions[kd["id"]] = Contribution.from_dict(kd)
        for cd in d.get("claims", []):
            a.claims[cd["id"]] = Claim.from_dict(cd)
        a.edges = [Edge.from_dict(ed) for ed in d.get("edges", [])]
        return a

    def summary(self) -> str:
        loc = sum(1 for e in self.edges if e.level == "local")
        glo = sum(1 for e in self.edges if e.level == "global")
        cit = sum(1 for e in self.edges if e.relation == "cites")
        return (f"atlas[{self.topic!r}]: {len(self.papers)} papers, "
                f"{len(self.contributions)} contributions, {len(self.claims)} claims, "
                f"{loc} local edges, {glo} global edges, {cit} citations")
