#!/usr/bin/env python3
"""The three QA arms, on the Claude Code subscription (no API key).

Same shape as ../graph_vs_web_ideation/arms.py, retargeted from "propose an idea"
to "answer a researcher's question". Three arms, identical task and blinding:

  • GRAPH arm — the v12 atlas via in-process MCP tools built from `graph_tools`
    (IMPORTED from the ideation folder, never copied). No web.
  • WEB arm   — the SDK's WebSearch + WebFetch. No graph.
  • NULL arm  — no tools at all beyond `submit_answer`: the model's own knowledge.
    This is the true null. Whatever the graph and web arms score, the honest
    question is how much either adds OVER the model answering closed-book, and
    without this arm we cannot say.

`python qa_arms.py --selftest` checks the wiring with NO model call (zero cost).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# reuse the one atlas implementation — do not fork it
IDEATION = Path(__file__).resolve().parents[1] / "graph_vs_web_ideation"
sys.path.insert(0, str(IDEATION))
from graph_tools import GraphAtlas                                  # noqa: E402
from arms import build_graph_server                                 # noqa: E402

from claude_agent_sdk import (                                      # noqa: E402
    query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
    AssistantMessage, ResultMessage, ToolUseBlock,
)

ARMS = ("graph", "web", "null")

# ── output contract every arm must produce ───────────────────────────────────
ANSWER_SCHEMA = {
    "answer": str,
    "papers_named": list[str],
    "confidence": str,
    "limits": str,
}

# BLINDING CONTRACT — an answer must read like a knowledgeable colleague's reply
# and reveal nothing about HOW it was produced. Note the `limits` carve-out: an
# honest limit is about what could not be ESTABLISHED, never about what tools were
# unavailable ("I had no search" would identify the null arm instantly).
_BLIND = (
    "Write the answer as a SELF-CONTAINED reply a colleague could read with no idea "
    "how you produced it. Name prior work by paper title or author, never by an "
    "internal ID. Do NOT mention your tools, your search or exploration process, 'the "
    "graph', 'the corpus', a database, 'web search', node/edge IDs, or how you arrived "
    "at the answer. In `limits`, describe what you could not ESTABLISH about the "
    "question itself — never what tools or sources you did or did not have. Do not "
    "invent papers, findings, or numbers.\n"
    "Write in ordinary scholarly English. Never quote or name a classification label "
    "from any system you consulted — words like 'background', 'uses_extends', "
    "'compares_contrasts', 'builds_on', 'contradicts', 'citation intent', 'edge' or "
    "'relation type' as TECHNICAL TERMS are forbidden, and so is any underscored_token. "
    "Say what is true in plain prose ('cites it only in passing', 'genuinely extends "
    "it', 'reaches the opposite conclusion') — a colleague would never say a paper was "
    "tagged compares_contrasts."
)

TASK = (
    "A researcher asks you the QUESTION below. Answer it.\n\n"
    "Give a direct, concrete answer: name the specific papers involved and state "
    "precisely how they relate to each other and to the question. If the evidence is "
    "mixed, say so and give both sides. If you cannot answer confidently, say that "
    "plainly and say what you WERE able to establish — an honest 'I can't establish "
    "this' is a better answer than a confident vague one, and inventing a plausible "
    "paper is the worst possible answer. Do not pad; a researcher wants the substance.\n\n"
    "Call `submit_answer` EXACTLY ONCE with: `answer` (your reply to the researcher); "
    "`papers_named` (the exact titles of the papers your answer relies on); "
    "`confidence` (high / medium / low); `limits` (one line on what you could not "
    "establish).\n\n"
    + _BLIND + "\n\nQUESTION: {question}"
)

GRAPH_SYS = (
    "You have a structured research atlas to consult, and it rewards traversal over "
    "reading entries in isolation. Two coupled layers:\n"
    "• CONTRIBUTIONS — atomic claims / methods / findings from ~150 papers.\n"
    "• RELATIONS — how they connect: typed semantic edges (builds_on, refines, "
    "supports, contradicts — all four matter equally), each with a stated REASON, plus "
    "the CITATIONS between papers, each tagged with an intent (background / "
    "uses-and-extends / compares-and-contrasts) and a justification for why one paper "
    "cited another. The semantic edges were derived from those citations.\n"
    "Answer the researcher's question from what the structure actually says. "
    "`search_contributions` to find where the question lives, then follow `get_edges` / "
    "`get_neighbors` for typed relations and their reasons, and `get_citations` / "
    "`citations_between` for why papers cite each other. The citation INTENT is often "
    "the whole answer: a paper cited as background is not a paper that builds on the "
    "work. Report what you find, and be straight about what the material does not "
    "cover — if the question is outside it, say so rather than guessing. Present the "
    "answer as ordinary scholarly knowledge, citing papers by name; reveal nothing "
    "about this atlas."
)

WEB_SYS = (
    "You are a researcher with a web browser: use WebSearch/WebFetch and your own "
    "knowledge to answer the question and ground it in real papers. When you write the "
    "answer, cite the papers by name and reveal nothing about your search process."
)

NULL_SYS = (
    "Answer the researcher's question from your own knowledge of the literature. Cite "
    "the papers by name. Be precise about what you actually know versus what you are "
    "inferring, and do not invent papers, findings or numbers to fill a gap."
)

SYS = {"graph": GRAPH_SYS, "web": WEB_SYS, "null": NULL_SYS}


def _submit_tool(holder: dict):
    @tool("submit_answer", "Record your final answer. Call exactly once.", ANSWER_SCHEMA)
    async def submit_answer(args):
        holder["answer"] = {
            "answer": args.get("answer", ""),
            "papers_named": list(args.get("papers_named") or []),
            "confidence": args.get("confidence", ""),
            "limits": args.get("limits", ""),
        }
        return {"content": [{"type": "text", "text": "recorded"}]}
    return submit_answer


def build_options(arm: str, atlas: GraphAtlas | None, holder: dict, *, model: str,
                  max_turns: int, budget_usd: float) -> ClaudeAgentOptions:
    mcp: dict[str, Any] = {"io": create_sdk_mcp_server(name="io",
                                                       tools=[_submit_tool(holder)])}
    allowed = ["mcp__io__submit_answer"]
    if arm == "graph":
        gserver, gnames = build_graph_server(atlas)
        mcp["graph"] = gserver
        allowed = gnames + allowed
    elif arm == "web":
        allowed = ["WebSearch", "WebFetch"] + allowed
    elif arm != "null":                       # null: submit_answer only, by design
        raise ValueError(arm)
    return ClaudeAgentOptions(
        system_prompt=SYS[arm], mcp_servers=mcp, allowed_tools=allowed,
        max_turns=max_turns, model=model, permission_mode="bypassPermissions",
        max_budget_usd=budget_usd,
    )


async def run_one(arm: str, question: str, atlas: GraphAtlas | None, *, model: str,
                  max_turns: int, budget_usd: float) -> dict:
    """Run one question through one arm. Returns the answer + usage metrics."""
    holder: dict = {}
    opts = build_options(arm, atlas, holder, model=model, max_turns=max_turns,
                         budget_usd=budget_usd)
    t0 = time.time()
    tool_calls: list[str] = []
    tool_args: list[dict] = []
    result: ResultMessage | None = None
    async for msg in query(prompt=TASK.format(question=question), options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    tool_calls.append(b.name)
                    # log ARGUMENTS too (the ideation study can't report coverage
                    # because it only logged names — don't repeat that mistake)
                    if not b.name.endswith("submit_answer"):
                        tool_args.append({"tool": b.name, "args": b.input})
        elif isinstance(msg, ResultMessage):
            result = msg
    explore = [t for t in tool_calls if t != "ToolSearch" and not t.endswith("submit_answer")]
    return {
        "arm": arm, "question": question, "answer": holder.get("answer"),
        "completed": holder.get("answer") is not None,
        "tool_calls": tool_calls, "tool_args": tool_args,
        "n_tool_calls": len(tool_calls), "n_explore": len(explore),
        "seconds": round(time.time() - t0, 1),
        "num_turns": getattr(result, "num_turns", None),
        "total_cost_usd": getattr(result, "total_cost_usd", None),
        "usage": getattr(result, "usage", None),
        "stop_reason": getattr(result, "stop_reason", None),
        "is_error": getattr(result, "is_error", None),
    }


def _selftest() -> None:
    """Check all three arms' wiring — no model call, zero cost."""
    atlas = GraphAtlas()
    holder: dict = {}
    for arm in ARMS:
        opts = build_options(arm, atlas, holder, model="claude-sonnet-5",
                             max_turns=12, budget_usd=0.5)
        print(f"{arm:6} allowed_tools={len(opts.allowed_tools):2}  "
              f"servers={sorted(opts.mcp_servers)}  sys={len(opts.system_prompt)} chars")
    assert build_options("null", None, holder, model="m", max_turns=1,
                         budget_usd=0.1).allowed_tools == ["mcp__io__submit_answer"], \
        "null arm must have exactly one tool"
    qs = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))
    print(f"\nquestions: {len(qs['questions'])} "
          f"({sum(q['expected_winner'] == 'graph' for q in qs['questions'])} graph-expected, "
          f"{sum(q['expected_winner'] == 'web' for q in qs['questions'])} control)")
    print("atlas:", atlas.overview()["papers"], "papers /",
          atlas.overview()["contributions"], "contributions")
    print("OK — all three arms wired (no model was called).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    else:
        print("Import from qa_gen.py, or run with --selftest.")
