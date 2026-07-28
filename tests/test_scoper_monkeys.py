import importlib.util
import json
import sys
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
