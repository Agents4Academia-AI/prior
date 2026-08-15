#!/usr/bin/env python3
"""Label only newly localized citation sites, preserving site-level intent."""
from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import llm  # noqa: E402

OUT = Path(__file__).parent / "out"
SUBSTRATE_OUT = Path("/Users/kk1918_1/projects/Otto/worktrees/prior-citation-substrate/experiments/edge_quality/out")
INTENTS = ["background", "uses_extends", "compares_contrasts"]

SYSTEM = """You are a citation INTENT classifier. Classify why the citing paper invokes
the work marked [CITED:TARGET], using only the supplied citing passage and cited-paper
abstract. Choose exactly one:
- background: general context, prior art, motivation, or a grouped/passive mention.
- uses_extends: explicit use, adoption, or extension of the target's method, dataset,
  code, framework, protocol, artifact, or result.
- compares_contrasts: the citing work specifically compares itself/results against,
  distinguishes itself from, or critiques the target.
Grouping rule: a contrast or limitation applied to a group or the field is background;
the target must be singled out for compares_contrasts. Detailed description alone is
background unless the citing method actively relies on the target. For baselines,
comparison/outperformance is compares_contrasts, while adoption of experimental
protocol, dataset, or infrastructure is uses_extends. When genuinely unsure, prefer
background with lower confidence. Never use outside knowledge."""

SCHEMA = {"type": "object", "properties": {"labels": {"type": "array", "items": {
    "type": "object", "properties": {
        "site_key": {"type": "string"},
        "intent": {"type": "string", "enum": INTENTS},
        "confidence": {"type": "number"},
        "justification": {"type": "string"},
    }, "required": ["site_key", "intent", "confidence", "justification"]
}}}, "required": ["labels"]}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {row["site_key"]: row for line in path.read_text().splitlines()
            if line.strip() for row in [json.loads(line)]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", type=Path,
                        default=SUBSTRATE_OUT / "citation_contexts_incoming_v12.json")
    parser.add_argument("--existing-intents", type=Path,
                        default=SUBSTRATE_OUT / "citations_intent.json")
    parser.add_argument("--papers", type=Path,
                        default=ROOT / "data/prior-core-v0.2/papers_core.jsonl")
    parser.add_argument("--output", type=Path,
                        default=OUT / "citations_intent_incoming_v12_new.json")
    parser.add_argument("--checkpoint", type=Path,
                        default=OUT / "citations_intent_incoming_v12_new.ckpt.jsonl")
    parser.add_argument("--model", default="claude-sonnet-5")
    parser.add_argument("--batch-size", type=int, default=12)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()

    context_obj = load_json(args.contexts)
    context_rows = context_obj.get("edges", []) if isinstance(context_obj, dict) else context_obj
    existing = load_json(args.existing_intents)
    old_edges = {(row["citing_id"], row["cited_id"]) for row in existing["edges"]}
    papers = {row["id"]: row for line in args.papers.read_text().splitlines()
              if line.strip() for row in [json.loads(line)]}
    sites = []
    for row in context_rows:
        edge = (row["citing_id"], row["cited_id"])
        if edge in old_edges:
            continue
        for i, passage in enumerate(row.get("contexts") or []):
            text = passage if isinstance(passage, str) else passage.get("text", "")
            if text.strip():
                sites.append({
                    "site_key": f"{edge[0]}->{edge[1]}#{i}",
                    "citing_id": edge[0], "cited_id": edge[1],
                    "claim": text.strip(),
                    "abstract": (papers.get(edge[1], {}).get("abstract") or ""),
                    "context_status": row.get("context_status"),
                })
    edge_count = len({(s["citing_id"], s["cited_id"]) for s in sites})
    preflight = {"new_edges_with_sites": edge_count, "new_sites": len(sites),
                 "existing_edges_excluded": len(old_edges), "model": args.model}
    print(json.dumps(preflight, indent=2), flush=True)
    if args.prepare_only:
        return

    done = load_jsonl(args.checkpoint)
    batches = [[s for s in sites if s["site_key"] not in done][i:i + args.batch_size]
               for i in range(0, len([s for s in sites if s["site_key"] not in done]), args.batch_size)]
    lock = threading.Lock()

    def label_once(batch: list[dict]) -> list[dict]:
        payload = [{"site_key": s["site_key"], "citing_passage": s["claim"],
                    "cited_abstract": s["abstract"]} for s in batch]
        result = llm.structured(
            model=args.model, system=SYSTEM,
            user="Classify every citation site: " + json.dumps(payload, ensure_ascii=False),
            schema=SCHEMA, tool_name="emit_intents", max_tokens=1800,
            timeout=args.timeout, retries=3,
        )
        expected = {s["site_key"]: s for s in batch}
        labels = result.get("labels", [])
        if {r.get("site_key") for r in labels} != set(expected):
            raise ValueError("model did not return exactly the requested site keys")
        return [{**expected[row["site_key"]], **row, "model": args.model,
                 "prompt_version": "callum-intent-rubric-v1"} for row in labels]

    def label(batch: list[dict]) -> list[dict]:
        try:
            return label_once(batch)
        except ValueError:
            if len(batch) == 1:
                raise
            middle = len(batch) // 2
            return label(batch[:middle]) + label(batch[middle:])

    print(f"label phase: {sum(map(len, batches))} remaining / {len(sites)}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(label, batch): batch for batch in batches}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                rows = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[{i}/{len(batches)}] ERROR ({len(futures[future])} sites): {exc}",
                      flush=True)
                continue
            with lock, args.checkpoint.open("a", encoding="utf-8") as handle:
                for row in rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    done[row["site_key"]] = row
            print(f"[{i}/{len(batches)}] +{len(rows)}", flush=True)

    missing = [s["site_key"] for s in sites if s["site_key"] not in done]
    ordered = [done[s["site_key"]] for s in sites if s["site_key"] in done]
    artifact = {
        "sites": ordered,
        "meta": {**preflight, "complete": not missing,
                 "n_judged_sites": len(ordered), "missing_site_keys": missing,
                 "site_intent_distribution": dict(Counter(r["intent"] for r in ordered)),
                 "note": "Site-level intent only; no edge rollup is produced or used by Cartographer."},
    }
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(artifact["meta"], indent=2), flush=True)
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
