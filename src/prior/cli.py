"""Command-line interface for Prior.

    prior build "<topic>"      ingest + read + map -> data/atlas/atlas.json
    prior ingest "<topic>"     fetch papers only
    prior read                 run Reader over cached papers
    prior map                  run Cartographer over cached papers + claims
    prior ask "<question>"     Navigator, forward (state of evidence)
    prior origin "<concept>"   Navigator, backward (trace to origin)
    prior info                 summarise the current atlas
    prior serve                launch the web API (for the React UI)
    prior view                 render the atlas as ONE self-contained HTML file (no server)
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
                         help="expand backward along citations N hops (reach origins)")
    p_build.add_argument("--view", action="store_true",
                         help="render a self-contained HTML viewer when done (no server)")
    p_build.add_argument("--open", action="store_true", dest="open_",
                         help="with --view: open the viewer in a browser")

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

    p_eval = sub.add_parser("eval", help="run the evaluation scorecard")
    p_eval.add_argument("--data", default=None, help="cached reading dir for faithfulness")
    p_eval.add_argument("--no-llm", action="store_true", help="key-free metrics only")
    p_eval.add_argument("--sample", type=int, default=6)

    p_srv = sub.add_parser("serve", help="launch the web API")
    p_srv.add_argument("--host", default="127.0.0.1")
    p_srv.add_argument("--port", type=int, default=8077)

    p_dmn = sub.add_parser("daemon", help="continuous ingestion into the live graph")
    p_dmn.add_argument("--topic", action="append", default=[], dest="topics",
                       help="watch this topic via raw search (repeatable)")
    p_dmn.add_argument("--topic-def", action="append", default=[], dest="topic_defs",
                       help="watch this topic via the Scoper relevance filter — pass a "
                            "definition with include/exclude criteria (repeatable)")
    p_dmn.add_argument("--rounds", type=int, default=1)
    p_dmn.add_argument("--per-topic", type=int, default=10)
    p_dmn.add_argument("--workers", type=int, default=None)
    p_dmn.add_argument("--watch", action="store_true", help="loop forever")
    p_dmn.add_argument("--interval", type=int, default=300)

    p_col = sub.add_parser("collection", help="manage named paper collections")
    col_sub = p_col.add_subparsers(dest="col_cmd", required=True)
    c_load = col_sub.add_parser("load", help="load a release bundle as a collection")
    c_load.add_argument("bundle_dir", help="dir with papers_core.jsonl + contributions_core_consensus.json")
    c_load.add_argument("--name", required=True, help="collection name, e.g. core-v0.2")
    c_load.add_argument("--topic", default="", help="display topic for the UI")
    c_load.add_argument("--source", default="", help="provenance, e.g. release URL")
    col_sub.add_parser("list", help="list collections with counts")
    c_tag = col_sub.add_parser("tag-legacy", help="tag pre-collections data with a name")
    c_tag.add_argument("--name", default="legacy")

    p_clu = sub.add_parser("cluster", help="(re)cluster a collection + cache its render payload")
    p_clu.add_argument("--collection", required=True)

    p_cl = sub.add_parser("claims", help="backfill the local claim layer for a collection")
    p_cl.add_argument("--collection", required=True)
    p_cl.add_argument("--fulltext-dir", required=True, help="dir of <paper_id>.txt full texts")
    p_cl.add_argument("--workers", type=int, default=None)

    p_se = sub.add_parser("selfeval", help="LLM self-eval: Claude labels its own extraction")
    p_se.add_argument("--collection", required=True)
    p_se.add_argument("--kind", action="append", default=[], dest="kinds",
                      choices=["contribution", "edge", "claim"], help="repeatable; default all")
    p_se.add_argument("--limit", type=int, default=0,
                      help="max NOT-yet-judged items per kind this run (0 = all remaining)")
    p_se.add_argument("--workers", type=int, default=None)
    p_se.add_argument("--model", default=None,
                      help="judge model id (default READER_MODEL); pair with PRIOR_LLM_BACKEND")
    p_se.add_argument("--judge", default="claude",
                      help="annotator label to store verdicts under, e.g. opus / qwen")

    p_cal = sub.add_parser("calibration",
                           help="AUC-ROC + accuracy-vs-threshold of stored scores vs the judge")
    p_cal.add_argument("--collection", default=None, help="limit to one collection")

    p_view = sub.add_parser("view",
                            help="render the atlas as ONE self-contained HTML file (no server)")
    p_view.add_argument("--out", default=None,
                        help="output HTML path (default: data/atlas/view.html)")
    p_view.add_argument("--open", action="store_true", dest="open_",
                        help="open the rendered file in a browser")
    p_view.add_argument("--evolution", action="store_true",
                        help="staged reveal: papers -> contributions -> relations")
    p_view.add_argument("--classic", action="store_true",
                        help="classic vis-network view instead of the D3 tabbed viewer")
    p_view.add_argument("--contributions", action="store_true",
                        help="contributions graph (needs contributions.json)")

    args = ap.parse_args(argv)

    if args.cmd == "build":
        atlas = pipeline.build(args.topic, max_papers=args.max_papers,
                               relate=not args.no_relate, cite_hops=args.cite_hops)
        try:
            pipeline.sink_to_neo4j(atlas)   # push into the live graph store
        except Exception as e:  # noqa: BLE001 — atlas.json still written
            print(f"(neo4j sink skipped: {e})")
        if args.view:
            from . import render_html
            p = render_html.render()
            print(f"viewer: {p}")
            if args.open_:
                import webbrowser
                webbrowser.open(p.resolve().as_uri())
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
    elif args.cmd == "view":
        from pathlib import Path
        from . import render_html
        out = Path(args.out) if args.out else None
        if args.evolution:
            p = render_html.render_evolution(out_path=out)
        elif args.contributions:
            p = render_html.render_contributions(out_path=out)
        elif not args.classic:
            p = render_html.render_global(out_path=out)
        else:
            p = render_html.render(out_path=out)
        print(f"wrote {p}")
        if args.open_:
            import webbrowser
            webbrowser.open(p.resolve().as_uri())
    elif args.cmd == "eval":
        from . import eval_suite
        r = eval_suite.run(data_dir=args.data, with_llm=not args.no_llm, sample=args.sample)
        for m in r["metrics"]:
            v = "—" if m["value"] is None else m["value"]
            print(f"  [{m['status']:>7}] {m['name']}: {v}  (target {m['threshold']})")
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("prior.web.api:app", host=args.host, port=args.port)
    elif args.cmd == "daemon":
        from . import daemon
        if not args.topics and not args.topic_defs:
            sys.exit("daemon needs at least one --topic or --topic-def")
        daemon.run(args.topics, topic_defs=args.topic_defs, rounds=args.rounds,
                   per_topic=args.per_topic, workers=args.workers,
                   watch=args.watch, interval=args.interval)
    elif args.cmd == "collection":
        from . import collections as colmod
        if args.col_cmd == "load":
            st = colmod.load_bundle(args.bundle_dir, collection=args.name,
                                    topic=args.topic, source=args.source)
            print(f"loaded: {st}")
        elif args.col_cmd == "list":
            for c in colmod.list_collections():
                print(f"  {c['name']:18} {c['papers']:5} papers   {c['topic']}")
        elif args.col_cmd == "tag-legacy":
            print(f"tagged {colmod.tag_untagged(args.name)} nodes as {args.name}")
    elif args.cmd == "cluster":
        from . import render
        st = render.recluster(args.collection)
        print(f"clustered {args.collection}: {st}")
    elif args.cmd == "claims":
        from . import claims as claimsmod
        claimsmod.run(args.collection, args.fulltext_dir, workers=args.workers)
    elif args.cmd == "selfeval":
        from . import selfeval
        selfeval.run(args.collection, kinds=args.kinds or None,
                     limit=args.limit, workers=args.workers,
                     model=args.model, judge=args.judge)
    elif args.cmd == "calibration":
        from . import evaluation
        for d in evaluation.calibration(args.collection)["dimensions"]:
            head = f"{d['kind']}/{d['signal']}"
            if not d["n"]:
                print(f"  {head}: no scored+judged items"); continue
            print(f"  {head}  n={d['n']}  AUC={d['auc']}  acc={d['accuracy']}  "
                  f"mean={d['mean_score']}  ECE={d['ece']}")
            for t in d["thresholds"]:
                acc = "n/a" if t["accuracy"] is None else f"{t['accuracy']:.3f}"
                print(f"      >={t['t']:<4} keep {t['kept']:>4} "
                      f"(cov {t['coverage']})  acc {acc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
