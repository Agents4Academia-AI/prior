#!/usr/bin/env python3
"""The three QA arms, on the Claude Code subscription (no API key).  [v2]

Three arms, identical task and blinding:

  • GRAPH arm — the v12 atlas via in-process MCP tools. No web, no shell.
  • WEB arm   — WebSearch + WebFetch only. No graph.
  • NULL arm  — no tools at all beyond `submit_answer`: the model's own knowledge.
    The true null: whatever graph and web score, the honest question is how much
    either adds OVER the model answering closed-book.

WHAT CHANGED IN v2 (see ../TOOL_SURFACE_V2.md for the measurements)
-------------------------------------------------------------------
1. THE ARMS ARE NOW SEALED. `allowed_tools` is a PERMISSION allowlist, not a
   tool-surface restriction — that is the separate `tools=` field. v1 set only the
   former and ran `permission_mode="bypassPermissions"`, so every default Claude
   Code tool was live in every arm. It bit us: the v1 q02 GRAPH run opened with
   `Skill(prior)` and `Bash(python -m prior.cli info)`, and the NULL arm had
   WebSearch available throughout (it happened not to call it). v2 pins `tools=`,
   `setting_sources=[]` and `skills=[]`, and adds `disallowed_tools` as a second
   line of defence. `_selftest` asserts all of it, and `run_one` records an
   `off_arm_tools` canary on every row.

2. THE GRAPH SURFACE IS NOW PAPER-SHAPED. Every question here is paper-level
   ("which papers build on X?") but every v1 traversal tool was contribution-level,
   so the agent spent turns reassembling paper facts the atlas already holds — 15
   calls / 59k chars on q01, two of them returning `[]`. `find_paper` and
   `paper_neighbourhood` do that aggregation in Python, where it is free.

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

from claude_agent_sdk import (                                      # noqa: E402
    ClaudeSDKClient, tool, create_sdk_mcp_server, ClaudeAgentOptions,
    AssistantMessage, UserMessage, ResultMessage, TextBlock, ToolUseBlock,
    ToolResultBlock,
)

ARMS = ("graph", "web", "null")

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
    "Work efficiently: reach for the broadest tool that answers the question before "
    "drilling into specifics, and stop EXPLORING once you have what you need.\n\n"
    "You deliver the answer by calling `submit_answer` EXACTLY ONCE with: `answer` "
    "(your reply to the researcher); `papers_named` (the exact titles of the papers "
    "your answer relies on); `confidence` (high / medium / low); `limits` (one line "
    "on what you could not establish).\n\n"
    + _BLIND + "\n\nQUESTION: {question}\n\n"
    # v2: the first v2 run explored correctly, then wrote the answer as prose and
    # ended the turn without ever calling the tool. Prose is not an answer here.
    "Do not write your reply as ordinary text — text is discarded. The ONLY way to "
    "deliver it is the `submit_answer` tool call. Make that call now."
)

# Sent if the model finishes a turn without having called `submit_answer`. Applied
# identically to all three arms, and counted on the row as `n_nudges`, so it cannot
# quietly advantage one environment over another.
NUDGE = (
    "You have not called `submit_answer`, so nothing has been recorded and the "
    "researcher has received nothing. Call `submit_answer` now with your answer, "
    "`papers_named`, `confidence` and `limits`. If you were unable to establish an "
    "answer, submit that honestly — say what you could and could not establish, with "
    "`confidence` set to low. Do not explore further and do not reply in prose."
)

GRAPH_SYS = (
    "You have a structured research atlas to consult, covering ~150 papers. Two "
    "coupled layers:\n"
    "• CONTRIBUTIONS — atomic claims / methods / findings.\n"
    "• RELATIONS — how they connect: typed semantic edges (builds_on, refines, "
    "supports, contradicts — all four matter equally), each with a stated REASON, plus "
    "the CITATIONS between papers, each tagged with an intent (background / "
    "uses-and-extends / compares-and-contrasts) and a justification for why one paper "
    "cited another. The semantic edges were derived from those citations.\n\n"
    "HOW TO USE IT — get the SHAPE first, then read the evidence you need:\n"
    "1. If the question names a paper: `find_paper`, then `paper_neighbourhood`. That "
    "one call gives you its contributions, the typed relations touching them, its "
    "citations ranked by intent, and every count.\n"
    "2. If the question is about a topic rather than a named paper, "
    "`topic_structure` searches and returns the relations around the best hits in the "
    "same call.\n"
    "3. Those calls give edge LABELS, not justifications. Decide which relations "
    "actually bear on the question, then call `edge_reasons` ONCE with all of them "
    "(`relation=` to filter by type, or `others=[...]` to name specific papers) and "
    "read the full evidence. One batched call, not one per edge.\n"
    "4. Narrow filters beat second calls: `paper_neighbourhood(paper_id, "
    "relation='contradicts')` or `intent='uses_extends'` answers a pointed question "
    "directly.\n"
    "5. Only then drill further if something is still missing: `get_edges`, "
    "`citations_between` for site-level citation justifications, `get_paper` for an "
    "abstract, `get_contribution` for detail. `overview` is orientation only.\n\n"
    "Read the COUNTS before the lists — they are often the answer on their own. A "
    "paper cited 53 times as background and 3 times as uses-and-extends has three "
    "papers building on it, not fifty-six. The listing deliberately omits routine "
    "background citations; the count is still there, and `intent='background'` "
    "enumerates them if you genuinely need the names.\n\n"
    "Answer from what the structure actually says, and be straight about what it does "
    "not cover: if the question falls outside this material, say so plainly rather "
    "than guessing. Present the answer as ordinary scholarly knowledge, citing papers "
    "by name; reveal nothing about this atlas."
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

# every built-in tool an arm must never see, whatever the CLI defaults are.
# Names must be REAL tools or the CLI warns "deny rule matches no known tool" on
# every single call — `tools=` is the actual seal, this is belt and braces.
_BUILTINS = ["Bash", "Read", "Write", "Edit", "NotebookEdit", "Glob", "Grep",
             "Skill", "Task", "WebSearch", "WebFetch", "TodoWrite",
             "KillShell", "BashOutput"]


def _ok(payload: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}


def build_qa_graph_server(atlas: GraphAtlas):
    """The QA arm's graph surface. Defined here rather than imported from the
    ideation study so that (parked) experiment's environment stays frozen."""

    # ── broad, paper-shaped entry points (v3 lean) ───────────────────────────
    _RELATIONS = ["builds_on", "refines", "contradicts", "supports"]
    _INTENTS = ["uses_extends", "compares_contrasts", "background"]

    @tool("find_paper", "Look a paper up BY NAME (title / author / venue). Use this "
          "first whenever the question names a paper.", {"query": str})
    async def find_paper(args): return _ok(atlas.find_paper(args["query"], k=5))

    @tool("paper_neighbourhood",
          "How one paper connects, in a single call: its contributions, the typed "
          "relations touching them, and its citations ranked by intent, with ALL "
          "counts precomputed. Start here for any question about a named paper. "
          "Edge labels only — call `edge_reasons` for the justification behind the "
          "specific edges you care about. Routine `background` citations are counted "
          "but not listed; pass intent='background' if you need to enumerate them.",
          {"type": "object",
           "properties": {
               "paper_id": {"type": "string", "description": "id from find_paper"},
               "relation": {"type": "string", "enum": _RELATIONS,
                            "description": "optional: show only this relation type"},
               "intent": {"type": "string", "enum": _INTENTS,
                          "description": "optional: show only citations with this intent"},
           },
           "required": ["paper_id"]})
    async def paper_neighbourhood(args):
        return _ok(atlas.paper_neighbourhood(args["paper_id"],
                                             relation=args.get("relation"),
                                             intent=args.get("intent")))

    @tool("edge_reasons",
          "The full justification recorded on specific typed edges — batched, so "
          "asking about six edges costs ONE call. Use it after "
          "`paper_neighbourhood`/`topic_structure` to read the evidence behind the "
          "relations that matter to the question. Filter by `relation`, or name the "
          "other papers in `others`.",
          {"type": "object",
           "properties": {
               "paper_id": {"type": "string", "description": "the paper whose edges you want"},
               "others": {"type": "array", "items": {"type": "string"},
                          "description": "optional: paper_ids or contribution_ids "
                                         "from the listing, to read only those edges"},
               "relation": {"type": "string", "enum": _RELATIONS,
                            "description": "optional: only edges of this relation type"},
               "max_items": {"type": "integer",
                             "description": "optional, default 6; raise if you need more"},
           },
           "required": ["paper_id"]})
    async def edge_reasons(args):
        return _ok(atlas.edge_reasons(args["paper_id"], others=args.get("others"),
                                      relation=args.get("relation"),
                                      max_items=int(args.get("max_items") or 6)))

    @tool("topic_structure", "Search a TOPIC and get the typed relations around the "
          "best-matching contributions in the same call — use this for questions "
          "about an area rather than a named paper (e.g. whether a finding is "
          "disputed). Edge labels only; `edge_reasons` gives the justifications.",
          {"query": str})
    async def topic_structure(args): return _ok(atlas.topic_structure(args["query"]))

    # ── narrow drill-down (v1 surface, retained) ─────────────────────────────
    @tool("overview", "High-level map: sizes, relation-type counts, citation-intent "
          "counts, most-connected contributions. Orientation only.", {})
    async def overview(args): return _ok(atlas.overview())

    @tool("search_contributions", "Keyword search over the 581 contribution "
          "statements. Returns best matches as entry points.", {"query": str})
    async def search(args): return _ok(atlas.search_contributions(args["query"], k=8))

    @tool("get_contribution", "Full detail on one contribution (statement, kind, "
          "grounding quote, paper).", {"contribution_id": str})
    async def get_contribution(args):
        return _ok(atlas.get_contribution(args["contribution_id"]))

    @tool("get_paper", "A paper's identity, abstract, and its contributions.",
          {"paper_id": str})
    async def get_paper(args): return _ok(atlas.get_paper(args["paper_id"]))

    @tool("get_edges", "The full typed relationships around ONE contribution — "
          "relation, direction, the reason, and citation intent between the papers.",
          {"contribution_id": str})
    async def get_edges(args): return _ok(atlas.get_edges(args["contribution_id"]))

    @tool("get_neighbors", "Brief adjacency list (typed edges only) for a "
          "contribution — cheaper than get_edges when you only need to see where you "
          "can go next.", {"contribution_id": str})
    async def get_neighbors(args): return _ok(atlas.get_neighbors(args["contribution_id"]))

    @tool("get_citations", "Every citation link touching a paper, each with intent, "
          "support/priority and #sites. paper_neighbourhood already includes this, "
          "ranked — prefer that.", {"paper_id": str})
    async def get_citations(args): return _ok(atlas.get_citations(args["paper_id"]))

    @tool("citations_between", "Site-level citation detail (justifications + "
          "passages) between two specific papers.", {"paper_id_a": str, "paper_id_b": str})
    async def citations_between(args):
        return _ok(atlas.citations_between(args["paper_id_a"], args["paper_id_b"]))

    tools = [find_paper, paper_neighbourhood, edge_reasons, topic_structure,
             overview, search, get_contribution, get_paper, get_edges,
             get_neighbors, get_citations, citations_between]
    return (create_sdk_mcp_server(name="graph", tools=tools),
            [f"mcp__graph__{t.name}" for t in tools])


