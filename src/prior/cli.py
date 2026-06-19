"""Command-line interface for Prior.

    prior build "<topic>"      ingest + read + map -> data/atlas/atlas.json
    prior ingest "<topic>"     fetch papers only
    prior read                 run Reader over cached papers
    prior map                  run Cartographer over cached papers + claims
    prior ask "<question>"     Navigator, forward (state of evidence)
    prior origin "<concept>"   Navigator, backward (trace to origin)
    prior info                 summarise the current atlas
    prior serve                launch the web API (for the React UI)
"""

from __future__ import annotations

import argparse
import sys

from . import cartographer, config, navigator, pipeline
from .atlas import Atlas


def _load_atlas() -> Atlas:
    path = config.ATLAS / "atlas.json"
    if not path.exists():
        sys.exit("No atlas found. Run `prior build \"<topic>\"` first.")
    return Atlas.load(path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="prior", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="ingest + read + map")
    p_build.add_argument("topic")
    p_build.add_argument("--max-papers", type=int, default=None)
    p_build.add_argument("--no-relate", action="store_true",
                         help="skip LLM claim-relation finding (fast first pass)")

    p_ing = sub.add_parser("ingest", help="fetch papers only")
    p_ing.add_argument("topic")
    p_ing.add_argument("--max-papers", type=int, default=None)

    sub.add_parser("read", help="run Reader over cached papers")

    p_map = sub.add_parser("map", help="run Cartographer over cached papers+claims")
    p_map.add_argument("--no-relate", action="store_true")

    p_ask = sub.add_parser("ask", help="forward: state of evidence (over the graph)")
    p_ask.add_argument("question")

    p_solved = sub.add_parser("solved", help="has this problem/hypothesis been solved?")
    p_solved.add_argument("problem")

    p_org = sub.add_parser("origin", help="backward: trace to origin")
    p_org.add_argument("concept")

    sub.add_parser("info", help="summarise the current atlas")

    p_srv = sub.add_parser("serve", help="launch the web API")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8077)

    args = ap.parse_args(argv)

    if args.cmd == "build":
        atlas = pipeline.build(args.topic, max_papers=args.max_papers,
                               relate=not args.no_relate)
        try:
            pipeline.sink_to_neo4j(atlas)   # push into the live graph store
        except Exception as e:  # noqa: BLE001 — atlas.json still written
            print(f"(neo4j sink skipped: {e})")
    elif args.cmd == "ingest":
        papers = pipeline.ingest(args.topic, max_papers=args.max_papers)
        print(f"{len(papers)} papers cached.")
    elif args.cmd == "read":
        papers = pipeline.load_papers()
        if not papers:
            sys.exit("No cached papers. Run `prior ingest` first.")
        r = pipeline.read_all(papers)
        print(f"{len(r.contributions)} contributions, {len(r.claims)} claims, "
              f"{len(r.local_edges)} local edges.")
    elif args.cmd == "map":
        papers, reading = pipeline.load_papers(), pipeline.load_reading()
        if not papers or not reading.contributions:
            sys.exit("Need cached papers and reading. Run `prior ingest` + `prior read`.")
        atlas = cartographer.build(papers, reading, relate=not args.no_relate)
        atlas.save()
        print(atlas.summary())
    elif args.cmd == "ask":
        from . import agent
        a = agent.ask(args.question)
        print(f"VERDICT: {a.verdict.upper()}\n\n{a.answer}\n")
        for s in a.supporting:
            print(f"  + {s}")
        for s in a.contradicting:
            print(f"  - {s}")
        for s in a.open_questions:
            print(f"  ? {s}")
        if a.verdict == "not_found":
            print(f"\nClosest: {a.closest}\nGap: {a.gap}")
    elif args.cmd == "solved":
        from . import agent
        s = agent.has_been_solved(args.problem)
        print(f"VERDICT: {s.verdict.upper()}\n\n{s.summary}\n")
        print(f"Addressed by: {', '.join(s.addressed_by) or '(none)'}")
        print(f"Consensus: {s.consensus}")
        print(f"\nClosest: {s.closest}\nGap: {s.gap}")
    elif args.cmd == "origin":
        print(navigator.origin(_load_atlas(), args.concept).render())
    elif args.cmd == "info":
        print(_load_atlas().summary())
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("prior.web.api:app", host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
