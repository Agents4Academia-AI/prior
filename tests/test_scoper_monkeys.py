import importlib.util
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    path = ROOT / "evals" / "scoper_monkeys" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = _load("common")
seed_collection = _load("seed_collection")
ledger = _load("ledger")


def test_gold_bib_parser_and_identity(tmp_path):
    bib = tmp_path / "gold.bib"
    bib.write_text(
        "@article{needle,\n"
        " title={A {Nested} Scientific Title},\n"
        " doi={https://doi.org/10.1234/ABC},\n"
        " year={2020}\n"
        "}\n"
    )
    gold = common.load_gold(bib)
    assert len(gold) == 1
    assert gold[0].title == "A Nested Scientific Title"
    assert gold[0].doi == "10.1234/abc"
    assert gold[0].year == 2020
    assert common.match_gold(
        gold[0], {"title": "Different", "doi": "10.1234/ABC", "id": "x"}
    ) == 1.0


def test_stage_recall_and_miss_diagnosis(tmp_path, monkeypatch):
    # score.py imports common by its script-local name.
    monkeypatch.syspath_prepend(str(ROOT / "evals" / "scoper_monkeys"))
    score = _load("score")
    gold = [
        common.GoldItem("g1", "Alpha treatment works"),
        common.GoldItem("g2", "Beta intervention works"),
        common.GoldItem("g3", "Gamma intervention works"),
    ]
    events = [
        {"event": "manifest", "order": 1, "case": "toy"},
        {"event": "candidate", "order": 2, "stage": "single_query",
         "work_key": "alpha", "paper": {"id": "a", "title": "Alpha treatment works"}},
        {"event": "candidate", "order": 3, "stage": "adaptive_1",
         "work_key": "beta", "paper": {"id": "b", "title": "Beta intervention works"}},
        {"event": "decision", "order": 4, "stage": "multi_query",
         "work_key": "alpha", "decision": "kept", "reason": "",
         "paper": {"id": "a", "title": "Alpha treatment works"}},
        {"event": "decision", "order": 5, "stage": "adaptive_1",
         "work_key": "beta", "decision": "dropped",
         "reason": "pre-filtered: low topic similarity",
         "paper": {"id": "b", "title": "Beta intervention works"}},
        {"event": "snapshot", "order": 6, "stage": "adaptive_1",
         "candidates": 1, "new_kept": 0, "stop_triggered": True,
         "stop_reason": "low_yield"},
    ]
    report = score.analyse(events, gold)
    assert report["cumulative"][-1]["discovery_recall"] == 0.6667
    assert report["cumulative"][-1]["accepted_recall"] == 0.3333
    diagnoses = {row["gold_id"]: row["automatic_diagnosis"] for row in report["gold"]}
    assert diagnoses == {
        "g1": "recovered",
        "g2": "prefilter_rejection",
        "g3": "not_retrieved_query_depth_or_index_gap",
    }
    assert report["stopping"][0]["true_discovery_recall"] == 0.6667


def test_seed_collection_adapter_guards_leakage_and_missing_gold(tmp_path):
    root = tmp_path / "dataset"
    (root / "collection_data").mkdir(parents=True)
    (root / "corpus").mkdir()
    topic = {
        "id": "toy", "link_to_review": "https://example.test/review",
        "title": "Secret review title", "search_name": "Widget training",
        "Date_to": "31/12/2020", "included_studies": ["1", "2"],
        "seed_studies": ["1"], "query": "SECRET BOOLEAN QUERY",
    }
    (root / "collection_data" / "overall_collection.jsonl").write_text(
        json.dumps(topic) + "\n"
    )
    with zipfile.ZipFile(root / "corpus" / "all.jsonl.zip", "w") as archive:
        archive.writestr(
            "all.jsonl",
            json.dumps({"pmid": "1", "title": "A widget trial"}) + "\n",
        )

    out = tmp_path / "case"
    try:
        seed_collection.prepare(root, "toy", out)
        assert False, "missing included records must fail by default"
    except ValueError as error:
        assert "['2']" in str(error)

    manifest = seed_collection.prepare(root, "toy", out, allow_missing=True)
    assert manifest["missing_included_pmids"] == ["2"]
    combined = "\n".join(path.read_text() for path in out.iterdir())
    assert "SECRET BOOLEAN QUERY" not in combined
    assert "Secret review title" not in combined
    assert "Widget training" in (out / "scope.smoke.txt").read_text()

    supplement = tmp_path / "supplement.jsonl"
    supplement.write_text(json.dumps({"pmid": "2", "title": "Another trial"}) + "\n")
    complete = seed_collection.prepare(
        root, "toy", tmp_path / "complete", supplement=supplement
    )
    assert complete["gold_n_exported"] == 2
    assert complete["missing_included_pmids"] == []


