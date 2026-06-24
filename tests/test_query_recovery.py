"""explore()'s search channel reformulates queries from results (recovery rounds)
to lift recall — the query-axis complement to the citation snowball. Offline:
network + LLM stubbed; snowball disabled (hops=0)."""
import prior.completeness as _comp
from prior import scoper
from prior.models import Paper


def _p(pid):
    return Paper(id=pid, source="t", title=f"title {pid}", abstract="x", url="")


def _stub_common(monkeypatch):
    monkeypatch.setattr(_comp, "capture_recapture", lambda *a, **k: {"estimate": None})
    monkeypatch.setattr(scoper, "scope",
                        lambda t, c, **k: ([(p, "in") for p in c], []))   # keep everything


def test_recovery_reformulates_and_accumulates(monkeypatch):
    _stub_common(monkeypatch)
    n = {"gather": 0, "followup": 0}
    monkeypatch.setattr(scoper, "propose_queries", lambda *a, **k: ["q0"])

    def fake_gather(queries, **k):
        i = n["gather"]; n["gather"] += 1
        return [_p(f"r{i}-a"), _p(f"r{i}-b")]          # 2 fresh papers per round

    def fake_followup(topic, kept, dropped=None, **k):
        n["followup"] += 1
        return [f"followup-{n['followup']}"]           # a fresh query each round

    monkeypatch.setattr(scoper, "gather_candidates", fake_gather)
    monkeypatch.setattr(scoper, "followup_queries", fake_followup)

    corpus, dropped, stats = scoper.explore(
        "topic", hops=0, recover_rounds=2, use_prefilter=False,
        repair_abstracts=False, progress=lambda m: None)

    assert n["gather"] == 3            # round 0 + 2 recovery rounds
    assert n["followup"] == 2          # reformulated between the 3 rounds
    assert len(corpus) == 6 and stats["n"] == 6        # accumulated across rounds


def test_recovery_dedups_queries_and_stops(monkeypatch):
    _stub_common(monkeypatch)
    monkeypatch.setattr(scoper, "propose_queries", lambda *a, **k: ["dup"])
    monkeypatch.setattr(scoper, "followup_queries", lambda *a, **k: ["dup"])  # already asked
    g = {"n": 0}

    def fake_gather(queries, **k):
        g["n"] += 1
        return [_p("same")]                            # same paper every round

    monkeypatch.setattr(scoper, "gather_candidates", fake_gather)
    corpus, _, _ = scoper.explore("topic", hops=0, recover_rounds=3, use_prefilter=False,
                                  repair_abstracts=False, progress=lambda m: None)
    assert g["n"] == 1                 # follow-up query was a dup -> no new round
    assert len(corpus) == 1            # paper deduped by key
