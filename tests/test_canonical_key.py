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


def test_short_title_falls_back_to_id():
    # too-short titles must not collapse different papers
    assert _p("openalex:W1", "openalex", "Intro").key() != \
           _p("arxiv:9", "arxiv", "Intro").key()
