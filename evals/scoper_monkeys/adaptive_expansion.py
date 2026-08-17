"""Resumable post-retrieval expansion for an exhaustive Scoper run.

The stages deliberately separate bibliographic evidence and citation topology
from semantic geometry.  ``prepare-embedding`` writes a model-neutral bundle;
embedding/model selection and query-map induction happen on the GPU machine.
Gold targets are never read here.  Recovery is scored by the existing offline
scorer after each immutable stage snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import fulltext, scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import arxiv, openalex, semanticscholar  # noqa: E402


USEFUL_ROLES = ("eligible", "retrieval_only", "uncertain")


def _read_role(path: Path) -> list[tuple[Paper, dict]]:
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    return [(Paper.from_dict(row["paper"]), row["decision"]) for row in rows]


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _receipt(out_dir: Path, stage: str, inputs: list[Path], outputs: list[Path],
             *, deterministic: bool, parameters: dict | None = None) -> None:
    """Write an auditable stage receipt after outputs have been closed."""
    receipt = {
        "stage": stage, "status": "complete", "deterministic": deterministic,
        "parameters": parameters or {},
        "inputs": [{"path": str(p), "sha256": _sha256(p)} for p in inputs if p.exists()],
        "outputs": [{"path": str(p), "sha256": _sha256(p)} for p in outputs if p.exists()],
    }
    (out_dir / f"stage-{stage}.json").write_text(json.dumps(receipt, indent=2) + "\n")


def _doi(paper: Paper) -> str:
    return (paper.doi or "").replace("https://doi.org/", "").replace("doi:", "")


def _arxiv_id(paper: Paper) -> str:
    for item in paper.all_manifestations():
        pid = str(item.get("id") or "")
        if pid.startswith("arxiv:"):
            return pid.split(":", 1)[1].split("v", 1)[0]
    return ""


def _merge_evidence(original: Paper, variants: list[Paper]) -> Paper:
    """Retain canonical identity/topology, adopting richer verified evidence."""
    valid = [v for v in variants if scoper._same_work(original, v)]
    if not valid:
        return original
    richest = max([original] + valid, key=lambda p: len(p.abstract or ""))
    if len(richest.abstract or "") > len(original.abstract or ""):
        original.abstract = richest.abstract
    for variant in valid:
        if not original.pdf_url and variant.pdf_url:
            original.pdf_url = variant.pdf_url
        if not original.doi and variant.doi:
            original.doi = variant.doi
        for item in variant.all_manifestations():
            if item.get("id") != original.id and item not in original.manifestations:
                original.manifestations.append(item)
    return original


def repair(run_dir: Path, out_dir: Path, *, use_s2: bool = False,
           probe_s2: bool = False, progress=print) -> None:
    """Repair uncertain records through exact identifiers and manifestations.

    The optional S2 channel is circuit-broken: one credentialed probe must pass
    before any further S2 requests are attempted.
    """
    uncertain = _read_role(run_dir / "uncertain.jsonl")
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger = out_dir / "repair-ledger.jsonl"
    completed = set()
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            try:
                row = json.loads(line)
                if row.get("event") == "repair_terminal":
                    completed.add(row["work_key"])
            except (ValueError, KeyError):
                pass

    s2_ok = False
    # One arXiv export call repairs all already-known arXiv manifestations.  Do
    # not issue one request per record (both slower and less polite).
    arxiv_ids = list(dict.fromkeys(_arxiv_id(p) for p, _ in uncertain if _arxiv_id(p)))
    arxiv_variants = arxiv.fetch_ids(arxiv_ids) if arxiv_ids else {}
    if use_s2 and probe_s2:
        probe = next((p for p, _ in uncertain if _doi(p) or _arxiv_id(p)), None)
        if probe:
            sid = "ARXIV:" + _arxiv_id(probe) if _arxiv_id(probe) else "DOI:" + _doi(probe)
            try:
                s2_ok = semanticscholar.fetch(sid) is not None
            except Exception:  # adapter has already exhausted/paced retries
                s2_ok = False
    with ledger.open("a") as handle:
        if use_s2:
            handle.write(json.dumps({"event": "source_probe", "source": "semanticscholar",
                                     "status": "available" if s2_ok else "circuit_open"}) + "\n")
            handle.flush()
        for index, (paper, old_decision) in enumerate(uncertain, 1):
            key = paper.key()
            if key in completed:
                continue
            before = len(paper.abstract or "")
            variants: list[Paper] = []
            aid = _arxiv_id(paper)
            if aid:
                candidate = arxiv_variants.get(aid) or arxiv_variants.get("arxiv:" + aid)
                if candidate:
                    variants.append(candidate)
            if _doi(paper):
                candidate = openalex.fetch_doi(_doi(paper))
                if candidate:
                    variants.append(candidate)
                if s2_ok:
                    candidate = semanticscholar.fetch("DOI:" + _doi(paper))
                    if candidate:
                        variants.append(candidate)
            elif aid and s2_ok:
                candidate = semanticscholar.fetch("ARXIV:" + aid)
                if candidate:
                    variants.append(candidate)
            paper = _merge_evidence(paper, variants)
            row = {"event": "repair_terminal", "work_key": key,
                   "old_decision": old_decision, "paper": paper.to_dict(),
                   "abstract_chars_before": before,
                   "abstract_chars_after": len(paper.abstract or ""),
                   "evidence_changed": len(paper.abstract or "") > before,
                   "sources_attempted": ["arxiv", "openalex"] + (["semanticscholar"] if s2_ok else [])}
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            if index % 25 == 0:
                progress(f"repair {index}/{len(uncertain)}")

    terminals = {}
    for line in ledger.read_text().splitlines():
        row = json.loads(line)
        if row.get("event") == "repair_terminal":
            terminals[row["work_key"]] = row
    repaired = [Paper.from_dict(row["paper"]) for row in terminals.values()]
    changed = sum(row["evidence_changed"] for row in terminals.values())
    _write_jsonl(out_dir / "repaired-uncertain.jsonl",
                 ({"paper": p.to_dict()} for p in repaired))
    (out_dir / "repair-status.json").write_text(json.dumps({
        "records": len(repaired), "evidence_changed": changed,
        "still_missing_abstract": sum(not p.abstract for p in repaired),
        "semantic_scholar": "available" if s2_ok else "circuit_open",
        "next": "reassess repaired-uncertain with scope_exhaustive",
    }, indent=2) + "\n")
    _receipt(out_dir, "repair_metadata", [run_dir / "uncertain.jsonl"],
             [ledger, out_dir / "repaired-uncertain.jsonl", out_dir / "repair-status.json"],
             deterministic=False,
             parameters={"sources": ["arxiv", "openalex"] + (["semanticscholar"] if s2_ok else []),
                         "s2_circuit": "closed" if s2_ok else "open"})


def _screening_excerpt(text: str, *, limit: int = 12000) -> tuple[str, str]:
    """Deterministically select scope evidence from retrieved full text.

    Prefer an explicit abstract section. Otherwise retain a labelled leading
    excerpt; this is evidence repair, not a claim that the excerpt is an abstract.
    """
    normalized = text.replace("\r", "\n")
    match = re.search(
        r"(?is)(?:^|\n)\s*abstract\s*\n+(.*?)(?=\n\s*(?:1\.?\s+)?(?:introduction|keywords?)\b)",
        normalized,
    )
    if match and len(match.group(1).strip()) >= 80:
        return match.group(1).strip()[:limit], "fulltext_abstract_section"
    return normalized.strip()[:limit], "fulltext_leading_excerpt"


def repair_fulltext(run_dir: Path, out_dir: Path, *, workers: int = 6,
                    progress=print) -> None:
    """Retrieve legal OA text for abstract-missing uncertain works and inventory it."""
    source = out_dir / "repaired-uncertain.jsonl"
    if source.exists():
        papers = [Paper.from_dict(json.loads(line)["paper"])
                  for line in source.read_text().splitlines() if line]
    else:
        papers = [paper for paper, _ in _read_role(run_dir / "uncertain.jsonl")]
    missing = [paper for paper in papers if not paper.abstract]
    channels = fulltext.fetch_many(missing, workers=workers, progress=progress)
    rows = []
    repaired = 0
    for paper in papers:
        text, channel = fulltext.fetch_with_source(paper)
        evidence, evidence_type = ("", "unavailable")
        if not paper.abstract and text:
            evidence, evidence_type = _screening_excerpt(text)
            repaired += 1
        rows.append({"paper": paper.to_dict(), "screening_evidence": evidence,
                     "evidence_type": evidence_type, "channel": channel,
                     "text_sha256": hashlib.sha256(text.encode()).hexdigest() if text else ""})
    evidence_file = out_dir / "fulltext-repair.jsonl"
    _write_jsonl(evidence_file, rows)
    status_file = out_dir / "fulltext-repair-status.json"
    status_file.write_text(json.dumps({
        "attempted": len(missing), "screening_evidence_recovered": repaired,
        "still_without_evidence": sum(not r["paper"].get("abstract") and
                                      not r["screening_evidence"] for r in rows),
        "channels": channels,
    }, indent=2) + "\n")
    _receipt(out_dir, "repair_fulltext", [source if source.exists() else run_dir / "uncertain.jsonl"],
             [evidence_file, status_file], deterministic=False,
             parameters={"workers": workers, "legal_open_access_only": True,
                         "excerpt_algorithm": "abstract-section-else-leading-12000-v1"})


def prepare_embedding(run_dir: Path, out_dir: Path) -> None:
    """Write the semantic corpus and leakage-safe GPU model-selection protocol."""
    records = []
    for role in USEFUL_ROLES:
        for paper, decision in _read_role(run_dir / f"{role}.jsonl"):
            text = f"{paper.title}\n\n{paper.abstract}".strip()
            records.append({
                "work_key": paper.key(), "role": role, "title": paper.title,
                "abstract": paper.abstract, "text": text,
                "year": paper.year, "source": paper.source,
                "decision_criterion": decision.get("criterion", ""),
                "decision_reason": decision.get("reason", ""),
                "provenance": {"stage": "depth_200", "gold_visible": False},
            })
    _write_jsonl(out_dir / "semantic-corpus.jsonl", records)
    protocol = {
        "purpose": "choose geometry for evolving query-map induction, not generic retrieval",
        "gold_visible_during_model_selection": False,
        "candidate_models": "specified on GPU machine; record exact model/revision/pooling/normalization",
        "required_comparisons": [
            "domain scientific-document embedding model",
            "strong general retrieval embedding model",
            "lexical BM25 baseline",
        ],
        "intrinsic_checks": [
            "neighbour coherence by blinded human audit",
            "stability across seeds and clustering resolutions",
            "separation without collapsing eligible/retrieval_only/uncertain roles",
            "minority-community preservation",
        ],
        "downstream_checks": [
            "novel eligible yield per induced query branch",
            "hidden-target recovery scored only after branch freeze",
            "boundary disagreement rate under strict synthesis scope",
            "stopping-curve sensitivity to model choice",
        ],
        "selection_rule": "freeze model and query branches before joining hidden recovery targets",
        "corpus_sha256": hashlib.sha256((out_dir / "semantic-corpus.jsonl").read_bytes()).hexdigest(),
    }
    (out_dir / "embedding-experiment.json").write_text(json.dumps(protocol, indent=2) + "\n")
    _receipt(out_dir, "prepare_embedding", [run_dir / f"{r}.jsonl" for r in USEFUL_ROLES],
             [out_dir / "semantic-corpus.jsonl", out_dir / "embedding-experiment.json"],
             deterministic=True)


def citation_queue(run_dir: Path, out_dir: Path) -> None:
    """Place every useful canonical work in both citation directions."""
    tasks = []
    seen = set()
    for role in USEFUL_ROLES:
        for paper, decision in _read_role(run_dir / f"{role}.jsonl"):
            key = paper.key()
            if key in seen:
                continue
            seen.add(key)
            for direction in ("backward", "forward"):
                tasks.append({
                    "task_id": hashlib.sha256(f"{key}|{direction}".encode()).hexdigest()[:20],
                    "work_key": key, "paper": paper.to_dict(), "role": role,
                    "direction": direction, "status": "pending",
                    "priority_signals": {
                        "uncertain": role == "uncertain",
                        "citation_count": paper.cited_by_count,
                        "year": paper.year,
                        "has_openalex_topology": paper.id.startswith("openalex:"),
                    },
                    "decision_criterion": decision.get("criterion", ""),
                })
    tasks.sort(key=lambda x: (
        not x["priority_signals"]["uncertain"],
        not x["priority_signals"]["has_openalex_topology"],
        -x["priority_signals"]["citation_count"],
    ))
    _write_jsonl(out_dir / "citation-queue.jsonl", tasks)
    (out_dir / "citation-queue-status.json").write_text(json.dumps({
        "works": len(seen), "tasks": len(tasks), "directions": ["backward", "forward"],
        "policy": "all useful records queued; priority controls order, never eligibility",
        "terminal_states": ["exhausted", "pending_retry", "source_unavailable"],
    }, indent=2) + "\n")
    _receipt(out_dir, "citation_queue", [run_dir / f"{r}.jsonl" for r in USEFUL_ROLES],
             [out_dir / "citation-queue.jsonl", out_dir / "citation-queue-status.json"],
             deterministic=True)


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("repair", "repair-fulltext", "prepare-embedding", "citation-queue"):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True, type=Path)
        p.add_argument("--out-dir", required=True, type=Path)
        if name == "repair":
            p.add_argument("--use-s2", action="store_true")
            p.add_argument("--probe-s2", action="store_true")
        if name == "repair-fulltext":
            p.add_argument("--workers", type=int, default=6)
    return ap


if __name__ == "__main__":
    args = parser().parse_args()
    if args.command == "repair":
        repair(args.run_dir, args.out_dir, use_s2=args.use_s2, probe_s2=args.probe_s2)
    elif args.command == "repair-fulltext":
        repair_fulltext(args.run_dir, args.out_dir, workers=args.workers)
    elif args.command == "prepare-embedding":
        prepare_embedding(args.run_dir, args.out_dir)
    else:
        citation_queue(args.run_dir, args.out_dir)
