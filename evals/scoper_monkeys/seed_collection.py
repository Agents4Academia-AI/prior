"""Prepare a local case from ielab/sysrev-seed-collection.

The adapter deliberately does not export the review's Boolean query.  That query
is useful as an oracle comparator, but feeding it to Prior would leak the answer
to the retrieval experiment.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def load_topic(root: Path, topic_id: str) -> dict:
    path = root / "collection_data" / "overall_collection.jsonl"
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if str(row["id"]) == str(topic_id):
            return row
    raise ValueError(f"topic {topic_id!r} not found in {path}")


def load_records(root: Path, pmids: set[str]) -> dict[str, dict]:
    archive = root / "corpus" / "all.jsonl.zip"
    found: dict[str, dict] = {}
    with zipfile.ZipFile(archive) as handle:
        names = [
            name for name in handle.namelist()
            if name.endswith(".jsonl") and not name.startswith("__MACOSX/")
        ]
        if len(names) != 1:
            raise ValueError(f"expected one JSONL member in {archive}, found {names}")
        with handle.open(names[0]) as rows:
            for raw in rows:
                record = json.loads(raw)
                pmid = str(record.get("pmid", ""))
                if pmid in pmids:
                    found[pmid] = record
                    if len(found) == len(pmids):
                        break
    return found


def _gold_row(pmid: str, record: dict) -> dict:
    return {
        "gold_id": f"pmid:{pmid}",
        "pmid": pmid,
        "title": record["title"],
        "abstract": record.get("abstract", ""),
    }


def prepare(root: Path, topic_id: str, out_dir: Path, *,
            supplement: Path | None = None, allow_missing: bool = False) -> dict:
    topic = load_topic(root, topic_id)
    included = [str(value) for value in topic["included_studies"]]
    seeds = [str(value) for value in topic["seed_studies"]]
    records = load_records(root, set(included) | set(seeds))
    if supplement:
        for line in supplement.read_text().splitlines():
            record = json.loads(line)
            records[str(record["pmid"])] = record
    missing_included = [pmid for pmid in included if pmid not in records]
    missing_seeds = [pmid for pmid in seeds if pmid not in records]
    if missing_included and not allow_missing:
        raise ValueError(
            "dataset corpus is missing included PMIDs "
            f"{missing_included}; supplement them or pass --allow-missing"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    gold = [_gold_row(pmid, records[pmid]) for pmid in included if pmid in records]
    seed_rows = [_gold_row(pmid, records[pmid]) for pmid in seeds if pmid in records]
    (out_dir / "gold.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in gold)
    )
    (out_dir / "seeds.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in seed_rows)
    )

    # This is a weak, intentionally visible smoke-test scope. A domain expert
    # should replace it before treating the result as benchmark evidence.
    scope = (
        f"Research question: {topic['search_name']}.\n\n"
        "Include: primary empirical studies directly evaluating the intervention "
        "or technology in the stated learner population, with a measured learning "
        "or assessment outcome.\n"
        "Exclude: reviews, protocols, editorials, non-empirical papers, studies "
        "outside the stated learner population, and studies without a relevant "
        "learning or assessment outcome.\n"
        f"Publication cutoff: {topic['Date_to']}.\n"
    )
    (out_dir / "scope.smoke.txt").write_text(scope)

    manifest = {
        "dataset": "ielab/sysrev-seed-collection",
        "topic_id": str(topic_id),
        "review_url": topic["link_to_review"],
        "cutoff": topic["Date_to"],
        "included_n_declared": len(included),
        "gold_n_exported": len(gold),
        "seed_n_declared": len(seeds),
        "seeds_n_exported": len(seed_rows),
        "missing_included_pmids": missing_included,
        "missing_seed_pmids": missing_seeds,
        "scope_quality": "automatic smoke-test draft; requires domain review",
        "leakage_guard": "original review title and Boolean queries not exported",
    }
    (out_dir / "case.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--supplement", type=Path,
        help="JSONL records used to fill corpus omissions (pmid and title required)",
    )
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()
    manifest = prepare(
        args.dataset_root, args.topic, args.out_dir,
        supplement=args.supplement,
        allow_missing=args.allow_missing,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
