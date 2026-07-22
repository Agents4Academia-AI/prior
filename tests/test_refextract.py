"""Tests for prior.sources.refextract — paper -> raw reference strings.

Pure/offline: the extractor is deterministic string work (channel selection +
bibliography segmentation), so everything here runs without network or keys.
"""
from __future__ import annotations

from types import SimpleNamespace

from prior.sources import refextract as X
from prior.sources.refresolve import REFERENCE_CHAR_CAP


def _paper(full_text=""):
    return SimpleNamespace(full_text=full_text)


# ── channel 1: caller-mined references passed straight through ─────────────────
def test_mined_refs_used_verbatim_and_trimmed():
    mined = ["  Foo. A paper. 2024.  ", "", "   ", "Bar. Another. 2023."]
    assert X.references_for(_paper("ignored"), mined=mined) == [
        "Foo. A paper. 2024.", "Bar. Another. 2023."]


def test_mined_over_cap_dropped():
    mined = ["Foo. A real ref. 2024.", "x" * (REFERENCE_CHAR_CAP + 1)]
    out = X.references_for(_paper(), mined=mined)
    assert out == ["Foo. A real ref. 2024."]


# ── channel 2: full-text bibliography segmentation (the generalization) ────────
def test_bracketed_markers_segmented():
    text = (
        "Body of the paper discussing things.\n\n"
        "References\n"
        "[1] Alice Smith. A great method. In NeurIPS, 2020.\n"
        "[2] Bob Jones. Another method for things. In ICML, 2021.\n"
        "[3] Carol Lee. Yet more. arXiv:2203.00001, 2022.\n"
    )
    out = X.references_for(_paper(text))
    assert len(out) == 3
    assert out[0].startswith("Alice Smith. A great method")
    assert "arXiv:2203.00001" in out[2]


def test_numbered_markers_segmented_and_linebreaks_collapsed():
    text = (
        "REFERENCES\n"
        "1. Alice Smith. A method that spans\n   two lines. NeurIPS 2020.\n"
        "2. Bob Jones. Second reference. ICML 2021.\n"
    )
    out = X.references_for(_paper(text))
    assert len(out) == 2
    assert out[0] == "Alice Smith. A method that spans two lines. NeurIPS 2020."


def test_unnumbered_blank_line_separated():
    text = (
        "Bibliography\n\n"
        "Alice Smith. A method. NeurIPS 2020.\n\n"
        "Bob Jones. Second reference. ICML 2021.\n"
    )
    out = X.references_for(_paper(text))
    assert len(out) == 2


def test_entries_without_a_year_are_dropped():
    text = (
        "References\n"
        "[1] Page footer with no year, just noise text here.\n"
        "[2] Alice Smith. A real reference. NeurIPS 2020.\n"
    )
    out = X.references_for(_paper(text))
    assert out == ["Alice Smith. A real reference. NeurIPS 2020."]


def test_takes_the_last_references_heading():
    # An appendix can mention "References"; the real list is the final block.
    text = (
        "Related work references prior art.\n"
        "References\n"
        "[1] Real Author. The actual bibliography entry. 2020.\n"
    )
    out = X.references_for(_paper(text))
    assert out == ["Real Author. The actual bibliography entry. 2020."]


def test_no_bibliography_yields_empty():
    assert X.references_for(_paper("A paper with no reference section at all.")) == []
    assert X.references_for(_paper("")) == []


def test_count_capped():
    body = "References\n" + "".join(
        f"[{i}] Author {i}. Title number {i}. Venue 20{i % 100:02d}.\n"
        for i in range(1, X._MAX_REFERENCES + 50))
    out = X.references_for(_paper(body))
    assert len(out) == X._MAX_REFERENCES


# ── mega-records: a whole bibliography captured as one over-cap field ──────────
def _bibtex_blob(n, title="A Study of Topic Number"):
    return "".join(
        f"@article{{key{i}, title={{{title} {i}}}, "
        f"author={{Author {i} and Coauthor {i}}}, journal={{Venue {i}}}, "
        f"year={{20{i % 100:02d}}}}} " for i in range(n))


def test_mega_blob_of_bibtex_entries_is_segmented_not_dropped():
    blob = _bibtex_blob(60)
    assert len(blob) > REFERENCE_CHAR_CAP           # triggers the blob path
    out = X.references_for(_paper(), mined=[blob])
    assert len(out) == 60                           # split into individual references
    assert all(len(o) <= REFERENCE_CHAR_CAP for o in out)
    assert any("A Study of Topic Number 7" in o for o in out)


def test_mega_blob_with_leading_bibitem_section():
    blob = (r"\bibitem{a} Alice Smith. A first reference. arXiv:2401.00001, 2021. "
            r"\bibitem{b} Bob Jones. A second reference. NeurIPS, 2022. "
            r"\end{thebibliography} ") + _bibtex_blob(60, title="Later Paper")
    assert len(blob) > REFERENCE_CHAR_CAP
    out = X.references_for(_paper(), mined=[blob])
    assert any("A first reference" in o for o in out)   # leading \bibitem refs kept
    assert any("Later Paper 5" in o for o in out)       # trailing bibtex entries kept
    assert all(len(o) <= REFERENCE_CHAR_CAP for o in out)


def test_duplicate_mega_blobs_deduped():
    # citation_map repeats the whole-bibliography blob once per cited target, so
    # the same blob can arrive many times — its references must not multiply.
    blob = _bibtex_blob(60, title="Dup Paper")
    assert len(blob) > REFERENCE_CHAR_CAP
    out = X.references_for(_paper(), mined=[blob, blob, blob])
    assert len(out) == 60 and len(out) == len(set(out))


def test_mega_blob_non_bibtex_falls_back_to_markers():
    # A huge bracketed list (no BibTeX) still segments via the generic scheme,
    # rather than surviving as one over-cap entry that then gets dropped.
    blob = "".join(f"[{i}] Author {i}. A reference title number {i}. Some Venue 20{i % 100:02d}.\n"
                   for i in range(1, 140))
    assert len(blob) > REFERENCE_CHAR_CAP
    out = X.references_for(_paper(), mined=[blob])
    assert len(out) >= 130
    assert all(len(o) <= REFERENCE_CHAR_CAP for o in out)