def _submit_tool(holder: dict):
    """FIRST COMPLETE submission wins, and every attempt is kept.

    The original version overwrote `holder["answer"]` on each call, so a row kept
    the LAST submission. Models do not always submit once: 14 of 24 rows in the v3
    batch called `submit_answer` more than once, and two called it eleven times,
    degrading the payload on each retry until it went through. q04/graph ended up
    storing an 823-char stub with `limits="test"` and one paper named — a probe,
    not an answer — while its real answer sat in an earlier attempt we had thrown
    away. Under last-wins that stub is what the judge scored.

    "Complete" = prose AND at least one paper named. A later attempt can only
    replace an INCOMPLETE one, never a complete one.
    """
    @tool("submit_answer", "Record your final answer. Call exactly once.", ANSWER_SCHEMA)
    async def submit_answer(args):
        cand = {
            "answer": args.get("answer", ""),
            "papers_named": list(args.get("papers_named") or []),
            "confidence": args.get("confidence", ""),
            "limits": args.get("limits", ""),
        }
        holder.setdefault("submissions", []).append(cand)
        complete = bool(str(cand["answer"]).strip()) and bool(cand["papers_named"])
        prev = holder.get("answer")
        prev_complete = bool(prev) and bool(str(prev.get("answer", "")).strip()) \
            and bool(prev.get("papers_named"))
        if prev is None or (complete and not prev_complete):
            holder["answer"] = cand
        if prev is not None:
            return {"content": [{"type": "text", "text":
                    "Already recorded — your first complete answer is the one that "
                    "counts and it is safely stored. Do not call this again; stop "
                    "and end your turn."}]}
        return {"content": [{"type": "text", "text": "recorded"}]}
    return submit_answer