def test_versioned_ledger_envelope_and_reformulation_reason(tmp_path):
    run_id = "scoper:test"
    base = {
        "schema_version": ledger.SCHEMA_VERSION, "run_id": run_id,
        "recorded_at": "2026-08-12T12:00:00Z",
    }
    rows = [
        base | {"event_id": f"{run_id}:e000001", "event": "manifest", "order": 1,
                "case": "toy", "scope": "IN: widgets", "scope_sha256": "sha256:x",
                "code_version": "abc123", "parameters": {}},
        base | {"event_id": f"{run_id}:e000002", "event": "query", "order": 2,
                "stage": "adaptive_1", "kind": "reformulation", "queries": ["q2"],
                "motivation": "A method facet was absent from accepted records."},
    ]
    ledger.validate_ledger(rows)
    path = tmp_path / "ledger.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    assert common.load_events(path) == rows

    invalid = dict(rows[1], motivation="")
    try:
        ledger.validate_event(invalid)
        assert False, "a reformulation without an observation must fail"
    except ValueError as error:
        assert "motivation" in str(error)


def test_branch_growth_uses_first_observed_attribution(tmp_path):
    run = _load("run")
    paper_a = run.Paper(id="a", source="test", title="Alpha paper", abstract="", url="")
    paper_b = run.Paper(id="b", source="test", title="Beta paper", abstract="", url="")
    recorder = run.Recorder(tmp_path / "growth.jsonl")
    recorder.emit("manifest", case="toy", scope="widgets", scope_sha256="sha256:x",
                  code_version="abc", parameters={})
    branches = [("q1", "alpha", [paper_a, paper_b]), ("q2", "beta", [paper_b])]
    run._record_branch_growth(
        recorder, stage="multi_query", branches=branches,
        first_branch={paper_a.key(): "q1", paper_b.key(): "q1"}, known_before=set(),
        kept=[(paper_b, "in")], corpus_before=0,
    )
    recorder.close()
    rows = ledger.load_and_validate(tmp_path / "growth.jsonl")
    growth = [row for row in rows if row["event"] == "branch_snapshot"]
    assert [(row["globally_new"], row["newly_included"]) for row in growth] == [(2, 1), (0, 0)]
    assert growth[1]["rediscovered"] == 1


def test_ledger_accepts_explicit_bounded_terminal_states():
    run_id = "scoper:terminal"
    base = {
        "schema_version": ledger.SCHEMA_VERSION, "run_id": run_id,
        "recorded_at": "2026-08-15T12:00:00Z",
    }
    rows = [
        base | {"event_id": f"{run_id}:e000001", "event": "manifest", "order": 1,
                "case": "toy", "scope": "widgets", "scope_sha256": "sha256:x",
                "code_version": "abc", "parameters": {}},
        base | {"event_id": f"{run_id}:e000002", "event": "branch_terminal",
                "order": 2, "branch_id": "q1:openalex", "stage": "multi_query",
                "status": "bounded", "reason": "fixed_depth"},
        base | {"event_id": f"{run_id}:e000003", "event": "run_terminal", "order": 3,
                "status": "bounded", "reason": "baseline_policy", "open_tasks": []},
    ]
    ledger.validate_ledger(rows)


def test_citation_observer_records_exact_seed_direction_and_path(tmp_path):
    run = _load("run")
    seed = run.Paper(id="openalex:S", source="openalex", title="Seed work",
                     abstract="", url="")
    paper = run.Paper(id="openalex:P", source="openalex", title="Recovered work",
                      abstract="", url="")
    recorder = run.Recorder(tmp_path / "citation.jsonl")
    recorder.emit("manifest", case="toy", scope="widgets", scope_sha256="sha256:x",
                  code_version="abc", parameters={})
    recorder.citation_observer("snowball_1")({
        "source": "openalex", "hop": 1, "direction": "backward",
        "seed": seed, "paper": paper, "endpoint": "works/filter:ids.openalex",
    })
    recorder.close()
    rows = ledger.load_and_validate(tmp_path / "citation.jsonl")
    path = next(row for row in rows if row["event"] == "citation_path")
    assert path["seed_work_key"] == seed.key()
    assert path["work_key"] == paper.key()
    assert path["direction"] == "backward"


