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
        "g3": "not_retrieved_or_not_indexed",
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
