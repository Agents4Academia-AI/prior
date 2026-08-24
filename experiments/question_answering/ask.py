#!/usr/bin/env python3
"""Ask your OWN question against Prior's atlas, and see how the agent answered it.

This is the friendly front door to the experiment. One command runs the graph arm
on a question you type, prints the answer, and draws the exploration figure:

    python ask.py "Which papers actually extend AIDE?"

You get four files in out/ask/, named after the question:

    <id>.answer.md   the answer, the papers it named, its confidence and limits
    <id>.svg         the exploration figure (PowerPoint-ready vector, Arial)
    <id>.md          the call-by-call narrative, including the FULL justification
                     text of every relationship the agent read
    <id>.json        the explored subgraph in Prior's GlobalGraph shape

RUN THIS IN YOUR OWN TERMINAL. It uses your Claude Code subscription via the Agent
SDK — no API key, no metered spend — but it does consume your rate window. One
question costs roughly $0.25 of subscription-equivalent credit and takes ~30-90s.

  • Checkpointed: re-asking the same question replays from the saved row for free.
  • Ctrl+C safe: a partial answer is never saved.
  • Budget-capped: --budget, default $1.20, a runaway guard rather than a target.

Examples
    python ask.py --dry-run "..."          free — shows the prompt, calls nothing
    python ask.py "..." --id aide          choose the output filename
    python ask.py "..." --arm web          same question, browser arm (no figure)
    python ask.py --replot aide            redraw the figure only — free
    python ask.py --replot aide --max-listed 8 --aspect 0.5 --png
    python ask.py --list                   what you have asked so far

How to read the figure: visualisations_explained.md
How the arms work:      ARMS.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
OUT = HERE / "out" / "ask"
CKPT = OUT / "answers.jsonl"
MODEL = "claude-sonnet-5"


def slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:n].rstrip("-") or "question")


def load() -> list[dict]:
    if not CKPT.exists():
        return []
    return [json.loads(l) for l in CKPT.read_text(encoding="utf-8").splitlines()
            if l.strip()]


def answer_md(row: dict) -> str:
    a = row.get("answer") or {}
    named = a.get("papers_named") or []
    L = [f"# {row['question']}", "",
         f"*Answered by the **{row['arm'].upper()}** arm "
         f"({row.get('model', MODEL)}) in {row.get('seconds')}s, "
         f"{row.get('n_explore', 0)} exploration calls, "
         f"{row.get('payload_chars', 0):,} payload chars.*", "",
         str(a.get("answer", "")).strip(), "",
         f"## Papers named ({len(named)})", ""]
    L += [f"{i}. {t}" for i, t in enumerate(named, 1)] or ["*none*"]
    L += ["", f"**Stated confidence:** {a.get('confidence', '?')}  ",
          f"**Stated limits:** {a.get('limits', '—')}"]
    if row["arm"] == "graph" and row.get("tool_args"):
        L += ["", "## What it did", "",
              "| # | call | arguments | chars back |", "|---|---|---|---|"]
        for i, t in enumerate(row["tool_args"], 1):
            name = t["tool"].split("__")[-1]
            args = ", ".join(f"`{k}`={json.dumps(v)[:60]}"
                             for k, v in (t.get("args") or {}).items())
            L.append(f"| {i} | `{name}` | {args or '—'} | "
                     f"{(t.get('result_chars') or 0):,} |")
        L += ["", "*Figure: the `.svg` beside this file. Full justification text "
              "of every relationship it read: the `.md`.*"]
    return "\n".join(L) + "\n"


def draw(row: dict, args) -> list[Path]:
    """Replay the logged calls against the local atlas and render the figure.

    Zero cost and deterministic: the atlas is local, so re-issuing the logged
    arguments returns exactly the rows the agent saw. This is a replay, not a
    reconstruction — which is what makes the figure evidence.
    """
    # `trace` is also a stdlib module, so load ours by path rather than by name —
    # otherwise this works from this directory and mysteriously fails from anywhere
    # else.
    import importlib.util
    spec = importlib.util.spec_from_file_location("qa_trace", HERE / "trace.py")
    tr = importlib.util.module_from_spec(spec)
    sys.modules["qa_trace"] = tr
    spec.loader.exec_module(tr)

    T = tr.replay(row, tr.GraphAtlas())
    tr.prune(T, max_listed=args.max_listed, no_citations=args.no_citations,
             drop=[d for d in args.drop.split(",") if d.strip()], keep=[])
    pos = tr.layout(T, spread=args.spread, aspect=args.aspect,
                    metrics=tr.label_metrics(T, args.font_scale))
    opts = SimpleNamespace(
        font_scale=args.font_scale, width=args.width, aspect=args.aspect,
        spread=args.spread, label_listed=None, queries=args.queries,
        # the bold heading only — the question itself is drawn under it, wrapped,
        # by the renderer, so putting it here too would overflow the line
        title=args.title or T.qid.replace("-", " ").upper(), font=None,
        no_title=False, no_timeline=False, no_legend=False, no_caption=False,
        no_rings=False)

    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"{T.qid}.svg"
    svg.write_text(tr.render_svg(T, pos, opts), encoding="utf-8")
    (OUT / f"{T.qid}.json").write_text(
        json.dumps(tr.to_global_graph(T), indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / f"{T.qid}.md").write_text(tr.narrative(T), encoding="utf-8")
    (OUT / f"{T.qid}.answer.md").write_text(answer_md(row), encoding="utf-8")

    n = lambda e: sum(1 for x in T.nodes.values() if x["engagement"] == e)  # noqa: E731
    print(f"\n  figure: {len(T.steps)} calls · {n('focus')} papers chosen · "
          f"{n('read')} read in depth · {n('listed')} listed · "
          f"{sum(1 for e in T.edges.values() if e['kind'] == 'semantic')} typed edges")
    if args.png:
        made = tr.to_png([svg], args.png)
        print(f"  {made} PNG at {args.png}x" if made
              else "  (no Chrome/Edge found — SVG only)")
    return [svg, OUT / f"{T.qid}.answer.md", OUT / f"{T.qid}.md",
            OUT / f"{T.qid}.json"]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?", help="the question to ask, in quotes")
    ap.add_argument("--id", help="output filename stem (default: from the question)")
    ap.add_argument("--arm", choices=("graph", "web", "null"), default="graph",
                    help="which environment answers. Only graph produces a figure")
    ap.add_argument("--list", action="store_true", help="list previous questions")
    ap.add_argument("--replot", metavar="ID",
                    help="redraw a saved question's figure — free, no model call")
    ap.add_argument("--force", action="store_true", help="re-ask even if saved")
    ap.add_argument("--dry-run", action="store_true", help="free: show the prompt")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--max-turns", type=int, default=14)
    ap.add_argument("--budget", type=float, default=1.20,
                    help="max spend for this one answer (runaway guard)")
    # figure controls — the same ones trace.py takes
    ap.add_argument("--max-listed", type=int, default=14,
                    help="cap the faint outer ring of merely-listed papers")
    ap.add_argument("--no-citations", action="store_true",
                    help="drop the citation layer, leaving only typed relations")
    ap.add_argument("--drop", default="", help="comma-separated titles to prune")
    ap.add_argument("--queries", choices=("auto", "on", "off"), default="auto")
    ap.add_argument("--font-scale", type=float, default=1.1)
    ap.add_argument("--aspect", type=float, default=0.62,
                    help="lower = wider, shorter figure (type prints bigger)")
    ap.add_argument("--spread", type=float, default=0.92)
    ap.add_argument("--width", type=int, default=1900)
    ap.add_argument("--title", help="override the figure title")
    ap.add_argument("--png", nargs="?", const=2, type=int, default=None,
                    metavar="SCALE", help="also write a PNG via headless Chrome")
    args = ap.parse_args()

    rows = load()

    if args.list:
        if not rows:
            print("nothing asked yet.  python ask.py \"your question\"")
            return
        print(f"{'id':<44} {'arm':6} {'calls':>5} {'papers':>7}  question")
        for r in rows:
            a = r.get("answer") or {}
            print(f"{r['question_id']:<44} {r['arm']:6} {r.get('n_explore', 0):>5} "
                  f"{len(a.get('papers_named') or []):>7}  {r['question'][:60]}")
        print(f"\nfiles in {OUT}")
        return

    if args.replot:
        row = next((r for r in rows if r["question_id"] == args.replot), None)
        if not row:
            sys.exit(f"no saved question {args.replot!r}. `python ask.py --list`")
        if row["arm"] != "graph":
            sys.exit(f"{args.replot} was answered by the {row['arm']} arm — only the "
                     f"graph arm leaves a replayable trace.")
        for p in draw(row, args):
            print(f"  {p}")
        return

    if not args.question:
        ap.error("give a question in quotes, or use --list / --replot")

    qid = args.id or slug(args.question)
    saved = next((r for r in rows
                  if r["question_id"] == qid and r["arm"] == args.arm), None)
    if saved and not args.force:
        print(f"already answered ({qid}, {args.arm} arm) — replaying for free.\n"
              f"Use --force to ask again.\n")
        print(str((saved.get("answer") or {}).get("answer", "")).strip())
        if saved["arm"] == "graph":
            for p in draw(saved, args):
                print(f"  {p}")
        return

    if args.dry_run:
        from qa_arms import TASK, SYS
        print(f"--- system prompt [{args.arm}] ---\n{SYS[args.arm][:600]} ...\n")
        print(f"--- task ---\n{TASK.format(question=args.question)[:900]} ...\n")
        print(f"(dry-run) would run 1 unit on {args.model}, "
              f"budget ${args.budget}. No model called.")
        return

    from qa_arms import run_one, GraphAtlas
    atlas = GraphAtlas() if args.arm == "graph" else None
    print(f"asking the {args.arm} arm: {args.question}\n"
          f"  (Ctrl+C is safe — a partial answer is never saved)\n", flush=True)

    try:
        res = asyncio.run(run_one(args.arm, args.question, atlas, model=args.model,
                                  max_turns=args.max_turns, budget_usd=args.budget))
    except KeyboardInterrupt:
        sys.exit("\ninterrupted — nothing saved.")

    row = {"question_id": qid, "family": "ask", "expected_winner": "",
           "model": args.model, **res}
    if not res["completed"]:
        sys.exit("no answer came back (the model never called submit_answer). "
                 "Nothing saved — try again, or raise --max-turns.")
    if res.get("off_arm_tools"):
        print(f"  !! SEAL BREACH: this arm used {res['off_arm_tools']} — the row is "
              f"contaminated. Investigate before trusting it.", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    a = res.get("answer") or {}
    print("\n" + "=" * 72)
    print(str(a.get("answer", "")).strip())
    print("=" * 72)
    print(f"\npapers named ({len(a.get('papers_named') or [])}): "
          + "; ".join(a.get("papers_named") or []) or "none")
    print(f"confidence: {a.get('confidence')}   limits: {a.get('limits')}")
    print(f"\n{res['n_explore']} calls · {res['payload_chars']:,} payload chars · "
          f"{res['seconds']}s · ${res.get('total_cost_usd', 0):.3f}")

    if args.arm == "graph":
        for p in draw(row, args):
            print(f"  {p}")
        print("\nPowerPoint: Insert > Pictures > This Device, pick the .svg.")
        print("How to read it: visualisations_explained.md")
    else:
        print(f"\nwritten to {OUT / (qid + '.answer.md')}"
              f"\n(only the graph arm leaves a replayable trace, so there is no figure)")


if __name__ == "__main__":
    main()
