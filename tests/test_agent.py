"""Agent tests — graph + LLM mocked, so they run with no Neo4j and no API key."""
from prior import agent


def _patch(monkeypatch, *, ann_hits, structured_out):
    monkeypatch.setattr(agent.embeddings, "embed_one", lambda t: [0.0] * 8)
    monkeypatch.setattr(agent.graph, "ann", lambda v, label="Contribution", k=10: ann_hits)
    monkeypatch.setattr(agent.graph, "neighbours", lambda nid, rels=None: [])
    monkeypatch.setattr(agent.graph, "aggregate_relations", lambda ids: {"MENTIONS": 2})
    monkeypatch.setattr(agent.llm, "structured", lambda **kw: structured_out)


def test_ask_grounded(monkeypatch):
    _patch(monkeypatch,
           ann_hits=[{"id": "p::c00", "claim_type": "empirical", "text": "X improves Y"}],
           structured_out={"verdict": "established", "answer": "Yes.",
                           "supporting": ["p::c00"], "contradicting": [], "open_questions": []})
    a = agent.ask("does X improve Y?")
    assert a.verdict == "established"
    assert a.used and a.used[0]["id"] == "p::c00"


def test_ask_empty_graph_is_graceful(monkeypatch):
    monkeypatch.setattr(agent.embeddings, "embed_one", lambda t: [0.0] * 8)
    monkeypatch.setattr(agent.graph, "ann", lambda *a, **k: [])
    # llm.structured must NOT be called when there is no evidence
    monkeypatch.setattr(agent.llm, "structured",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("should not call LLM")))
    a = agent.ask("anything")
    assert a.verdict == "not_found"
    assert a.closest


def test_has_been_solved(monkeypatch):
    _patch(monkeypatch,
           ann_hits=[{"id": "p::k0", "paper_id": "p", "problem": "forgetting",
                      "method": "EWC", "result": "less forgetting", "_score": 0.9}],
           structured_out={"verdict": "partially_solved", "summary": "EWC helps.",
                           "addressed_by": ["p::k0"], "supporting": ["p::k0"],
                           "contradicting": [], "closest": "EWC", "gap": "scaling"})
    s = agent.has_been_solved("is catastrophic forgetting solved?")
    assert s.verdict == "partially_solved"
    assert s.addressed_by == ["p::k0"]
    assert s.consensus == {"MENTIONS": 2}
    assert s.candidates and s.candidates[0]["id"] == "p::k0"


def test_solved_empty_graph(monkeypatch):
    monkeypatch.setattr(agent.embeddings, "embed_one", lambda t: [0.0] * 8)
    monkeypatch.setattr(agent.graph, "ann", lambda *a, **k: [])
    s = agent.has_been_solved("anything")
    assert s.verdict == "not_addressed"
