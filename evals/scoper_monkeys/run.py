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
        self.failures: dict[tuple[str, str], list[str]] = {}
        self.disabled_sources: set[str] = set()
        self.citation_seeds: set[tuple[str, str]] = set()

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
            event = dict(event)
            kind = event.pop("kind")
            if kind == "source_failure":
                self.failures.setdefault((branch_id, event["source"]), []).append(
                    event.get("error_type", "unknown")
                )
                self.disabled_sources.add(event["source"])
            paper = event.get("paper")
            if paper is not None:
                event["work_key"] = paper.key()
                event["paper"] = paper.to_dict()
            self.emit(kind, branch_id=branch_id, stage=stage, **event)
        return observe

    def close_query_branch(self, branch_id: str, stage: str, query: str,
                           sources: tuple[str, ...] = (
                               "openalex", "arxiv", "semanticscholar")) -> None:
        """Close each fixed-depth baseline source branch without calling it saturated."""
        for source in sources:
            errors = self.failures.get((branch_id, source), [])
            self.emit(
                "branch_terminal", branch_id=f"{branch_id}:{source}", stage=stage,
                parent_branch_id=branch_id, source=source, query=query,
                status="failed" if errors else "bounded",
                reason=("source_failure:" + ",".join(errors) if errors
                        else "original_policy_fixed_retrieval_depth"),
            )

    def citation_observer(self, stage: str):
        """Record the exact seed, provider and direction for each citation edge."""
        def observe(event: dict) -> None:
            event = dict(event)
            seed = event.pop("seed")
            paper = event.pop("paper")
            source = event["source"]
            direction = event["direction"]
            branch_id = f"{stage}:{source}:{direction}:{seed.key()}"
            seed_marker = (branch_id, seed.id)
            if seed_marker not in self.citation_seeds:
                self.citation_seeds.add(seed_marker)
                self.emit(
                    "seed", branch_id=branch_id, stage=stage, source=source,
                    direction=direction, seed_role="original_policy_selected",
                    work_key=seed.key(), paper=seed.to_dict(),
                )
            self.emit(
                "citation_path", branch_id=branch_id, stage=stage,
                seed_work_key=seed.key(), work_key=paper.key(), seed=seed.to_dict(),
                paper=paper.to_dict(), **event,
            )
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
        for source in sorted(recorder.disabled_sources):
            recorder.emit(
                "retrieval_request", branch_id=branch_id, stage=stage,
                source=source, query=query,
                parameters={"state": "pending_retry", "attempted": False},
            )
            recorder.emit(
                "source_failure", branch_id=branch_id, stage=stage,
                source=source, query=query, error_type="circuit_open",
                message="source paused after an earlier exhausted retry sequence",
                retry_or_fallback="pending_retry",
            )
            recorder.failures.setdefault((branch_id, source), []).append("circuit_open")
        papers = _before_cutoff(scoper.gather_candidates(
            [query], per_query=per_query, progress=progress,
            observe=recorder.retrieval_observer(branch_id, stage),
            use_openalex="openalex" not in recorder.disabled_sources,
            use_arxiv="arxiv" not in recorder.disabled_sources,
            use_s2="semanticscholar" not in recorder.disabled_sources,
        ), cutoff)
        recorder.close_query_branch(branch_id, stage, query)
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
                "retrieval_policy": "original_scoper_v1_fixed_depth",
                "screening_policy": "original_scoper_v1_binary_truncated_abstract",
                "stopping_policy": "original_scoper_v1_global_yield",
                "strict_topic_file": args.strict_topic_file,
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
            selected = {paper.id for paper in seeds}
            for paper in corpus:
                recorder.emit(
                    "seed", branch_id=f"{stage}:selection", stage=stage,
                    seed_role=("selected" if paper.id in selected else
                               "not_selected_by_original_policy"),
                    work_key=paper.key(), paper=paper.to_dict(),
                )
            new_oa, reached_oa = scoper.snowball(
                seeds, corpus=corpus, progress=progress,
                observe=recorder.citation_observer(stage), hop=hop,
            )
            if "semanticscholar" in recorder.disabled_sources:
                new_s2, reached_s2 = [], set()
                recorder.emit(
                    "branch_terminal", branch_id=f"{stage}:semanticscholar",
                    stage=stage, source="semanticscholar", status="pending",
                    reason="source_circuit_open_pending_retry",
                )
            else:
                try:
                    new_s2, reached_s2 = scoper.snowball_s2(
                        seeds, corpus=corpus, progress=progress,
                        observe=recorder.citation_observer(stage), hop=hop,
                    )
                except Exception as error:  # noqa: BLE001
                    new_s2, reached_s2 = [], set()
                    recorder.disabled_sources.add("semanticscholar")
                    recorder.failures.setdefault(
                        (f"{stage}:semanticscholar", "semanticscholar"), []
                    ).append(type(error).__name__)
                    recorder.emit(
                        "source_failure", branch_id=f"{stage}:semanticscholar",
                        stage=stage, source="semanticscholar", query="citation expansion",
                        error_type=type(error).__name__, message=str(error)[:500],
                        retry_or_fallback="pending_retry",
                    )
                    recorder.emit(
                        "branch_terminal", branch_id=f"{stage}:semanticscholar",
                        stage=stage, source="semanticscholar", status="failed",
                        reason="citation_source_failure_pending_retry",
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
            for branch_id, _seed_id in sorted(recorder.citation_seeds):
                if branch_id.startswith(stage + ":"):
                    recorder.emit(
                        "branch_terminal", branch_id=branch_id, stage=stage,
                        status="bounded", reason="original_policy_fixed_citation_depth",
                    )
            if stopped:
                break
        if args.strict_topic_file:
            strict_topic = Path(args.strict_topic_file).read_text()
            stage = "strict_rescreen"
            recorder.candidates(stage, corpus, "strict_scope")
            strict_kept, strict_dropped = _scope_stage(
                strict_topic, stage, corpus, recorder, model=args.model,
                use_prefilter=False, progress=progress,
            )
            corpus = [paper for paper, _ in strict_kept]
            recorder.emit(
                "snapshot", stage=stage, candidates=len(strict_kept) + len(strict_dropped),
                new_kept=len(strict_kept), corpus=len(corpus), stop_triggered=False,
                stop_reason="historical_strict_core_rescreen",
            )
        failed = [
            {"branch_id": branch, "source": source, "errors": errors}
            for (branch, source), errors in recorder.failures.items()
        ]
        recorder.emit(
            "run_terminal", status="incomplete" if failed else "bounded",
            reason=("unresolved_source_failures" if failed
                    else "original_policy_fixed_depth_and_yield_stopping"),
            open_tasks=failed,
        )
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
    ap.add_argument("--strict-topic-file")
    return ap


if __name__ == "__main__":
    collect(parser().parse_args())
