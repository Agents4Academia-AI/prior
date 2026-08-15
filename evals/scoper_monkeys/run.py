"""Collect an instrumented Scoper run for the small viability experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior import completeness, scoper  # noqa: E402
from prior.models import Paper  # noqa: E402
from prior.sources import openalex  # noqa: E402

from common import load_gold  # noqa: E402
from ledger import (  # noqa: E402
    SCHEMA_VERSION, code_version, new_run_id, sha256_text, utc_now, validate_event,
)


STAGE_ORDER = [
    "single_query",
    "multi_query",
    "adaptive_1",
    "adaptive_2",
    "adaptive_3",
    "adaptive_4",
    "adaptive_5",
    "snowball_1",
    "snowball_2",
    "snowball_3",
    "snowball_4",
]


class Recorder:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("w")
        self.order = 0
        self.run_id = new_run_id()
        self.first_seen: dict[str, str] = {}

    def emit(self, event: str, **fields) -> None:
        self.order += 1
        row = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "event_id": f"{self.run_id}:e{self.order:06d}",
            "event": event,
            "order": self.order,
            "recorded_at": utc_now(),
            **fields,
        }
        validate_event(row)
        self.handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.handle.flush()

    def candidates(self, stage: str, papers: list[Paper], channel: str) -> None:
        for paper in papers:
            key = paper.key()
            if key in self.first_seen:
                self.emit("reached_again", stage=stage, channel=channel,
                          work_key=key, paper=paper.to_dict())
                continue
            self.first_seen[key] = stage
            self.emit("candidate", stage=stage, channel=channel,
                      work_key=key, paper=paper.to_dict())

    def decisions(self, stage: str, kept, dropped) -> None:
        for paper, reason in kept:
            self.emit("decision", stage=stage, work_key=paper.key(),
                      decision="kept", reason=reason, paper=paper.to_dict())
        for paper, reason in dropped:
            self.emit("decision", stage=stage, work_key=paper.key(),
                      decision="dropped", reason=reason, paper=paper.to_dict())

    def close(self) -> None:
        self.handle.close()

    def retrieval_observer(self, branch_id: str, stage: str):
        def observe(event: dict) -> None:
            kind = event.pop("kind")
            paper = event.get("paper")
            if paper is not None:
                event["work_key"] = paper.key()
                event["paper"] = paper.to_dict()
            self.emit(kind, branch_id=branch_id, stage=stage, **event)
        return observe


def _dedup(papers: list[Paper]) -> list[Paper]:
    return scoper._dedup_cross_source(papers)


def _before_cutoff(papers: list[Paper], cutoff: int | None) -> list[Paper]:
    if cutoff is None:
        return papers
    return [paper for paper in papers if paper.year is None or paper.year <= cutoff]


def _scope_stage(topic: str, stage: str, candidates: list[Paper], recorder: Recorder,
                 *, model: str | None, use_prefilter: bool, progress=print):
    gated: list[Paper] = []
    survivors = candidates
    if use_prefilter and candidates:
        survivors, gated = scoper.prefilter(topic, candidates, progress=progress)
    kept, dropped = (scoper.scope(topic, survivors, model=model, progress=progress)
                     if survivors else ([], []))
    dropped += [(paper, "pre-filtered: low topic similarity") for paper in gated]
    recorder.decisions(stage, kept, dropped)
    return kept, dropped


def _gather_query_branches(queries: list[str], *, stage: str, kind: str,
                           motivation: str, per_query: int, cutoff: int | None,
                           recorder: Recorder, known_before: set[str], progress=print):
    """Gather each query as an auditable branch and retain overlap for attribution."""
    pooled: list[Paper] = []
    branches: list[tuple[str, str, list[Paper]]] = []
    for index, query in enumerate(queries, 1):
        branch_id = f"{stage}:q{index:03d}"
        recorder.emit("query", stage=stage, branch_id=branch_id, kind=kind,
                      queries=[query], motivation=motivation)
        papers = _before_cutoff(scoper.gather_candidates(
            [query], per_query=per_query, progress=progress,
            observe=recorder.retrieval_observer(branch_id, stage),
        ), cutoff)
        branches.append((branch_id, query, papers))
        pooled.extend(papers)
    pool = _dedup(pooled)
    first_branch: dict[str, str] = {}
    for branch_id, _query, papers in branches:
        for paper in papers:
            first_branch.setdefault(paper.key(), branch_id)
    return pool, branches, first_branch


def _record_branch_growth(recorder: Recorder, *, stage: str, branches,
                          first_branch: dict[str, str], known_before: set[str], kept,
                          corpus_before: int) -> None:
    kept_keys = {paper.key() for paper, _ in kept}
    running_corpus = corpus_before
    for branch_id, query, papers in branches:
        keys = {paper.key() for paper in papers}
        new_keys = {key for key in keys if key not in known_before
                    and first_branch.get(key) == branch_id}
        new_kept = new_keys & kept_keys
        running_corpus += len(new_kept)
        recorder.emit(
            "branch_snapshot", branch_id=branch_id, stage=stage, query=query,
            attribution="first_observed", returned_unique=len(keys),
            globally_new=len(new_keys), rediscovered=len(keys - new_keys),
            newly_included=len(new_kept),
            eligible_yield=len(new_kept) / max(1, len(new_keys)),
            corpus_after=running_corpus,
        )


def collect(args) -> None:
    topic = Path(args.topic_file).read_text()
    gold = load_gold(args.gold)
    recorder = Recorder(Path(args.out))
    progress = lambda message: print(message, flush=True)
    try:
        if args.queries_file:
            queries = [
                line.strip() for line in Path(args.queries_file).read_text().splitlines()
                if line.strip()
            ]
        else:
            queries = scoper.propose_queries(topic, model=args.model)
            if args.save_queries:
                target = Path(args.save_queries)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n".join(queries) + "\n")
        if not queries:
            raise RuntimeError("no queries generated or supplied")

        recorder.emit(
            "manifest", case=args.case, scope=topic, scope_sha256=sha256_text(topic),
            topic_file=str(args.topic_file), gold_file=str(args.gold), gold_n=len(gold),
            code_version=code_version(ROOT),
            parameters={
                "cutoff_year": args.cutoff_year, "per_query": args.per_query,
                "recover_rounds": args.recover_rounds, "hops": args.hops,
                "use_prefilter": not args.no_prefilter, "epsilon": args.epsilon,
                "model": args.model, "sources": ["openalex", "arxiv", "semanticscholar"],
            },
        )
        # Monkey baseline: one literal OpenAlex query.
        single = _before_cutoff(
            openalex.search(queries[0], max_papers=args.per_query), args.cutoff_year
        )
        recorder.candidates("single_query", single, "openalex")

        # Multi-source, multi-query search and one common scope decision.
        search_pool, branches, first_branch = _gather_query_branches(
            queries, stage="multi_query", kind="probe",
            motivation="Initial probe derived from the frozen scope.",
            per_query=args.per_query, cutoff=args.cutoff_year, recorder=recorder,
            known_before=set(), progress=progress,
        )
        recorder.candidates("multi_query", search_pool, "search")
        kept, dropped = _scope_stage(
            topic, "multi_query", search_pool, recorder, model=args.model,
            use_prefilter=not args.no_prefilter, progress=progress,
        )
        _record_branch_growth(
            recorder, stage="multi_query", branches=branches,
            first_branch=first_branch, known_before=set(), kept=kept, corpus_before=0,
        )
        corpus = [paper for paper, _ in kept]
        known = {paper.key() for paper in search_pool}
        search_keys = set(known)
        all_dropped = list(dropped)
        recorder.emit("snapshot", stage="multi_query", candidates=len(search_pool),
                      new_kept=len(kept), corpus=len(corpus), stop_triggered=False)

        # Adaptive query recovery.
        asked = {query.lower() for query in queries}
        for round_index in range(1, args.recover_rounds + 1):
            stage = f"adaptive_{round_index}"
            followups = [
                query for query in scoper.followup_queries(
                    topic, corpus, all_dropped, model=args.model
                )
                if query.lower() not in asked
            ]
            asked |= {query.lower() for query in followups}
            if not followups:
                recorder.emit("snapshot", stage=stage, candidates=0, new_kept=0,
                              corpus=len(corpus), stop_triggered=True,
                              stop_reason="no_followup_queries")
                break
            known_before = set(known)
            pool, branches, first_branch = _gather_query_branches(
                followups, stage=stage, kind="reformulation",
                motivation=(f"After {len(corpus)} included and {len(all_dropped)} "
                            "excluded records, the Scoper identified a retrieval gap."),
                per_query=args.per_query, cutoff=args.cutoff_year, recorder=recorder,
                known_before=known_before, progress=progress,
            )
            new = [paper for paper in pool if paper.key() not in known]
            recorder.candidates(stage, new, "adaptive_search")
            search_keys |= {paper.key() for paper in new}
            known |= {paper.key() for paper in new}
            newly_kept, newly_dropped = _scope_stage(
                topic, stage, new, recorder, model=args.model,
                use_prefilter=not args.no_prefilter, progress=progress,
            )
            _record_branch_growth(
                recorder, stage=stage, branches=branches, first_branch=first_branch,
                known_before=known_before, kept=newly_kept, corpus_before=len(corpus),
            )
            corpus.extend(paper for paper, _ in newly_kept)
            all_dropped.extend(newly_dropped)
            yield_rate = len(newly_kept) / max(1, len(new))
            stopped = yield_rate < args.epsilon
            recorder.emit("snapshot", stage=stage, candidates=len(new),
                          new_kept=len(newly_kept), corpus=len(corpus),
                          yield_rate=yield_rate, stop_triggered=stopped,
                          stop_reason="low_yield" if stopped else "")
            if stopped:
                break

        # Citation expansion, retaining reached-again events for channel overlap.
        snow_keys: set[str] = set()
        for hop in range(1, args.hops + 1):
            stage = f"snowball_{hop}"
            seeds = list(corpus)[:200] if hop == 1 else scoper.high_yield_seeds(corpus)
            new_oa, reached_oa = scoper.snowball(
                seeds, corpus=corpus, progress=progress
            )
            new_s2, reached_s2 = scoper.snowball_s2(
                seeds, corpus=corpus, progress=progress
            )
            snow_keys |= reached_oa | reached_s2
            pool = _before_cutoff(_dedup(new_oa + new_s2), args.cutoff_year)
            recorder.candidates(stage, pool, "citation")
            snow_keys |= {paper.key() for paper in pool}
            new = [paper for paper in pool if paper.key() not in known]
            known |= {paper.key() for paper in new}
            newly_kept, newly_dropped = _scope_stage(
                topic, stage, new, recorder, model=args.model,
                use_prefilter=not args.no_prefilter, progress=progress,
            )
            corpus.extend(paper for paper, _ in newly_kept)
            all_dropped.extend(newly_dropped)
            yield_rate = len(newly_kept) / max(1, len(new))
            stopped = not newly_kept or yield_rate < args.epsilon
            estimate = completeness.capture_recapture(
                len(search_keys), len(snow_keys), len(search_keys & snow_keys)
            )
            recorder.emit(
                "snapshot", stage=stage, candidates=len(new),
                new_kept=len(newly_kept), corpus=len(corpus),
                yield_rate=yield_rate, stop_triggered=stopped,
                stop_reason="no_new_kept" if not newly_kept else (
                    "low_yield" if stopped else ""
                ),
                completeness=estimate,
            )
            if stopped:
                break
    finally:
        recorder.close()


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--topic-file", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--queries-file")
    ap.add_argument("--save-queries")
    ap.add_argument("--cutoff-year", type=int)
    ap.add_argument("--per-query", type=int, default=25)
    ap.add_argument("--recover-rounds", type=int, default=2, choices=range(0, 6))
    ap.add_argument("--hops", type=int, default=2, choices=range(0, 5))
    ap.add_argument("--epsilon", type=float, default=0.03)
    ap.add_argument("--no-prefilter", action="store_true")
    ap.add_argument("--model")
    return ap


if __name__ == "__main__":
    collect(parser().parse_args())
