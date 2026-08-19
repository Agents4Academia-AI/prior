"""Preliminary, auditable subarea coverage figure for matched search systems."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from product_disagreement import identity  # noqa: E402


TAXONOMY = {
    "End-to-end agents & experimentation": (
        "ai scientist", "autonomous scientist", "autonomous research", "agent laboratory",
        "automated scientific discovery", "autonomous experiment", "automated experiment",
        "laboratory automation", "self driving laboratory", "robotic lab"),
    "Hypotheses, ideas & novelty": (
        "hypothesis generation", "hypothesis discovery", "hypothesis validation",
        "falsification", "research idea", "idea generation", "novelty assessment",
        "novel research", "scientific creativity"),
    "Literature search & synthesis": (
        "literature search", "literature review", "systematic review", "evidence synthesis",
        "scientific literature", "paperqa", "retrieval augmented", "research assistant",
        "citation recommendation", "information retrieval"),
    "Peer review & research evaluation": (
        "peer review", "paper review", "reviewer", "manuscript evaluation",
        "research evaluation", "paper scoring", "acceptance decision"),
    "Verification, integrity & reproducibility": (
        "reproduc", "replicat", "verification", "fact check", "claim verification",
        "citation verification", "hallucinated citation", "plagiarism", "integrity",
        "error detection", "scientific misconduct", "retraction"),
    "Knowledge extraction & representation": (
        "knowledge graph", "claim extraction", "information extraction", "ontology",
        "taxonomy", "structured contribution", "scientific entity", "relation extraction",
        "data extraction"),
    "Writing & communication": (
        "scientific writing", "paper writing", "manuscript generation", "academic writing",
        "citation generation", "text generation", "research communication"),
    "Benchmarks, safety & governance": (
        "benchmark", "evaluation framework", "risk", "safety", "governance",
        "responsible ai", "audit", "reliability", "trustworthy"),
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def aliases_in(rows: list[dict]) -> set[str]:
    return {alias for row in rows for alias in identity(row.get("paper", row))}


def classify(paper: dict) -> tuple[str, str, int]:
    text = " ".join((paper.get("title") or "", paper.get("abstract") or "")).lower()
    title = (paper.get("title") or "").lower()
    scores = {}
    evidence = {}
    for area, terms in TAXONOMY.items():
        hits = [term for term in terms if term in text]
        scores[area] = sum(3 if term in title else 1 for term in hits)
        evidence[area] = hits
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "Other / ambiguous", "", 0
    return best, "; ".join(evidence[best]), scores[best]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scoper", type=Path, required=True)
    ap.add_argument("--targets", type=Path, required=True)
    ap.add_argument("--scoper-not-elicit", type=Path, required=True)
    ap.add_argument("--scoper-not-undermind", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args(); args.out_dir.mkdir(parents=True, exist_ok=True)

    scoper = read_jsonl(args.scoper)
    targets = read_jsonl(args.targets)
    not_e = aliases_in(read_jsonl(args.scoper_not_elicit))
    not_u = aliases_in(read_jsonl(args.scoper_not_undermind))
    rows = []
    for paper in scoper:
        ids = identity(paper); area, evidence, score = classify(paper)
        rows.append({"title": paper.get("title", ""), "year": paper.get("year", ""),
                     "subarea": area, "classification_evidence": evidence,
                     "classification_score": score, "scoper": 1,
                     "elicit": int(not bool(ids & not_e)),
                     "undermind": int(not bool(ids & not_u)), "origin": "scoper_v1"})
    for target in targets:
        paper = target["paper"]; area, evidence, score = classify(paper)
        products = set(target["products"])
        rows.append({"title": paper.get("title", ""), "year": paper.get("year", ""),
                     "subarea": area, "classification_evidence": evidence,
                     "classification_score": score, "scoper": 0,
                     "elicit": int("elicit" in products),
                     "undermind": int("undermind" in products), "origin": "external_only"})

    fields = list(rows[0])
    with (args.out_dir / "subarea-assignments.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)

    import matplotlib.pyplot as plt
    import numpy as np

    systems = [("Scoper v1", "scoper"), ("Elicit", "elicit"), ("Undermind", "undermind")]
    counts = Counter(row["subarea"] for row in rows)
    areas = sorted(counts, key=lambda x: (-counts[x], x))
    values = np.array([[sum(r[key] for r in rows if r["subarea"] == area) / counts[area]
                        for key in [s[1] for s in systems]] for area in areas])

    fig, ax = plt.subplots(figsize=(9.2, 6.8))
    image = ax.imshow(values, cmap="magma", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(3), [s[0] for s in systems], fontsize=11)
    ax.set_yticks(range(len(areas)), [f"{a}  (n={counts[a]})" for a in areas], fontsize=9.5)
    for i, area in enumerate(areas):
        for j, (_, key) in enumerate(systems):
            found = sum(r[key] for r in rows if r["subarea"] == area)
            color = "white" if values[i, j] < .62 else "#16131d"
            ax.text(j, i, f"{found}/{counts[area]}\n{values[i,j]:.0%}", ha="center", va="center",
                    fontsize=9, color=color, fontweight="semibold")
    ax.set_title("Search systems expose different regions of the AI-for-science literature",
                 loc="left", fontsize=14, fontweight="bold", pad=18)
    ax.text(0, 1.015, "Coverage within the union of 152 Scoper-v1 works and 192 eligible pre-cutoff external works",
            transform=ax.transAxes, fontsize=9.5, color="#55505e")
    ax.tick_params(length=0); [sp.set_visible(False) for sp in ax.spines.values()]
    cbar = fig.colorbar(image, ax=ax, fraction=.025, pad=.035)
    cbar.set_label("Share of subarea retrieved", fontsize=9)
    fig.text(.01, .01, "Preliminary: deterministic title/abstract taxonomy; assignments are exported for audit and later blinded validation.",
             fontsize=8.5, color="#625c69")
    fig.tight_layout(rect=(0, .035, 1, 1))
    fig.savefig(args.out_dir / "system-coverage-by-subarea.png", dpi=220, bbox_inches="tight")
    fig.savefig(args.out_dir / "system-coverage-by-subarea.pdf", bbox_inches="tight")
    summary = {"works": len(rows), "subareas": counts, "classification": "deterministic preliminary",
               "inputs": {k: str(v) for k, v in vars(args).items() if isinstance(v, Path)}}
    (args.out_dir / "status.json").write_text(json.dumps(summary, indent=2, default=dict) + "\n")


if __name__ == "__main__":
    main()
