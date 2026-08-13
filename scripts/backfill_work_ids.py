"""Backfill stable work IDs and strong DOI/arXiv aliases on older Paper nodes.

``work_id`` remains the migration-stable normalized-title hash. Strong aliases
provide safer cross-source/version matching despite title changes. New ingests
carry both automatically via ``Paper.to_dict``; this stamps the back catalogue
and reports title-hash duplicates for manual review.

    PYTHONPATH=src python3 scripts/backfill_work_ids.py
"""
from __future__ import annotations

from prior import graph
from prior.models import Paper

with graph.session() as s:
    rows = s.run("""MATCH (p:Paper)
                    WHERE p.work_id IS NULL OR p.work_aliases IS NULL
                    RETURN p.id AS id, p.title AS title, p.doi AS doi,
                           p.url AS url""").data()
    updates = []
    for r in rows:
        paper = Paper(id=r["id"], source="", title=r["title"] or "",
                      abstract="", url=r.get("url") or "", doi=r.get("doi"))
        updates.append({"id": r["id"], "w": paper.work_id(),
                        "aliases": paper.identity_aliases()})
    if updates:
        s.run("""UNWIND $rows AS r MATCH (p:Paper {id:r.id})
                 SET p.work_id = coalesce(p.work_id, r.w),
                     p.work_aliases = r.aliases""",
              rows=updates)
    print(f"backfilled {len(updates)} papers")

    dupes = s.run("MATCH (p:Paper) WITH p.work_id AS w, collect(p.id) AS ids "
                  "WHERE w STARTS WITH 'work:' AND size(ids) > 1 "
                  "RETURN w, ids").data()
    for d in dupes:
        print(f"  duplicate work {d['w']}: {d['ids']}")
    print(f"{len(dupes)} works exist under multiple source records"
          + (" — consider merging or linking them" if dupes else ""))
