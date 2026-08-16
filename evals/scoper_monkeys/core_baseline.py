"""Prepare a reproducible replay of the policy that produced Prior's 152-work core.

The historical run combined build_scoped.TOPIC + SEEDS, model-proposed query
additions, per-query depth 20, broad screening, a one-hop citation snowball, and a
later strict rescreen. The original generated additions and private bibliography
anchors were not archived; this adapter records those gaps instead of pretending
the replay is byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_scoped  # noqa: E402
import tighten  # noqa: E402
from prior import scoper  # noqa: E402


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(out_dir: Path, core_path: Path, *, propose_extra: bool) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    scope = out_dir / "broad-scope.txt"
    strict = out_dir / "strict-core-scope.txt"
    fixed = out_dir / "fixed-seed-queries.txt"
    generated = out_dir / "generated-extra-queries.txt"
    combined = out_dir / "all-replay-queries.txt"
    empty_gold = out_dir / "empty-gold-for-blind-run.jsonl"
    gold = out_dir / "gold-current-core.jsonl"

    scope.write_text(build_scoped.TOPIC.strip() + "\n")
    strict.write_text(tighten.STRICT_TOPIC.strip() + "\n")
    fixed.write_text("\n".join(build_scoped.SEEDS) + "\n")
    extra = scoper.propose_queries(build_scoped.TOPIC) if propose_extra else []
    generated.write_text("\n".join(extra) + ("\n" if extra else ""))
    queries = list(dict.fromkeys(build_scoped.SEEDS + extra))
    combined.write_text("\n".join(queries) + "\n")
    empty_gold.write_text("")

    rows = [json.loads(line) for line in core_path.read_text().splitlines() if line]
    with gold.open("w") as handle:
        for row in rows:
            handle.write(json.dumps({
                "id": row.get("id", ""), "title": row.get("title", ""),
                "doi": row.get("doi", ""), "year": row.get("year"),
            }, ensure_ascii=False) + "\n")

    manifest = {
        "replay": "prior-152-core-construction-policy",
        "policy": {
            "scope": "scripts/build_scoped.py:TOPIC",
            "fixed_queries": "scripts/build_scoped.py:SEEDS",
            "generated_queries": "fresh replay; historical generated queries unavailable",
            "sources": ["openalex", "arxiv", "semanticscholar"],
            "per_query": 20,
            "adaptive_rounds": 0,
            "citation_hops": 1,
            "prefilter": False,
            "cutoff": None,
            "strict_rescreen": "scripts/tighten.py:STRICT_TOPIC",
        },
        "known_input_gaps": [
            "Historical model-generated query additions were not archived.",
            "Private bibliography/grant anchors used by weekend_run._gold_anchors are unavailable in the repository.",
            "Live indexes and model outputs have changed since the June 2026 construction run.",
        ],
        "target_core": {"path": str(core_path), "works": len(rows)},
        "files": {},
    }
    for path in (scope, strict, fixed, generated, combined, empty_gold, gold):
        manifest["files"][path.name] = _sha(path)
    (out_dir / "replay-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--core", required=True, type=Path)
    ap.add_argument("--propose-extra", action="store_true")
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    result = prepare(args.out_dir, args.core, propose_extra=args.propose_extra)
    print(json.dumps(result, indent=2))
