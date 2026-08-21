import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals" / "scoper_monkeys"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, EVALS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _paper(identifier, title, *, abstract="complete abstract", doi=None,
           year=2026, date="2026-07-01"):
    return {
        "id": identifier,
        "source": "semanticscholar" if identifier.startswith("s2:") else "openalex",
        "title": title,
        "abstract": abstract,
        "url": "",
        "year": year,
        "date": date,
        "date_precision": "day",
        "doi": doi,
    }


def test_identity_never_collapses_identifierless_s2_stubs():
    identity = _load("anchored_identity")
    occurrences = [
        {"occurrence_id": "a", "channel": "s2_backward",
         "paper": _paper("s2:None", "First unrelated bibliography stub")},
        {"occurrence_id": "b", "channel": "s2_backward",
         "paper": _paper("s2:None", "Second unrelated bibliography stub")},
        {"occurrence_id": "c", "channel": "openalex_forward",
         "paper": _paper("openalex:W1", "A real identified paper")},
    ]

    result = identity.resolve_occurrences(occurrences)

    assert len(result.groups) == 1
    assert len(result.unresolved) == 2
    assert {row["occurrence_id"] for row in result.unresolved} == {"a", "b"}


def test_identity_preserves_manifestations_joined_by_doi():
    identity = _load("anchored_identity")
    occurrences = [
        {"occurrence_id": "oa", "channel": "openalex_forward",
         "paper": _paper("openalex:W2", "One scientific work", doi="10.1234/work")},
        {"occurrence_id": "s2", "channel": "s2_forward",
         "paper": _paper("s2:" + "a" * 40, "One scientific work",
                          doi="https://doi.org/10.1234/WORK")},
    ]

    result = identity.resolve_occurrences(occurrences)

    assert len(result.groups) == 1
    group = result.groups[0]
    assert group["occurrence_count"] == 2
    assert group["work_key"] == "doi:10.1234/work"
    assert len(group["manifestations"]) == 2


def test_s2_404_is_not_counted_as_a_complete_branch():
    expansion = _load("anchored_expansion")
    rows = [
        {"event": "adapter_observation", "seed_work_key": "seed", "direction": "backward",
         "kind": "request_attempt", "status_code": 404},
        {"event": "branch_terminal", "seed_work_key": "seed", "direction": "backward",
         "status": "complete"},
        {"event": "adapter_observation", "seed_work_key": "seed", "direction": "forward",
         "kind": "request_attempt", "status_code": 200},
        {"event": "branch_terminal", "seed_work_key": "seed", "direction": "forward",
         "status": "complete"},
    ]

    outcomes = expansion.base_outcomes(rows)

    assert outcomes[("seed", "backward")]["state"] == "failed_http"
    assert outcomes[("seed", "backward")]["latest_http_status"] == 404
    assert not outcomes[("seed", "backward")]["successful"]
    assert outcomes[("seed", "forward")]["state"] == "successful"


def test_prepare_freezes_exact_anchor_and_reporting_boundary(tmp_path):
    expansion = _load("anchored_expansion")
    seed_file = tmp_path / "seed.jsonl"
    rows = [_paper(f"openalex:W{index}", f"Frozen seed paper {index}")
            for index in range(152)]
    seed_file.write_text("".join(json.dumps(row) + "\n" for row in rows))
    out_dir = tmp_path / "anchored"

    protocol = expansion.prepare(seed_file, out_dir)

    assert len((out_dir / "seed-snapshot.jsonl").read_text().splitlines()) == 152
    assert len((out_dir / "seed-screen" / "eligible.jsonl").read_text().splitlines()) == 152
    assert all(not (out_dir / "seed-screen" / f"{role}.jsonl").read_text()
               for role in ("retrieval_only", "uncertain", "excluded"))
    assert protocol["reporting_boundary"] == "2026-06-24"
    assert "not a retrieval" in protocol["reporting_boundary_semantics"]
    assert "historical_cutoff" not in protocol
    with pytest.raises(FileExistsError):
        expansion.prepare(seed_file, out_dir)


