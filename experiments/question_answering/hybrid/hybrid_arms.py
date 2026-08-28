#!/usr/bin/env python3
"""Two HYBRID arms — the atlas AND a browser — as a pure add-on.

NOTHING IN THE PARENT FOLDER IS MODIFIED. This module imports `qa_arms`, builds
two extra arms out of its pieces, and wraps its `build_options` with a
delegating shim so that `qa_arms.run_one` drives them unchanged. The wrap is in
memory only; `qa_arms.py` on disk is untouched, and `--selftest` asserts the
original three arms come back through the shim with an identical configuration
signature.

Why wrap rather than copy: `run_one` carries the usage accounting that has been
debugged three times (per-query vs cumulative `usage`, first-complete-wins
submission, the `off_arm_tools` canary, payload-size attribution). A fork of it
here would silently drift from the arm it is being compared against.

THE TWO VARIANTS
----------------
Both get all 12 atlas tools PLUS WebSearch/WebFetch, the same TASK, the same
blinding contract, the same seal. They differ only in the system prompt:

  hybrid_directed — `qa_arms.GRAPH_SYS` VERBATIM, plus a routing policy:
      atlas first for structure, browser for coverage / detail / verification.
  hybrid_free     — the atlas DESCRIPTION from `GRAPH_SYS` (verbatim, procedure
      stripped) plus "you also have a browser". No ordering, no policy.

Both are derived from the live `GRAPH_SYS` rather than retyped, so the delta
between them is the PROCEDURE and not incidental wording. That is the thing
being tested. See PLAN_HYBRID.md §2.

Free to run:
  python hybrid_arms.py --selftest              # wiring + seal, no model call
  python hybrid_arms.py --show-prompt directed  # the exact system prompt
  python hybrid_arms.py --show-prompt free
  python hybrid_arms.py --diff                  # what the policy adds to GRAPH_SYS
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(PARENT))          # import the parent's modules, don't fork them

import qa_arms                                                       # noqa: E402
from qa_arms import (GraphAtlas, build_qa_graph_server, ANSWER_SCHEMA,  # noqa: E402
                     _BUILTINS)

from claude_agent_sdk import (ClaudeAgentOptions, create_sdk_mcp_server,  # noqa: E402
                             tool)

HYBRID_ARMS = ("hybrid_directed", "hybrid_free")

# The browser tools both variants get. Identical to the WEB arm's surface, so
# "what a browser can do" is held constant across the whole experiment.
_BROWSER = ["WebSearch", "WebFetch"]


# ─────────────────────────────────────────────────────────────────────────────
# Prompts, derived from the live GRAPH_SYS so they cannot drift from the arm
# they are being compared against.
# ─────────────────────────────────────────────────────────────────────────────

_SPLIT = "HOW TO USE IT"
assert _SPLIT in qa_arms.GRAPH_SYS, "GRAPH_SYS no longer has the procedure block"

# Everything before "HOW TO USE IT": what the atlas IS (contributions, relations,
# reasons, citation intents). Both variants need this — withholding it from the
# hands-off arm would make it a strawman rather than a comparison.
ATLAS_DESCRIPTION = qa_arms.GRAPH_SYS.split(_SPLIT, 1)[0].strip()

# ── hybrid_directed = GRAPH_SYS + this ──────────────────────────────────────
#
# Trigger 3 is the generalisable rule from the q06 post-mortem (../NOTES.md §1):
# the edge labeller referred to `Towards end-to-end automation of AI research`
# by the SYSTEM name "The AI Scientist" in 36 of its 42 edges, and the graph arm
# inherited that and called the 2026 paper "the original". The policy names no
# paper, no system and no question — but it was written AFTER seeing that
# failure, so PLAN_HYBRID.md §2 declares it as engineered rather than
# discovered, and prediction 1 is registered as expected rather than surprising.
ROUTING_POLICY = (
    "YOU ALSO HAVE A WEB BROWSER — `WebSearch` and `WebFetch`. This changes the "
    "last point above: you are no longer limited to what the atlas covers.\n\n"
    "WORK ATLAS-FIRST. Establish the SHAPE of the answer — what relates to what, "
    "and why — from the atlas before you search. The atlas is the only thing that "
    "can tell you a paper genuinely extends another rather than citing it in "
    "passing; a search cannot, and will mislead you if you let it.\n\n"
    "Then reach for the browser in exactly three situations:\n"
    "1. COVERAGE — the question, or part of it, falls outside these ~150 papers. "
    "Search rather than guess, and rather than declining.\n"
    "2. DETAIL — you need something the atlas does not hold: a number from a "
    "results table, an experimental setting, the exact wording of a claim in the "
    "full text.\n"
    "3. VERIFICATION — your answer is about to rest on a characterisation of WHAT "
    "A PAPER DOES, WHO WROTE IT or WHEN IT APPEARED that you took from a recorded "
    "justification rather than from the paper's own title and contributions. Those "
    "justifications are written automatically. They are reliable about the "
    "RELATIONSHIP they describe and can be unreliable about IDENTITY: they "
    "sometimes refer to a paper by a SYSTEM name, and a system name can belong to "
    "a different paper, an earlier version of it, or a later one. Check a "
    "load-bearing claim of that kind before you assert it.\n\n"
    "DO NOT LET THE BROWSER REPLACE THE STRUCTURE. The atlas decides what relates "
    "to what; the browser confirms what things are, and fills what the atlas does "
    "not cover. Searching for something the atlas has already told you wastes the "
    "answer's budget twice over. If the two disagree, say so in the answer rather "
    "than silently picking one.\n\n"
    "Reveal nothing about either the atlas or your searching."
)

DIRECTED_SYS = qa_arms.GRAPH_SYS + "\n\n" + ROUTING_POLICY

# ── hybrid_free = the description, a browser, and no advice at all ───────────
FREE_SYS = (
    ATLAS_DESCRIPTION + "\n\n"
    "You also have a web browser: `WebSearch` and `WebFetch`.\n\n"
    "Use whichever of these you judge appropriate for the question. No particular "
    "order is required and you need not use both.\n\n"
    "Present the answer as ordinary scholarly knowledge, citing papers by name; "
    "reveal nothing about the atlas, your searching, or how you arrived at the "
    "answer."
)

HYBRID_SYS = {"hybrid_directed": DIRECTED_SYS, "hybrid_free": FREE_SYS}


# ─────────────────────────────────────────────────────────────────────────────
# submit_answer — BEST-WINS, because first-complete-wins loses to a smoke test
# ─────────────────────────────────────────────────────────────────────────────
#
# The parent's `_submit_tool` is first-complete-wins, where "complete" is
# `answer non-blank AND papers_named non-empty`. That predicate cannot tell an
# answer from a probe, and models probe this tool constantly: in the first
# hybrid batch, q01/hybrid_free opened with
#
#     answer="Test", papers_named=["Test Paper"], confidence="high", limits="test"
#
# which satisfies the predicate, so it was locked in as the final answer. The
# model's real 4,428-char answer arrived one call later and was DISCARDED, and
# the tool told it "your first complete answer is the one that counts and it is
# safely stored", so it stopped. The judge scored the word "Test" 1/1/1.
#
# This is the same root cause as the parent's own last-wins bug (a degrading
# retry overwrote a real answer with a stub): the ORDERING was never the
# problem, the completeness PREDICATE is. First-wins loses when the junk comes
# first, last-wins loses when it comes last.
#
# So: keep every attempt, and store the BEST one — passes the bar first, then
# longest. That beats a probe whichever end it arrives at. The bar is
# deliberately low; it is there to exclude smoke tests, not to grade answers.
# The longest probe observed was 459 chars, the shortest real answer 3,734.

MIN_ANSWER_CHARS = 900
_PLACEHOLDER_LIMITS = {"", "test", "test2", "testing", "n/a", "na", "none", "-",
                       "tbd", "placeholder", "x"}


def is_probe(cand: dict) -> tuple[bool, str]:
    """Is this a smoke test rather than an answer? (verdict, why)"""
    body = str(cand.get("answer") or "").strip()
    if not body:
        return True, "empty answer"
    if not (cand.get("papers_named") or []):
        return True, "no papers named"
    if len(body) < MIN_ANSWER_CHARS:
        return True, f"answer is {len(body)} chars (< {MIN_ANSWER_CHARS})"
    if str(cand.get("limits") or "").strip().lower() in _PLACEHOLDER_LIMITS:
        return True, f"placeholder limits {cand.get('limits')!r}"
    return False, ""


def quality_key(cand: dict) -> tuple[int, int]:
    """Sort key for picking the stored answer. Passing the bar dominates; among
    passing candidates the longest wins, which is also what defeats the parent's
    degrading-retry case (its stub was shorter than the real answer it replaced)."""
    probe, _ = is_probe(cand)
    return (0 if probe else 1, len(str(cand.get("answer") or "").strip()))


def pick_best(submissions: list[dict]) -> dict | None:
    """The submission the fixed harness would have stored. Ties go to the
    earliest, so this is deterministic and replayable over an old log."""
    if not submissions:
        return None
    return max(reversed(submissions), key=quality_key)


def _hybrid_submit_tool(holder: dict):
    @tool("submit_answer", "Record your final answer. Call exactly once.", ANSWER_SCHEMA)
    async def submit_answer(args):
        cand = {"answer": args.get("answer", ""),
                "papers_named": list(args.get("papers_named") or []),
                "confidence": args.get("confidence", ""),
                "limits": args.get("limits", "")}
        holder.setdefault("submissions", []).append(cand)
        holder["answer"] = pick_best(holder["submissions"])
        probe, why = is_probe(cand)
        if probe:
            # Never tell a model its probe is safely stored — that is precisely
            # what made it stop last time. Say the slot is still open.
            return {"content": [{"type": "text", "text":
                    f"NOT ACCEPTED as your final answer ({why}). Nothing has been "
                    "delivered to the researcher yet. Call `submit_answer` again "
                    "with your real answer: the full reply, the exact titles of "
                    "the papers it relies on, your confidence, and one honest "
                    "line on what you could not establish."}]}
        if holder["answer"] is cand:
            return {"content": [{"type": "text", "text":
                    "Recorded. This is your final answer — stop and end your turn."}]}
        return {"content": [{"type": "text", "text":
                "A fuller answer of yours is already recorded and is the one that "
                "counts. Do not call this again; stop and end your turn."}]}
    return submit_answer


# ─────────────────────────────────────────────────────────────────────────────
# Options + the delegating shim
# ─────────────────────────────────────────────────────────────────────────────

def build_hybrid_options(arm: str, atlas: GraphAtlas, holder: dict, *, model: str,
                         max_turns: int, budget_usd: float) -> ClaudeAgentOptions:
    """Atlas tools + browser, sealed exactly as the parent arms are."""
    if arm not in HYBRID_SYS:
        raise ValueError(arm)
    gserver, gnames = build_qa_graph_server(atlas)
    return ClaudeAgentOptions(
        system_prompt=HYBRID_SYS[arm],
        mcp_servers={"graph": gserver,
                     "io": create_sdk_mcp_server(
                         name="io", tools=[_hybrid_submit_tool(holder)])},
        allowed_tools=gnames + _BROWSER + ["mcp__io__submit_answer"],
        # ── the seal — same contract as qa_arms.build_options ────────────────
        tools=list(_BROWSER),             # THE tool-surface restriction
        disallowed_tools=[t for t in _BUILTINS if t not in _BROWSER],
        setting_sources=[],               # no project CLAUDE.md / settings
        skills=[],                        # no repo skills
        # ────────────────────────────────────────────────────────────────────
        max_turns=max_turns, model=model, permission_mode="bypassPermissions",
        max_budget_usd=budget_usd,
    )


_ORIGINAL_BUILD_OPTIONS = qa_arms.build_options       # captured before any wrap
_installed = False


def install() -> None:
    """Teach `qa_arms.run_one` about the hybrid arms, without editing it.

    `run_one` looks `build_options` up as a module global, so replacing that name
    with a shim that delegates every unknown arm to the original is enough.
    Idempotent: re-importing or re-calling never double-wraps.
    """
    global _installed
    if _installed:
        return

    def build_options(arm: str, atlas, holder: dict, **kw):
        if arm in HYBRID_SYS:
            return build_hybrid_options(arm, atlas, holder, **kw)
        return _ORIGINAL_BUILD_OPTIONS(arm, atlas, holder, **kw)

    build_options.__doc__ = _ORIGINAL_BUILD_OPTIONS.__doc__
    qa_arms.build_options = build_options
    _installed = True


install()


def _signature(o: ClaudeAgentOptions) -> dict[str, Any]:
    """The parts of an options object that define an arm. Excludes the live MCP
    server objects, which are new instances every call and never compare equal."""
    return {"system_prompt": o.system_prompt,
            "tools": sorted(o.tools or []),
            "allowed_tools": sorted(o.allowed_tools or []),
            "disallowed_tools": sorted(o.disallowed_tools or []),
            "mcp_servers": sorted(o.mcp_servers or {}),
            "setting_sources": o.setting_sources, "skills": o.skills,
            "max_turns": o.max_turns, "model": o.model,
            "permission_mode": o.permission_mode,
            "max_budget_usd": o.max_budget_usd}


def _selftest() -> None:
    """Wiring, seal, and proof that the parent arms are unaffected. No model call."""
    atlas = GraphAtlas()
    holder: dict = {}
    kw = dict(model="claude-sonnet-5", max_turns=18, budget_usd=1.0)

    # 1. the shim must leave the original three arms bit-identical -------------
    for arm in qa_arms.ARMS:
        before = _signature(_ORIGINAL_BUILD_OPTIONS(
            arm, atlas if arm == "graph" else None, holder, **kw))
        after = _signature(qa_arms.build_options(
            arm, atlas if arm == "graph" else None, holder, **kw))
        assert before == after, f"{arm}: the shim changed the parent arm!"
    print(f"parent arms unchanged through the shim: {', '.join(qa_arms.ARMS)}")

    # 2. the hybrid arms ------------------------------------------------------
    _s, gnames = build_qa_graph_server(atlas)
    for arm in HYBRID_ARMS:
        o = qa_arms.build_options(arm, atlas, holder, **kw)
        print(f"{arm:16} tools={str(o.tools):26} mcp={sorted(o.mcp_servers)} "
              f"allowed={len(o.allowed_tools):2} disallowed={len(o.disallowed_tools)} "
              f"sys={len(o.system_prompt):,}ch")
        assert list(o.tools) == _BROWSER, f"{arm}: browser surface wrong"
        assert set(gnames) <= set(o.allowed_tools), f"{arm}: atlas tools missing"
        assert "mcp__io__submit_answer" in o.allowed_tools, f"{arm}: no submit tool"
        assert len(o.allowed_tools) == len(gnames) + 3, f"{arm}: unexpected tool count"
        assert o.setting_sources == [] and o.skills == [], f"{arm}: not sealed"
        for bad in ("Bash", "Skill", "Task", "Read", "Write", "Grep"):
            assert bad not in (o.tools or []), f"{arm}: {bad} in tool surface"
            assert bad in o.disallowed_tools, f"{arm}: {bad} not disallowed"

    # 3. the prompts are DERIVED from GRAPH_SYS, not retyped -------------------
    assert qa_arms.GRAPH_SYS in DIRECTED_SYS, \
        "hybrid_directed must contain GRAPH_SYS verbatim"
    assert ATLAS_DESCRIPTION in FREE_SYS, \
        "hybrid_free must contain the atlas description verbatim"
    assert ATLAS_DESCRIPTION in qa_arms.GRAPH_SYS
    assert _SPLIT not in FREE_SYS, "hybrid_free must NOT carry the procedure block"
    assert "atlas-first" in DIRECTED_SYS.lower() and "atlas-first" not in FREE_SYS.lower()
    # the policy must stay generalisable — no leak of the question it came from
    for leak in ("AIDE", "AI Scientist", "q06", "Lu et al", "tree search"):
        assert leak.lower() not in ROUTING_POLICY.lower(), \
            f"routing policy leaks the diagnosing case: {leak!r}"
    print(f"prompts derived from GRAPH_SYS  directed={len(DIRECTED_SYS):,}ch "
          f"(+{len(DIRECTED_SYS) - len(qa_arms.GRAPH_SYS):,} over graph)  "
          f"free={len(FREE_SYS):,}ch")

    # 4. the submit gate must reject a probe and prefer the fuller answer -----
    probe = {"answer": "Test", "papers_named": ["Test Paper"],
             "confidence": "high", "limits": "test"}
    probe2 = {"answer": "x" * 460, "papers_named": ["A Real Title"],
              "confidence": "high", "limits": "test2"}
    real = {"answer": "y" * 3_700, "papers_named": ["A Real Title"],
            "confidence": "medium", "limits": "I could not establish X."}
    assert is_probe(probe)[0] and is_probe(probe2)[0], "probe not rejected"
    assert not is_probe(real)[0], "real answer rejected"
    # both orderings must land on the real answer — that is the whole fix
    assert pick_best([probe, real]) is real, "probe-first still wins"
    assert pick_best([real, probe]) is real, "degrading retry still wins"
    assert pick_best([probe, probe2]) is probe2, "should keep the fuller probe"
    assert pick_best([]) is None
    # and it must reproduce over the real batch: the answer the fixed harness
    # would have stored for q01/hybrid_free is the 4,428-char one, not "Test"
    log = HERE / "out" / "answers.jsonl"
    if log.exists():
        import json as _json
        for r in (_json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()):
            subs = r.get("submissions") or []
            if len(subs) > 1:
                best = pick_best(subs)
                stored = len(str((r.get("answer") or {}).get("answer") or ""))
                print(f"  repairable: {r['question_id']}/{r['arm']} "
                      f"stored {stored}ch -> best {len(best['answer'])}ch"
                      + ("  (still a probe — must re-run)"
                         if is_probe(best)[0] else ""))
    print("submit gate: probes rejected, best-wins in both orderings")

    # 5. the incumbents this pilot will be judged against ---------------------
    import json
    ans = PARENT / "out" / "answers.jsonl"
    rows = [json.loads(l) for l in ans.read_text(encoding="utf-8").splitlines() if l.strip()]
    have = {(r["question_id"], r["arm"]) for r in rows if r.get("answer")}
    for qid, inc in (("q01", "graph"), ("q04", "graph"), ("q06", "web")):
        assert (qid, inc) in have, f"missing incumbent answer {qid}/{inc}"
    print("incumbents present (read-only): q01/graph, q04/graph, q06/web")
    print(f"atlas: {atlas.overview()['papers']} papers / "
          f"{atlas.overview()['contributions']} contributions")
    print("\nOK — two hybrid arms wired and SEALED, parent untouched "
          "(no model was called).")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--show-prompt", choices=("directed", "free", "graph"))
    ap.add_argument("--diff", action="store_true",
                    help="what hybrid_directed adds to GRAPH_SYS")
    a = ap.parse_args()
    if a.show_prompt:
        print({"directed": DIRECTED_SYS, "free": FREE_SYS,
               "graph": qa_arms.GRAPH_SYS}[a.show_prompt])
    elif a.diff:
        print("=== hybrid_directed = GRAPH_SYS + ===\n")
        print(ROUTING_POLICY)
        print(f"\n(+{len(ROUTING_POLICY):,} chars on top of GRAPH_SYS's "
              f"{len(qa_arms.GRAPH_SYS):,})")
    elif a.selftest:
        _selftest()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
