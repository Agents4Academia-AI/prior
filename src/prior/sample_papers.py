"""Curated sample papers for exercising the extraction methods.

Used by the integration tests and by scripts/compare_methods.py. Each entry's
`route` is the fullpaper channel it should resolve through, chosen so the set
spans both extraction paths:

  arxiv_html — arXiv HTML render: recovers LaTeX math + tagged figures
  pdf        — no HTML render exists, so it forces the PDF path (pymupdf4llm /
               fitz): figures come through, but a PDF carries no LaTeX
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SamplePaper:
    id: str            # canonical id, e.g. "arxiv:1706.03762"
    title: str
    route: str         # expected fullpaper channel: "arxiv_html" | "pdf"
    note: str          # what this paper is good for exercising


SAMPLE_PAPERS: list[SamplePaper] = [
    SamplePaper("arxiv:1706.03762", "Attention Is All You Need", "arxiv_html",
                "classic; heavy math (~140 eq) + 8 figures"),
    SamplePaper("arxiv:2010.11929", "ViT: An Image Is Worth 16x16 Words", "arxiv_html",
                "math (~170 eq) + many figures (~20)"),
    SamplePaper("arxiv:2302.10130", "Stochastic Interpolants", "arxiv_html",
                "declares <base href>; ~1500 eq, ~27 figures (figure-URL regression)"),
    SamplePaper("arxiv:1412.6980", "Adam: A Method for Stochastic Optimization", "pdf",
                "no HTML render → exercises the PDF path; ~34 images, no recovered LaTeX"),
]
