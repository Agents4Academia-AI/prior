#!/usr/bin/env python3
"""Blind pairwise judging of the two arms' ideas — resumable, killable, capped.

RUN THIS IN YOUR OWN TERMINAL (never spawned from a Claude Code session). Uses
your Claude Code subscription via the Agent SDK, same credit-free path as gen.py.

What it does (seed-vs-seed, the v1 comparison):
  for each seed with a completed idea on BOTH arms, show `claude-opus-5` the two
  ideas ANONYMISED as "Idea A" / "Idea B" and ask for an ABSOLUTE 1-10 score on
  novelty and on feasibility/soundness FOR EACH idea, plus a "same core idea?"
  flag, AND a forced direct comparison (which is more novel / sounder, and by how
  big a margin) — strong proposals cluster at 6-8, so the margin is what separates
  them when the integer scores tie. Keep the 1-10 (more signal); binarize to a
  winrate later in aggregate.py.

  ORDER: the v1 pilot judged every pair twice with A/B swapped and position bias
  was negligible (3 seeds x 4 scores: max 1-point drift, zero flipped winners), so
  the default is now `--orders alt` — ONE judgement per seed, alternating which arm
  is shown as A. Half the cost, and positions stay exactly balanced across the set
  rather than merely estimated per pair. `--orders both` restores the 2x design.

The judge never learns which side is which, never sees the arms, the graph or the
seed's provenance, and gets no tools but `submit_judgement` — it rates novelty
from its own knowledge of the literature (so the web arm's live-search
*verification* edge doesn't leak into the score).

Safety / cost design (same contract as gen.py):
  • Checkpointed: each finished (seed_id, order) is appended to
    out/judgements.jsonl the instant it lands. Re-running SKIPS what's done.
  • Ctrl+C safe: a partial judgement is never written.
  • Capped: --max-turns and --budget per judgement, --sleep between calls, serial.
  • --dry-run renders the exact prompts with NO model call.

Each output row leads with the unblinded scores so you can eyeball the .jsonl:
  seed_id, order, graph_novelty, graph_feasibility, web_novelty, web_feasibility,
  … then the reasons, then cost / tokens / wall-clock.

Examples:
  python judge.py --dry-run                 # free: see the plan + a rendered prompt
  python judge.py --limit 3                 # small live pilot (3 seeds, 1 call each)
  python judge.py --orders both --limit 3   # re-measure position bias if ever needed
  python judge.py                           # everything (resumes if interrupted)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Annotated

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "out"
GENERATIONS = OUT_DIR / "generations.jsonl"
CKPT = OUT_DIR / "judgements.jsonl"

JUDGE_MODEL = "claude-opus-5"          # strictly stronger than the sonnet-5 generator
FIELDS = ("title", "gap", "proposed_study", "expected_result", "grounding")
ORDERS = {"gw": ("graph", "web"), "wg": ("web", "graph")}   # which arm is shown as A

JUDGE_SYS = (
    "You are a senior reviewer on a grant panel, expert in AI-for-science and "
    "machine-learning methodology. You will be shown a research TOPIC and TWO "
    "independently written research proposals on it, Idea A and Idea B. Score EACH "
    "idea on its own merits — this is absolute scoring, not a forced choice; both may "
    "be excellent, both may be weak, and ties are fine.\n\n"
    "NOVELTY (1-10) — how new is this against the BROADER published literature you "
    "know, not against the other idea:\n"
    "  1-2  already standard practice / done many times\n"
    "  3-4  minor variation on well-known published work\n"
    "  5-6  plausible incremental extension, not obviously published\n"
    "  7-8  genuinely new framing, mechanism or measurement\n"
    "  9-10 strikingly original AND important if it worked\n\n"
    "FEASIBILITY & SOUNDNESS (1-10) — could a competent group actually run this and "
    "learn something, and is the reasoning sound:\n"
    "  1-2  incoherent or not executable as written\n"
    "  3-4  central pieces undefined; the result would not support the claim\n"
    "  5-6  executable, but with significant gaps or an unclear measurement\n"
    "  7-8  concrete design, plausible resources, a clear measurable outcome\n"
    "  9-10 fully specified, well-controlled, the outcome is decisive either way\n\n"
    "Judge substance, not style. Ignore length, formatting and rhetorical polish — but "
    "DO reward specificity that makes a study executable (named baselines, a concrete "
    "measurement, a stated expected result) and penalise vagueness dressed up as rigour. "
    "Do not favour an idea for citing more prior work. If a proposal's cited grounding "
    "looks fabricated or misattributed, penalise soundness and say so.\n\n"
    "Strong proposals cluster in the middle of both scales, so the absolute score alone "
    "often cannot separate them. After scoring, make the DIRECT comparison explicitly: say "
    "which idea is more novel and which is more feasible/sound, and how big each gap is "
    "('decisive' / 'clear' / 'slight' / 'none'). Use 'neither' + 'none' only when you "
    "genuinely cannot separate them — a one-point difference in your scores should normally "
    "show up here as 'slight', not 'none'.\n\n"
    "Also decide SAME_IDEA: are these two, at their core, the same proposal (same gap "
    "attacked by substantially the same study), regardless of wording? Two proposals in "
    "the same subfield are NOT the same idea; only flag true near-duplicates.\n\n"
    "Call `submit_judgement` EXACTLY ONCE. Keep each reason to one sentence. You have no "
    "other tools and no browser — score from your own knowledge."
)

PROMPT = (
    "TOPIC: {topic}\n\n"
    "=== IDEA A ===\n{a}\n\n"
    "=== IDEA B ===\n{b}\n\n"
    "Score each idea 1-10 on novelty and on feasibility/soundness, state which is more "
    "novel and which is sounder (with the size of each gap), decide whether they are the "
    "same core idea, and submit."
)

_S = "1-10"
JUDGEMENT_SCHEMA = {
    "a_novelty": Annotated[int, f"Idea A novelty, {_S}"],
    "a_novelty_reason": Annotated[str, "One sentence justifying Idea A's novelty score"],
    "a_feasibility": Annotated[int, f"Idea A feasibility/soundness, {_S}"],
    "a_feasibility_reason": Annotated[str, "One sentence justifying Idea A's feasibility score"],
    "b_novelty": Annotated[int, f"Idea B novelty, {_S}"],
    "b_novelty_reason": Annotated[str, "One sentence justifying Idea B's novelty score"],
    "b_feasibility": Annotated[int, f"Idea B feasibility/soundness, {_S}"],
    "b_feasibility_reason": Annotated[str, "One sentence justifying Idea B's feasibility score"],
    # forced comparison — breaks the ties the integer scale cannot resolve
    "more_novel": Annotated[str, "Which idea is more novel: 'A', 'B', or 'neither'"],
    "novelty_margin": Annotated[str, "Size of the novelty gap: 'decisive', 'clear', 'slight', or 'none'"],
    "sounder": Annotated[str, "Which idea is more feasible/sound: 'A', 'B', or 'neither'"],
    "feasibility_margin": Annotated[str, "Size of the feasibility gap: 'decisive', 'clear', 'slight', or 'none'"],
    "same_idea": Annotated[bool, "True only if A and B are at core the same proposal"],
    "same_idea_reason": Annotated[str, "One sentence on how they overlap or differ"],
}


def render_idea(idea: dict) -> str:
    """The five idea fields as a plain proposal — no arm, no seed, no provenance."""
    labels = {"title": "Title", "gap": "Gap", "proposed_study": "Proposed study",
              "expected_result": "Expected result", "grounding": "Motivation / grounding"}
    return "\n".join(f"{labels[f]}: {str(idea.get(f, '')).strip()}" for f in FIELDS)


def load_pairs() -> list[tuple[str, str, dict, dict]]:
    """(seed_id, topic, graph_row, web_row) for every seed complete on both arms."""
    rows = [json.loads(l) for l in GENERATIONS.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    by_seed: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_seed.setdefault(r["seed_id"], {})[r["arm"]] = r
    pairs = []
    for sid, d in sorted(by_seed.items()):
        g, w = d.get("graph"), d.get("web")
        if g and w and g.get("idea") and w.get("idea"):
            pairs.append((sid, g.get("topic") or w.get("topic"), g, w))
        else:
            print(f"  (skipping {sid}: needs a completed idea on both arms)")
    return pairs


def done_keys() -> set[tuple[str, str]]:
    if not CKPT.exists():
        return set()
    keys = set()
    for line in CKPT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            keys.add((r["seed_id"], r["order"]))
    return keys


def append(row: dict) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


def _clamp(v, lo=1, hi=10):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return None


async def judge_one(topic: str, idea_a: dict, idea_b: dict, *, model: str,
                    max_turns: int, budget_usd: float) -> dict:
    """One blind judgement of an already-ordered (A, B) pair. Returns raw fields
    keyed by a_/b_ plus usage metrics — the caller maps A/B back to arms."""
    import time
    from claude_agent_sdk import (query, tool, create_sdk_mcp_server, ClaudeAgentOptions,
                                  ResultMessage)

    holder: dict = {}

    @tool("submit_judgement", "Record your scores for both ideas. Call exactly once.",
          JUDGEMENT_SCHEMA)
    async def submit_judgement(args):
        holder["j"] = {k: args.get(k) for k in JUDGEMENT_SCHEMA}
        return {"content": [{"type": "text", "text": "recorded"}]}

    opts = ClaudeAgentOptions(
        system_prompt=JUDGE_SYS,
        mcp_servers={"io": create_sdk_mcp_server(name="io", tools=[submit_judgement])},
        allowed_tools=["mcp__io__submit_judgement"],     # no web, no graph, no files
        max_turns=max_turns, model=model,
        permission_mode="bypassPermissions", max_budget_usd=budget_usd,
    )
    t0 = time.time()
    result = None
    prompt = PROMPT.format(topic=topic, a=render_idea(idea_a), b=render_idea(idea_b))
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, ResultMessage):
            result = msg
    j = holder.get("j")
    return {
        "judgement": j,
        "completed": j is not None,
        "seconds": round(time.time() - t0, 1),
        "num_turns": getattr(result, "num_turns", None),
        "total_cost_usd": getattr(result, "total_cost_usd", None),
        "usage": getattr(result, "usage", None),
        "stop_reason": getattr(result, "stop_reason", None),
        "is_error": getattr(result, "is_error", None),
    }


def build_row(seed_id: str, order: str, topic: str, g: dict, w: dict, res: dict) -> dict:
    """Un-blind the A/B scores back onto graph/web, scores FIRST for eyeballing."""
    j = res["judgement"]
    a_arm, b_arm = ORDERS[order]
    by_arm = {a_arm: "a", b_arm: "b"}
    ga, wa = by_arm["graph"], by_arm["web"]
    gn, gf = _clamp(j[f"{ga}_novelty"]), _clamp(j[f"{ga}_feasibility"])
    wn, wf = _clamp(j[f"{wa}_novelty"]), _clamp(j[f"{wa}_feasibility"])

    def winner(a, b):
        return "tie" if a == b else ("graph" if a > b else "web")

    def side(v):
        """Map the judge's 'A'/'B'/'neither' back onto the arm it actually was."""
        s = str(v or "").strip().upper()
        return {"A": a_arm, "B": b_arm}.get(s[:1] if s[:1] in ("A", "B") else "", "neither")

    def margin(v):
        m = str(v or "").strip().lower()
        return m if m in ("decisive", "clear", "slight", "none") else "none"

    return {
        # --- headline: what you want to see when you cat the jsonl ---
        "seed_id": seed_id, "order": order,
        "graph_novelty": gn, "graph_feasibility": gf,
        "web_novelty": wn, "web_feasibility": wf,
        "novelty_winner": winner(gn, wn), "feasibility_winner": winner(gf, wf),
        # the judge's forced call — the tiebreaker when the 1-10 scores are equal
        "more_novel": side(j.get("more_novel")), "novelty_margin": margin(j.get("novelty_margin")),
        "sounder": side(j.get("sounder")), "feasibility_margin": margin(j.get("feasibility_margin")),
        "same_idea": bool(j.get("same_idea")),
        "topic": topic,
        "graph_title": (g["idea"] or {}).get("title"),
        "web_title": (w["idea"] or {}).get("title"),
        # --- the judge's reasoning ---
        "graph_novelty_reason": j[f"{ga}_novelty_reason"],
        "graph_feasibility_reason": j[f"{ga}_feasibility_reason"],
        "web_novelty_reason": j[f"{wa}_novelty_reason"],
        "web_feasibility_reason": j[f"{wa}_feasibility_reason"],
        "same_idea_reason": j.get("same_idea_reason"),
        # --- provenance + cost (we care about judging cost too) ---
        "a_arm": a_arm, "b_arm": b_arm, "judge_model": res["model"],
        "seconds": res["seconds"], "num_turns": res["num_turns"],
        "total_cost_usd": res["total_cost_usd"], "usage": res["usage"],
        "stop_reason": res["stop_reason"], "is_error": res["is_error"],
        "gen_cost_usd": {"graph": g.get("total_cost_usd"), "web": w.get("total_cost_usd")},
        "gen_seconds": {"graph": g.get("seconds"), "web": w.get("seconds")},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", help="comma-separated seed_ids (default: all)")
    ap.add_argument("--limit", type=int, help="cap number of seeds (after filtering)")
    ap.add_argument("--orders", choices=("alt", "both", "gw", "wg"), default="alt",
                    help="'alt' (default): ONE judgement per seed, alternating which arm is "
                         "shown as A so positions are exactly balanced across the set. "
                         "'both' = the 2x order-swapped design; 'gw'/'wg' = force one side.")
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--max-turns", type=int, default=6)
    ap.add_argument("--budget", type=float, default=0.60, help="max_budget_usd per judgement")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between calls")
    ap.add_argument("--dry-run", action="store_true", help="no model call; just plan")
    args = ap.parse_args()

    if not GENERATIONS.exists():
        sys.exit(f"no generations at {GENERATIONS} — run gen.py first.")
    pairs = load_pairs()
    # order assignment is fixed by each seed's index in the FULL pair list, before any
    # filtering, so --limit / --seeds never shifts which side a seed shows as A.
    alt_order = {sid: ("gw" if i % 2 == 0 else "wg") for i, (sid, *_) in enumerate(pairs)}
    if args.seeds:
        keep = set(args.seeds.split(","))
        pairs = [p for p in pairs if p[0] in keep]
    if args.limit:
        pairs = pairs[: args.limit]
    if args.orders == "alt":
        units = [(p, alt_order[p[0]]) for p in pairs]
        orders = "alt (1/seed, balanced)"
    else:
        orders = ["gw", "wg"] if args.orders == "both" else [args.orders]
        units = [(p, o) for p in pairs for o in orders]
    done = done_keys()
    todo = [(p, o) for (p, o) in units if (p[0], o) not in done]
    print(f"pairs={len(pairs)} orders={orders} units={len(units)} "
          f"done={len(units) - len(todo)} todo={len(todo)}")

    if args.dry_run:
        for (sid, topic, g, w), o in todo[:2]:
            a_arm, b_arm = ORDERS[o]
            rows = {"graph": g, "web": w}
            print(f"\n--- {sid} order={o} (A={a_arm}, B={b_arm}) ---")
            print(PROMPT.format(topic=topic, a=render_idea(rows[a_arm]["idea"]),
                                b=render_idea(rows[b_arm]["idea"]))[:1200], "...")
        print(f"\n(dry-run) would run {len(todo)} judgements on {args.model}; "
              f"max_turns={args.max_turns} budget=${args.budget} each. No model called.")
        return

    import time

    async def go():
        spend = 0.0
        for i, ((sid, topic, g, w), o) in enumerate(todo, 1):
            a_arm, b_arm = ORDERS[o]
            rows = {"graph": g, "web": w}
            print(f"[{i}/{len(todo)}] {sid} order={o} · {topic[:46]}", flush=True)
            try:
                res = await judge_one(topic, rows[a_arm]["idea"], rows[b_arm]["idea"],
                                      model=args.model, max_turns=args.max_turns,
                                      budget_usd=args.budget)
            except KeyboardInterrupt:
                print("\ninterrupted — partial judgement not saved; safe to resume.")
                raise
            if not res["completed"]:
                print(f"    NO-JUDGEMENT (stop={res['stop_reason']}) — not saved, will retry",
                      flush=True)
                continue
            res["model"] = args.model
            row = build_row(sid, o, topic, g, w, res)
            append(row)                                   # persist immediately
            spend += res["total_cost_usd"] or 0.0
            same = " SAME-IDEA" if row["same_idea"] else ""
            print(f"    graph nov={row['graph_novelty']} feas={row['graph_feasibility']} | "
                  f"web nov={row['web_novelty']} feas={row['web_feasibility']} | "
                  f"novel:{row['more_novel']}({row['novelty_margin']}) "
                  f"sound:{row['sounder']}({row['feasibility_margin']}){same}  "
                  f"{res['seconds']}s ${res['total_cost_usd']} (run ${spend:.2f})", flush=True)
            if i < len(todo):
                time.sleep(args.sleep)

    try:
        asyncio.run(go())
    except KeyboardInterrupt:
        sys.exit(130)
    print(f"done. checkpoint: {CKPT}")


if __name__ == "__main__":
    main()
