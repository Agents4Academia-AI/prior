# Handoff: relation direction is unreliable (Cartographer / relate)

The Cartographer reliably detects *that* two contributions are in a directed
relationship (`builds_on` / `refines`), but the **direction it assigns (`src` →
`dst`) is not a trustworthy precedence signal**. This surfaced in the viewer:
clicking an earlier paper showed it "building on" a paper published years later.

## Evidence
Across the 212 `builds_on` edges in the core graph, comparing `year(src)` vs
`year(dst)`:

| | count |
|---|---|
| same year (can't order) | 88 |
| **`src` is the *older* endpoint** (src can't be the deriver) | **83** |
| `src` is the newer endpoint (consistent with src = deriver) | 41 |

So among the 124 dated, differing-year pairs, the direction is chronologically
**consistent only ~33% of the time** — worse than a coin flip. There is no stable
convention being followed; the direction is effectively noise. (`refines` is too
sparse — 9 total — to matter either way.)

## Why it matters
Precedence / lineage is a headline feature. The unreliable direction propagates to:
- relation wording ("A builds on B" vs "B built on by A"),
- the graph **arrowheads**,
- the frontier **lineage-depth** layout (parent/child from `src`/`dst`).

The viewer currently **works around** it by inferring direction from **year** (the
older work is the antecedent — chronology strictly bounds precedence) and showing
same-year/unknown pairs as undirected `(≈)`. That's a band-aid; the data should be
right at the source.

## What to fix (Cartographer)
1. **Separate detection from direction.** The model is good at "these two are
   builds-on related"; it's weak at "which built on which". Treat them as two
   outputs.
2. **Set direction by chronology, not the model.** Once a `builds_on`/`refines`
   pair is detected, make the **earlier** contribution the antecedent (`dst`) and
   the later one the deriver (`src`). Document and enforce the convention
   (`src` = derivative/newer, `dst` = antecedent/older).
3. **Same-date → emit as undirected.** When the two share a date (preprint races,
   same month), don't fabricate a direction. Add `directed: false` /
   `precedence: "ambiguous"` so consumers can render it without an arrow.
4. **Validate at emission.** Re-run the `atlas_review.py` `precedence_year_conflict`
   check as a gate (it already flags "derivative predates antecedent"); a clean
   build should have zero such conflicts once direction is chronology-derived.

Month-level dates (see `scoper-dates-handoff.md`) shrink the same-year bucket and
make the chronology rule sharper.

## Verify
```python
import json
g=json.load(open("graph.json"))           # or contributions_core_consensus.json + years
yr={c["id"]:c["year"] for c in g["contribs"]}
from collections import Counter
c=Counter()
for e in g["contribLinks"]:
    if e["rel"]!="builds_on": continue
    ys,yt=yr.get(e["source"]),yr.get(e["target"])
    if ys is None or yt is None or ys==yt: c["same/unknown"]+=1
    else: c["src_older(wrong)" if ys<yt else "src_newer(ok)"]+=1
print(c)   # goal after fix: src_older(wrong) == 0
```

Cross-ref: `scoper-dates-handoff.md` (month dates sharpen this),
`atlas_review.py` (`precedence_year_conflict` gate), `gen_atlas_view.py`
(year-inference workaround in the relation panel + frontier).
