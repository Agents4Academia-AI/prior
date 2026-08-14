import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_review_covers_snapshot_once():
    snapshot = json.loads((ROOT / "experiments/graph_ideation/gap_atlas_snapshot/gap_atlas.json").read_text())
    review = json.loads((ROOT / "experiments/graph_ideation/gap_atlas_agent_review.json").read_text())
    card_ids = [card["id"] for card in snapshot["cards"]]
    reviewed_ids = [row["id"] for row in review["decisions"]]
    assert len(reviewed_ids) == len(set(reviewed_ids))
    assert set(reviewed_ids) == set(card_ids)
    canonical_ids = {row["canonical"] for row in review["decisions"] if row["canonical"]}
    assert canonical_ids <= set(card_ids)
