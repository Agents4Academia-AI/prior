"""Parsing tests for source adapters (no network: feed canned payloads)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior.sources import openalex
from prior.sources import arxiv as arxiv_src


def test_openalex_abstract_inverted_index_reconstructs_order():
    inv = {"Retrieval": [0], "augmented": [1], "generation": [2], "works": [3]}
    assert openalex._abstract_from_index(inv) == "Retrieval augmented generation works"


def test_openalex_id_normalisation():
    assert openalex._norm_id("https://openalex.org/W4389984066") == "openalex:W4389984066"
    assert openalex._norm_id(None) == ""


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
