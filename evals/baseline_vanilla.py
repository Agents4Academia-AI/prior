"""Vanilla-Claude baseline vs. Prior, side by side.

Vanilla Claude answers from parametric memory with no grounding; Prior answers
from the atlas with cited papers and an honest "not_found" path. This script
runs both on the same questions and writes evals/baseline_comparison.md.

Goes through prior.llm so it honours PRIOR_LLM_BACKEND (api or claude-code) — so
it runs on a Max login without an API key, same as the rest of the pipeline.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from prior import config, llm, navigator  # noqa: E402
from prior.atlas import Atlas  # noqa: E402

QUESTIONS = [
    "Does retrieval-augmented generation reduce hallucination?",
    "Has anyone shown RAG works for clinical decision support?",
]


def vanilla_claude(question: str) -> str:
    return llm.text(
        model=config.READER_MODEL,
        system="You are a helpful research assistant. Answer concisely.",
        user=question,
    )


def main() -> None:
    atlas_path = config.ATLAS / "atlas.json"
    atlas = Atlas.load(atlas_path) if atlas_path.exists() else None

    out = ["# Baseline comparison — Prior vs. vanilla Claude", ""]
    for q in QUESTIONS:
        print(f"… {q}")
        out += [f"## Q: {q}", "", "### Vanilla Claude (no grounding)", "",
                vanilla_claude(q).strip(), ""]
        if atlas:
            ans = navigator.ask(atlas, q)
            cited = ", ".join(sorted({c.paper_id for c in ans.used})) or "(none)"
            out += ["### Prior (grounded in the atlas)", "",
                    f"**Verdict:** {ans.verdict}", "",
                    ans.render(), "", f"**Papers cited:** {cited}", ""]
        else:
            out += ["### Prior", "", "_No atlas found — run `prior build` first._", ""]
        out.append("---")

    dest = ROOT / "evals" / "baseline_comparison.md"
    dest.write_text("\n".join(out))
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
