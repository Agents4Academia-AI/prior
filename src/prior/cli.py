"""Command-line interface for Prior.

    prior build "<topic>"      ingest + read + map -> data/atlas/atlas.json
    prior ingest "<topic>"     fetch papers only
    prior read                 run Reader over cached papers
    prior map                  run Cartographer over cached papers + claims
    prior ask "<question>"     Navigator, forward (state of evidence)
    prior origin "<concept>"   Navigator, backward (trace to origin)
    prior info                 summarise the current atlas
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
    p_build.add_argument("--cite-hops", type=int, default=0,
                         help="expand backward along citations N hops (reaches origins)")

    p_ing = sub.add_parser("ingest", help="fetch papers only")
    p_ing.add_argument("topic")
    p_ing.add_argument("--max-papers", type=int, default=None)
    p_ing.add_argument("--cite-hops", type=int, default=0,
                       help="expand backward along citations N hops (reaches origins)")

    sub.add_parser("read", help="run Reader over cached papers")

    p_map = sub.add_parser("map", help="run Cartographer over cached papers+claims")
    p_map.add_argument("--no-relate", action="store_true")

    p_ask = sub.add_parser("ask", help="forward: state of evidence")
    p_ask.add_argument("question")
    p_ask.add_argument("--contributions", action="store_true",
                       help="assess over the contributions graph (not raw claims)")

    p_org = sub.add_parser("origin", help="backward: trace to origin")
    p_org.add_argument("concept")
    p_org.add_argument("--contributions", action="store_true",
                       help="trace over the contributions graph (not raw claims)")

    p_con = sub.add_parser("contributions",
                           help="extract papers' self-declared contributions (full text)")
    p_con.add_argument("--limit", type=int, default=None)

    sub.add_parser("info", help="summarise the current atlas")
    p_view = sub.add_parser("view", help="render the atlas to an interactive HTML graph")
    p_view.add_argument("--contributions", action="store_true",
                        help="show only contribution claims (filter definitional/background)")
    p_view.add_argument("--evolution", action="store_true",
                        help="staged reveal: papers → contributions → relations")

    args = ap.parse_args(argv)

    if args.cmd == "build":
        pipeline.build(args.topic, max_papers=args.max_papers,
                       relate=not args.no_relate, cite_hops=args.cite_hops)
    elif args.cmd == "ingest":
        papers = pipeline.ingest(args.topic, max_papers=args.max_papers,
                                 cite_hops=args.cite_hops)
        print(f"{len(papers)} papers cached.")
    elif args.cmd == "read":
        papers = pipeline.load_papers()
        if not papers:
            sys.exit("No cached papers. Run `prior ingest` first.")
        claims = pipeline.read_all(papers)
        print(f"{len(claims)} claims extracted.")
    elif args.cmd == "map":
        papers, claims = pipeline.load_papers(), pipeline.load_claims()
        if not papers or not claims:
            sys.exit("Need cached papers and claims. Run `prior ingest` + `prior read`.")
        atlas = cartographer.build(papers, claims, relate=not args.no_relate)
        atlas.save()
        print(atlas.summary())
    elif args.cmd == "ask":
        atlas = pipeline.contributions_atlas() if args.contributions else _load_atlas()
        print(navigator.ask(atlas, args.question).render())
    elif args.cmd == "origin":
        atlas = pipeline.contributions_atlas() if args.contributions else _load_atlas()
        print(navigator.origin(atlas, args.concept).render())
    elif args.cmd == "contributions":
        papers = pipeline.load_papers()
        if not papers:
            sys.exit("No cached papers. Run `prior build \"<topic>\"` first.")
        cs = pipeline.extract_contributions(papers, limit=args.limit)
        print(f"\n{len(cs)} contributions → {pipeline._contributions_path()}")
    elif args.cmd == "info":
        print(_load_atlas().summary())
    elif args.cmd == "view":
        from . import render_html
        if not (config.ATLAS / "atlas.json").exists():
            sys.exit("No atlas found. Run `prior build \"<topic>\"` first.")
        if args.evolution:
            if not (config.ATLAS / "contributions.json").exists():
                sys.exit("Run `prior contributions` first (needs contributions + relations).")
            path = render_html.render_evolution()
        elif args.contributions and (config.ATLAS / "contributions.json").exists():
            path = render_html.render_contributions()   # real self-declared contributions
        else:
            path = render_html.render(contributions_only=args.contributions)
        print(f"atlas view → {path}\n  open in a browser:  file://{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
