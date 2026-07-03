"""fullpaper: HTML→Markdown conversion (LaTeX math + figures), offline.

The network paths (arXiv HTML / PDF fetch) aren't exercised here; we drive the
converter directly on a synthetic ar5iv-style fragment and assert the instrumented
behaviour — math on/off, images on/off, embed vs. link.
"""

import requests

from prior import fullpaper
from prior.fullpaper import FullPaperOptions, FullPaperResult, _HTMLToMarkdown


# a compact stand-in for an arXiv/ar5iv render: heading, inline + display math,
# a figure, a list and a table.
HTML = """
<article>
  <h2 class="ltx_title">Method</h2>
  <p>The loss is <math alttext="\\mathcal{L} = \\sum_i x_i">MATHML JUNK</math> over examples.</p>
  <p>We optimise:</p>
  <math display="block" alttext="\\nabla_\\theta J(\\theta) = 0"><mrow>junk</mrow></math>
  <figure>
    <img src="x1.png" alt="Training curve">
    <figcaption>Figure 1: loss over epochs.</figcaption>
  </figure>
  <ul><li>first</li><li>second</li></ul>
  <table>
    <tr><th>a</th><th>b</th></tr>
    <tr><td>1</td><td>2</td></tr>
  </table>
  <script>var ignore = 1;</script>
</article>
"""

# 1x1 transparent PNG
_PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
        b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


def _convert(html, opts):
    """Run the converter with image downloads stubbed to a fixed PNG."""
    result = FullPaperResult(None, "x")
    orig = fullpaper._download_image
    fullpaper._download_image = lambda url, session: (_PNG, "image/png")
    try:
        p = _HTMLToMarkdown("https://arxiv.org/html/2401.00001v1/", opts, result,
                            "arxiv_2401.00001", requests.Session())
        p.feed(html)
        return fullpaper._clean_markdown(p.markdown()), result
    finally:
        fullpaper._download_image = orig


def test_math_as_latex_inline_and_display():
    md, result = _convert(HTML, FullPaperOptions(embed_images=True))
    assert "$\\mathcal{L} = \\sum_i x_i$" in md            # inline
    assert "$$\n\\nabla_\\theta J(\\theta) = 0\n$$" in md   # display
    assert "MATHML JUNK" not in md and "junk" not in md     # inner MathML dropped
    assert result.n_math == 2


def test_no_math_drops_equations():
    md, result = _convert(HTML, FullPaperOptions(include_math=False))
    assert "mathcal" not in md and "nabla" not in md
    assert result.n_math == 0


def test_images_embedded_as_data_uri():
    md, result = _convert(HTML, FullPaperOptions(embed_images=True))
    assert "![Training curve](data:image/png;base64," in md
    assert result.n_images == 1 and not result.assets


def test_images_linked_to_assets_dir():
    md, result = _convert(HTML, FullPaperOptions(embed_images=False))
    assert "![Training curve](arxiv_2401.00001_assets/fig001.png)" in md
    assert result.assets == {"fig001.png": _PNG}


def test_no_images_drops_figures():
    md, result = _convert(HTML, FullPaperOptions(include_images=False))
    assert "data:image" not in md and "_assets/" not in md
    assert result.n_images == 0


def test_structure_headings_list_table():
    md, _ = _convert(HTML, FullPaperOptions())
    assert "## Method" in md
    assert "- first" in md and "- second" in md
    assert "| a | b |" in md and "| 1 | 2 |" in md


# arXiv wraps numbered display equations in <table class="...ltx_eqn_table">, with
# the number in a ltx_eqn_eqno cell. These must become clean $$…$$ blocks, not tables.
EQN_HTML = """
<article>
  <p>Attention is defined as</p>
  <table class="ltx_equation ltx_eqn_table"><tbody>
    <tr class="ltx_eqn_row">
      <td class="ltx_eqn_cell ltx_eqn_center_padleft"></td>
      <td class="ltx_eqn_cell ltx_align_center"><math display="block" alttext="E = mc^2">junk mathml</math></td>
      <td class="ltx_eqn_cell ltx_eqn_center_padright"></td>
      <td class="ltx_eqn_cell ltx_eqn_eqno ltx_align_right"><span class="ltx_tag">(1)</span></td>
    </tr></tbody></table>
  <table><tr><th>a</th><th>b</th></tr><tr><td>1</td><td>2</td></tr></table>
</article>
"""


def test_equation_table_becomes_clean_block_with_tag():
    md, result = _convert(EQN_HTML, FullPaperOptions())
    assert "$$\nE = mc^2 \\tag{1}\n$$" in md          # clean display block + number
    assert "junk" not in md                            # MathML subtree dropped
    assert result.n_math == 1
    # no table scaffolding around the equation ...
    assert "| | " not in md and "$$ |" not in md
    # ... but a genuine table still renders as a table
    assert "| a | b |" in md and "| 1 | 2 |" in md


def test_equation_table_dropped_when_math_off():
    md, result = _convert(EQN_HTML, FullPaperOptions(include_math=False))
    assert "$$" not in md and "E = mc" not in md
    assert "(1)" not in md                             # eqno scaffolding gone too
    assert result.n_math == 0
    assert "| a | b |" in md                           # real table unaffected
