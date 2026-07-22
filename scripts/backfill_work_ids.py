"""Backfill `work_id` on Paper nodes ingested before the identity existed.

work_id is the source-independent identity of a WORK (hash of the normalised
title), letting the arXiv preprint, its v2, and the published OpenAlex record
be recognised as one paper while each keeps its own id for provenance. New
ingests carry it automatically (Paper.to_dict); this stamps the back catalogue
and reports any cross-source duplicates it reveals.

    PYTHONPATH=src python3 scripts/backfill_work_ids.py
"""
from __future__ import annotations

from collections import Counter

from prior import graph
from prior.models import Paper

with graph.session() as s:
    rows = s.run("MATCH (p:Paper) WHERE p.work_id IS NULL "
                 "RETURN p.id AS id, p.title AS title").data()
    updates = [{"id": r["id"],
                "w": Paper(id=r["id"], source="", title=r["title"] or "",
                           abstract="", url="").work_id()}
               for r in rows]
    if updates:
        s.run("UNWIND $rows AS r MATCH (p:Paper {id:r.id}) SET p.work_id = r.w",
              rows=updates)
    print(f"backfilled {len(updates)} papers")

    dupes = s.run("MATCH (p:Paper) WITH p.work_id AS w, collect(p.id) AS ids "
                  "WHERE w STARTS WITH 'work:' AND size(ids) > 1 "
                  "RETURN w, ids").data()
    for d in dupes:
        print(f"  duplicate work {d['w']}: {d['ids']}")
    print(f"{len(dupes)} works exist under multiple source records"
          + (" — consider merging or linking them" if dupes else ""))
