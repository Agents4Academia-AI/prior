"""Origin-eval tests — key-free, over synthetic citation graphs."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

import origin_check  # noqa: E402
from prior.atlas import Atlas  # noqa: E402
from prior.models import Claim, Paper  # noqa: E402


def _atlas():
    """p1 (2018, foundational) <- p2 (2020) <- p3 (2022). p4 unrelated."""
    a = Atlas()
    for pid, year, refs in [("p1", 2018, []), ("p2", 2020, ["p1"]),
                            ("p3", 2022, ["p1", "p2"]), ("p4", 2021, [])]:
        a.add_paper(Paper(id=pid, source="t", title=f"Paper {pid}",
                          abstract="", url="", year=year, authors=["A B"],
                          referenced_works=refs))
    a.add_claim(Claim("p1::c0", "p1", "graph neural networks aggregate neighbours",
                      "methodological"))
    a.add_claim(Claim("p2::c0", "p2", "attention improves graph neural networks",
                      "empirical"))
    a.add_claim(Claim("p3::c0", "p3", "graph attention scales to large graphs",
                      "empirical"))
    a.add_claim(Claim("p4::c0", "p4", "diffusion models generate images",
                      "empirical"))
    a.link_citations()
    return a


def test_ancestors_follow_citation_edges():
    a = _atlas()
    assert origin_check.ancestors(a, "p3") == {"p1", "p2"}
    assert origin_check.ancestors(a, "p1") == set()   # foundational: no ancestors
    assert origin_check.ancestors(a, "p4") == set()


def test_structural_origin_picks_most_foundational():
    a = _atlas()
    # p1 is cited within the atlas by p2 and p3 -> the foundational origin.
    assert origin_check.structural_origin(a, "graph neural networks", k=5) == "p1"


def test_score_traced_grounded_when_ancestor():
    a = _atlas()
    # Tracing the origin to p1 should be grounded (it's an ancestor of p2/p3).
    r = origin_check.score_traced(a, "graph attention networks", ["p1"], k=5)
    assert r["grounded"] is True
    assert "p1" in r["grounded_ids"]


def test_score_traced_not_grounded_for_unrelated_paper():
    a = _atlas()
    r = origin_check.score_traced(a, "graph attention networks", ["p4"], k=5)
    assert r["grounded"] is False


def test_cited_ids_regex():
    assert origin_check.cited_ids("origin is [openalex:W1] per [arxiv:2401.1]") \
        == ["openalex:W1", "arxiv:2401.1"]
