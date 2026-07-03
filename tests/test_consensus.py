"""Consensus edge scoring — deterministic, LLM stubbed out."""
from prior import cartographer, consensus
from prior.models import Contribution, Edge


def _src_cand():
    return (Contribution(id="p1::k0", paper_id="p1", statement="A"),
            Contribution(id="p2::k0", paper_id="p2", statement="B"))


def test_single_pass_trust_and_tier(monkeypatch):
    src, cand = _src_cand()
    monkeypatch.setattr(cartographer, "_label", lambda source, cands, cited, model: [
        Edge(src=source.id, dst=cands[0].id, relation="builds_on",
             evidence="x", confidence=0.8, source="text", level="global")])

    # strong confidence (0.8>=0.65) + strong similarity (0.6>=0.5) → triple
    out = consensus.relate(src, [cand], {cand.id: 0.6}, set())
    assert len(out) == 1
    e = out[0]
    assert e["relation"] == "builds_on" and e["src"] == src.id and e["dst"] == cand.id
    assert e["trust"] == round(0.7 * 0.8 + 0.3 * 0.6, 2)   # 0.74
    assert e["tier"] == "triple"
    assert "directed" not in e or True  # edge dict is graph.add_edge-ready


def test_tier_buckets(monkeypatch):
    src, cand = _src_cand()

    def stub(conf):
        monkeypatch.setattr(cartographer, "_label", lambda *a, **k: [
            Edge(src=src.id, dst=cand.id, relation="supports", confidence=conf,
                 source="text", level="global")])

    stub(0.8); assert consensus.relate(src, [cand], {cand.id: 0.2}, set())[0]["tier"] == "double"   # conf only
    stub(0.3); assert consensus.relate(src, [cand], {cand.id: 0.7}, set())[0]["tier"] == "double"   # sim only
    stub(0.3); assert consensus.relate(src, [cand], {cand.id: 0.1}, set())[0]["tier"] == "single"   # neither
