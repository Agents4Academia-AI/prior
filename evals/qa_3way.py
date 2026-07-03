"""Show the benefit: Prior vs vanilla Claude vs Claude+web, on super-specific,
provenance-demanding questions.

These are deliberately *not* breadth questions (web search wins those). They
require pinpointing specific results, disagreements, or per-paper contributions
in the corpus — where vanilla fabricates citations and web gives loose prose,
but Prior answers from grounded, traceable claims. Writes evals/qa_3way.md.

Runs on the claude-code backend (no API key).
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "evals"))

from prior import config, llm, navigator  # noqa: E402
from prior.atlas import Atlas  # noqa: E402
from baseline_websearch import _web_search  # noqa: E402  (reuse the web helper)

# Super-specific, provenance-demanding — Prior's grounding should show.
QUESTIONS = [
    # contradiction-surfacing
    "Within this literature, do any works disagree about whether specialized or "
    "fine-tuned RAG outperforms general LLMs for clinical tasks? Name the "
    "specific papers on each side.",
    # precise quantitative provenance
    "What is the largest specific reduction in hallucinated responses reported "
    "for retrieval-augmented dialogue generation, and which paper reports it?",
    # cross-paper contribution synthesis
    "List the distinct retriever-side methods (training or adapting the "
    "retriever, not the generator) that have been proposed, each with its "
    "source paper.",
]

VANILLA_SYS = ("You are a research assistant. Answer concisely and cite the "
               "specific papers (authors, year) that support each point.")


def main() -> None:
    atlas = Atlas.load(config.ATLAS / "atlas.json")
    out = ["# Showing the benefit — Prior vs. vanilla Claude vs. Claude + web", "",
           "_Super-specific, provenance-demanding questions: the answer must be "
           "pinned to specific works. Watch for fabricated citations (vanilla) "
           "and loose, unverifiable prose (web) vs. grounded, cited claims "
           "(Prior)._", ""]
    for q in QUESTIONS:
        print(f"… {q[:60]}")
        vanilla = llm.text(model=config.READER_MODEL, system=VANILLA_SYS, user=q).strip()
        web, tools = asyncio.run(_web_search(q))
        ans = navigator.ask(atlas, q)
        cited = ", ".join(sorted({c.paper_id for c in ans.used})) or "(none)"
        out += [
            f"## Q: {q}", "",
            "### Vanilla Claude", "", vanilla, "",
            f"### Claude + web search  _(tools: {', '.join(tools) or 'none'})_", "",
            web.strip(), "",
            "### Prior (grounded atlas)", "",
            f"**Verdict:** {ans.verdict}", "", ans.render(), "",
            f"**Primary sources cited:** {cited}", "", "---",
        ]
    dest = ROOT / "evals" / "qa_3way.md"
    dest.write_text("\n".join(out))
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
