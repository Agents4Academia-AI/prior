"""Canonical cross-source key + dedup (the fix for OpenAlex/arXiv/S2 id mismatch)."""

from prior import refresh, scoper
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


def test_identity_aliases_normalise_doi_and_arxiv_versions():
    paper = Paper(id="arxiv:2408.06292v3", source="arxiv", title=TITLE,
                  abstract="", url="https://arxiv.org/abs/2408.06292v3",
                  doi="https://doi.org/10.48550/arXiv.2408.06292v3")
    assert paper.identity_aliases() == [
        "arxiv:2408.06292", "doi:10.48550/arxiv.2408.06292v3"]


def test_identity_aliases_include_alternate_manifestations():
    paper = _p("openalex:W1", "openalex", TITLE)
    paper.manifestations = [{"id": "arxiv:2408.06292v2", "source": "arxiv",
                             "doi": "10.1000/published-paper"}]
    assert paper.identity_aliases() == [
        "arxiv:2408.06292", "doi:10.1000/published-paper"]


def test_shared_doi_merges_retitled_versions():
    a = Paper(id="openalex:W1", source="openalex", title="Early preprint title",
              abstract="", url="", doi="10.1000/the-work")
    b = Paper(id="s2:abc", source="semanticscholar",
              title="Substantially revised published title", abstract="", url="",
              doi="https://doi.org/10.1000/THE-WORK")
    assert scoper._same_work(a, b)


def test_disjoint_dois_prevent_generic_title_collision():
    a = Paper(id="openalex:W1", source="openalex", title="Editorial",
              abstract="", url="", doi="10.1000/one")
    b = Paper(id="openalex:W2", source="openalex", title="Editorial",
              abstract="", url="", doi="10.1000/two")
    assert not scoper._same_work(a, b)


def test_pending_dedup_prefers_strong_alias_over_title_hash():
    paper = Paper(id="openalex:W1", source="openalex", title="Editorial",
                  abstract="", url="", doi="10.1000/one")
    assert refresh._identity_keys(paper) == {"openalex:W1", "doi:10.1000/one"}
    assert paper.key() not in refresh._identity_keys(paper)


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
