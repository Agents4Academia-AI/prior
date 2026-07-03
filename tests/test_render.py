"""Test the HTML atlas renderer (key-free)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior import render_html
from prior.atlas import Atlas
from prior.models import Claim, Edge, Paper


def _atlas():
    a = Atlas()
    a.topic = "test topic"
    a.add_paper(Paper(id="openalex:W1", source="openalex", title="RAG paper",
                      abstract="x", url="http://x", year=2020, authors=["A Lewis"]))
    a.add_paper(Paper(id="openalex:W2", source="openalex", title="Active RAG",
                      abstract="x", url="", year=2023, authors=["B Jiang"],
                      referenced_works=["openalex:W1"]))
    a.add_claim(Claim("openalex:W1::c00", "openalex:W1",
                      "RAG reduces hallucination in QA", "empirical", "quote", confidence=0.8))
    a.add_claim(Claim("openalex:W2::c00", "openalex:W2",
                      "active retrieval reduces it further", "empirical", "q", confidence=0.6))
    a.link_citations()
    a.add_edge(Edge("openalex:W2::c00", "openalex:W1::c00", "extends", "builds on", 0.9))
    return a


def test_render_writes_self_contained_html(tmp_path):
    a = _atlas()
    ap = tmp_path / "atlas.json"
    a.save(ap)
    out = render_html.render(ap, tmp_path / "view.html")
    html = out.read_text()
    assert "vis-network" in html                       # graph library loaded
    assert "RAG reduces hallucination in QA" in html   # claim node present
    assert "extends" in html                           # typed edge present
    assert "openalex:W1" in html                       # paper node present
    assert html.strip().startswith("<!doctype html>")


def test_render_handles_empty_atlas(tmp_path):
    ap = tmp_path / "atlas.json"
    Atlas().save(ap)
    out = render_html.render(ap, tmp_path / "view.html")
    assert out.exists() and "vis-network" in out.read_text()
