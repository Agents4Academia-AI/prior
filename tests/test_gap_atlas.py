import importlib.util
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "experiments/graph_ideation/build_gap_atlas.py"
SPEC = importlib.util.spec_from_file_location("build_gap_atlas", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

TEMPORAL_PATH = Path(__file__).resolve().parents[1] / "experiments/graph_ideation/temporal_gap_closure.py"
TEMPORAL_SPEC = importlib.util.spec_from_file_location("temporal_gap_closure", TEMPORAL_PATH)
TEMPORAL = importlib.util.module_from_spec(TEMPORAL_SPEC)
TEMPORAL_SPEC.loader.exec_module(TEMPORAL)


def test_gap_card_separates_evidence_from_hypothesis():
    manifest = {"packets": [{
        "packet_id": "abc", "motif": "contradiction_resolution",
        "sources": [{"id": "S1", "contribution_id": "p1::k00"}],
        "edge_evidence": {"relation": "contradicts", "existence_confidence": .9},
    }]}
    predictions = [{
        "packet_id": "abc", "gap_type": "contradiction_resolution", "model": "test",
        "gap_statement": "Candidate gap", "missing_evidence": "Missing comparison",
        "minimal_study": "Run comparison", "reason": "Because",
    }]
    contributions = {"p1::k00": {"id": "p1::k00", "paper_id": "p1",
        "statement": "Contribution", "quote_verbatim": "Exact quote", "grounding": .99}}
    papers = {"p1": {"id": "p1", "title": "Paper", "year": 2025, "url": "url"}}

    card = MODULE.build_cards(manifest, predictions, contributions, papers)[0]

    assert card["status"] == "draft_unverified"
    assert card["gap_hypothesis"] == "Candidate gap"
    assert card["evidence"]["sources"][0]["supporting_quote"] == "Exact quote"
    assert card["review"]["gap_confirmed"] is None


def test_temporal_work_key_collapses_arxiv_versions():
    first = {"id": "arxiv:2501.01234v1", "title": "A Paper"}
    second = {"id": "openalex:W1", "doi": "https://doi.org/10.48550/arXiv.2501.01234",
              "title": "A Paper revised"}
    assert TEMPORAL.work_key(first) == TEMPORAL.work_key(second) == "arxiv:2501.01234"
