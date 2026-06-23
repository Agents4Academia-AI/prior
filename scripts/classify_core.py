"""Two-axis classification of the core, to filter it down to PRIMARY LLM-AGENT
work. For each core paper (title + abstract) a cheap model returns:
  - primary: primary research/evaluation, vs secondary (survey/review/perspective/
    commentary/editorial/opinion/news)
  - scope:   llm_agent | classical_discovery | other

The kept core = primary AND llm_agent. Classical-discovery (the pre-LLM DENDRAL/
BACON/AM lineage) and secondary papers are recorded for separate views — nothing
is deleted. Incremental + resumable.

    PRIOR_LLM_BACKEND=claude-code PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src \
        python3 scripts/classify_core.py --model claude-haiku-4-5-20251001
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))

from prior import config, llm                    # noqa: E402
from prior.models import Paper                     # noqa: E402

SYSTEM = """You classify a paper for a corpus about LLM-AGENT systems acting as AI
scientists — autonomous/agentic research driven by large language models / foundation
models, and the rigorous evaluation of such systems.

Return two fields:
- primary: true if the paper makes a PRIMARY contribution (a new system/method/agent,
  an experiment, a dataset or benchmark, or a rigorous empirical evaluation/study).
  false if it is SECONDARY literature (survey, review, perspective, commentary,
  editorial, opinion, position, or news piece).
- scope:
    "llm_agent"            core contribution is about MODERN LLM / foundation-model
                           agents for the scientific process (LLM-based AI scientists,
                           agentic research pipelines, automated ideation / experiment /
                           review / reproduction with LLMs, or their evaluation/safety).
    "classical_discovery"  pre-LLM symbolic AI / automated scientific discovery
                           (e.g. DENDRAL, BACON, AM/EURISKO, symbolic regression,
                           classical ML for discovery) WITHOUT LLM agents.
    "other"                off-topic for an LLM-agent AI-scientist corpus."""

_SCHEMA = {
    "type": "object",
    "properties": {
        "primary": {"type": "boolean"},
        "scope": {"type": "string", "enum": ["llm_agent", "classical_discovery", "other"]},
    },
    "required": ["primary", "scope"],
}


def _log(m):
    print(m, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    args = ap.parse_args()

    corpus = {p.id: p for p in (
        Paper.from_dict(json.loads(l))
        for l in (config.RAW / "papers.jsonl").read_text().splitlines() if l)}
    core_ids = json.load(open(config.ATLAS / "core_scope.json"))["core_ids"]
    out = config.ATLAS / "core_classification.json"
    done = json.load(open(out)) if out.exists() else {}

    for n, pid in enumerate(core_ids, 1):
        if pid in done or pid not in corpus:
            continue
        p = corpus[pid]
        try:
            c = llm.structured(
                model=args.model, system=SYSTEM,
                user=f"TITLE: {p.title}\nYEAR: {p.year}\nABSTRACT: {p.abstract}",
                schema=_SCHEMA, tool_name="classify", max_tokens=200)
        except Exception as e:  # noqa: BLE001
            _log(f"  [{n}/{len(core_ids)}] {p.short_cite()}: ERROR {e}")
            continue
        done[pid] = {"primary": bool(c.get("primary")), "scope": c.get("scope", "other"),
                     "cite": p.short_cite(), "year": p.year, "title": p.title}
        out.write_text(json.dumps(done, indent=2))           # incremental
        if n % 20 == 0:
            _log(f"  classified {n}/{len(core_ids)} ...")

    keep = [i for i, c in done.items() if c["primary"] and c["scope"] == "llm_agent"]
    sec = [c for c in done.values() if not c["primary"]]
    classical = [c for c in done.values() if c["primary"] and c["scope"] == "classical_discovery"]
    other = [c for c in done.values() if c["primary"] and c["scope"] == "other"]
    done["_keep"] = keep
    out.write_text(json.dumps(done, indent=2))

    _log(f"\nclassified {len(core_ids)} core papers:")
    _log(f"  KEEP (primary llm_agent) : {len(keep)}")
    _log(f"  drop secondary (survey/perspective/...): {len(sec)}")
    _log(f"  drop classical_discovery (pre-LLM lineage): {len(classical)}")
    _log(f"  drop other/off-topic: {len(other)}")
    _log("\n-- classical lineage (would move to ancestry view) --")
    for c in sorted(classical, key=lambda c: c.get("year") or 0)[:25]:
        _log(f"   {c.get('year')}  {(c.get('title') or '')[:64]}")
    _log("\n-- secondary (would move to survey layer) --")
    for c in sec[:25]:
        _log(f"   - {(c.get('title') or '')[:70]}")


if __name__ == "__main__":
    main()
