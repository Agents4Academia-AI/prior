"""Completeness estimators — pure math, so we can pin the behaviour exactly."""

from prior import completeness as c


def test_capture_recapture_basic():
    # search found 100, snowball found 80, 40 in both → N̂ ≈ 100*80/40 = 200
    r = c.capture_recapture(100, 80, 40)
    assert r["observed"] == 140
    assert 190 <= r["estimate_total"] <= 210
    assert 0.65 <= r["recall"] <= 0.75
    assert r["missing_estimate"] > 0


def test_capture_recapture_high_overlap_means_high_recall():
    # almost everything seen by both → we've likely found nearly all of it
    r = c.capture_recapture(100, 95, 92)
    assert r["recall"] > 0.9


def test_capture_recapture_no_overlap_is_undefined():
    r = c.capture_recapture(50, 50, 0)
    assert r["estimate_total"] is None
    assert "note" in r


def test_buscar_pvalue_is_a_probability():
    for args in [(0, 0, 1000), (5, 20, 1000), (190, 300, 1000), (50, 1000, 1000)]:
        assert 0.0 <= c.buscar_pvalue(*args) <= 1.0


def test_buscar_stops_when_relevant_concentrated_early():
    # 190 relevant in the first 300 of 1000 → strong evidence the tail is thin
    assert c.recall_reached(190, 300, 1000, recall_target=0.95, alpha=0.05)


def test_buscar_earlier_concentration_lowers_pvalue():
    # same relevant count, found earlier ⇒ more confident to stop ⇒ smaller p
    early = c.buscar_pvalue(50, 60, 1000, 0.95)
    spread = c.buscar_pvalue(50, 600, 1000, 0.95)
    assert early < spread