def build_options(arm: str, atlas: GraphAtlas | None, holder: dict, *, model: str,
                  max_turns: int, budget_usd: float) -> ClaudeAgentOptions:
    mcp: dict[str, Any] = {"io": create_sdk_mcp_server(name="io",
                                                       tools=[_submit_tool(holder)])}
    allowed = ["mcp__io__submit_answer"]
    builtin: list[str] = []                 # the SEALED built-in surface for this arm
    if arm == "graph":
        gserver, gnames = build_qa_graph_server(atlas)
        mcp["graph"] = gserver
        allowed = gnames + allowed
    elif arm == "web":
        builtin = ["WebSearch", "WebFetch"]
        allowed = builtin + allowed
    elif arm != "null":                       # null: submit_answer only, by design
        raise ValueError(arm)
    return ClaudeAgentOptions(
        system_prompt=SYS[arm], mcp_servers=mcp, allowed_tools=allowed,
        # ── the seal ──────────────────────────────────────────────────────────
        tools=builtin,                        # THE tool-surface restriction
        disallowed_tools=[t for t in _BUILTINS if t not in builtin],
        setting_sources=[],                   # no project CLAUDE.md / settings
        skills=[],                            # no repo skills (v1 leaked Skill(prior))
        # ──────────────────────────────────────────────────────────────────────
        max_turns=max_turns, model=model, permission_mode="bypassPermissions",
        max_budget_usd=budget_usd,
    )


