"""Run the recovered June Scoper search policy against the current indexes.

This runner deliberately accepts no gold/recovery-target argument. Initial search
and main-pass source responses may be supplied as immutable caches; all subsequent
passes are checkpointed. OA and S2 candidates are joined and work-deduplicated
before a single broad screen in every pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prior import scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import semanticscholar  # noqa: E402
from product_disagreement import screen_historical  # noqa: E402


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, values) -> None:
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def paper_rows(path: Path) -> list[Paper]:
    return [Paper.from_dict(row.get("paper", row)) for row in rows(path)]


def unique_papers(values: list[Paper]) -> list[Paper]:
    return scoper._dedup_cross_source(values)


def keys(values: list[Paper]) -> set[str]:
    return {paper.key() for paper in values}


def copy_with_receipt(source: Path, target: Path, receipts: list[dict]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    receipts.append({"source": str(source), "target": str(target), "sha256": sha(source)})


def serialise_event(event: dict) -> dict:
    return {key: value.to_dict() if isinstance(value, Paper) else value
            for key, value in event.items()}


def oa_collect(seeds: list[Paper], corpus: list[Paper], out_dir: Path,
               *, anchor_k: int, per_paper: int) -> tuple[list[Paper], list[dict]]:
    candidate_path = out_dir / "oa-candidates.jsonl"
    ledger_path = out_dir / "oa-ledger.jsonl"
    if candidate_path.exists() and ledger_path.exists():
        return paper_rows(candidate_path), rows(ledger_path)
    events: list[dict] = []
    found, _reached = scoper.snowball(
        seeds, corpus=corpus, anchor_k=anchor_k, per_paper=per_paper,
        progress=lambda message: print("  OA " + message, flush=True),
        observe=lambda event: events.append(serialise_event(event)), hop=1,
    )
    write_jsonl(candidate_path, (paper.to_dict() for paper in found))
    write_jsonl(ledger_path, events)
    return found, events


def s2_collect(seeds: list[Paper], corpus: list[Paper], out_dir: Path,
               *, anchor_k: int, per_paper: int, recent_year: int = 2024
               ) -> tuple[list[Paper], list[dict]]:
    checkpoint = out_dir / "s2-seed-checkpoints.jsonl"
    anchors = [p for p in seeds
               if (p.year or 0) >= recent_year or p.id.startswith(("arxiv:", "s2:"))]
    anchors = sorted(anchors, key=lambda paper: -(paper.year or 0))[:anchor_k]
    complete = {row["seed_id"] for row in rows(checkpoint)
                if row.get("status") in {"complete", "unresolvable"}}
    with checkpoint.open("a") as handle:
        for index, seed in enumerate(anchors, 1):
            if seed.id in complete:
                continue
            sid = scoper._s2_id(seed)
            if not sid:
                handle.write(json.dumps({"seed_id": seed.id, "seed_title": seed.title,
                                         "status": "unresolvable"}) + "\n")
                handle.flush()
                continue
            backward = semanticscholar.references(sid, max_results=per_paper)
            forward = semanticscholar.citations(sid, max_results=per_paper)
            record = {"seed_id": seed.id, "seed_title": seed.title,
                      "s2_lookup_id": sid, "status": "complete",
                      "backward": [p.to_dict() for p in backward],
                      "forward": [p.to_dict() for p in forward]}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n"); handle.flush()
            print(f"  S2 seed {index}/{len(anchors)}: {seed.short_cite()} -> "
                  f"{len(backward)} back, {len(forward)} forward", flush=True)
    events = rows(checkpoint)
    found = []
    for event in events:
        found.extend(Paper.from_dict(p) for p in event.get("backward", []))
        found.extend(Paper.from_dict(p) for p in event.get("forward", []))
    found = [p for p in unique_papers(found) if p.key() not in keys(corpus)]
    write_jsonl(out_dir / "s2-candidates.jsonl", (p.to_dict() for p in found))
    return found, events


def provenance(oa_events: list[dict], s2_events: list[dict]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    ranks: dict[tuple[str, str, str], int] = {}
    for source, events in (("openalex", oa_events), ("semanticscholar", s2_events)):
        for event in events:
            if source == "openalex":
                candidate = event.get("paper")
                direction = event.get("direction")
                seed = event.get("seed") or {}
                if not candidate:
                    continue
                candidates = [(candidate, direction, seed, event.get("rank"))]
            else:
                seed = {"id": event.get("seed_id"), "title": event.get("seed_title")}
                candidates = [(p, "backward", seed, rank)
                              for rank, p in enumerate(event.get("backward", []), 1)]
                candidates += [(p, "forward", seed, rank)
                               for rank, p in enumerate(event.get("forward", []), 1)]
            for candidate, direction, seed, source_rank in candidates:
                p = Paper.from_dict(candidate)
                rank_key = (source, str(seed.get("id")), str(direction))
                if source_rank is None:
                    ranks[rank_key] = ranks.get(rank_key, 0) + 1
                    source_rank = ranks[rank_key]
                record = result.setdefault(p.key(), {"paper_id": p.id, "title": p.title,
                                                      "discoveries": []})
                discovery = {"source": source, "direction": direction,
                             "seed_id": seed.get("id"), "seed_title": seed.get("title"),
                             "source_rank": source_rank}
                if discovery not in record["discoveries"]:
                    record["discoveries"].append(discovery)
    return result


def screen_pass(name: str, corpus: list[Paper], oa: list[Paper], s2: list[Paper],
                oa_events: list[dict], s2_events: list[dict], scope: Path,
                out_dir: Path, cache: Path, model: str | None,
                *, prefilter: bool) -> tuple[list[Paper], dict]:
    stage = out_dir / name; stage.mkdir(exist_ok=True)
    prior_keys = keys(corpus)
    combined = [p for p in unique_papers(oa + s2) if p.key() not in prior_keys]
    fingerprint = hashlib.sha256("\n".join(sorted(keys(combined))).encode()).hexdigest()
    previous_fingerprints = {
        row.get("frontier_sha256") for row in rows(out_dir / "pass-ledger.jsonl")
    }
    repeated = fingerprint in previous_fingerprints if combined else False
    write_jsonl(stage / "combined-candidates.jsonl", (p.to_dict() for p in combined))
    write_jsonl(stage / "candidate-provenance.jsonl", provenance(oa_events, s2_events).values())
    if repeated:
        accepted, dropped = [], []
        status = {"records": len(combined), "eligible": 0, "excluded": 0,
                  "repeated_frontier": True, "frontier_sha256": fingerprint}
    else:
        if prefilter:
            survivors, gated = scoper.prefilter(scope.read_text(), combined,
                                                progress=lambda m: print("  " + m, flush=True))
        else:
            survivors, gated = combined, []
        screen_input = stage / "screen-input.jsonl"
        write_jsonl(screen_input, (p.to_dict() for p in survivors))
        screen_dir = stage / "screen"
        screen_historical(screen_input, scope, screen_dir, model, cache=cache)
        accepted = [Paper.from_dict(row["paper"]) for row in rows(screen_dir / "eligible.jsonl")]
        dropped = rows(screen_dir / "excluded.jsonl")
        gated_rows = [{"paper": p.to_dict(), "decision": {"in_scope": False,
                       "reason": "pre-filtered: low topic similarity"}} for p in gated]
        write_jsonl(stage / "prefilter-excluded.jsonl", gated_rows)
        status = {"records": len(combined), "llm_screened": len(survivors),
                  "prefilter_excluded": len(gated), "eligible": len(accepted),
                  "excluded": len(dropped) + len(gated), "repeated_frontier": False,
                  "frontier_sha256": fingerprint}
    merged = unique_papers(corpus + accepted)
    status["marginal_unique_eligible"] = len(merged) - len(corpus)
    status["corpus_after"] = len(merged)
    status["source_candidates"] = {"openalex": len(oa), "semanticscholar": len(s2)}
    (stage / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    write_jsonl(stage / "corpus.jsonl", (p.to_dict() for p in merged))
    with (out_dir / "pass-ledger.jsonl").open("a") as handle:
        handle.write(json.dumps({"pass": name, **status}) + "\n")
    return merged, status


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--construction", required=True, type=Path)
    ap.add_argument("--anchors", required=True, type=Path)
    ap.add_argument("--scope", required=True, type=Path)
    ap.add_argument("--strict-scope", required=True, type=Path)
    ap.add_argument("--cached-main-oa", required=True, type=Path)
    ap.add_argument("--cached-main-oa-ledger", required=True, type=Path)
    ap.add_argument("--cached-main-s2-checkpoints", required=True, type=Path)
    ap.add_argument("--reuse-broad-cache", type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--model")
    args = ap.parse_args()
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        raise SystemExit("output directory must be new and empty")
    args.out_dir.mkdir(parents=True)
    receipts: list[dict] = []
    copy_with_receipt(args.construction, args.out_dir / "00-construction.jsonl", receipts)
    copy_with_receipt(args.cached_main_oa, args.out_dir / "01-main/oa-candidates.jsonl", receipts)
    copy_with_receipt(args.cached_main_oa_ledger, args.out_dir / "01-main/oa-ledger.jsonl", receipts)
    copy_with_receipt(args.cached_main_s2_checkpoints,
                      args.out_dir / "01-main/s2-seed-checkpoints.jsonl", receipts)
    broad_cache = args.out_dir / "broad-screen-cache.jsonl"
    if args.reuse_broad_cache:
        copy_with_receipt(args.reuse_broad_cache, broad_cache, receipts)
    else:
        broad_cache.touch()
    (args.out_dir / "cache-reuse-receipts.json").write_text(json.dumps(receipts, indent=2) + "\n")

    corpus = paper_rows(args.out_dir / "00-construction.jsonl")
    oa = paper_rows(args.out_dir / "01-main/oa-candidates.jsonl")
    oa_events = rows(args.out_dir / "01-main/oa-ledger.jsonl")
    s2, s2_events = s2_collect(corpus, corpus, args.out_dir / "01-main",
                                anchor_k=40, per_paper=40)
    corpus, _ = screen_pass("01-main", corpus, oa, s2, oa_events, s2_events,
                            args.scope, args.out_dir, broad_cache, args.model,
                            prefilter=False)

    seeds = scoper.high_yield_seeds(corpus)
    stage = args.out_dir / "02-high-yield"; stage.mkdir(exist_ok=True)
    oa, oe = oa_collect(seeds, corpus, stage, anchor_k=25, per_paper=40)
    s2, se = s2_collect(seeds, corpus, stage, anchor_k=40, per_paper=40)
    corpus, _ = screen_pass("02-high-yield", corpus, oa, s2, oe, se, args.scope,
                            args.out_dir, broad_cache, args.model, prefilter=True)

    seeds = scoper.high_yield_seeds(corpus)
    stage = args.out_dir / "03-s2-only"; stage.mkdir(exist_ok=True)
    s2, se = s2_collect(seeds, corpus, stage, anchor_k=40, per_paper=40)
    corpus, _ = screen_pass("03-s2-only", corpus, [], s2, [], se, args.scope,
                            args.out_dir, broad_cache, args.model, prefilter=True)

    anchor_papers = paper_rows(args.anchors)
    anchor_keys = keys(anchor_papers)
    seeds = [p for p in corpus if p.key() in anchor_keys]
    stage = args.out_dir / "04-supplied-anchors"; stage.mkdir(exist_ok=True)
    anchor_k = max(len(seeds), 1)
    oa, oe = oa_collect(seeds, corpus, stage, anchor_k=anchor_k, per_paper=40)
    s2, se = s2_collect(seeds, corpus, stage, anchor_k=max(anchor_k, 40), per_paper=40)
    corpus, _ = screen_pass("04-supplied-anchors", corpus, oa, s2, oe, se, args.scope,
                            args.out_dir, broad_cache, args.model, prefilter=True)

    broad_path = args.out_dir / "broad-corpus-frozen.jsonl"
    write_jsonl(broad_path, (p.to_dict() for p in corpus))
    strict_dir = args.out_dir / "strict-screen"
    screen_historical(broad_path, args.strict_scope, strict_dir, args.model,
                      cache=args.out_dir / "strict-screen-cache.jsonl")
    strict_status = json.loads((strict_dir / "status.json").read_text())
    snapshot = args.out_dir / "snapshot"; snapshot.mkdir()
    shutil.copy2(strict_dir / "eligible.jsonl", snapshot / "eligible.jsonl")
    for role in ("retrieval_only", "uncertain"):
        (snapshot / f"{role}.jsonl").touch()
    summary = {
        "policy": "recovered-june-scoper-current-index-validated-v1",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "hidden_targets_loaded": False,
        "search_policy": ["initial_33_query_depth20_plus_anchors", "main_oa_s2",
                          "bounded_high_yield_oa_s2", "targeted_s2_only",
                          "supplied_anchor_oa_s2", "strict_screen"],
        "correctness_guards": ["combine_sources_before_screen", "work_dedup",
            "full_source_seed_direction_traces", "screen_rationales", "contradiction_reask",
            "source_checkpoints", "marginal_unique_yield", "repeated_frontier_detection"],
        "broad_corpus": len(corpus), "strict_screen": strict_status,
        "limitations": ["S2 relevance-ranked initial search unavailable; initial cached construction uses OA+arXiv.",
                        "Live indexes and model outputs differ from June 2026."],
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
