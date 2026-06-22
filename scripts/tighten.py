"""Tighten the corpus to the CORE: re-scope every paper with a STRICT filter that
drops the tangential snowball bloat (systematic-review automation, generic NLP
extraction, domain-science autonomous labs, general agent engines), then rebuild
contributions + relations + the HTML view over the focused set.

One clean job. A fresh cache (scope_strict_cache.jsonl) so it doesn't replay the
old lenient decisions.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src \
        python3 scripts/tighten.py
"""

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
sys.path.insert(0, str(HERE))

from prior import config, pipeline, render_html, scoper   # noqa: E402
from prior.atlas import Atlas                              # noqa: E402
from prior.models import Paper                             # noqa: E402

STRICT_TOPIC = """AI / LLM AGENTS and agentic SYSTEMS for the SCIENTIFIC PROCESS —
ONLY papers whose CORE CONTRIBUTION is an autonomous/agentic system that PERFORMS
a research task, or the RIGOROUS EVALUATION / trust / safety of such systems
("the AI scientist" and how we judge it).

STRICTLY IN SCOPE (the contribution IS the agentic research system or its evaluation):
- autonomous "AI scientist" / end-to-end research agents (idea -> experiment -> paper)
- autonomous experimentation agents where the contribution is the AGENT METHOD
- LLM/agent research-idea or hypothesis generation; automated falsification
- automated / AI-assisted PEER REVIEW; evaluation of review quality
- CITATION verification; CLAIM verification; result / experiment REPRODUCTION agents
- benchmarks / evaluations of LLM-agent RELIABILITY on agentic RESEARCH tasks
- structured scientific CLAIM / CONTRIBUTION / knowledge-graph extraction used to
  assess or organise research findings
- reliability / safety / integrity OF agentic research systems

STRICTLY OUT OF SCOPE (drop even if "AI + science" adjacent):
- SYSTEMATIC-REVIEW / literature-SCREENING automation, technology-assisted review,
  title/abstract screening, search-strategy methods (these are a SEPARATE corpus)
- generic information / entity / relation EXTRACTION or NLP methods not about an
  agentic research system
- DOMAIN-science autonomous-lab / materials / chemistry / biology synthesis papers
  where the contribution is the DISCOVERED science/material, not the agent method
- general LLM / agent capability, orchestration, or engines not tied to a research task
- opinion / ethics / authorship pieces with no concrete system or evaluation
- domain papers that merely USE an LLM as a tool"""


def _log(m):
    print(m, flush=True)


def main():
    pp = config.RAW / "papers.jsonl"
    corpus = [Paper.from_dict(json.loads(l))
              for l in pp.read_text().splitlines() if l]
    _log(f"re-scoping {len(corpus)} papers with the strict CORE filter ...")
    cache = str(config.ATLAS / "scope_strict_cache.jsonl")
    kept, dropped = scoper.scope(STRICT_TOPIC, corpus, batch=20, cache_path=cache,
                                 progress=lambda m: _log("  " + m))
    papers = [p for p, _ in kept]
    _log(f"\nCORE: {len(papers)} kept / {len(dropped)} dropped (from {len(corpus)})")
    yr = Counter(p.year for p in papers if p.year)
    _log("by year: " + " ".join(f"{y}:{yr[y]}" for y in sorted(yr)))

    with pp.open("w") as f:
        for p in papers:
            f.write(json.dumps(p.to_dict()) + "\n")
    a = Atlas(); a.topic = "agents for the scientific process (core)"
    for p in papers:
        a.add_paper(p)
    a.link_citations(); a.save()
    sc = config.ATLAS / "scope.json"
    o = json.loads(sc.read_text()) if sc.exists() else {}
    o["topic"] = STRICT_TOPIC
    o["kept"] = [{"id": p.id, "cite": p.short_cite(), "year": p.year,
                  "title": p.title} for p in papers]
    o["dropped"] = [{"id": p.id, "reason": r} for p, r in dropped]
    o["tightened_from"] = len(corpus)
    o.pop("completeness", None); o.pop("recall_expansion", None)
    sc.write_text(json.dumps(o, indent=2))

    _log("\ncontributions over the core (resumable) ...")
    pipeline.extract_contributions(papers, relate=False, progress=lambda m: _log("  " + m))
    pipeline.relate_contributions_fast(progress=lambda m: _log("  " + m))
    out = render_html.render_contributions()
    _log(f"DONE | core {len(papers)} papers | view {out}")


if __name__ == "__main__":
    main()