async def run_one(arm: str, question: str, atlas: GraphAtlas | None, *, model: str,
                  max_turns: int, budget_usd: float, max_nudges: int = 2) -> dict:
    """Run one question through one arm. Returns the answer + usage metrics.

    Uses ClaudeSDKClient rather than one-shot `query()` so that a model which
    finishes a turn WITHOUT calling `submit_answer` can be nudged inside the same
    session, keeping all its exploration context. The first v2 run lost a whole
    unit that way: it explored perfectly (find_paper -> paper_neighbourhood -> two
    drill-downs) and then wrote the answer as prose. The nudge is identical for
    all three arms and counted as `n_nudges`, so it cannot favour one environment.
    """
    holder: dict = {}
    opts = build_options(arm, atlas, holder, model=model, max_turns=max_turns,
                         budget_usd=budget_usd)
    surface = set(opts.tools or [])
    t0 = time.time()
    tool_calls: list[str] = []
    tool_args: list[dict] = []
    sizes_by_id: dict[str, int] = {}
    off_arm: list[str] = []
    finals: list[ResultMessage] = []
    texts: list[str] = []

    async def drain(client) -> None:
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, ToolUseBlock):
                        tool_calls.append(b.name)
                        # outside this arm's declared surface = seal breach
                        if not (b.name.startswith("mcp__") or b.name in surface
                                or b.name == "ToolSearch"):
                            off_arm.append(b.name)
                        if not b.name.endswith("submit_answer"):
                            tool_args.append({"tool": b.name, "args": b.input,
                                              "_id": b.id})
                    elif isinstance(b, TextBlock):
                        texts.append(b.text)
            elif isinstance(msg, UserMessage):
                # log RESULT SIZES too — v1 logged only arguments, so there was no
                # record of how much material each call put into context
                for b in getattr(msg, "content", None) or []:
                    if isinstance(b, ToolResultBlock):
                        c = b.content
                        txt = c if isinstance(c, str) else json.dumps(c,
                                                                      ensure_ascii=False)
                        sizes_by_id[b.tool_use_id] = len(txt or "")
            elif isinstance(msg, ResultMessage):
                finals.append(msg)

    n_nudges = 0
    async with ClaudeSDKClient(options=opts) as client:
        await client.query(TASK.format(question=question))
        await drain(client)
        # Only nudge a session that ended CLEANLY. If it stopped because it hit
        # max_budget_usd or max_turns, the session is already spent and every nudge
        # just bounces straight back off the same limit — which is exactly what
        # happened to q01/web on the first v2 run (2 wasted round-trips).
        while (holder.get("answer") is None and n_nudges < max_nudges
               and finals and not getattr(finals[-1], "is_error", False)):
            n_nudges += 1
            await client.query(NUDGE)
            await drain(client)

    for t in tool_args:                       # attach payload size to each call
        t["result_chars"] = sizes_by_id.get(t.pop("_id"), None)
    explore = [t for t in tool_calls if t != "ToolSearch" and not t.endswith("submit_answer")]
    # ResultMessage `usage` and `total_cost_usd` are PER-QUERY, not cumulative — so
    # a nudged unit needs them SUMMED across queries. Settled by evidence, not by
    # guessing: q03/web made 4 WebSearch/WebFetch calls, yet its LAST ResultMessage
    # reports server_tool_use.web_search_requests == 0, because those calls happened
    # in the FIRST query. An earlier build took the last message only and under-counted
    # that row (4,190 tokens_in for a session that had done four searches).
    # `num_turns`, by contrast, is a session-level counter feeding the max_turns guard,
    # so it takes the MAX rather than the sum.
    last = finals[-1] if finals else None

    def _tot(key: str) -> int:
        return sum(int((getattr(f, "usage", None) or {}).get(key) or 0) for f in finals)

    # keep every query's own numbers on the row so this is never ambiguous again
    finals_meta = [{"turns": getattr(f, "num_turns", None),
                    "usd": getattr(f, "total_cost_usd", None),
                    "is_error": getattr(f, "is_error", None),
                    "stop_reason": getattr(f, "stop_reason", None),
                    "usage": dict(getattr(f, "usage", None) or {})} for f in finals]
    return {
        "arm": arm, "question": question, "answer": holder.get("answer"),
        "completed": holder.get("answer") is not None,
        "n_nudges": n_nudges,
        "final_text": ("\n".join(texts)[-2000:] if holder.get("answer") is None
                       else None),          # keep the prose when the tool was skipped
        "tool_calls": tool_calls, "tool_args": tool_args,
        "n_tool_calls": len(tool_calls), "n_explore": len(explore),
        # >1 means the model retried the submission. Retries degrade: the two
        # 11-submit rows in the v3 batch both ended in a stub. Flag, don't hide.
        "n_submits": sum(1 for t in tool_calls if t.endswith("submit_answer")),
        "submissions": holder.get("submissions") or [],
        "off_arm_tools": off_arm,                 # MUST be empty; the seal's canary
        "payload_chars": sum(v for v in
                             (t.get("result_chars") for t in tool_args) if v),
        # ── efficiency metrics, in order of how much they can be trusted ──────
        # payload_chars (above) is the headline: OUR code sums what the tools
        # actually returned, so nothing in the harness can move it.
        # context_total is what the model genuinely had to process.
        # tokens_in was the ORIGINAL pre-registered headline and is retained only
        # so the record is complete — it is input + cache_creation, and
        # cache_creation tracks how the prefix was re-chunked across turns, not
        # ingestion. Proved on q01: v3's payload fell ~5,500 tokens while its
        # cache_creation rose 27,345. See PLAN.md 5.
        "tokens_in": _tot("input_tokens") + _tot("cache_creation_input_tokens"),
        "context_total": (_tot("input_tokens") + _tot("cache_creation_input_tokens")
                          + _tot("cache_read_input_tokens")),
        "seconds": round(time.time() - t0, 1),
        "num_turns": max((int(getattr(f, "num_turns", 0) or 0) for f in finals),
                         default=None),
        "total_cost_usd": sum(float(getattr(f, "total_cost_usd", 0) or 0)
                              for f in finals) or None,
        "usage": {k: _tot(k) for k in
                  ("input_tokens", "output_tokens", "cache_creation_input_tokens",
                   "cache_read_input_tokens")},
        "finals_meta": finals_meta,
        "n_queries": len(finals),
        "stop_reason": getattr(last, "stop_reason", None) if last else None,
        "is_error": bool(getattr(last, "is_error", False)) if last else None,
    }


