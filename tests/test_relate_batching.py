"""kNN-pair batching for cross-contribution relating (incl. cross-cluster pairs)."""

from prior import pipeline


def test_pack_pairs_keeps_endpoints_together_and_respects_batch():
    pairs = {(0, 1), (1, 2), (3, 4), (4, 5), (0, 5)}
    pos = {i: i for i in range(6)}
    groups = pipeline._pack_pairs(pairs, pos, batch=4)
    for a, b in pairs:                          # every candidate pair is judged
        assert any(a in g and b in g for g in groups), (a, b)
    assert all(len(g) <= 4 for g in groups)     # prompts stay bounded


def test_semantic_groups_small_set_is_one_group():
    assert pipeline._semantic_groups(["a contribution", "another one"], batch=70) == [[0, 1]]
    assert pipeline._semantic_groups([], batch=70) == []
