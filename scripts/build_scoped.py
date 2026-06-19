"""Build a clean, scoped corpus + contributions graph for the hackathon topic.

  Scoper (seed → gather → LLM relevance filter) → clean papers
        → papers-only atlas → Contribution agent (full text) → one-shot relate.

Seeds explicitly cover the cohort's project areas (citation / claim / empirical
verification, auto-review, PKM) AND Prior's own related work, plus LLM-proposed
queries for recall.

Run (writes to a separate data dir so it doesn't touch the committed demo snapshot):
    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon \
        PYTHONPATH=src python3 scripts/build_scoped.py
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from prior import config, pipeline, scoper          # noqa: E402
from prior.atlas import Atlas                        # noqa: E402

TOPIC = """AI / LLM AGENTS and agentic SYSTEMS for the SCIENTIFIC PROCESS — tools
that help researchers do research, or that autonomously perform research tasks,
AND the evaluation of such systems. Meta-research: the tools, evaluation, and
workflows by which science is done. Pillars: Trust & Evaluation, Efficiency,
Translation, Acceleration.

IN SCOPE (paper proposes / builds / rigorously evaluates such a system for a
research task):
- literature management / review / synthesis; research-idea or hypothesis
  generation; novelty / contribution assessment
- autonomous experimentation / "AI scientist" (autonomous chemistry/biology/ML)
- scientific writing / paper drafting; automated or AI-assisted PEER REVIEW
- CITATION verification; CLAIM verification; result/empirical REPRODUCTION
- structured scientific claim / contribution / knowledge-graph extraction
- personal knowledge management / research assistants for researchers
- grant / funding discovery; research coordination / matchmaking
- benchmarks / evaluations of LLM/agent RELIABILITY on agentic research tasks

OUT OF SCOPE: ChatGPT/LLMs in education / classroom / student-assessment /
academic-integrity; general LLM capability / finetuning / benchmark papers not
tied to a research task; domain-science papers that merely USE an LLM/tool;
scientific software / libraries / databases (NumPy, PRISMA, STRING); broad
opinion / ethics / agenda pieces with no concrete system."""

# Seeds covering the cohort's projects + Prior's related work (recall anchors).
SEEDS = [
    # AI scientist / autonomous research
    "fully automated scientific discovery AI scientist agent",
    "autonomous experimentation laboratory large language models chemistry",
    # idea / hypothesis generation, novelty
    "research idea generation large language models",
    "scientific hypothesis generation LLM",
    "novelty assessment research papers large language models",
    # literature management / review / PKM (Lit Buddy, Team 3)
    "automated literature review agent large language models",
    "personal knowledge management research assistant LLM",
    "retrieval augmented generation scientific literature question answering",
    # citation verification (cohort project)
    "citation verification accuracy large language models",
    # claim verification (cohort project + Prior)
    "scientific claim verification evidence SciFact",
    "fact checking scientific claims natural language",
    # empirical / paper verification, reproducibility (cohort project)
    "reproducibility machine learning experiments replication",
    "detecting errors in scientific papers automated",
    # auto review (cohort project)
    "automated peer review generation large language models",
    "AI reviewer scientific paper feedback",
    # Prior's area: structured claims / contributions / knowledge graphs
    "scientific knowledge graph claims contributions extraction",
    "open research knowledge graph structured contributions",
    "evidence synthesis automated systematic review LLM",
]

CAP = 60  # cap kept papers for a tractable first build


def main():
    config.ensure_dirs()
    print(f"data dir: {config.DATA}\n[1/5] proposing extra queries ...", flush=True)
    seeds = list(dict.fromkeys(SEEDS + scoper.propose_queries(TOPIC)))
    print(f"      {len(seeds)} seed queries total", flush=True)

    print("[2/5] gathering candidates ...", flush=True)
    cands = scoper.gather_candidates(seeds, per_query=20, progress=lambda m: None)
    print(f"      {len(cands)} candidates", flush=True)

    print("[3/3] scoping (LLM relevance filter) ...", flush=True)
    kept, dropped = scoper.scope(TOPIC, cands, progress=lambda m: print("   "+m, flush=True))
    papers = [p for p, _ in kept]          # FULL relevant set — no citation cap
    print(f"      kept {len(papers)} / dropped {len(dropped)}", flush=True)

    # cache full scoped corpus for inspection (coverage checkpoint)
    with (config.RAW / "papers.jsonl").open("w") as f:
        for p in papers:
            f.write(json.dumps(p.to_dict()) + "\n")
    a = Atlas(); a.topic = "agents for the scientific process"
    for p in papers:
        a.add_paper(p)
    a.link_citations(); a.save()
    (config.ATLAS / "scope.json").write_text(json.dumps({
        "topic": TOPIC,
        "kept": [{"id": p.id, "cite": p.short_cite(), "year": p.year,
                  "cited_by": p.cited_by_count, "title": p.title} for p in papers],
        "dropped": [{"id": p.id, "reason": r} for p, r in dropped],
    }, indent=2))

    yrs = Counter(p.year for p in papers if p.year)
    print("\n=== SCOPED CORPUS (coverage checkpoint) ===", flush=True)
    print("by year: " + " ".join(f"{y}:{yrs[y]}" for y in sorted(yrs)), flush=True)

    if os.environ.get("BUILD_CONTRIBUTIONS") != "1":
        print("\nScope-only. Inspect data_hackathon/atlas/scope.json. "
              "To build contributions: set BUILD_CONTRIBUTIONS=1 (will cap by recency).",
              flush=True)
        return

    # build phase — cap by RECENCY (this field is recent), not citations
    papers = sorted(papers, key=lambda p: (p.year or 0), reverse=True)[:CAP]
    print(f"\n[build] contributions over {len(papers)} most-recent papers ...", flush=True)
    pipeline.extract_contributions(papers, relate=False,
                                   progress=lambda m: print("   "+m, flush=True))
    pipeline.relate_contributions_fast(progress=lambda m: print("   "+m, flush=True))
    print("DONE.", flush=True)


if __name__ == "__main__":
    main()
