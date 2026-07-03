"""Abstract repair — the fix for corrupted source abstracts dropping good papers.

Offline: the arXiv / S2 lookups are stubbed; we assert id derivation, the
title↔abstract suspicion check, and that backfill overwrites a corrupted abstract.
"""

from prior import repair
from prior.models import Paper


def _p(**kw):
    base = dict(id="openalex:W1", source="openalex", title="", abstract="", url="")
    base.update(kw)
    return Paper(**base)


# ── arXiv id derivation ──────────────────────────────────────────────────────────

def test_arxiv_id_from_arxiv_doi():
    p = _p(doi="https://doi.org/10.48550/arXiv.2006.11239")
    assert repair.arxiv_id_of(p) == "2006.11239"


def test_arxiv_id_from_arxiv_source_id():
    assert repair.arxiv_id_of(_p(id="arxiv:2006.11239v2", source="arxiv")) == "2006.11239"


def test_arxiv_id_none_for_journal_doi():
    assert repair.arxiv_id_of(_p(doi="https://doi.org/10.1145/3292500")) is None
    assert repair.arxiv_id_of(_p()) is None


# ── title↔abstract suspicion ─────────────────────────────────────────────────────

def test_suspect_when_abstract_contradicts_title():
    assert repair.abstract_suspect(
        "Graph attention transformers for protein folding prediction",
        "A historical survey of Baroque music composers in 18th-century Vienna.")


def test_not_suspect_when_consistent():
    assert not repair.abstract_suspect(
        "Graph attention transformers for protein folding prediction",
        "We propose graph attention transformers that predict protein folding from sequence.")


def test_not_suspect_when_empty_or_short_title():
    assert not repair.abstract_suspect("Denoising diffusion", "")        # empty abstract
    assert not repair.abstract_suspect("Deep learning", "Unrelated text about cooking.")  # <4 salient


# ── backfill ─────────────────────────────────────────────────────────────────────

def test_backfill_overwrites_corrupted_abstract_from_arxiv(monkeypatch):
    # the real DDPM case: arXiv-DOI OpenAlex record with a wrong (methylation) abstract
    ddpm = _p(id="openalex:W3036167779", title="Denoising Diffusion Probabilistic Models",
              doi="https://doi.org/10.48550/arxiv.2006.11239", cited_by_count=5640,
              abstract="DiffuCpG. We address missing DNA methylation with a diffusion model "
                       "trained on whole-genome bisulfite sequencing of leukemia samples.")
    good = "We present high quality image synthesis results using diffusion probabilistic models."
    # arXiv returns the VERSIONED key, which backfill must map back to the base id
    monkeypatch.setattr(repair.arxiv, "fetch_ids",
                        lambda ids, **k: {"arxiv:2006.11239v2": _p(id="arxiv:2006.11239v2",
                                                                   source="arxiv", abstract=good)})
    monkeypatch.setattr(repair.semanticscholar, "fetch", lambda sid: None)

    stats = repair.backfill_abstracts([ddpm], progress=lambda m: None)
    assert ddpm.abstract == good
    assert stats["arxiv"] == 1 and stats["s2"] == 0


def test_backfill_s2_fallback_for_suspect_journal_paper(monkeypatch):
    bad = _p(id="openalex:W2", title="Attention mechanisms for machine translation systems",
             doi="https://doi.org/10.1145/3292500",
             abstract="Recipes for sourdough bread and the chemistry of fermentation.")
    fixed = _p(abstract="We study attention mechanisms that improve machine translation quality.")
    monkeypatch.setattr(repair.arxiv, "fetch_ids", lambda ids, **k: {})
    monkeypatch.setattr(repair.semanticscholar, "fetch", lambda sid: fixed)

    stats = repair.backfill_abstracts([bad], progress=lambda m: None)
    assert "machine translation" in bad.abstract
    assert stats["s2"] == 1


def test_backfill_leaves_healthy_papers_untouched(monkeypatch):
    ok = _p(id="openalex:W3", title="Attention mechanisms for machine translation",
            doi="https://doi.org/10.1145/3292500",
            abstract="We study attention mechanisms for machine translation.")
    before = ok.abstract
    monkeypatch.setattr(repair.arxiv, "fetch_ids", lambda ids, **k: {})
    called = []
    monkeypatch.setattr(repair.semanticscholar, "fetch", lambda sid: called.append(sid))
    stats = repair.backfill_abstracts([ok], progress=lambda m: None)
    assert ok.abstract == before and not called and stats == {"arxiv": 0, "s2": 0, "suspect_unrepaired": 0}
