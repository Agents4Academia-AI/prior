"""scope() must not silently drop a paper the batch LLM omits — it re-asks the
omitted indices, then keeps anything still undecided (recall-safe). Offline: the
LLM call is stubbed.
"""

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
