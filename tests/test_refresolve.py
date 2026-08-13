"""Tests for prior.sources.refresolve — the ported reference resolver adapter.

Offline by default (no network, no API key), mirroring the rest of the suite:
the deterministic logic (LaTeX/BibTeX conditioning, id extraction, corpus join,
the fail-soft + explicit-id-fallback branches of ``resolve_reference``) is tested
with a fake resolver injected via the ``resolver=`` seam. The one test that hits
the live grounding sources is gated behind ``PRIOR_RESOLVE_NETWORK_TEST=1`` and
skipped otherwise, so CI stays green and offline.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from prior.sources import refresolve as R


# ── normalisation helpers ─────────────────────────────────────────────────────
def test_norm_arxiv_strips_prefix_url_and_version():
    assert R._norm_arxiv("arXiv:2407.00466v3") == "2407.00466"
    assert R._norm_arxiv("https://arxiv.org/abs/2407.00466") == "2407.00466"
    assert R._norm_arxiv("") == "" and R._norm_arxiv(None) == ""


def test_norm_doi_strips_resolver_prefix_and_lowercases():
    assert R._norm_doi("https://doi.org/10.1145/ABC.def") == "10.1145/abc.def"
    assert R._norm_doi("10.1/XYZ.") == "10.1/xyz"


def test_norm_title_matches_paper_key_collapsing():
    # Same collapsing as prior.models.Paper.key(), so titles join on one string.
    assert R._norm_title("Attention Is All You Need!") == "attention is all you need"


# ── LaTeX \bibitem conditioning: the three arXiv-id spellings ──────────────────
@pytest.mark.parametrize("raw, expected_id", [
    (r"Foo. \newblock Bar. \newblock URL \url{https://arxiv.org/abs/2404.07738}.", "2404.07738"),
    (r"Foo. \newblock Bar. \emph{ArXiv}, abs/2411.15114, 2024.", "2411.15114"),
    (r"Foo. Bar. arXiv:2503.18102 , 2025.", "2503.18102"),
])
def test_clean_latex_unifies_arxiv_spellings(raw, expected_id):
    cleaned = R._clean_latex_reference(raw)
    assert f"arXiv:{expected_id}" in cleaned
    assert "\\newblock" not in cleaned and "\\url" not in cleaned


def test_clean_latex_drops_tildes_and_braces():
    assert "~" not in R._clean_latex_reference("Sujay~Kumar {Jauhar}")


# ── raw BibTeX field syntax ────────────────────────────────────────────────────
def test_bibtex_fields_detected_and_reconstructed():
    bib = ('title={PaperBench: Evaluating}, author={Starace, Giulio and Jaffe, O}, '
           'booktitle={ICML}, year={2025}, eprint={2504.01848}')
    assert R._looks_like_bibtex_fields(bib)
    ref = R._bibtex_fields_to_reference(bib)
    assert "PaperBench: Evaluating" in ref
    assert "Starace" in ref and "2025" in ref
    assert "arXiv:2504.01848" in ref          # eprint promoted to an id the cascade reads


def test_bibtex_without_title_yields_empty():
    assert R._bibtex_fields_to_reference("author={Nobody}, year={2020}") == ""


# ── explicitly-stated id extractors (owned by Prior, not c-v internals) ────────
def test_find_stated_ids():
    assert R._FIND_ARXIV_RE.search("see arXiv:2411.15114v2 here").group(1) == "2411.15114"
    assert R._FIND_DOI_RE.search("doi 10.1145/abc.def-1").group(1) == "10.1145/abc.def-1"


# ── CorpusIndex: the canonical-identity -> Prior-node-id join ───────────────────
def _paper(pid, doi=None, title="", arxiv_id=""):
    return SimpleNamespace(id=pid, doi=doi, title=title, arxiv_id=arxiv_id)


def _corpus():
    return R.CorpusIndex.from_papers([
        _paper("arxiv:2407.00466", title="A Great Paper About Agents"),
        _paper("openalex:W123", doi="10.1/xyz", title="Some Journal Only Paper Title"),
    ])


def test_corpus_match_by_arxiv_doi_title_and_miss():
    idx = _corpus()
    assert idx.match(R.ResolvedRef(reference="x", arxiv_id="2407.00466v1")) == "arxiv:2407.00466"
    assert idx.match(R.ResolvedRef(reference="y", doi="https://doi.org/10.1/XYZ")) == "openalex:W123"
    assert idx.match(R.ResolvedRef(reference="z", title="Some Journal-Only Paper Title.")) == "openalex:W123"
    assert idx.match(R.ResolvedRef(reference="q", title="Totally Unrelated")) is None


def test_corpus_match_precedence_arxiv_over_title():
    # arXiv id is more specific than a title; it must win when both are present.
    idx = _corpus()
    rref = R.ResolvedRef(reference="x", arxiv_id="2407.00466",
                         title="Some Journal Only Paper Title")  # title of the OTHER paper
    assert idx.match(rref) == "arxiv:2407.00466"


def test_short_title_not_indexed():
    idx = R.CorpusIndex.from_papers([_paper("openalex:W9", title="AI")])  # < 8 chars normalised
    assert idx.match(R.ResolvedRef(reference="x", title="AI")) is None


# ── resolve_reference: mapping, fail-soft, cap, fallback (fake resolver) ────────
def _fake_resolver(resolved):
    return SimpleNamespace(resolve=lambda cite_key, ref: resolved)


def test_resolve_reference_projects_and_normalises_fields():
    resolved = SimpleNamespace(match_method="doi", doi="https://doi.org/10.1/ABC",
                               arxiv_id="2401.00001v2", title="  A Title  ", year=2024,
                               source="crossref", match_score=0.97)
    rref = R.resolve_reference("some reference", resolver=_fake_resolver(resolved))
    assert rref.doi == "10.1/abc"
    assert rref.arxiv_id == "2401.00001"          # version stripped
    assert rref.title == "A Title" and rref.match_method == "doi"
    assert rref.match_score == pytest.approx(0.97)


def test_resolve_reference_empty_and_oversize_return_none_without_network():
    # Neither path constructs the network resolver.
    assert R.resolve_reference("") is None
    assert R.resolve_reference("x" * (R.REFERENCE_CHAR_CAP + 1)) is None


def test_resolve_reference_failsoft_on_resolver_error():
    boom = SimpleNamespace(resolve=lambda *a: (_ for _ in ()).throw(RuntimeError("net down")))
    assert R.resolve_reference("Foo. Bar. 2024.", resolver=boom) is None


def test_stated_id_fallback_arxiv_enriches_title(monkeypatch):
    # Resolver abstains, but the reference states an arXiv id -> trust it, and
    # enrich the title from Prior's arXiv source so title-only nodes still join.
    from prior.sources import arxiv as prior_arxiv
    monkeypatch.setattr(prior_arxiv, "fetch_ids",
                        lambda ids: {"arxiv:x": SimpleNamespace(title="Recovered Title", year=2024)})
    rref = R.resolve_reference("Two Authors. Some work. arXiv:2503.18102 , 2025.",
                               resolver=_fake_resolver(None))
    assert rref is not None
    assert rref.arxiv_id == "2503.18102"
    assert rref.title == "Recovered Title" and rref.match_method == "arxiv"


def test_stated_id_fallback_doi():
    # A real DOI is 10.<4-9 digits>/suffix; the extractor requires that shape.
    rref = R.resolve_reference("Some work. doi:10.1145/ABC.def.", resolver=_fake_resolver(None))
    assert rref is not None and rref.doi == "10.1145/abc.def" and rref.match_method == "doi"


def test_no_stated_id_and_resolver_abstains_returns_none():
    assert R.resolve_reference("Plain title with no ids at all.", resolver=_fake_resolver(None)) is None


# ── live network smoke over the citation_map fixture (opt-in) ───────────────────
_FIXTURE = Path("experiments/edge_quality/out/citation_map.json")
_PAPERS = Path("data/prior-core-v0.2/papers_core.jsonl")


@pytest.mark.skipif(not os.environ.get("PRIOR_RESOLVE_NETWORK_TEST"),
                    reason="network test; set PRIOR_RESOLVE_NETWORK_TEST=1 to run")
def test_network_resolves_fixture_sample():
    papers = [SimpleNamespace(id=d["id"], doi=d.get("doi"), title=d.get("title") or "",
                              arxiv_id=d.get("arxiv_id", ""))
              for d in (json.loads(l) for l in _PAPERS.read_text(encoding="utf-8").splitlines() if l.strip())]
    idx = R.CorpusIndex.from_papers(papers)
    records = json.loads(_FIXTURE.read_text(encoding="utf-8"))[:10]
    correct = sum(1 for rec in records
                  if (rref := R.resolve_reference(rec["bibtex"])) is not None
                  and R.map_to_corpus(rref, idx) == rec["cited_id"])
    assert correct >= 7          # keyless floor cleared 8/10 in dev; guard against regressions