def _selftest() -> None:
    """Check all three arms' wiring AND the seal — no model call, zero cost."""
    atlas = GraphAtlas()
    holder: dict = {}
    for arm in ARMS:
        o = build_options(arm, atlas, holder, model="claude-sonnet-5",
                          max_turns=12, budget_usd=0.5)
        print(f"{arm:6} tools={str(o.tools):26} mcp={sorted(o.mcp_servers)} "
              f"allowed={len(o.allowed_tools):2} disallowed={len(o.disallowed_tools)}")
        assert o.setting_sources == [], f"{arm}: project settings not sealed"
        assert o.skills == [], f"{arm}: repo skills not sealed"
        for bad in ("Bash", "Skill", "Task", "Read"):
            assert bad not in (o.tools or []), f"{arm}: {bad} in tool surface"
            assert bad in o.disallowed_tools, f"{arm}: {bad} not disallowed"
        if arm != "web":
            assert "WebSearch" in o.disallowed_tools, f"{arm}: web not sealed out"
    n = build_options("null", None, holder, model="m", max_turns=1, budget_usd=0.1)
    assert n.allowed_tools == ["mcp__io__submit_answer"] and n.tools == [], \
        "null arm must have exactly one tool"
    assert list(build_options("web", None, holder, model="m", max_turns=1,
                              budget_usd=0.1).tools) == ["WebSearch", "WebFetch"]
    _s, gnames = build_qa_graph_server(atlas)
    print(f"\ngraph tools ({len(gnames)}): "
          + ", ".join(g.replace("mcp__graph__", "") for g in gnames))
    qs = json.loads((Path(__file__).parent / "questions.json").read_text(encoding="utf-8"))
    print(f"questions: {len(qs['questions'])} "
          f"({sum(q['expected_winner'] == 'graph' for q in qs['questions'])} graph-expected, "
          f"{sum(q['expected_winner'] == 'web' for q in qs['questions'])} control)")
    ov = atlas.overview()
    print("atlas:", ov["papers"], "papers /", ov["contributions"], "contributions")
    print("OK — three arms wired and SEALED (no model was called).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    else:
        print("Import from qa_gen.py, or run with --selftest.")
