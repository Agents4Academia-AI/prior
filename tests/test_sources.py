"""Parsing tests for source adapters (no network: feed canned payloads)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior.sources import openalex
from prior.sources import arxiv as arxiv_src
from prior.sources import semanticscholar as s2_src


def test_openalex_abstract_inverted_index_reconstructs_order():
    inv = {"Retrieval": [0], "augmented": [1], "generation": [2], "works": [3]}
    assert openalex._abstract_from_index(inv) == "Retrieval augmented generation works"


def test_openalex_id_normalisation():
    assert openalex._norm_id("https://openalex.org/W4389984066") == "openalex:W4389984066"
    assert openalex._norm_id(None) == ""


def test_openalex_api_key_comes_only_from_environment(monkeypatch):
    monkeypatch.setenv("PRIOR_OPENALEX_API_KEY", "private-test-key")
    assert openalex._params()["api_key"] == "private-test-key"
    assert "private-test-key" not in openalex.redact_error(
        "https://api.openalex.org/works?api_key=private-test-key")


def test_openalex_to_paper_extracts_citations():
    work = {
        "id": "https://openalex.org/W2",
        "title": "On Retrieval",
        "publication_year": 2020,
        "authorships": [{"author": {"display_name": "Grace Hopper"}}],
        "primary_location": {"source": {"display_name": "NeurIPS"}},
        "abstract_inverted_index": {"Hello": [0], "world": [1]},
        "referenced_works": ["https://openalex.org/W1"],
        "cited_by_count": 42,
    }
    p = openalex._to_paper(work)
    assert p.id == "openalex:W2"
    assert p.abstract == "Hello world"
    assert p.referenced_works == ["openalex:W1"]
    assert p.cited_by_count == 42
    assert p.venue == "NeurIPS"


def test_arxiv_entry_parsing():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v2</id>
        <title>A   Great   Paper</title>
        <summary>We show
        something.</summary>
        <published>2024-01-02T00:00:00Z</published>
        <author><name>Alan Turing</name></author>
      </entry>
    </feed>"""
    import xml.etree.ElementTree as ET
    entry = ET.fromstring(xml).find("atom:entry", arxiv_src.NS)
    p = arxiv_src._to_paper(entry)
    assert p.id == "arxiv:2401.00001v2"
    assert p.title == "A Great Paper"        # whitespace collapsed
    assert p.abstract == "We show something."
    assert p.year == 2024
    assert p.authors == ["Alan Turing"]


def test_arxiv_abs_fallback_parses_metadata(monkeypatch):
    class Response:
        text = ('<meta name="citation_title" content="The AI Scientist">'
                '<meta name="citation_author" content="Chris Lu">'
                '<meta name="citation_date" content="2024/08/12">'
                '<meta name="citation_abstract" content="An autonomous system.">')
        def raise_for_status(self): pass
    monkeypatch.setattr(arxiv_src.requests, "get", lambda *a, **k: Response())
    paper = arxiv_src.fetch_abs("2408.06292")
    assert paper.title == "The AI Scientist"
    assert paper.authors == ["Chris Lu"]
    assert paper.date == "2024-08-12"


def test_semantic_scholar_proactively_paces_each_rate_tier(monkeypatch):
    clock = {"now": 100.0}
    sleeps = []
    monkeypatch.setattr(s2_src.time, "monotonic", lambda: clock["now"])
    monkeypatch.setattr(
        s2_src.time, "sleep",
        lambda seconds: (sleeps.append(seconds), clock.__setitem__("now", clock["now"] + seconds)),
    )
    s2_src._LAST_REQUEST.update({"slow": 100.0, "standard": 100.0})
    s2_src._pace(s2_src.SEARCH)
    s2_src._LAST_REQUEST["standard"] = clock["now"]
    s2_src._pace(f"{s2_src.GRAPH}/ARXIV:1/references")
    assert sleeps == [1.05, 0.11]


def test_semantic_scholar_honours_retry_after(monkeypatch):
    class Response:
        def __init__(self, status, retry=""):
            self.status_code = status
            self.headers = {"Retry-After": retry} if retry else {}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise s2_src.requests.HTTPError()
    responses = iter([Response(429, "7"), Response(200)])
    sleeps = []
    monkeypatch.setattr(s2_src, "_pace", lambda *a, **k: None)
    monkeypatch.setattr(s2_src.requests, "get", lambda *a, **k: next(responses))
    monkeypatch.setattr(s2_src.random, "uniform", lambda *a: 0.0)
    monkeypatch.setattr(s2_src.time, "sleep", sleeps.append)
    assert s2_src._get(s2_src.SEARCH, {}, tries=2).status_code == 200
    assert sleeps == [7.0]
