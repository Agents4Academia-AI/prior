"""Tests for the key-free eval primitives."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

import groundedness  # noqa: E402
import citation_check  # noqa: E402
from prior.atlas import Atlas  # noqa: E402
from prior.models import Claim, Paper  # noqa: E402


def test_overlap_full_and_none():
    src = "Retrieval augmented generation reduces hallucination on QA benchmarks."
    assert groundedness.overlap("reduces hallucination", src) == 1.0
    assert groundedness.overlap("improves image resolution dramatically", src) < 0.5


def test_overlap_empty_evidence_is_zero():
    assert groundedness.overlap("", "anything") == 0.0


def _atlas_with_one_claim():
    a = Atlas()
    a.add_paper(Paper(id="openalex:W1", source="t", title="t", abstract="a", url=""))
    a.add_claim(Claim(id="openalex:W1::c00", paper_id="openalex:W1", text="x",
                      claim_type="empirical"))
    return a


def test_cited_ids_extracts_claim_and_paper_ids():
    ids = citation_check.cited_ids("see [openalex:W1::c00] and [arxiv:2401.1]")
    assert ids == ["openalex:W1::c00", "arxiv:2401.1"]


def test_validate_flags_fabricated_ids():
    a = _atlas_with_one_claim()
    r = citation_check.validate(a, "grounded [openalex:W1::c00] vs fake [openalex:W9::c00]")
    assert r["valid"] == 1
    assert r["invalid_ids"] == ["openalex:W9::c00"]
    assert r["validity_rate"] == 0.5
