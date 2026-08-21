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


def test_scope_uses_full_available_abstract(monkeypatch):
    marker = "THIS SURVEY SELF-IDENTIFICATION MUST BE VISIBLE"
    candidate = Paper(id="long", source="t", title="ambiguous",
                      abstract="x" * 500 + marker, url="")
    seen = []

    def fake_structured(**kw):
        seen.append(kw["user"])
        return {"decisions": [{"index": 0, "in_scope": False,
                                "reason": "This is a survey article."}]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    kept, dropped = scoper.scope(TOPIC, [candidate], progress=lambda _m: None)
    assert marker in seen[0]
    assert not kept and _ids(dropped) == {"long"}


def test_exhaustive_scope_reasks_nonprimary_eligible(monkeypatch):
    calls = 0

    def fake_structured(**_kw):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"decisions": [{
                "index": 0, "role": "eligible", "criterion": "primary only",
                "evidence": "alpha", "reason": "a review article",
                "publication_role": "secondary_review_or_survey",
                "has_original_contribution": False,
            }]}
        return {"decisions": [{
            "index": 0, "role": "retrieval_only", "criterion": "secondary source",
            "evidence": "alpha", "reason": "useful review article",
            "publication_role": "secondary_review_or_survey",
            "has_original_contribution": False,
        }]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    roles = scoper.scope_exhaustive(TOPIC, [CANDS[0]], progress=lambda _m: None)
    assert calls == 2
    assert [p.id for p, _ in roles["retrieval_only"]] == ["a"]
    assert not roles["eligible"]


def test_exhaustive_scope_does_not_cache_transport_failure(monkeypatch, tmp_path):
    def fail(**_kw):
        raise RuntimeError("temporary API failure")

    monkeypatch.setattr(scoper.llm, "structured", fail)
    cache = tmp_path / "scope.jsonl"
    roles = scoper.scope_exhaustive(
        TOPIC, [CANDS[0]], cache_path=cache, progress=lambda _m: None)
    assert sum(map(len, roles.values())) == 0
    assert cache.read_text() == ""


def test_exhaustive_evidence_validation_normalises_only_whitespace():
    paper = Paper(id="quote", source="t", title="Quoted result",
                  abstract="The system evaluates scientific hypotheses\nwith expert rubrics.",
                  url="")
    decision = {
        "role": "eligible", "criterion": "primary evaluation",
        "evidence": "system evaluates scientific hypotheses with expert rubrics",
        "reason": "direct evaluation",
        "publication_role": "primary_empirical_evaluation",
        "has_original_contribution": True,
    }
    assert scoper._exhaustive_decision_issues(paper, decision) == []
    decision["evidence"] = "system assesses scientific hypotheses with expert rubrics"
    assert "evidence_not_verbatim" in scoper._exhaustive_decision_issues(paper, decision)


def test_exhaustive_reask_receives_validation_feedback(monkeypatch):
    users = []

    def fake_structured(**kw):
        users.append(kw["user"])
        evidence = "" if len(users) == 1 else "alpha"
        return {"decisions": [{
            "index": 0, "role": "eligible", "criterion": "primary system",
            "evidence": evidence, "reason": "directly in scope",
            "publication_role": "primary_system_or_method",
            "has_original_contribution": True,
        }]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    roles = scoper.scope_exhaustive(TOPIC, [CANDS[0]], progress=lambda _m: None)
    assert [paper.id for paper, _ in roles["eligible"]] == ["a"]
    assert "CORRECTION REQUIRED" in users[1]
    assert "evidence_not_verbatim" in users[1]


def test_exhaustive_span_choice_is_copied_by_pipeline(monkeypatch):
    paper = Paper(id="span", source="t", title="A title",
                  abstract="First supporting sentence. Second sentence.", url="")

    def fake_structured(**_kw):
        return {"decisions": [{
            "index": 0, "role": "eligible", "criterion": "primary system",
            "evidence_span_index": 1, "reason": "directly in scope",
            "publication_role": "primary_system_or_method",
            "has_original_contribution": True,
        }]}

    monkeypatch.setattr(scoper.llm, "structured", fake_structured)
    roles = scoper.scope_exhaustive(TOPIC, [paper], progress=lambda _m: None)
    decision = roles["eligible"][0][1]
    assert decision["evidence"] == "First supporting sentence."
    assert decision["evidence_span_index"] == 1
