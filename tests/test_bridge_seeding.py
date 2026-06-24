"""explore()'s first snowball hop must seed from the whole search/recovery set, not
just high_yield_seeds — so cross-cluster BRIDGE papers (moderately cited, hence not
in the top-cited seed set) get their citation neighborhoods expanded. Offline."""
import prior.completeness as _comp
from prior import scoper
from prior.models import Paper


def test_first_hop_seeds_include_low_cited_bridge(monkeypatch):
    monkeypatch.setattr(_comp, "capture_recapture", lambda *a, **k: {})
    # search channel: 60 highly-cited old papers (fill the top-cited seed slots) + one
    # low-cited, non-recent BRIDGE that high_yield_seeds would exclude.
    hubs = [Paper(id=f"h{i}", source="t", title=f"h{i}", abstract="x", url="",
                  cited_by_count=1000 + i, year=2020) for i in range(60)]
    bridge = Paper(id="BRIDGE", source="t", title="bridge", abstract="x", url="",
                   cited_by_count=5, year=2019)

    monkeypatch.setattr(scoper, "propose_queries", lambda *a, **k: ["q"])
    monkeypatch.setattr(scoper, "gather_candidates", lambda *a, **k: hubs + [bridge])
    monkeypatch.setattr(scoper, "scope", lambda t, c, **k: ([(p, "in") for p in c], []))
    monkeypatch.setattr(scoper, "snowball_s2", lambda *a, **k: ([], set()))

    seen = {}

    def fake_snowball(seeds, **k):
        seen.setdefault("hop1", {s.id for s in seeds})
        return ([], set())

    monkeypatch.setattr(scoper, "snowball", fake_snowball)

    # sanity: high_yield_seeds alone would NOT include the bridge
    assert "BRIDGE" not in {s.id for s in scoper.high_yield_seeds(hubs + [bridge])}

    scoper.explore("topic", hops=1, recover_rounds=0, use_prefilter=False,
                   repair_abstracts=False, progress=lambda m: None)
    assert "BRIDGE" in seen["hop1"]      # but the first snowball hop DOES seed from it
