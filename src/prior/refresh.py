"""Scheduled freshness: scan → propose → approve → version.

Keeps the atlas up to date without letting an imperfect pipeline silently
mutate it. A `scan` searches each watched topic for papers published since the
topic's watermark (date-windowed — relevance rank alone never surfaces new
work) and writes them to a PENDING batch on disk; nothing touches the graph.
A human reviews the batch, then `approve` ingests the accepted papers via the
daemon's incremental merge and records a graph version.

Versioning model: every approved batch is a version (v1, v2, ...). Each Paper
node ingested through this path carries `added_in_version`, and
data/refresh/versions.json logs what each version added (papers + graph
totals after). Rollback of a version = delete its papers by that property.

State on disk (data/refresh/):
    state.json            {topic: {"watermark": "YYYY-MM-DD"}}
    pending/<batch>.json  proposed papers awaiting review
    approved/<batch>.json archived batches (with per-paper decisions)
    versions.json         append-only version log
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import config
from .models import Paper
from .sources import arxiv, openalex

DIR = config.DATA / "refresh"
PENDING = DIR / "pending"
APPROVED = DIR / "approved"
STATE = DIR / "state.json"
VERSIONS = DIR / "versions.json"

# Re-scan a few days behind the watermark: indexing lag means a paper can
# appear in OpenAlex/arXiv after its publication date has already passed.
OVERLAP_DAYS = 7


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _save(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def _in_graph(paper: Paper, progress=print) -> bool:
    """Graph-dedup check (by source id OR work_id, so another source's record
    of the same work counts) that tolerates Neo4j being down/uninstalled —
    scan and propose must run standalone (approval re-checks via MERGE)."""
    global _graph_warned
    try:
        from . import graph
        return graph.have_paper(paper.id) or graph.have_work(paper.work_id())
    except Exception:  # noqa: BLE001 — driver missing or DB unreachable
        if not _graph_warned:
            progress("  (graph unreachable — skipping already-ingested dedup)")
            _graph_warned = True
        return False


_graph_warned = False


def _pending_keys() -> set[str]:
    """Ids AND title-keys of everything already queued — OpenAlex and arXiv key
    the same paper differently, so cross-source dedup needs Paper.key()."""
    keys = set()
    if PENDING.exists():
        for f in PENDING.glob("*.json"):
            for row in _load(f, {}).get("papers", []):
                p = Paper.from_dict(row["paper"])
                keys |= {p.id, p.key()}
    return keys


def scan(topics: list[str], *, per_topic: int = 25, progress=print) -> Path | None:
    """Date-windowed search of each topic since its watermark; write ONE pending
    batch of never-seen papers. Registers new topics with a 30-day lookback."""
    state = _load(STATE, {})
    today = date.today().isoformat()
    seen = _pending_keys()
    proposed = []
    for t in topics:
        wm = state.get(t, {}).get("watermark")
        since = ((date.fromisoformat(wm) - timedelta(days=OVERLAP_DAYS)).isoformat()
                 if wm else (date.today() - timedelta(days=30)).isoformat())
        progress(f"scanning '{t}' since {since} ...")
        papers: dict[str, Paper] = {}
        ok = 0
        # Each source fails soft: an outage in one must not kill the weekly run.
        try:
            for p in openalex.search(t, max_papers=per_topic, from_date=since):
                papers[p.key()] = p
            ok += 1
        except Exception as e:  # noqa: BLE001
            progress(f"  ! openalex failed: {e}")
        try:
            for p in arxiv.search(t, max_papers=per_topic, from_date=since):
                papers.setdefault(p.key(), p)
            ok += 1
        except Exception as e:  # noqa: BLE001
            progress(f"  ! arxiv failed: {e}")
        fresh = [p for p in papers.values()
                 if not ({p.id, p.key()} & seen) and not _in_graph(p, progress)]
        seen |= {k for p in fresh for k in (p.id, p.key())}
        proposed += [{"topic": t, "paper": p.to_dict(), "status": "proposed"} for p in fresh]
        progress(f"  {len(papers)} found, {len(fresh)} new → proposed")
        if ok:   # both sources down → keep the old watermark so the window re-runs
            state[t] = {"watermark": today}
    _save(STATE, state)
    if not proposed:
        progress("nothing new — no batch written")
        return None
    batch_id = f"batch-{today}"
    path = PENDING / f"{batch_id}.json"
    if path.exists():                       # same-day rescan: merge into today's batch
        prior = _load(path, {}).get("papers", [])
        proposed = prior + proposed
    _save(path, {"id": batch_id, "scanned": today, "papers": proposed})
    progress(f"wrote {path} ({len(proposed)} proposed)")
    return path


def propose(arxiv_ids: list[str], *, topic: str = "manual", progress=print) -> Path | None:
    """Manually queue specific arXiv papers (e.g. one someone flagged)."""
    fetched = arxiv.fetch_ids(arxiv_ids)
    for aid in arxiv_ids:
        if any(aid in p.id for p in fetched.values()):
            continue
        p = arxiv.fetch_abs(aid)     # export API lags new listings; abs page is live
        if p:
            fetched[p.id] = p
        else:
            progress(f"  ! could not fetch {aid}")
    seen = _pending_keys()
    fresh = [p for p in fetched.values()
             if not ({p.id, p.key()} & seen) and not _in_graph(p, progress)]
    if not fresh:
        progress("all already in the graph or pending")
        return None
    today = date.today().isoformat()
    path = PENDING / f"batch-{today}.json"
    batch = _load(path, {"id": f"batch-{today}", "scanned": today, "papers": []})
    batch["papers"] += [{"topic": topic, "paper": p.to_dict(), "status": "proposed"}
                        for p in fresh]
    _save(path, batch)
    progress(f"proposed {len(fresh)} paper(s) → {path}")
    return path


def pending(progress=print) -> list[dict]:
    batches = [_load(f, {}) for f in sorted(PENDING.glob("*.json"))] if PENDING.exists() else []
    for b in batches:
        progress(f"\n{b['id']}  ({len(b['papers'])} proposed)")
        for i, row in enumerate(b["papers"]):
            p = row["paper"]
            progress(f"  [{i}] {p.get('date', '????')[:10]}  {p['title'][:90]}"
                     f"  ({row['topic']})")
    if not batches:
        progress("no pending batches")
    return batches


def approve(batch_id: str, *, skip: list[int] | None = None,
            workers: int = 4, progress=print) -> dict:
    """Ingest a reviewed batch (minus skipped indices) via the daemon's
    incremental merge; stamp a new graph version."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from . import daemon, graph
    path = PENDING / f"{batch_id}.json"
    if not path.exists():
        raise SystemExit(f"no pending batch {batch_id}")
    batch = _load(path, {})
    skip = set(skip or [])
    log = _load(VERSIONS, [])
    version = len(log) + 1
    accepted, results = [], []
    for i, row in enumerate(batch["papers"]):
        row["status"] = "skipped" if i in skip else "approved"
        if i not in skip:
            accepted.append(Paper.from_dict(row["paper"]))
    progress(f"approving {len(accepted)}/{len(batch['papers'])} papers as v{version} ...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(daemon.process_paper, p): p for p in accepted}
        for f in as_completed(futs):
            p = futs[f]
            try:
                st = f.result()
                results.append(st)
                progress(f"  + {p.short_cite()}: {st['contribs']} contribs, "
                         f"{st['claims']} claims, {st['edges']} edges")
            except Exception as e:  # noqa: BLE001
                results.append({"id": p.id, "error": str(e)})
                progress(f"  ! {p.short_cite()}: ERROR {e}")
    with graph.session() as s:
        s.run("MATCH (p:Paper) WHERE p.id IN $ids SET p.added_in_version = $v",
              ids=[p.id for p in accepted], v=version)
    entry = {"version": version, "date": date.today().isoformat(), "batch": batch_id,
             "papers": [p.id for p in accepted], "results": results,
             "graph_after": graph.summary()}
    log.append(entry)
    _save(VERSIONS, log)
    _save(APPROVED / f"{batch_id}.json", batch)
    path.unlink()
    progress(f"v{version} recorded; graph now: {entry['graph_after']}")
    return entry


def rollback(version: int, progress=print) -> int:
    """Detach-delete every paper (and its contributions/claims) added in a version."""
    from . import graph
    with graph.session() as s:
        n = s.run(
            "MATCH (p:Paper {added_in_version:$v}) "
            "OPTIONAL MATCH (p)-[:HAS_CONTRIBUTION]->(k:Contribution) "
            "OPTIONAL MATCH (cl:Claim)-[:STATED_IN]->(p) "
            "DETACH DELETE k, cl, p RETURN count(DISTINCT p) AS n", v=version).single()["n"]
    log = [e for e in _load(VERSIONS, []) if e["version"] != version]
    _save(VERSIONS, log)
    progress(f"rolled back v{version}: {n} papers removed")
    return n
