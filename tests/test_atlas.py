"""Tests for the parts that don't need an API key: models, atlas graph,
citation linking, persistence, and retrieval ranking."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior.atlas import Atlas
from prior.models import Claim, Edge, Paper
from prior import navigator


def _paper(pid, year, refs=(), cited=0):
    return Paper(id=pid, source="test", title=f"Paper {pid}",
                 abstract="abstract", url="", year=year,
                 authors=["Ada Lovelace"], referenced_works=list(refs),
                 cited_by_count=cited)


def _claim(cid, pid, text, ctype="empirical"):
    return Claim(id=cid, paper_id=pid, text=text, claim_type=ctype)


def build_small_atlas():
    a = Atlas()
    a.topic = "test"
    a.add_paper(_paper("p1", 2018, cited=500))
    a.add_paper(_paper("p2", 2020, refs=["p1"], cited=100))
    a.add_paper(_paper("p3", 2022, refs=["p1", "p2"], cited=10))
    a.add_claim(_claim("p1::c00", "p1", "RAG reduces hallucination in QA tasks"))
    a.add_claim(_claim("p2::c00", "p2", "Active retrieval further reduces hallucination"))
    a.add_claim(_claim("p3::c00", "p3", "Retrieval adds latency to generation"))
    a.link_citations()
    return a


def test_stated_in_edges_created_per_claim():
    a = build_small_atlas()
    stated = [e for e in a.edges if e.relation == "stated_in"]
    assert len(stated) == len(a.claims) == 3
    assert all(e.dst in a.papers for e in stated)


def test_citation_linking_only_within_atlas():
    a = build_small_atlas()
    cites = [(e.src, e.dst) for e in a.edges if e.relation == "cites"]
    assert ("p2", "p1") in cites
    assert ("p3", "p1") in cites and ("p3", "p2") in cites
    assert len(cites) == 3  # no dangling refs to papers we don't hold


def test_roundtrip_save_load(tmp_path):
    a = build_small_atlas()
    a.add_edge(Edge("p2::c00", "p1::c00", "extends", "builds on RAG", 0.9))
    path = tmp_path / "atlas.json"
    a.save(path)
    b = Atlas.load(path)
    assert b.topic == a.topic
    assert set(b.papers) == set(a.papers)
    assert set(b.claims) == set(a.claims)
    assert len(b.edges) == len(a.edges)
    assert any(e.relation == "extends" for e in b.edges)


def test_retrieval_ranks_relevant_claim_first():
    a = build_small_atlas()
    hits = navigator._retrieve(a, "latency cost of retrieval", n=3)
    assert hits, "expected at least one hit"
    assert hits[0][0].id == "p3::c00"


def test_origin_ordering_prefers_foundational_paper():
    a = build_small_atlas()
    # p1 is cited within the atlas by p2 and p3 -> most foundational.
    g = a.graph()
    in_cites = lambda pid: sum(
        1 for _, _, d in g.in_edges(pid, data=True) if d.get("relation") == "cites")
    assert in_cites("p1") == 2
    assert in_cites("p3") == 0
