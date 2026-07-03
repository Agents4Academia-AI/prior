# Handoff: capture full publication dates (Scoper)

The atlas only stores `year`. The frontier / chronology view needs **month-level**
dates — most of the corpus bunches into 2024–2025, so a year axis collapses
"what came first". The source APIs already return full dates; we're discarding
them in favour of `year`. Capture them at ingestion.

## What's missing
- `papers_core.jsonl` / `atlas.json` carry `year` only — **no `date` field**.
- Of the 152 core papers: 57 (37%) have arXiv ids (month derivable for free from
  the id), 95 (63%) are OpenAlex (year-only locally, but the API has full dates).

## The signal (all three sources already return it)
| source | where the date is | notes |
|---|---|---|
| **OpenAlex** | `work["publication_date"]` (e.g. `"2024-08-12"`) | already in the response you fetch — just store it |
| **arXiv** | Atom `<published>` (first version) → `YYYY-MM-DD` | first *appearance*; truest for precedence |
| **Semantic Scholar** | `paper["publicationDate"]` | sometimes null → see fallback |

## What to do
1. **Add `date` (ISO `YYYY-MM-DD`) per paper**, alongside `year`, sourced as above.
2. **Fallback chain** when a full date is missing (first that resolves):
   1. arXiv id present (`arxiv:YYMM.xxxxx`) → derive `20YY-MM-01` from the id
      (zero-cost, covers ~37% even with no API call).
   2. else `{year}-01-01`, low-confidence.
   - Also emit `date_precision`: `"day" | "month" | "year"` so consumers know how
     far to trust the granularity.
3. **Precedence rule (matters for lineage):** when a paper exists as preprint +
   published (version variants), record the **earliest** date — the preprint.
   Don't let an OpenAlex venue date (often months after the preprint) override an
   earlier arXiv `<published>`. (Same rule as `atlas_review.py`'s
   `version_variant` → "use earliest/preprint date for precedence".)
4. **Backfill the 152 core papers** — re-pull OpenAlex `publication_date` + derive
   arXiv ids (both free, no key). Target: 100% have ≥ `year` precision, ~95%+ month
   or better.

## Schema / downstream contract
The field must flow into `atlas.json` / `papers_core.jsonl` per paper:
```json
{ "id": "...", "year": 2024, "date": "2024-08-12", "date_precision": "day", "date_source": "openalex" }
```
The viewer side is mine: `gen_atlas_view.py` reads `date` (falling back to `year`)
and switches the frontier rings from year → month. No other coordination needed —
just `date` present on the paper records.

## Re-ship
Once backfilled, regenerate `papers_core.jsonl` in the `core-graph-v0.2` bundle
with the `date` field; then I re-run clustering / payload and re-upload
`graph.json` + `clusters.json`.

## Verify
```python
import json
from collections import Counter
rows=[json.loads(l) for l in open("papers_core.jsonl")]
print(Counter(r.get("date_precision","MISSING") for r in rows))   # want mostly day/month
print(sum(1 for r in rows if not r.get("date")), "papers with no date")
```

Cross-ref: `scoper-primary-filter-handoff.md` (sibling handoff), `atlas_review.py`
(`version_variant` precedence rule), `gen_atlas_view.py` (frontier chronology consumer).