def test_core_baseline_preserves_policy_inputs_and_blind_gold(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    adapter = _load("core_baseline")
    core = tmp_path / "core.jsonl"
    core.write_text(json.dumps({
        "id": "arxiv:1", "title": "A core work", "year": 2026,
        "doi": "10.1/example",
    }) + "\n")
    out = tmp_path / "replay"
    manifest = adapter.prepare(out, core, propose_extra=False)
    assert manifest["policy"]["per_query"] == 20
    assert manifest["policy"]["cutoff"] is None
    assert (out / "empty-gold-for-blind-run.jsonl").read_text() == ""
    assert "fully automated scientific discovery" in (
        out / "fixed-seed-queries.txt"
    ).read_text()
    assert json.loads((out / "gold-current-core.jsonl").read_text())["year"] == 2026


def test_query_runner_opens_source_circuit_after_exhausted_failure(tmp_path, monkeypatch):
    run = _load("run")
    calls = []

    def fake_gather(_queries, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            kwargs["observe"]({
                "kind": "source_failure", "source": "semanticscholar",
                "query": "q1", "error_type": "HTTPError", "message": "429",
                "retry_or_fallback": "continue_with_remaining_sources",
            })
        return []

    monkeypatch.setattr(run.scoper, "gather_candidates", fake_gather)
    recorder = run.Recorder(tmp_path / "circuit.jsonl")
    recorder.emit("manifest", case="toy", scope="widgets", scope_sha256="sha256:x",
                  code_version="abc", parameters={})
    run._gather_query_branches(
        ["q1", "q2"], stage="multi_query", kind="probe", motivation="initial",
        per_query=20, cutoff=None, recorder=recorder, known_before=set(),
    )
    recorder.close()
    assert calls[0]["use_s2"] is True
    assert calls[1]["use_s2"] is False
    rows = ledger.load_and_validate(tmp_path / "circuit.jsonl")
    pending = [row for row in rows if row.get("error_type") == "circuit_open"]
    assert len(pending) == 1
    assert pending[0]["retry_or_fallback"] == "pending_retry"


def test_recover_interleaved_reconstructs_candidate_and_proven_keep(tmp_path):
    recovery = _load("recover_interleaved")
    run_id = "scoper:good"
    base = {
        "schema_version": ledger.SCHEMA_VERSION, "run_id": run_id,
        "recorded_at": "2026-08-16T09:00:00Z",
    }
    paper_a = {"id": "a", "title": "A work"}
    paper_b = {"id": "b", "title": "B work"}
    rows = [
        base | {"event_id": f"{run_id}:e000001", "event": "manifest", "order": 1,
                "case": "toy", "scope": "widgets", "scope_sha256": "sha256:x",
                "code_version": "abc", "parameters": {}},
        base | {"event_id": f"{run_id}:e000002", "event": "candidate", "order": 2,
                "stage": "multi_query", "channel": "search", "work_key": "a",
                "paper": paper_a},
        # Orders 3 and 4 emulate one lost candidate plus one lost broad keep.
        base | {"event_id": f"{run_id}:e000005", "event": "decision", "order": 5,
                "stage": "multi_query", "work_key": "b", "decision": "dropped",
                "reason": "outside", "paper": paper_b},
        base | {"event_id": f"{run_id}:e000006", "event": "decision", "order": 6,
                "stage": "strict_rescreen", "work_key": "a", "decision": "kept",
                "reason": "core", "paper": paper_a},
        base | {"event_id": f"{run_id}:e000007", "event": "run_terminal", "order": 7,
                "status": "bounded", "reason": "done", "open_tasks": []},
    ]
    raw = tmp_path / "raw.jsonl"
    raw.write_text("".join(json.dumps(row) + "\n" for row in rows))
    out, report = tmp_path / "recovered.jsonl", tmp_path / "report.json"
    result = recovery.recover(raw, out, report)
    recovered = ledger.load_and_validate(out)
    assert result["reconstructed_candidate_events"] == 1
    assert result["reconstructed_decision_events"] == 1
    assert next(row for row in recovered if row["order"] == 3)["work_key"] == "b"
    assert next(row for row in recovered if row["order"] == 4)["decision"] == "kept"
