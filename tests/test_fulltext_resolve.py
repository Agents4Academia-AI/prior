"""fulltext._meta_pdf — landing-page citation_pdf_url resolution (offline).

Regression cover for the relative-URL bug: a citation_pdf_url that is relative or
scheme-relative must be resolved (against <base href>, else the final landing URL)
before fetching, exactly as a browser would. We stub the network so the test is
deterministic and asserts the URL handed to the PDF fetcher.
"""

from prior import fulltext


class _FakeResp:
    status_code = 200

    def __init__(self, text, url):
        self.text, self.url = text, url


def _run(monkeypatch, html, landing_url):
    """Drive _meta_pdf with a stubbed landing page; capture the URL _oa_pdf sees."""
    captured = {}
    monkeypatch.setattr(fulltext.requests, "get",
                        lambda *a, **k: _FakeResp(html, landing_url))

    def _fake_oa_pdf(url):
        captured["url"] = url
        return "BODY"

    monkeypatch.setattr(fulltext, "_oa_pdf", _fake_oa_pdf)
    out = fulltext._meta_pdf("10.1234/abc")
    return out, captured.get("url")


LANDING = "https://repo.example.org/articles/123"


def _meta(content):
    return f'<html><head><meta name="citation_pdf_url" content="{content}"></head></html>'


def test_absolute_url_unchanged(monkeypatch):
    out, url = _run(monkeypatch, _meta("https://cdn.example.org/x.pdf"), LANDING)
    assert out == "BODY"
    assert url == "https://cdn.example.org/x.pdf"


def test_root_relative_resolved_against_landing(monkeypatch):
    out, url = _run(monkeypatch, _meta("/files/x.pdf"), LANDING)
    assert url == "https://repo.example.org/files/x.pdf"


def test_path_relative_resolved_against_landing(monkeypatch):
    out, url = _run(monkeypatch, _meta("download/x.pdf"), LANDING)
    assert url == "https://repo.example.org/articles/download/x.pdf"


def test_scheme_relative_inherits_scheme(monkeypatch):
    out, url = _run(monkeypatch, _meta("//cdn.example.org/x.pdf"), LANDING)
    assert url == "https://cdn.example.org/x.pdf"


def test_base_href_takes_precedence(monkeypatch):
    html = ('<html><head><base href="/data/">'
            '<meta name="citation_pdf_url" content="pdf/x.pdf"></head></html>')
    out, url = _run(monkeypatch, html, LANDING)
    assert url == "https://repo.example.org/data/pdf/x.pdf"
