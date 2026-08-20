"""scope() must not silently drop a paper the batch LLM omits — it re-asks the
omitted indices, then keeps anything still undecided (recall-safe). Offline: the
LLM call is stubbed.
"""

import pytest

from prior import scoper
from prior.models import Paper


def _p(pid, title):
    return Paper(id=pid, source="t", title=title, abstract="x", url="")


CANDS = [_p("a", "alpha"), _p("b", "beta"), _p("c", "gamma")]
TOPIC = "anything"


def _ids(pairs):
    return {p.id for p, _ in pairs}


def test_omitted_index_is_reasked_not_dropped(monkeypatch):
    calls = []

    def fake_structured(**kw):
        calls.append(kw)
        if len(calls) == 1:                         # first batch omits index 1 (paper b)
            return {"decisions": [{"index": 0, "in_scope": True, "reason": "ok"},
                                  {"index": 2, "in_scope": False, "reason": "off"}]}
        return {"decisions": [{"index": 0, "in_scope": True, "reason": "reasked-in"}]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    kept, dropped = scope_ = scoper.scope(TOPIC, CANDS, progress=lambda m: None)

    assert len(calls) == 2                           # it re-asked the omitted one
    assert _ids(kept) == {"a", "b"} and _ids(dropped) == {"c"}
    assert dict((p.id, r) for p, r in kept)["b"] == "reasked-in"   # got the real decision


def test_still_undecided_is_kept_recall_safe(monkeypatch):
    def fake_structured(**kw):
        # never decides on index 1 — even on re-ask
        return {"decisions": [{"index": 0, "in_scope": True, "reason": "ok"}]
                if "alpha" in kw["user"] else []}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    kept, dropped = scoper.scope(TOPIC, CANDS, progress=lambda m: None)

    kd = {p.id: r for p, r in kept}
    assert "b" in kd and kd["b"] == "undecided — kept for review"   # kept, not dropped
    assert all(p.id != "b" for p, _ in dropped)


def test_contradictory_accept_is_reasked(monkeypatch):
    calls = 0

    def fake_structured(**_kw):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"decisions": [{"index": 0, "in_scope": True,
                                    "reason": "This is a review article and out of scope."}]}
        return {"decisions": [{"index": 0, "in_scope": False,
                                "reason": "A review article, excluded by the primary-source rule."}]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    kept, dropped = scoper.scope(TOPIC, [CANDS[0]], progress=lambda _m: None)
    assert calls == 2
    assert not kept and _ids(dropped) == {"a"}


def test_persistent_contradiction_fails_without_caching(monkeypatch, tmp_path):
    def fake_structured(**_kw):
        return {"decisions": [{"index": 0, "in_scope": True,
                                "reason": "This paper is out of scope."}]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    cache = tmp_path / "scope.jsonl"
    with pytest.raises(RuntimeError, match="internally contradictory"):
        scoper.scope(TOPIC, [CANDS[0]], cache_path=cache, progress=lambda _m: None)
    assert not cache.read_text()
