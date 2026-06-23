"""Live end-to-end renders over the curated sample papers (prior.sample_papers).

Skipped automatically when the network (or `requests`) is unavailable, so the
offline unit suite stays green. Run explicitly with:

    PYTHONPATH=src python3 -m pytest tests/test_fullpaper_integration.py -q

Covers both extraction routes:
  * arXiv HTML — LaTeX math + figures (incl. the 2302.10130v3 <base href> case,
    a regression guard for relative figure-URL resolution)
  * PDF        — papers with no HTML render (e.g. Adam), via pymupdf4llm
"""

import pytest

requests = pytest.importorskip("requests")

from prior import fullpaper                          # noqa: E402
from prior.models import Paper                        # noqa: E402
from prior.sample_papers import SAMPLE_PAPERS         # noqa: E402

_HTML = [s for s in SAMPLE_PAPERS if s.route == "arxiv_html"]
_PDF = [s for s in SAMPLE_PAPERS if s.route == "pdf"]


def _online() -> bool:
    try:
        requests.head("https://arxiv.org/", timeout=8, allow_redirects=True)
        return True
    except requests.RequestException:
        return False


def _render(sp):
    paper = Paper(id=sp.id, source="arxiv", title=sp.title, abstract="", url="")
    opts = fullpaper.FullPaperOptions(embed_images=False)   # link mode → assets staged
    result = fullpaper.render(paper, opts, use_cache=False, write=False)
    if result.channel == "none":
        pytest.skip(f"{sp.id} not retrievable right now (transient)")
    return paper, result


@pytest.mark.skipif(not _online(), reason="network unavailable")
@pytest.mark.parametrize("sp", _HTML, ids=[s.id for s in _HTML])
def test_arxiv_html_render(sp):
    paper, r = _render(sp)
    assert r.channel == "arxiv_html"
    assert r.markdown and len(r.markdown) > 5000
    assert r.n_math > 0                              # arXiv HTML recovers LaTeX
    assert r.n_images > 0                            # figures come through
    assert r.assets, "link mode should stage figure bytes"
    assert all(v[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"GIF8")
               or v[:5] == b"<?xml" or v[:4] == b"<svg" for v in r.assets.values())
    assert f"{paper.id.replace(':', '_')}_assets/" in r.markdown


@pytest.mark.skipif(not _online(), reason="network unavailable")
@pytest.mark.parametrize("sp", _PDF, ids=[s.id for s in _PDF])
def test_pdf_path_render(sp):
    _, r = _render(sp)
    assert r.channel == "pdf"                        # no HTML render → PDF route
    assert r.markdown and len(r.markdown) > 2000
    assert r.n_images > 0                            # figures captured from the PDF
