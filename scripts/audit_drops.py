"""Audit the Scoper's drop decisions: are the rejected papers actually noise?

Two checks:
  1. a readable sample of dropped papers with the filter's one-line reason
     (precision — do the rejections look justified?)
  2. cross-check the DROPPED set against the gold bib (recall — did we throw away
     anything we know is relevant? those are false negatives to worry about)

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/audit_drops.py
"""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from prior import config                       # noqa: E402
from prior.sources import arxiv, openalex      # noqa: E402
from check_recall import norm, parse_bib       # noqa: E402


def _resolve_titles(dropped):
    oa = [x["id"] for x in dropped if x["id"].startswith("openalex:")]
    ax = [x["id"].split(":", 1)[1] for x in dropped if x["id"].startswith("arxiv:")]
    titles = {}
    for pid, p in openalex.fetch_many(oa).items():
        titles[pid] = p.title
    for pid, p in arxiv.fetch_ids(ax).items():
        titles[pid.split("v")[0]] = p.title       # normalise version suffix
    return titles


def _title_for(pid, titles):
    if pid in titles:
        return titles[pid]
    if pid.startswith("arxiv:"):
        base = "arxiv:" + pid.split(":", 1)[1].split("v")[0]
        return titles.get(base)
    return None


def main():
    d = json.loads((config.ATLAS / "scope.json").read_text())
    dropped = d.get("dropped", [])
    print(f"kept {len(d.get('kept', []))} | dropped {len(dropped)}\n")
    if not dropped:
        return

    titles = _resolve_titles(dropped)
    rows = [(_title_for(x["id"], titles), x["reason"]) for x in dropped]
    named = [(t, r) for t, r in rows if t]
    print(f"resolved titles for {len(named)}/{len(dropped)} dropped papers\n")

    print("=== random sample of DROPPED papers (title — reason) ===")
    random.seed(0)
    for t, reason in random.sample(named, min(25, len(named))):
        print(f"  - {t[:70]}\n      ↳ {reason[:95]}")

    print("\n=== gold papers that were DROPPED (false negatives) ===")
    gold = parse_bib(config.DATA / "gold.bib")
    fn = 0
    for t, reason in named:
        nt = norm(t)
        for g in gold:
            gn = norm(g["title"])
            if len(nt & gn) / max(1, len(nt | gn)) >= 0.6:
                print(f"  ! {g['title'][:62]}\n      ↳ dropped: {reason[:90]}")
                fn += 1
                break
    if fn == 0:
        print("  none — no known-relevant (gold) paper was dropped ✓")
    else:
        print(f"\n  {fn} gold papers dropped — but they re-enter as snowball anchors")


if __name__ == "__main__":
    main()
