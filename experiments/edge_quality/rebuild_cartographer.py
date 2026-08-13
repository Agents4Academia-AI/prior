#!/usr/bin/env python3
"""Blind, evidence-enriched relabeling of a frozen Cartographer candidate union."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from prior import llm  # noqa: E402

BUNDLE = ROOT / "data" / "prior-core-v0.2"
OUT = Path(__file__).parent / "out"
DEFAULT_FULLTEXT = Path(
    "/Users/kk1918_1/Desktop/Projects/hackathon/prior/data_hackathon/fulltext"
)
WORD = re.compile(r"[a-z0-9]+")
RELATIONS = ["supports", "builds_on", "refines", "contradicts",
             "related", "none", "unclear"]

SYSTEM = """You are rebuilding a scientific contribution graph from a frozen
candidate set. Classify exactly one contribution pair using only supplied evidence.
- supports: comparable findings materially corroborate one another
- builds_on: one explicitly uses or extends the other's method, artifact, or result
- refines: one qualifies, narrows, corrects, or makes the other more precise
- contradicts: the same construct/question has genuinely incompatible findings
- related: a substantive relationship exists but no hard type is defensible
- none: no substantive contribution-level relationship is established
- unclear: supplied evidence is insufficient
For builds_on/refines identify which contribution acts on the other. Supports and
contradicts are symmetric. Citation existence is a fact, not proof of a semantic
relation; background citation and topical similarity are insufficient. Cite exact
evidence IDs. Prefer related, none, or unclear to an unsupported hard relation."""

SCHEMA = {"type": "object", "properties": {
    "relation": {"type": "string", "enum": RELATIONS},
    "direction": {"type": "string",
                  "enum": ["a_to_b", "b_to_a", "symmetric", "none", "unclear"]},
    "existence_confidence": {"type": "number"},
    "type_confidence": {"type": "number"},
    "evidence_ids": {"type": "array", "items": {"type": "string"}},
    "reason": {"type": "string"},
}, "required": ["relation", "direction", "existence_confidence",
                 "type_confidence", "evidence_ids", "reason"]}


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", value)


def paper_id(contribution_id: str) -> str:
    return contribution_id.split("::")[0]


def tokens(text: str) -> Counter[str]:
    return Counter(WORD.findall(text.lower()))


def cosine(a: Counter[str], b: Counter[str]) -> float:
    common = sum(a[k] * b[k] for k in a.keys() & b.keys())
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return common / (da * db) if da and db else 0.0


def chunks(text: str, prefix: str, size: int = 1400) -> list[tuple[str, str]]:
    paragraphs = [re.sub(r"\s+", " ", value).strip()
                  for value in re.split(r"\n\s*\n", text) if value.strip()]
    if len(paragraphs) < 8:
        paragraphs = [re.sub(r"\s+", " ", text[i:i + size]).strip()
                      for i in range(0, len(text), size - 200)]
    return [(f"{prefix}{i:03d}", value[:size])
            for i, value in enumerate(paragraphs) if value]


def retrieve(items: list[tuple[str, str]], query: str,
             n: int = 4) -> list[tuple[str, str]]:
    query_vector = tokens(query)
    ranked = sorted(items, key=lambda item: (-cosine(query_vector, tokens(item[1])),
                                              item[0]))
    return ranked[:n]


def source_quote(row: dict) -> str:
    return (row.get("quote_verbatim") or row.get("quote")
            or row.get("evidence") or "").strip()


def read_jsonl(path: Path) -> dict[str, dict]:
    rows = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["candidate_id"]] = row
    return rows


def append_jsonl(path: Path, row: dict, lock: threading.Lock) -> None:
    with lock, path.open("a") as handle:
        handle.write(json.dumps(row) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path,
                        default=OUT / "cartographer_rebuild_candidates.json")
    parser.add_argument("--fulltext-dir", type=Path, default=DEFAULT_FULLTEXT)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--fulltext-chars", type=int, default=60000)
    parser.add_argument("--passages-per-paper", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--output", type=Path,
                        default=OUT / "cartographer_rebuild_predictions.jsonl")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    candidates = manifest["candidates"][:args.limit or None]
    grounded = json.loads((BUNDLE / "contributions_core_grounded.json").read_text())
    contributions = grounded["contributions"] if isinstance(grounded, dict) else grounded
    by_id = {row["id"]: row for row in contributions}
    context_rows = json.loads((OUT / "citation_map.json").read_text())
    contexts = {(row["citing_id"], row["cited_id"]): row.get("contexts", [])
                for row in context_rows}
    text_cache = {}

    def fulltext(pid: str) -> str:
        if pid not in text_cache:
            path = args.fulltext_dir / f"{safe_id(pid)}.txt"
            text_cache[pid] = (path.read_text(errors="replace")[:args.fulltext_chars]
                               if path.exists() else "")
        return text_cache[pid]

    def packet(candidate: dict) -> tuple[str, dict]:
        ca, cb = by_id[candidate["a"]], by_id[candidate["b"]]
        citation_passages = []
        for citation in candidate["citations"]:
            key = (citation["citing_id"], citation["cited_id"])
            for i, item in enumerate(contexts.get(key, [])[:3], 1):
                citation_passages.append((
                    f"CIT:{citation['citing_id']}->{citation['cited_id']}:{i}",
                    item.get("text", ""),
                ))
        query = " ".join((ca["statement"], cb["statement"],
                          *(text for _, text in citation_passages)))
        pa, pb = paper_id(ca["id"]), paper_id(cb["id"])
        passages_a = retrieve(chunks(fulltext(pa), "A:"), query,
                              args.passages_per_paper)
        passages_b = retrieve(chunks(fulltext(pb), "B:"), query,
                              args.passages_per_paper)
        evidence = [("AQ", source_quote(ca)[:1400]),
                    ("BQ", source_quote(cb)[:1400]),
                    *citation_passages, *passages_a, *passages_b]
        citation_facts = "\n".join(
            f"- {row['citing_id']} cites {row['cited_id']}"
            + ("; localized passages supplied" if row["localized"]
               else "; passage unavailable")
            for row in candidate["citations"]
        ) or "- no citation between these papers in the resolved corpus graph"
        rendered = "\n\n".join(f"[{eid}] {text}" for eid, text in evidence if text)
        prompt = (
            f"CONTRIBUTION A ({ca['id']}): {ca['statement']}\n"
            f"CONTRIBUTION B ({cb['id']}): {cb['statement']}\n\n"
            f"CITATION FACTS:\n{citation_facts}\n\nEVIDENCE:\n{rendered}"
        )
        metadata = {
            "has_fulltext_a": bool(fulltext(pa)), "has_fulltext_b": bool(fulltext(pb)),
            "n_citation_passages": len(citation_passages),
            "n_retrieved_a": len(passages_a), "n_retrieved_b": len(passages_b),
        }
        return prompt, metadata

    packets = {row["candidate_id"]: packet(row) for row in candidates}
    coverage = Counter()
    for _, metadata in packets.values():
        coverage["with_two_fulltexts"] += metadata["has_fulltext_a"] and metadata["has_fulltext_b"]
        coverage["with_citation_passage"] += metadata["n_citation_passages"] > 0
    preflight = {
        "manifest": str(args.manifest), "n_candidates": len(candidates),
        "model": args.model, "fulltext_chars": args.fulltext_chars,
        "passages_per_paper": args.passages_per_paper, **coverage,
    }
    preflight_path = OUT / "cartographer_rebuild_preflight.json"
    preflight_path.write_text(json.dumps(preflight, indent=2))
    print(json.dumps(preflight, indent=2), flush=True)
    if args.prepare_only:
        return

    done = read_jsonl(args.output)
    todo = [row for row in candidates if row["candidate_id"] not in done]
    lock = threading.Lock()

    def label(candidate: dict) -> dict:
        prompt, metadata = packets[candidate["candidate_id"]]
        result = llm.structured(model=args.model, system=SYSTEM, user=prompt,
                                schema=SCHEMA, tool_name="emit_relation",
                                max_tokens=650, timeout=args.timeout, retries=3)
        return {
            "candidate_id": candidate["candidate_id"],
            "a": candidate["a"], "b": candidate["b"],
            "channels": candidate["channels"],
            "citation_directions": [
                [row["citing_id"], row["cited_id"]] for row in candidate["citations"]
            ],
            **metadata, **result,
        }

    print(f"label phase: {len(todo)} remaining / {len(candidates)}", flush=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(label, row): row for row in todo}
        for i, future in enumerate(as_completed(futures), 1):
            candidate = futures[future]
            try:
                row = future.result()
                append_jsonl(args.output, row, lock)
                print(f"[{i}/{len(todo)}] {row['relation']}", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{i}/{len(todo)}] ERROR {candidate['candidate_id']}: {exc}",
                      flush=True)


if __name__ == "__main__":
    main()
