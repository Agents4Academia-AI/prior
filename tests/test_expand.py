"""Tests for citation reference-expansion and ancestor-aware origin candidates.
Key-free: network fetch is monkeypatched."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior import navigator, pipeline
from prior.atlas import Atlas
from prior.models import Claim, Paper
from prior.sources import openalex


def _paper(pid, year, refs=(), cited=0, abstract="abstract here"):
    return Paper(id=pid, source="test", title=f"Paper {pid}", abstract=abstract,
                 url="", year=year, authors=["A B"], referenced_works=list(refs),
                 cited_by_count=cited)


def test_expand_references_pulls_in_cited_works(monkeypatch):
    # p1 (modern) references openalex:W1989 (not initially in the corpus).
    p_modern = _paper("openalex:Wmod", 2020, refs=["openalex:W1989", "openalex:Wskip"])
    origin = _paper("openalex:W1989", 1989, cited=5000)

    def fake_fetch_many(ids, **_):
        return {origin.id: origin} if "openalex:W1989" in ids else {}

    monkeypatch.setattr(openalex, "fetch_many", fake_fetch_many)
    out = pipeline.expand_references([p_modern], hops=1)
    ids = {p.id for p in out}
    assert "openalex:W1989" in ids          # reached the 1989 origin
    assert "openalex:Wmod" in ids           # kept the original


def test_expand_respects_cap(monkeypatch):
    p = _paper("openalex:Wa", 2020, refs=["openalex:Wb", "openalex:Wc"])
    monkeypatch.setattr(openalex, "fetch_many",
                        lambda ids, **_: {f"x{i}": _paper(f"x{i}", 2000) for i in ids})
    out = pipeline.expand_references([p], hops=1, cap=1)
    assert len(out) == 1                     # already at cap, no room to add


def test_origin_candidates_include_citation_ancestors():
    a = Atlas()
    a.add_paper(_paper("p1", 1989, cited=9000))          # foundational origin
    a.add_paper(_paper("p3", 2022, refs=["p1"]))         # modern, cites p1
    for pid, yr in [("p2", 2015), ("p4", 2018), ("p5", 2020)]:
        a.add_paper(_paper(pid, yr))
    # p1's claim does NOT mention the concept -> only reachable as an ancestor.
    a.add_claim(Claim("p1::c0", "p1", "early connectionist memory interference model",
                      "theoretical"))
    a.add_claim(Claim("p3::c0", "p3", "graph attention networks scale to large graphs",
                      "empirical"))
    a.add_claim(Claim("p2::c0", "p2", "convolutional networks classify images", "empirical"))
    a.add_claim(Claim("p4::c0", "p4", "recurrent networks model long sequences", "empirical"))
    a.add_claim(Claim("p5::c0", "p5", "transformers apply self attention to tokens", "empirical"))
    a.link_citations()

    cands = navigator.origin_candidates(a, "graph attention networks", n=5)
    assert "p3" in cands                     # the matched paper
    assert "p1" in cands                     # pulled in as citation ancestor
    assert cands[0] == "p1"                  # ranked foundational-first