def test_initial_s2_expansion_is_strict_capped_and_resumable(tmp_path, monkeypatch):
    expansion = _load("anchored_expansion")
    seed_snapshot = tmp_path / "seed-snapshot.jsonl"
    rows = []
    for index in range(152):
        paper = _paper(f"openalex:W{index}", f"Expansion seed paper {index}",
                       doi=f"10.1234/work-{index}")
        paper["work_aliases"] = [f"arxiv:2501.{index:05d}", f"doi:10.1234/work-{index}"]
        rows.append({"paper": paper})
    seed_snapshot.write_text("".join(json.dumps(row) + "\n" for row in rows))
    out_dir = tmp_path / "run"
    calls = []

    def fake(direction):
        def call(identifier, **kwargs):
            calls.append((direction, identifier, kwargs["max_results"],
                          kwargs["strict_errors"]))
            if direction == "backward" and identifier == "ARXIV:2501.00000":
                kwargs["observe"]({"kind": "request_attempt", "status_code": 404})
                raise RuntimeError("not found")
            kwargs["observe"]({"kind": "request_attempt", "status_code": 200})
            return []
        return call

    monkeypatch.setattr(expansion.semanticscholar, "references", fake("backward"))
    monkeypatch.setattr(expansion.semanticscholar, "citations", fake("forward"))
    monkeypatch.setattr(expansion.semanticscholar, "recommendations", fake("recommendation"))

    status = expansion.s2_expand(seed_snapshot, out_dir, progress=lambda *_: None)

    assert status["branches"] == 456
    assert status["states"] == {"complete": 456}
    assert len(calls) == 457
    assert all(strict is True for _, _, _, strict in calls)
    assert {direction: {cap for used, _, cap, _ in calls if used == direction}
            for direction in expansion.DIRECTION_ORDER} == {
                "backward": {60}, "forward": {60}, "recommendation": {10}}
    ledger = [json.loads(line) for line in
              (out_dir / "s2-expansion-ledger.jsonl").read_text().splitlines()]
    assert sum(row.get("event") == "branch_terminal" for row in ledger) == 456
    assert sum(row.get("event") == "adapter_observation" for row in ledger) == 457

    monkeypatch.setattr(expansion.semanticscholar, "references",
                        lambda *a, **k: pytest.fail("completed branch reran"))
    monkeypatch.setattr(expansion.semanticscholar, "citations",
                        lambda *a, **k: pytest.fail("completed branch reran"))
    monkeypatch.setattr(expansion.semanticscholar, "recommendations",
                        lambda *a, **k: pytest.fail("completed branch reran"))
    assert expansion.s2_expand(seed_snapshot, out_dir, progress=lambda *_: None) == status


def test_screening_cohort_requires_complete_abstracts(tmp_path):
    screening = _load("anchored_screening")
    candidates = tmp_path / "candidates.jsonl"
    scope = tmp_path / "scope.txt"
    output = tmp_path / "screen"
    scope.write_text("Include primary scientific research agents.\n")
    rows = []
    for index in range(6):
        paper = _paper(
            f"openalex:W{index + 10}", f"Candidate paper number {index}",
            abstract="" if index == 0 else f"This is the complete abstract number {index}",
        )
        rows.append({
            "work_key": paper["id"],
            "identity_status": "resolved",
            "identity_keys": ["id:" + paper["id"]],
            "paper": paper,
            "channels": ["openalex_forward"],
            "seed_work_keys": ["seed"],
            "seed_path_count": 1,
            "retrieval_occurrences": 1,
            "date_bucket": "after_snapshot",
        })
    candidates.write_text("".join(json.dumps(row) + "\n" for row in rows))

    status = screening.prepare(candidates, scope, output, cap=4)
    cohort = [json.loads(line) for line in (output / "cohort-600.jsonl").read_text().splitlines()]
    unavailable = [json.loads(line) for line in
                   (output / "evidence-unavailable.jsonl").read_text().splitlines()]

    assert status["cohort_records"] == 4
    assert status["evidence_unavailable"] == 1
    assert all(row["paper"]["abstract"] for row in cohort)
    assert unavailable[0]["not_screened"]["reasons"] == ["complete_abstract_unavailable"]
