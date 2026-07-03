"""Backfill OpenAlex `type` into the corpus (we fetched it all along but discarded
it). Snapshots papers.jsonl first, batch-fetches type for every openalex-sourced
paper, writes it back. Additive — only adds the `type` field.

    PRIOR_DATA_DIR=data_hackathon PYTHONPATH=src python3 scripts/backfill_types.py
"""

import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "src"))
from prior import config                          # noqa: E402

UA = {"User-Agent": config.USER_AGENT}


def _log(m):
    print(m, flush=True)


def main():
    pp = config.RAW / "papers.jsonl"
    snap = config.RAW / "papers_pretype.jsonl"
    if not snap.exists():
        shutil.copy2(pp, snap)
        _log(f"snapshot -> {snap.name}")

    papers = [json.loads(l) for l in pp.read_text().splitlines() if l.strip()]
    oa = {p["id"].split(":")[-1]: p for p in papers if p["id"].startswith("openalex:")}
    ids = list(oa)
    _log(f"fetching type for {len(ids)} openalex papers ...")

    got = {}
    for k in range(0, len(ids), 50):
        chunk = ids[k:k + 50]
        try:
            r = requests.get("https://api.openalex.org/works",
                             params={"filter": "ids.openalex:" + "|".join(chunk),
                                     "per_page": 50, "select": "id,type"},
                             headers=UA, timeout=40)
            for w in r.json().get("results", []):
                got[w["id"].split("/")[-1]] = w.get("type") or ""
        except Exception as e:  # noqa: BLE001
            _log(f"  batch {k}: {e}")
        time.sleep(0.3)

    n = 0
    dist = Counter()
    for wid, p in oa.items():
        if wid in got:
            p["type"] = got[wid]
            dist[got[wid]] += 1
            n += 1
    pp.write_text("\n".join(json.dumps(p) for p in papers) + "\n")
    _log(f"backfilled type on {n} papers")
    _log("corpus type distribution: " + ", ".join(f"{k}:{v}" for k, v in dist.most_common()))


if __name__ == "__main__":
    main()
