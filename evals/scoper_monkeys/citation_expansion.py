"""Checkpointed OpenAlex citation traversal over the complete useful-work queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prior.models import Paper  # noqa: E402
from prior.sources import openalex  # noqa: E402
from adaptive_expansion import _receipt, _write_jsonl  # noqa: E402


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def expand_backward(queue_file: Path, out_dir: Path, *, batch_size: int = 100,
                    delay: float = 0.13, progress=print) -> None:
    """Resolve every stored backward reference, preserving every seed edge."""
    tasks = [row for row in _rows(queue_file) if row["direction"] == "backward"]
    ledger = out_dir / "citation-backward-ledger.jsonl"
    previous = _events(ledger)
    complete_batches = {row["batch"] for row in previous
                        if row.get("event") == "batch_terminal" and row.get("status") == "complete"}
    result_by_id = {row["paper"]["id"]: row["paper"] for row in previous
                    if row.get("event") == "result"}
    refs = sorted({ref for task in tasks for ref in task["paper"].get("referenced_works", [])
                   if ref.startswith("openalex:")})
    batches = [refs[i:i + batch_size] for i in range(0, len(refs), batch_size)]
    out_dir.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as handle:
        if not previous:
            handle.write(json.dumps({"event": "manifest", "direction": "backward",
                                     "queue_sha256": hashlib.sha256(queue_file.read_bytes()).hexdigest(),
                                     "tasks": len(tasks), "unique_reference_ids": len(refs),
                                     "batch_size": batch_size}) + "\n")
        for index, ids in enumerate(batches):
            if index in complete_batches:
                continue
            request = {"event": "request", "batch": index, "ids": ids,
                       "endpoint": "works/filter:ids.openalex"}
            handle.write(json.dumps(request) + "\n"); handle.flush()
            try:
                found = openalex.fetch_many(ids, batch=batch_size)
                for paper in found.values():
                    result_by_id[paper.id] = paper.to_dict()
                    handle.write(json.dumps({"event": "result", "batch": index,
                                             "paper": paper.to_dict()}, ensure_ascii=False) + "\n")
                missing = sorted(set(ids) - set(found))
                handle.write(json.dumps({"event": "batch_terminal", "batch": index,
                                         "status": "complete", "returned": len(found),
                                         "unresolved_ids": missing}) + "\n")
                handle.flush()
            except Exception as error:  # source state must not masquerade as empty
                handle.write(json.dumps({"event": "batch_terminal", "batch": index,
                                         "status": "pending_retry",
                                         "error_type": type(error).__name__,
                                         "message": openalex.redact_error(str(error))[:500]}) + "\n")
                handle.flush()
                progress(f"backward batch {index + 1}/{len(batches)} pending retry: {error}")
                break
            if (index + 1) % 25 == 0:
                progress(f"backward batches {index + 1}/{len(batches)}; works={len(result_by_id)}")
            time.sleep(delay)

    events = _events(ledger)
    complete_batches = {row["batch"] for row in events
                        if row.get("event") == "batch_terminal" and row.get("status") == "complete"}
    result_by_id = {row["paper"]["id"]: row["paper"] for row in events
                    if row.get("event") == "result"}
    edges = []
    task_states = []
    for task in tasks:
        paper = task["paper"]
        task_refs = [ref for ref in paper.get("referenced_works", []) if ref.startswith("openalex:")]
        state = "exhausted" if paper["id"].startswith("openalex:") else "source_unavailable"
        task_states.append({"task_id": task["task_id"], "work_key": task["work_key"],
                            "direction": "backward", "status": state,
                            "references_declared": len(task_refs),
                            "references_resolved": sum(ref in result_by_id for ref in task_refs)})
        for ref in task_refs:
            edges.append({"seed_work_key": task["work_key"], "seed_id": paper["id"],
                          "direction": "backward", "cited_id": ref,
                          "resolved": ref in result_by_id})
    candidates_file = out_dir / "citation-backward-candidates.jsonl"
    edges_file = out_dir / "citation-backward-edges.jsonl"
    tasks_file = out_dir / "citation-backward-tasks.jsonl"
    _write_jsonl(candidates_file, ({"paper": p} for p in result_by_id.values()))
    _write_jsonl(edges_file, edges)
    _write_jsonl(tasks_file, task_states)
    status_file = out_dir / "citation-backward-status.json"
    all_complete = len(complete_batches) == len(batches)
    status_file.write_text(json.dumps({
        "status": "complete" if all_complete else "pending_retry",
        "tasks": len(tasks), "batches_complete": len(complete_batches),
        "batches_total": len(batches), "unique_candidates": len(result_by_id),
        "edges": len(edges), "unresolved_edges": sum(not e["resolved"] for e in edges),
    }, indent=2) + "\n")
    if all_complete:
        _receipt(out_dir, "citation_expand_backward", [queue_file],
                 [ledger, candidates_file, edges_file, tasks_file, status_file],
                 deterministic=False,
                 parameters={"source": "openalex", "batch_size": batch_size,
                             "delay_seconds": delay, "terminal": "source_exhausted"})


def expand_forward_pass(queue_file: Path, out_dir: Path, *, per_page: int = 200,
                        delay: float = 0.13, max_tasks: int | None = None,
                        workers: int = 4, progress=print) -> None:
    """Fetch one additional cursor page per forward branch per invocation."""
    tasks = [row for row in _rows(queue_file) if row["direction"] == "forward"]
    ledger = out_dir / "citation-forward-ledger.jsonl"
    previous = _events(ledger)
    latest = {}
    for row in previous:
        if row.get("event") == "task_terminal":
            latest[row["task_id"]] = row
    eligible = [task for task in tasks if task["paper"]["id"].startswith("openalex:")
                and latest.get(task["task_id"], {}).get("status") != "exhausted"]
    if max_tasks is not None:
        eligible = eligible[:max_tasks]
    def fetch_task(task):
        prior = latest.get(task["task_id"], {})
        cursor = prior.get("next_cursor") or "*"
        try:
            papers, next_cursor = openalex.cited_by_page(
                task["paper"]["id"], cursor=cursor, per_page=per_page)
            results = [{"event": "result", "task_id": task["task_id"],
                        "seed_work_key": task["work_key"], "cursor": cursor,
                        "page_rank": rank, "paper": paper.to_dict()}
                       for rank, paper in enumerate(papers, 1)]
            exhausted = not next_cursor or not papers
            terminal = {"event": "task_terminal", "task_id": task["task_id"],
                        "status": "exhausted" if exhausted else "page_complete",
                        "cursor": cursor, "next_cursor": next_cursor or "",
                        "returned": len(papers)}
        except Exception as error:
            results = []
            terminal = {"event": "task_terminal", "task_id": task["task_id"],
                        "status": "pending_retry", "cursor": cursor,
                        "next_cursor": cursor, "error_type": type(error).__name__,
                        "message": openalex.redact_error(str(error))[:500]}
        if delay:
            time.sleep(delay)
        return task, results, terminal

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ledger.open("a") as handle, ThreadPoolExecutor(max_workers=workers) as executor:
        if not previous:
            handle.write(json.dumps({"event": "manifest", "direction": "forward",
                                     "queue_sha256": hashlib.sha256(queue_file.read_bytes()).hexdigest(),
                                     "per_page": per_page}) + "\n")
        futures = [executor.submit(fetch_task, task) for task in eligible]
        for index, future in enumerate(as_completed(futures), 1):
            task, results, terminal = future.result()
            for result in results:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.write(json.dumps(terminal) + "\n"); handle.flush()
            latest[task["task_id"]] = terminal
            if index % 25 == 0:
                progress(f"forward pass {index}/{len(eligible)}")

    events = _events(ledger)
    candidate_by_key = {}
    for row in events:
        if row.get("event") == "result":
            paper = Paper.from_dict(row["paper"])
            candidate_by_key[paper.key()] = row["paper"]
    latest = {}
    for row in events:
        if row.get("event") == "task_terminal":
            latest[row["task_id"]] = row
    candidates_file = out_dir / "citation-forward-candidates.jsonl"
    _write_jsonl(candidates_file, ({"paper": paper} for paper in candidate_by_key.values()))
    status_file = out_dir / "citation-forward-status.json"
    counts = {state: sum(row.get("status") == state for row in latest.values())
              for state in ("exhausted", "page_complete", "pending_retry")}
    status_file.write_text(json.dumps({"tasks_total": len(tasks), "openalex_tasks":
        sum(t["paper"]["id"].startswith("openalex:") for t in tasks),
        "tasks_touched": len(latest), "states": counts,
        "unique_candidates": len(candidate_by_key),
        "stage_status": "progressive_not_saturated"}, indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("direction", choices=("backward", "forward-pass"))
    ap.add_argument("--queue", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--per-page", type=int, default=200)
    ap.add_argument("--delay", type=float, default=0.13)
    ap.add_argument("--max-tasks", type=int)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    if args.direction == "backward":
        expand_backward(args.queue, args.out_dir, batch_size=args.batch_size, delay=args.delay)
    else:
        expand_forward_pass(args.queue, args.out_dir, per_page=args.per_page,
                            delay=args.delay, max_tasks=args.max_tasks, workers=args.workers)


if __name__ == "__main__":
    main()
