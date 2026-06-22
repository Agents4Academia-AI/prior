"""Tests for review filtering, full-text helpers, and the Contribution agent
(key-free: the LLM call is monkeypatched)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior import contributor, fulltext, llm
from prior.models import Paper
from prior.sources import looks_like_review


# ── review filter ───────────────────────────────────────────────────────────
def test_review_filter_flags_surveys_not_primary():
    assert looks_like_review("Retrieval-Augmented Generation: A Survey")
    assert looks_like_review("A Comprehensive Review of RAG")
    assert looks_like_review("anything", work_type="review")
    assert not looks_like_review("AR-RAG: Autoregressive Retrieval Augmentation")
    assert not looks_like_review("Reducing hallucination in structured outputs")


# ── full-text helpers ───────────────────────────────────────────────────────
def test_html_to_text_strips_tags_and_scripts():
    html = "<html><body><script>x=1</script><p>We propose <b>AR-RAG</b>.</p></body></html>"
    assert fulltext._html_to_text(html) == "We propose AR-RAG ."


def test_arxiv_id_extraction():
    p = Paper(id="arxiv:2506.06962v3", source="arxiv", title="t", abstract="a", url="")
    assert fulltext._arxiv_id_of(p) == "2506.06962"
    p2 = Paper(id="openalex:W1", source="openalex", title="t", abstract="a", url="",
               pdf_url="https://arxiv.org/pdf/2404.08189")
    assert fulltext._arxiv_id_of(p2) == "2404.08189"
    p3 = Paper(id="openalex:W2", source="openalex", title="t", abstract="a", url="",
               pdf_url="https://aclanthology.org/2024.naacl.19.pdf")
    assert fulltext._arxiv_id_of(p3) is None


# ── contribution agent ──────────────────────────────────────────────────────
def test_extract_contributions_shapes_output(monkeypatch):
    def fake_structured(**kwargs):
        assert "self-declared" in kwargs["system"].lower() or "ITSELF" in kwargs["system"]
        return {"contributions": [
            {"statement": "We propose AR-RAG.", "kind": "framework", "quote": "we propose"},
            {"statement": "We introduce DAiD.", "kind": "method", "quote": "we introduce"},
        ]}
    monkeypatch.setattr(llm, "structured", fake_structured)
    p = Paper(id="arxiv:2506.06962", source="arxiv", title="AR-RAG", abstract="x", url="")
    cs = contributor.extract(p, "full text body")
    assert [c["kind"] for c in cs] == ["framework", "method"]
    assert cs[0]["id"] == "arxiv:2506.06962::k00"
    assert all(c["paper_id"] == "arxiv:2506.06962" for c in cs)


def test_extract_handles_empty(monkeypatch):
    monkeypatch.setattr(llm, "structured", lambda **k: {"contributions": []})
    p = Paper(id="x", source="t", title="A Survey", abstract="a", url="")
    assert contributor.extract(p, None) == []


# ── schema round-trip with new Paper fields ─────────────────────────────────
def test_paper_roundtrip_with_new_fields_and_old_dicts():
    p = Paper(id="openalex:W1", source="openalex", title="t", abstract="a", url="",
              pdf_url="http://x/y.pdf", is_review=True)
    assert Paper.from_dict(p.to_dict()).pdf_url == "http://x/y.pdf"
    # old atlas dict without the new fields → defaults, not None
    old = {"id": "W9", "source": "openalex", "title": "t", "abstract": "a", "url": ""}
    p2 = Paper.from_dict(old)
    assert p2.pdf_url == "" and p2.is_review is False
