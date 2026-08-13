"""Canonical cross-source key + dedup (the fix for OpenAlex/arXiv/S2 id mismatch)."""

from prior import scoper
from prior.models import Paper

TITLE = "The AI Scientist: Towards Fully Automated Open-Ended Discovery"


def _p(pid, source, title):
    return Paper(id=pid, source=source, title=title, abstract="", url="")


def test_key_matches_across_id_namespaces():
    a = _p("openalex:W4402952666", "openalex", TITLE)
    b = _p("arxiv:2408.06292v3", "arxiv", TITLE)
    c = _p("s2:dbbcdb281", "semanticscholar", "The  AI   Scientist  Towards Fully "
           "Automated  Open-Ended Discovery")     # spacing/punctuation differences
    assert a.key() == b.key() == c.key()


def test_dedup_collapses_and_prefers_openalex():
    papers = [
        _p("arxiv:2408.06292v3", "arxiv", TITLE),
        _p("openalex:W4402952666", "openalex", TITLE),
        _p("s2:dbbcdb281", "semanticscholar", TITLE),
        _p("openalex:W999", "openalex", "A Completely Different Paper On Another Topic"),
    ]
    out = scoper._dedup_cross_source(papers)
    assert len(out) == 2
    ai = [p for p in out if "ai scientist" in p.title.lower()][0]
    assert ai.source == "openalex"               # preferred source survives
    assert {m["id"] for m in ai.manifestations} == {
        "arxiv:2408.06292v3", "s2:dbbcdb281"}


def test_manifestations_survive_json_roundtrip():
    paper = _p("openalex:W1", "openalex", TITLE)
    paper.manifestations = [{"id": "arxiv:2408.06292v3", "source": "arxiv",
                             "url": "https://arxiv.org/abs/2408.06292v3",
                             "pdf_url": "https://arxiv.org/pdf/2408.06292"}]
    restored = Paper.from_dict(paper.to_dict())
    assert restored.all_manifestations()[1]["id"] == "arxiv:2408.06292v3"


def test_manifestations_do_not_change_canonical_work_id():
    paper = _p("openalex:W1", "openalex", TITLE)
    before = paper.work_id()
    paper.manifestations = [{"id": "arxiv:2408.06292v3", "source": "arxiv"}]
    assert paper.work_id() == before
    assert paper.to_dict()["work_id"] == before


def test_dedup_merges_preprint_with_small_title_change():
    publisher = Paper(id="openalex:W1", source="openalex",
        title="SciAgents: Automating Scientific Discovery Through Bioinspired Multi-Agent Intelligent Graph Reasoning",
        abstract="", url="", year=2025, authors=["Alireza Ghafarollahi", "Markus Buehler"])
    preprint = Paper(id="arxiv:2409.05556v1", source="arxiv",
        title="SciAgents: Automating scientific discovery through multi-agent intelligent graph reasoning",
        abstract="", url="https://arxiv.org/abs/2409.05556v1", year=2024,
        authors=["Alireza Ghafarollahi", "Markus J. Buehler"])
    out = scoper._dedup_cross_source([publisher, preprint])
    assert len(out) == 1 and out[0].manifestations[0]["id"] == preprint.id


def test_resolve_manifestations_attaches_arxiv_twin(monkeypatch):
    publisher = Paper(id="openalex:W1", source="openalex",
        title="SciAgents: Automating Scientific Discovery Through Bioinspired Multi-Agent Intelligent Graph Reasoning",
        abstract="", url="", year=2025, authors=["Alireza Ghafarollahi", "Markus Buehler"])
    preprint = Paper(id="arxiv:2409.05556v1", source="arxiv",
        title="SciAgents: Automating scientific discovery through multi-agent intelligent graph reasoning",
        abstract="", url="https://arxiv.org/abs/2409.05556v1", year=2024,
        authors=["Alireza Ghafarollahi", "Markus J. Buehler"])
    monkeypatch.setattr(scoper.semanticscholar, "fetch", lambda _id: None)
    monkeypatch.setattr(scoper.arxiv, "find_id_by_title", lambda _title: "2409.05556")
    monkeypatch.setattr(scoper.arxiv, "fetch_ids", lambda _ids: {preprint.id: preprint})
    scoper.resolve_manifestations([publisher], progress=lambda *_: None)
    assert publisher.manifestations[0]["id"] == preprint.id


def test_short_title_falls_back_to_id():
    # too-short titles must not collapse different papers
    assert _p("openalex:W1", "openalex", "Intro").key() != \
           _p("arxiv:9", "arxiv", "Intro").key()
