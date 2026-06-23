"""Ingestion helper tests — pure, no network / Neo4j / API key."""
from prior import ingestion


def test_arxiv_id_parsing():
    assert ingestion._arxiv_id("2106.09685") == "2106.09685"
    assert ingestion._arxiv_id("2106.09685v2") == "2106.09685"
    assert ingestion._arxiv_id("https://arxiv.org/abs/2305.14259") == "2305.14259"
    assert ingestion._arxiv_id("arxiv.org/pdf/2010.04003v2") == "2010.04003"
    assert ingestion._arxiv_id("no id here") is None


def test_norm_title_matches_versions():
    # arXiv vs proceedings vs a noisy PDF title should collapse to one key.
    a = ingestion._norm_title("Attention Is All You Need")
    b = ingestion._norm_title("ATTENTION is all you need!")
    c = ingestion._norm_title("Attention   is all  you need")
    assert a == b == c and a
    assert ingestion._norm_title("short") == ""   # too short → no title key


def test_start_registers_job():
    # arxiv with an unparseable value still registers a job that then fails fast.
    jid = ingestion.start("arxiv", value="not-an-id")
    st = ingestion.job_status(jid)
    assert st and st["id"] == jid and st["kind"] == "arxiv"
