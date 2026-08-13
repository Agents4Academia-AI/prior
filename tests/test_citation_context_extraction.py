"""Regression tests for bounded arXiv bibliography extraction."""
from __future__ import annotations

import importlib.util
from pathlib import Path


PATH = Path(__file__).parents[1] / "experiments/edge_quality/extract_citation_contexts.py"
SPEC = importlib.util.spec_from_file_location("extract_citation_contexts", PATH)
X = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(X)


def test_bbl_stops_at_end_thebibliography_before_appended_bib():
    text = r"""
    \begin{thebibliography}{9}
    \bibitem{deepreview} Authors. DeepReview. arXiv:2503.08569.
    \bibitem{other} Authors. Other Work. 2024.
    \end{thebibliography}
    % appended source must not become part of `other`
    @article{paperqa, title={PaperQA2}, year={2025}}
    """
    entries = X.bbl_entries(text)
    assert [key for key, _ in entries] == ["deepreview", "other"]
    assert "PaperQA2" not in entries[-1][1]


def test_bibtex_balanced_parser_keeps_multiline_nested_entries_separate():
    text = r"""
    @article{one,
      title = {A {Nested} Scientific Title},
      note = "text with a } brace inside quotes",
      year = {2024}
    }
    @inproceedings{two,
      title = {Second Title},
      year = {2025}
    }
    """
    entries = X.bibtex_entries(text)
    assert [key for key, _ in entries] == ["one", "two"]
    assert "Second Title" not in entries[0][1]


def test_files_are_parsed_independently_and_conflicting_keys_rejected():
    files = {
        "refs.bbl": r"\bibitem{same} Correct bounded reference. 2024.",
        "refs.bib": "@article{same, title={Different reference}, year={2024}}",
    }
    assert X.bibliography_entries(files) == []


def test_match_rejects_entry_with_multiple_corpus_targets():
    entries = [("blob", "DeepReview arXiv:2503.08569 and PaperQA2 arXiv:2409.13740")]
    signatures = {
        "citer": {"arx": None, "title": "citing paper"},
        "deep": {"arx": "2503.08569", "title": "deepreview"},
        "pqa": {"arx": "2409.13740", "title": "paperqa2"},
    }
    assert X.match_entries(entries, signatures, "citer") == {}


def test_match_rejects_target_resolved_by_multiple_entries():
    entries = [("one", "DeepReview arXiv:2503.08569"),
               ("duplicate", "Another record for arXiv:2503.08569")]
    signatures = {"deep": {"arx": "2503.08569", "title": "deepreview"}}
    assert X.match_entries(entries, signatures, "citer") == {}
