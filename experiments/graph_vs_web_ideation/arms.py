#!/usr/bin/env python3
"""The two ideation arms, on the Claude Code subscription (no API key).

Both arms use the Claude Agent SDK on your Claude Code login — the credit-free
path. Each is given a topic seed and a tool environment, explores (bounded), then
calls `submit_idea` exactly once. We record the idea + usage (tokens, cost,
wall-clock, tool calls).

  • GRAPH arm — the enriched atlas via in-process MCP tools built from
    `graph_tools.GraphAtlas` (overview / search / get_edges / …). No web.
  • WEB arm   — the SDK's WebSearch + WebFetch. No graph.

This module never runs on its own for real ideas; `gen.py` drives it (with
checkpointing + budget caps). `python arms.py --selftest` exercises the graph MCP
tool shapes with NO model call (zero cost).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from graph_tools import GraphAtlas

from claude_agent_sdk import (
    query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
    AssistantMessage, ResultMessage, ToolUseBlock,
)

# ── output contract every arm must produce ───────────────────────────────────
IDEA_SCHEMA = {
    "title": str, "gap": str, "proposed_study": str,
    "expected_result": str, "grounding": str,
}
# BLINDING CONTRACT (identical for both arms): the submitted idea must read as a
# normal, self-contained research proposal that reveals nothing about HOW it was
# found. Cite real prior work by paper title / author — never by internal ID, and
# never mention tools, "the graph", a database, "web search", or the process.
_BLIND = (
    "Write the idea as a SELF-CONTAINED research proposal a peer could read with no "
    "idea how you produced it. Cite specific prior work by paper title or author "
    "(e.g. 'CycleResearcher (Weng et al.)'), never by an internal ID. Do NOT mention "
    "your tools, your search or exploration process, 'the graph', 'the corpus', a "
    "database, 'web search', node/edge IDs, or how you arrived at the idea. Judge and "
    "state novelty against the BROADER scientific literature, not against any single "
    "source you consulted. Do not invent citations or findings."
)
TASK = (
    "You are a research strategist. Explore the topic below using the tools available "
    "to you, then propose ONE genuinely novel, concrete research direction within it. "
    "Explore efficiently. When ready, call `submit_idea` EXACTLY ONCE with: a short "
    "title; the specific gap; a concrete proposed study; the expected result; and one "
    "line of motivation (why it matters / what prior work grounds it).\n\n"
    "STAY ON TOPIC: the proposal MUST sit squarely within the stated TOPIC. If your "
    "exploration pulls you toward a neighbouring subject, use what you learned but bring "
    "it back to answer THIS topic — do not submit an idea that really belongs to an "
    "adjacent area.\n\n"
    + _BLIND + "\n\nTOPIC: {topic}"
)
GRAPH_SYS = (
    "You have a structured research atlas to explore, and it rewards traversal over "
    "reading entries in isolation. Two coupled layers:\n"
    "• CONTRIBUTIONS — atomic claims / methods / findings from ~150 papers.\n"
    "• RELATIONS — how they connect: typed semantic edges (builds_on, refines, supports, "
    "contradicts — all four matter equally), each with a stated REASON, plus the "
    "CITATIONS between papers, each tagged with an intent (background / uses-and-extends "
    "/ compares-and-contrasts) and a justification for why one paper cited another. The "
    "semantic edges were derived from those citations.\n"
    "Explore broadly and let the structure you actually find shape the idea — do NOT "
    "fixate on one kind of relation or one striking edge, and do not force every idea "
    "into the same mould. Anchor your exploration on the given TOPIC: "
    "`search_contributions` for the topic to find where you are, read a few "
    "contributions, then follow their `get_edges` / `get_neighbors` (relations + reasons) "
    "and `get_citations` / `citations_between` (why papers cite each other) to understand "
    "how THAT area is structured — what builds on what, what is well-supported, what is "
    "refined or disputed, what is still open. Use `overview` only for orientation. Build "
    "the idea from that topic-local structure. When you write the proposal, present it as "
    "ordinary research grounded in the underlying papers (cite them by name) — reveal "
    "nothing about this atlas.")
WEB_SYS = ("You are a researcher with a web browser: use WebSearch/WebFetch and your own "
           "knowledge to find and ground a non-obvious idea. When you write the proposal, "
           "cite the papers by name and reveal nothing about your search process.")


def _ok(payload: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def build_graph_server(atlas: GraphAtlas):
    """Wrap GraphAtlas as in-process MCP tools (server name 'graph')."""
    @tool("overview", "High-level map of the graph: sizes, relation-type counts, "
          "citation-intent counts, most-connected contributions, and example edges of "
          "each relation type.", {})
    async def overview(args): return _ok(atlas.overview())

    @tool("search_contributions", "Keyword search over the 581 contribution "
          "statements. Returns best matches as entry points.", {"query": str})
    async def search(args): return _ok(atlas.search_contributions(args["query"], k=8))

    @tool("get_contribution", "Full detail on one contribution (statement, kind, "
          "grounding quote, paper).", {"contribution_id": str})
    async def get_contribution(args): return _ok(atlas.get_contribution(args["contribution_id"]))

    @tool("get_paper", "A paper's identity, abstract, and its contributions.",
          {"paper_id": str})
    async def get_paper(args): return _ok(atlas.get_paper(args["paper_id"]))

    @tool("get_edges", "The typed relationships around a contribution — relation, "
          "direction, the LLM reason, and citation intent between the papers.",
          {"contribution_id": str})
    async def get_edges(args): return _ok(atlas.get_edges(args["contribution_id"]))

    @tool("get_neighbors", "Brief adjacency list (typed edges only) for a "
          "contribution.", {"contribution_id": str})
    async def get_neighbors(args): return _ok(atlas.get_neighbors(args["contribution_id"]))

    @tool("get_citations", "Walk the citation layer from a paper: what it CITES and "
          "what CITES IT, each with citation intent, support/priority and #sites.",
          {"paper_id": str})
    async def get_citations(args): return _ok(atlas.get_citations(args["paper_id"]))

    @tool("citations_between", "Full citation-intent detail (site justifications + "
          "passages) between two specific papers.", {"paper_id_a": str, "paper_id_b": str})
    async def citations_between(args):
        return _ok(atlas.citations_between(args["paper_id_a"], args["paper_id_b"]))

    tools = [overview, search, get_contribution, get_paper, get_edges,
             get_neighbors, get_citations, citations_between]
    server = create_sdk_mcp_server(name="graph", tools=tools)
    names = [f"mcp__graph__{t.name}" for t in tools]
    return server, names


def _submit_tool(holder: dict):
    @tool("submit_idea", "Record your final research idea. Call exactly once.",
          IDEA_SCHEMA)
    async def submit_idea(args):
        holder["idea"] = {k: args.get(k, "") for k in IDEA_SCHEMA}
        return {"content": [{"type": "text", "text": "recorded"}]}
    return submit_idea


def build_options(arm: str, atlas: GraphAtlas, holder: dict, *, model: str,
                  max_turns: int, budget_usd: float) -> ClaudeAgentOptions:
    submit = _submit_tool(holder)
    io_server = create_sdk_mcp_server(name="io", tools=[submit])
    mcp = {"io": io_server}
    if arm == "graph":
        gserver, gnames = build_graph_server(atlas)
        mcp["graph"] = gserver
        allowed = gnames + ["mcp__io__submit_idea"]
        system = GRAPH_SYS
    elif arm == "web":
        allowed = ["WebSearch", "WebFetch", "mcp__io__submit_idea"]
        system = WEB_SYS
    else:
        raise ValueError(arm)
    return ClaudeAgentOptions(
        system_prompt=system, mcp_servers=mcp, allowed_tools=allowed,
        max_turns=max_turns, model=model, permission_mode="bypassPermissions",
        max_budget_usd=budget_usd,
    )


async def run_one(arm: str, topic: str, atlas: GraphAtlas, *, model: str,
                  max_turns: int, budget_usd: float) -> dict:
    """Run one seed through one arm. Returns idea + usage metrics."""
    holder: dict = {}
    opts = build_options(arm, atlas, holder, model=model, max_turns=max_turns,
                         budget_usd=budget_usd)
    t0 = time.time()
    tool_calls: list[str] = []
    result: ResultMessage | None = None
    async for msg in query(prompt=TASK.format(topic=topic), options=opts):
        if isinstance(msg, AssistantMessage):
            for b in msg.content:
                if isinstance(b, ToolUseBlock):
                    tool_calls.append(b.name)
        elif isinstance(msg, ResultMessage):
            result = msg
    # exploration calls = real environment queries (exclude harness ToolSearch and
    # the final submit_idea); this is the fair per-arm exploration count.
    explore = [t for t in tool_calls if t != "ToolSearch" and not t.endswith("submit_idea")]
    return {
        "arm": arm, "topic": topic, "idea": holder.get("idea"),
        "completed": holder.get("idea") is not None,
        "tool_calls": tool_calls, "n_tool_calls": len(tool_calls),
        "n_explore": len(explore),
        "seconds": round(time.time() - t0, 1),
        "num_turns": getattr(result, "num_turns", None),
        "total_cost_usd": getattr(result, "total_cost_usd", None),
        "usage": getattr(result, "usage", None),
        "stop_reason": getattr(result, "stop_reason", None),
        "is_error": getattr(result, "is_error", None),
    }


def _selftest() -> None:
    """Check the graph MCP wiring + the atlas methods the tools wrap — no model
    call, zero cost."""
    atlas = GraphAtlas()
    _server, names = build_graph_server(atlas)
    print("graph tool names:", names)
    print("overview papers:", atlas.overview()["papers"])
    print("search hit:", atlas.search_contributions("peer review", k=1)[0]["contribution_id"])
    print("OK — graph environment ready (no model was called).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="check tool shapes, no model call")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
    else:
        print("Import this module from gen.py, or run with --selftest.")
