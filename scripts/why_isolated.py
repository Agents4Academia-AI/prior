#!/usr/bin/env python3
"""Why are 86 contributions isolated (no cross-paper edge)? Distinguish
'genuinely orphan' from 'Cartographer missed the edge' by checking whether each
isolated contribution is content-similar to a CONNECTED one (if it is, an edge
should plausibly exist → recall miss). Also: do they come from otherwise-connected
papers (→ likely miss) or fully-isolated papers (→ peripheral)?
"""
from __future__ import annotations
import os
import ast, json
from collections import Counter, defaultdict
from pathlib import Path

DIR = Path(os.environ.get("PRIOR_DATA_DIR", "data") + "/atlas")
C = json.loads((DIR / "contributions_core.json").read_text())
A = {p["id"]: p for p in json.loads((DIR / "atlas.json").read_text())["papers"]}
cons, edges = C["contributions"], C["edges"]
ids = {c["id"] for c in cons}
stmt = {c["id"]: c.get("statement", "") for c in cons}
cpaper = {c["id"]: c["paper_id"] for c in cons}
kind = {c["id"]: c.get("kind", "") for c in cons}

STOP = set("the a an of for to in on and or but with without via using use is are be as that this these "
           "those by from at into over under can we our their its it they show shows propose introduce "
           "while which when where what how also such new based across between both than more less".split())
tok = lambda s: {w for w in "".join(c if c.isalnum() or c == " " else " " for c in (s or "").lower()).split()
                 if len(w) > 2 and w not in STOP}
T = {cid: tok(stmt[cid]) for cid in ids}

deg = Counter()
for e in edges:
    if e["src"] in ids and e["dst"] in ids and e["src"] != e["dst"]:
        deg[e["src"]] += 1; deg[e["dst"]] += 1
iso = [c for c in ids if deg[c] == 0]
conn = [c for c in ids if deg[c] > 0]

# does the isolated contribution's PAPER have any connected contribution?
paper_conn = defaultdict(bool)
for c in conn:
    paper_conn[cpaper[c]] = True

jac = lambda a, b: len(a & b) / len(a | b) if (a or b) else 0
rows = []
for c in iso:
    best, bj = None, 0.0
    for d in conn:
        j = jac(T[c], T[d])
        if j > bj:
            bj, best = j, d
    rows.append((c, bj, best, paper_conn[cpaper[c]]))

hi = [r for r in rows if r[1] >= 0.18]      # quite similar to a connected one
mid = [r for r in rows if 0.10 <= r[1] < 0.18]
lo = [r for r in rows if r[1] < 0.10]
from_conn_paper = sum(1 for r in rows if r[3])

print(f"isolated contributions: {len(iso)} (of {len(ids)})")
print(f"  from a paper that DOES have connected contributions: {from_conn_paper}  "
      f"(→ paper is in the graph; this contribution just wasn't linked)")
print(f"  from fully-isolated papers: {len(iso)-from_conn_paper}  (→ peripheral paper)")
print(f"\nkinds of isolated (vs overall):")
ik = Counter(kind[c] for c in iso); ok = Counter(kind[c] for c in ids)
for k, n in ik.most_common():
    print(f"  {k:18s} {n:3d} isolated  / {ok[k]:3d} total  ({n/ok[k]:.0%} of this kind isolated)")
print(f"\ncontent similarity of each isolated contribution to its NEAREST connected one:")
print(f"  >=0.18 (likely a MISSED edge): {len(hi)} ({len(hi)/len(iso):.0%})")
print(f"  0.10-0.18 (borderline)       : {len(mid)} ({len(mid)/len(iso):.0%})")
print(f"  <0.10 (genuinely orphan)     : {len(lo)} ({len(lo)/len(iso):.0%})")


def cite(p):
    au = A.get(p, {}).get("authors") or []
    if isinstance(au, str):
        try: au = ast.literal_eval(au)
        except Exception: au = []
    return (au[0].split()[-1] if au else p)[:14]


print("\nexamples — LIKELY MISSED EDGE (isolated but ~ a connected one):")
for c, bj, best, _ in sorted(hi, key=lambda r: -r[1])[:4]:
    print(f"  sim {bj:.2f}  {cite(cpaper[c])}: {stmt[c][:72]}")
    print(f"           ~ {cite(cpaper[best])}: {stmt[best][:72]}")
print("\nexamples — GENUINELY ORPHAN (no similar connected contribution):")
for c, bj, best, _ in sorted(lo, key=lambda r: r[1])[:4]:
    print(f"  sim {bj:.2f}  {cite(cpaper[c])}: {stmt[c][:80]}")
