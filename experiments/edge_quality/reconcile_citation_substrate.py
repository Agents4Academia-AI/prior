#!/usr/bin/env python3
"""Reconcile all frozen citation artifacts onto one canonical 152-paper snapshot.

This does not mine or infer new citations. It identity-normalizes the completed
680-edge mining graph and Callum's later resolver atlas, unions them with source
provenance, and emits every ambiguity/unmapped endpoint for audit.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


def norm_doi(value: str | None) -> str:
    return (value or "").lower().replace("https://doi.org/", "").replace("doi:", "").strip()


def arxiv_stem(paper: dict) -> str:
    for field in ("id", "url", "doi", "pdf_url"):
        m = re.search(r"(?:arxiv[:._/]|abs/|pdf/)(\d{4}\.\d{4,5})(?:v\d+)?", str(paper.get(field) or ""), re.I)
        if m:
            return m.group(1)
    return ""


def norm_title(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--papers", type=Path, default=Path("data/prior-core-v0.2/papers_core.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("experiments/edge_quality/out"))
    args = ap.parse_args()

    papers = load_jsonl(args.papers)
    canonical = {p["id"]: p for p in papers}
    indexes: dict[str, dict[str, set[str]]] = {
        "doi": defaultdict(set), "arxiv": defaultdict(set), "title": defaultdict(set)
    }
    for p in papers:
        if d := norm_doi(p.get("doi")): indexes["doi"][d].add(p["id"])
        if a := arxiv_stem(p): indexes["arxiv"][a].add(p["id"])
        if t := norm_title(p.get("title")): indexes["title"][t].add(p["id"])

    resolver_atlas = json.loads((args.out / "atlas_resolved.json").read_text())
    old_papers = {p["id"]: p for p in resolver_atlas["papers"]}
    identity_rows = []
    old_to_new = {}
    for old_id, p in old_papers.items():
        candidates = set()
        evidence = []
        if old_id in canonical:
            candidates.add(old_id); evidence.append("same_id")
        for axis, value in (("doi", norm_doi(p.get("doi"))), ("arxiv", arxiv_stem(p)),
                            ("title", norm_title(p.get("title")))):
            if value and indexes[axis].get(value):
                candidates |= indexes[axis][value]; evidence.append(axis)
        status = "mapped" if len(candidates) == 1 else ("ambiguous" if candidates else "unmapped")
        mapped = next(iter(candidates)) if len(candidates) == 1 else None
        if mapped: old_to_new[old_id] = mapped
        identity_rows.append({"old_id": old_id, "canonical_id": mapped, "status": status,
                              "candidate_ids": sorted(candidates), "evidence_axes": evidence,
                              "title": p.get("title", "")})

    merged: dict[tuple[str, str], set[str]] = defaultdict(set)
    core = json.loads((args.out / "citations_core.json").read_text())
    core_sources = core.get("edge_source", {})
    invalid_core = []
    for src, dst in core["edges"]:
        if src not in canonical or dst not in canonical:
            invalid_core.append([src, dst]); continue
        merged[(src, dst)].add(f"core:{core_sources.get(f'{src}->{dst}', 'unknown')}")

    central_path = args.out / "backfill_central/citations_core.json"
    central = json.loads(central_path.read_text()) if central_path.exists() else {"edges": []}
    invalid_central = []
    for src, dst in central["edges"]:
        if src not in canonical or dst not in canonical:
            invalid_central.append([src, dst]); continue
        if src != dst:
            merged[(src, dst)].add("api_refresh:openalex_or_semanticscholar")

    complete_scan_path = args.out / "citations_fulltext_complete.json"
    complete_scan = json.loads(complete_scan_path.read_text()) if complete_scan_path.exists() else {"edges": []}
    complete_evidence = complete_scan.get("edge_evidence", {})
    invalid_complete_scan = []
    for src, dst in complete_scan["edges"]:
        if src not in canonical or dst not in canonical:
            invalid_complete_scan.append([src, dst]); continue
        if src != dst:
            kinds = complete_evidence.get(f"{src}->{dst}", ["legacy_unspecified"])
            for kind in kinds:
                merged[(src, dst)].add(f"fulltext_complete:{kind}")

    unresolved_resolver_edges = []
    resolver_edge_count = 0
    for edge in resolver_atlas["edges"]:
        if edge.get("relation") != "cites": continue
        resolver_edge_count += 1
        src, dst = old_to_new.get(edge["src"]), old_to_new.get(edge["dst"])
        if not src or not dst:
            unresolved_resolver_edges.append({"src": edge["src"], "dst": edge["dst"],
                                              "evidence": edge.get("evidence")})
            continue
        if src == dst: continue
        merged[(src, dst)].add(f"resolver:{edge.get('evidence', 'unknown')}")

    contexts = json.loads((args.out / "citation_contexts.json").read_text())
    context_keys = set()
    invalid_context_keys = []
    for key in contexts:
        src, dst = key.split("->", 1)
        # Contexts were generated closer to the canonical snapshot; still allow old aliases.
        src2 = src if src in canonical else old_to_new.get(src)
        dst2 = dst if dst in canonical else old_to_new.get(dst)
        if src2 and dst2: context_keys.add((src2, dst2))
        else: invalid_context_keys.append(key)

    edges = []
    for (src, dst), provenance in sorted(merged.items()):
        edges.append({"citing_id": src, "cited_id": dst, "provenance": sorted(provenance),
                      "context_available": (src, dst) in context_keys})
    outdegree = Counter(e["citing_id"] for e in edges)
    indegree = Counter(e["cited_id"] for e in edges)
    isolated = sorted(pid for pid in canonical if not outdegree[pid] and not indegree[pid])
    no_outgoing = sorted(pid for pid in canonical if not outdegree[pid])
    report = {
        "canonical_snapshot": {"papers": len(papers), "unique_ids": len(canonical)},
        "identity_reconciliation": dict(Counter(r["status"] for r in identity_rows)),
        "input_edges": {"core": len(core["edges"]), "resolver_atlas": resolver_edge_count,
                        "fulltext_complete": len(complete_scan["edges"]),
                        "api_refresh": len(central["edges"]),
                        "contexts": len(contexts)},
        "union": {"edges": len(edges),
                  "core_only": sum(all(not p.startswith("resolver:") for p in e["provenance"]) for e in edges),
                  "resolver_only": sum(all(not p.startswith("core:") for p in e["provenance"]) for e in edges),
                  "both_channels": sum(any(p.startswith("core:") for p in e["provenance"]) and
                                       any(p.startswith("resolver:") for p in e["provenance"]) for e in edges),
                  "with_context": sum(e["context_available"] for e in edges),
                  "without_context": sum(not e["context_available"] for e in edges)},
        "coverage": {"isolated_papers": isolated, "n_isolated": len(isolated),
                     "no_outgoing_citations": no_outgoing, "n_no_outgoing": len(no_outgoing)},
        "audit": {"invalid_core_edges": invalid_core,
                  "invalid_complete_scan_edges": invalid_complete_scan,
                  "invalid_api_refresh_edges": invalid_central,
                  "unmapped_resolver_edges": unresolved_resolver_edges,
                  "invalid_context_keys": invalid_context_keys},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "citation_identity_reconciliation.json").write_text(json.dumps(identity_rows, indent=2))
    (args.out / "citations_reconciled.json").write_text(json.dumps({"edges": edges, "report": report}, indent=2))
    (args.out / "citation_reconciliation_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
