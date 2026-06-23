"""Live end-to-end render of a real arXiv paper that has figures.

Skipped automatically when the network (or `requests`) is unavailable, so the
offline unit suite stays green. Run explicitly with:

    PYTHONPATH=src python3 -m pytest tests/test_fullpaper_integration.py -q

Doubles as a regression test for arXiv-HTML figure-URL resolution (this paper
declares a `<base href="/html/2302.10130v3/">`, which the resolver must honour).
"""

import pytest

requests = pytest.importorskip("requests")

from prior import fullpaper                      # noqa: E402
from prior.models import Paper                    # noqa: E402

# 2302.10130 — "Stochastic Interpolants" (diffusion/flow generative modelling):
# rich arXiv HTML render with ~28 figures and plenty of display math.
ARXIV_ID = "2302.10130v3"


def _online() -> bool:
    try:
        requests.head("https://arxiv.org/", timeout=8, allow_redirects=True)
        return True
    except requests.RequestException:
        return False


@pytest.mark.skipif(not _online(), reason="network unavailable")
def test_render_arxiv_paper_with_figures(tmp_path):
    paper = Paper(id=f"arxiv:{ARXIV_ID}", source="arxiv", title="Stochastic Interpolants",
                  abstract="", url="")
    opts = fullpaper.FullPaperOptions(embed_images=False)   # link mode → assets staged
    result = fullpaper.render(paper, opts, use_cache=False, write=False)

    if result.channel == "none":
        pytest.skip("paper not retrievable right now (transient)")

    assert result.channel in ("arxiv_html", "pdf")
    assert result.markdown and len(result.markdown) > 5000
    # the point of this paper: figures come through, and base-href resolution works
    assert result.n_images > 0
    assert result.assets, "link mode should stage figure bytes"
    assert all(v[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0", b"GIF8")  # png / jpeg / gif
               or v[:5] == b"<?xml" or v[:4] == b"<svg" for v in result.assets.values())
    assert f"{paper.id.replace(':', '_')}_assets/" in result.markdown

    if result.channel == "arxiv_html":
        assert result.n_math > 0                  # arXiv HTML recovers LaTeX
