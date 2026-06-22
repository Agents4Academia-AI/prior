"""Eval-logic tests — pure functions, no Neo4j / no API key."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
import graph_eval  # noqa: E402


def test_overlap_full_and_partial():
    assert graph_eval._overlap("catastrophic forgetting", "we study catastrophic forgetting here") == 1.0
    assert graph_eval._overlap("", "anything") == 0.0
    assert 0.0 < graph_eval._overlap("alpha beta gamma", "alpha beta only") < 1.0


def test_groundedness_on_synthetic(tmp_path):
    raw = tmp_path / "raw"; atlas = tmp_path / "atlas"
    raw.mkdir(); atlas.mkdir()
    (raw / "papers.jsonl").write_text(json.dumps(
        {"id": "p1", "abstract": "we propose method M that reduces forgetting", "full_text": ""}) + "\n")
    (atlas / "claims.jsonl").write_text("\n".join([
        json.dumps({"paper_id": "p1", "evidence": "method M that reduces forgetting"}),  # grounded
        json.dumps({"paper_id": "p1", "evidence": "quantum entanglement of qubits"}),    # not
    ]) + "\n")
    rep = graph_eval.groundedness(str(tmp_path))
    assert rep["claims"] == 2
    assert rep["grounded_rate@0.8"] == 0.5
