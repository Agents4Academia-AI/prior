"""Three-way baseline: web-search Claude vs. Prior (and vanilla for reference).

Web search is the *fair* baseline — unlike vanilla it can find real papers, so
the comparison is about what Prior adds on top of "an LLM that can search":
primary-source grounding, structured claims, surfaced contradictions, calibrated
confidence, and an honest "not_found". Writes evals/baseline_websearch.md.

Runs on the claude-code backend (Agent SDK), so no API key needed.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from claude_agent_sdk import (  # noqa: E402
    query, ClaudeAgentOptions, AssistantMessage, TextBlock,
)
from prior import config, navigator  # noqa: E402
from prior.atlas import Atlas  # noqa: E402

QUESTIONS = [
    "Does retrieval-augmented generation reduce hallucination?",
    "Has anyone shown RAG works for clinical decision support?",
    "Has anyone used retrieval-augmented generation for protein structure prediction?",
]


async def _web_search(question: str) -> tuple[str, list[str]]:
    opts = ClaudeAgentOptions(
        system_prompt=("You are a research assistant. Use web search to answer, "
                       "and cite the real sources you used with their URLs."),
        allowed_tools=["WebSearch", "WebFetch"],
        setting_sources=[],
        permission_mode="bypassPermissions",
        max_turns=12,
    )
    chunks, tools = [], []
    try:
        async for msg in query(prompt=question, options=opts):
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        chunks.append(b.text)
                    elif getattr(b, "name", None):
                        tools.append(b.name)
    except Exception as e:  # noqa: BLE001
        if not chunks:
            return f"(web-search error: {e})", tools
    return "".join(chunks), tools


def main() -> None:
    atlas = Atlas.load(config.ATLAS / "atlas.json")
    out = ["# Baseline — web-search Claude vs. Prior", "",
           "_Web search is the fair baseline: it can find real papers. The "
           "question is what Prior adds on top._", ""]
    for q in QUESTIONS:
        print(f"… {q}")
        web, tools = asyncio.run(_web_search(q))
        ans = navigator.ask(atlas, q)
        cited = ", ".join(sorted({c.paper_id for c in ans.used})) or "(none)"
        out += [
            f"## Q: {q}", "",
            f"### Web-search Claude  _(tools: {', '.join(tools) or 'none'})_", "",
            web.strip(), "",
            "### Prior (grounded in primary-source atlas)", "",
            f"**Verdict:** {ans.verdict}", "", ans.render(), "",
            f"**Primary sources cited:** {cited}", "", "---",
        ]
    dest = ROOT / "evals" / "baseline_websearch.md"
    dest.write_text("\n".join(out))
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
