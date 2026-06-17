"""SciFact harness tests — all key-free (no API calls)."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from scifact import dataset, harness  # noqa: E402
from scifact.dataset import Doc, SciFactClaim  # noqa: E402
from prior.navigator import ForwardAnswer  # noqa: E402


def _write_fixture(tmp_path):
    # 5 distinct docs so BM25 IDF is non-degenerate (with 2 docs a term in one
    # doc gets IDF=0 and all scores collapse — an artifact of tiny corpora).
    corpus = [
        {"doc_id": 1, "title": "RAG",
         "abstract": ["Retrieval augmented generation reduces hallucination in question answering.",
                      "It augments the model with retrieved documents."]},
        {"doc_id": 2, "title": "Latency",
         "abstract": ["Retrieval adds latency and computational cost to generation."]},
        {"doc_id": 3, "title": "Transformers",
         "abstract": ["Transformers use self attention over token sequences."]},
        {"doc_id": 4, "title": "Diffusion",
         "abstract": ["Diffusion models generate images by iterative denoising."]},
        {"doc_id": 5, "title": "Optimization",
         "abstract": ["The Adam optimizer adapts learning rates per parameter."]},
    ]
    claims = [
        {"id": 10, "claim": "Retrieval augmented generation reduces hallucination.",
         "evidence": {"1": [{"sentences": [0], "label": "SUPPORT"}]},
         "cited_doc_ids": [1]},
        {"id": 11, "claim": "Retrieval augmented generation eliminates all errors.",
         "evidence": {"1": [{"sentences": [0], "label": "CONTRADICT"}]},
         "cited_doc_ids": [1]},
        {"id": 12, "claim": "Retrieval augmented generation was invented in 1850.",
         "evidence": {}, "cited_doc_ids": []},
    ]
    (tmp_path / "corpus.jsonl").write_text("\n".join(json.dumps(d) for d in corpus))
    (tmp_path / "claims_dev.jsonl").write_text("\n".join(json.dumps(c) for c in claims))
    return tmp_path


def test_load_derives_gold_labels(tmp_path):
    _write_fixture(tmp_path)
    corpus, claims = dataset.load(tmp_path, split="dev")
    assert len(corpus) == 5 and len(claims) == 3
    by_id = {c.id: c for c in claims}
    assert by_id["10"].gold_label == "SUPPORT"
    assert by_id["11"].gold_label == "CONTRADICT"
    assert by_id["12"].gold_label == "NOINFO"


def test_corpus_index_retrieves_relevant_abstract(tmp_path):
    _write_fixture(tmp_path)
    corpus, _ = dataset.load(tmp_path)
    idx = harness.CorpusIndex(corpus)
    top = idx.topk("latency cost of retrieval", k=1)
    assert top and top[0].doc_id == "2"


def test_atlas_from_docs_makes_one_claim_per_sentence():
    docs = [Doc("1", "T", ["a.", "b."]), Doc("2", "T2", ["c."])]
    a = harness.atlas_from_docs(docs)
    assert len(a.papers) == 2
    assert len(a.claims) == 3
    assert "scifact:1::s0" in a.claims


def test_map_label_all_branches():
    mk = lambda v, s, c: ForwardAnswer(v, "", s, c, [], "", "", [])
    assert harness.map_label(mk("not_found", [], [])) == "NOINFO"
    assert harness.map_label(mk("established", ["x"], [])) == "SUPPORT"
    assert harness.map_label(mk("contested", [], ["y"])) == "CONTRADICT"
    assert harness.map_label(mk("emerging", [], [])) == "NOINFO"
    # tie, not established -> abstain
    assert harness.map_label(mk("contested", ["x"], ["y"])) == "NOINFO"
    # tie, established -> support
    assert harness.map_label(mk("established", ["x"], ["y"])) == "SUPPORT"


def test_run_eval_with_mock_is_credit_free(tmp_path):
    corpus, claims = dataset.load(_write_fixture(tmp_path))

    def perfect_oracle(atlas, question, *, model=None, **_):
        # Map back to the gold label via the question text — proves scoring works.
        if "1850" in question:
            return ForwardAnswer("not_found", "", [], [], [], "", "", [])
        if "eliminates" in question:
            return ForwardAnswer("contested", "", [], ["c"], [], "", "", [])
        return ForwardAnswer("established", "", ["c"], [], [], "", "", [])

    m = harness.run_eval(corpus, claims, ask_fn=perfect_oracle, progress=lambda *_: None)
    assert m["n"] == 3
    assert m["accuracy"] == 1.0
    assert m["per_label"]["NOINFO"]["recall"] == 1.0


def test_cache_resumes(tmp_path):
    corpus, claims = dataset.load(_write_fixture(tmp_path))
    cache = tmp_path / "preds.jsonl"
    calls = {"n": 0}

    def counting(atlas, question, *, model=None, **_):
        calls["n"] += 1
        return ForwardAnswer("established", "", ["c"], [], [], "", "", [])

    harness.run_eval(corpus, claims, ask_fn=counting, cache_path=cache,
                     progress=lambda *_: None)
    first = calls["n"]
    harness.run_eval(corpus, claims, ask_fn=counting, cache_path=cache,
                     progress=lambda *_: None)
    assert calls["n"] == first  # second run served entirely from cache


def test_extract_json_handles_fences_and_prose():
    from prior import llm
    assert llm.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.extract_json('sure, here:\n{"a": 2, "b": [1,2]}\nhope that helps') \
        == {"a": 2, "b": [1, 2]}
