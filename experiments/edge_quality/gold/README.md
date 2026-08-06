# Gold-set labelling — Google Sheets backend + phone-friendly web app

Milestone 2 §6C. Hand-label claim-sites blind, in a browser on any device, with the labels
landing in a Google Sheet you own.

```
export_gold_sheet.py ──► sheet.csv ──► one Google Sheet tab (`sites`)
                                              │
                                  Apps Script web app (phone/desktop URL)
                                              │  writes the gold_* columns
                                              ▼
                            download the tab ──► score_gold.py ──► out/gold_eval.md
```

**Everything that exists** — if you see a reference to anything else, it's out of date:

| path | what |
|---|---|
| `export_gold_sheet.py` | builds the one CSV; also does the label-preserving refresh (§6) |
| `appsscript/Code.gs` | server side — reads/writes the sheet |
| `appsscript/Index.html` | the labelling UI |
| `score_gold.py` | the downloaded sheet → `out/gold_eval.md` |
| `../out/gold_export/sheet.csv` | the generated export (derived; regenerate, don't edit) |

One CSV, one spreadsheet, one tab named `sites`, two Apps Script files.

---

## 0. Why an Apps Script *web app* and not a Sheets add-on

Your supervisor's advice (Sheets as the backend) is right — but one detail matters:
**Apps Script sidebars, dialogs and custom menus do not run in the Google Sheets mobile
app.** `SpreadsheetApp.getUi()` simply doesn't exist there. So the usual "Extensions >
Apps Script > show a sidebar" recipe is desktop-only and would fail exactly where you want
it most.

What *does* work on a phone is the same Apps Script project **deployed as a web app**: it
gets its own URL, renders a normal mobile web page, and talks to the spreadsheet
server-side via `SpreadsheetApp`. Sheet is still the backend and the single source of
truth; you just get a real UI in front of it. Free, no server, no OAuth setup on your side
— and it's the *same* amount of code as a desktop-only sidebar, so there's nothing to save
by giving up mobile.

---

## 1. Export

```bash
python experiments/edge_quality/gold/export_gold_sheet.py
```

Writes one file: **`out/gold_export/sheet.csv`** — 809 rows × 51 columns, ~3.6 MB.
Everything is in it: the gold columns the app writes, the context you read (abstracts
inlined, duplicated per site), the judge verdicts, the quality gates and the second-judge
fields.

Flags: `--n-random 80`, `--strat-per-class 27`, `--seed 17`, `--merge-gold <csv>` (§6).

### The sampling design (this is what makes accuracy computable)

`queue_rank` is the order the app serves; `sample_type` is the block:

| block | n | purpose |
|---|---|---|
| `random_eval` | 80 | uniform random sample, **in random order** → any prefix is still a uniform sample. Stop whenever; the accuracy number stays unbiased. |
| `disagreement` | 12 | the second-judge disagreement sites (2 of the 14 already fell in the random block). Deliberately enriched for hard cases → **excluded from accuracy**, used to referee the two taxonomy forks. |
| `strat_topup` | 30 | random top-up so each predicted class reaches 27 → per-class precision/recall and macro-F1. |
| `rest` | 687 | queued after, if you want to keep going. |

**Gold target = 122 sites**, covering `background` 68 / `uses_extends` 27 /
`compares_contrasts` 27. The `random_eval` block gives ≈ **±9pt** on the headline accuracy
at n=80 (n=120 would have been ±6pt — that's the price of the shorter session, and it's a
fine one to pay for a first real number).

**Judge verdicts are in the sheet but never reach the browser** — the web app builds its
payload field by field in `getSite()`, so labelling stays blind. `sample_type` is hidden
too, so you can't tell a hard case from a random one while labelling.

---

## 2. Set it up — the full checklist (~8 min, once)

There is **one** CSV, **one** spreadsheet, **one** tab. Nothing else to create.

### A. Make the spreadsheet (3 min)

1. Go to **[sheets.new](https://sheets.new)**. Name it **`prior-gold-intent`** (top-left).
2. **File > Import > Upload**, drop in `experiments/edge_quality/out/gold_export/sheet.csv`.
3. In the import dialog set:
   - Import location: **Replace spreadsheet**
   - Separator type: **Detect automatically**
   - ⚠️ **Untick "Convert text to numbers, dates, and formulas"** — otherwise Sheets
     mangles claim text that looks like a date or a formula. This is the one setting that
     will silently ruin the data if you get it wrong.
4. **Import data**, and wait — it's 3.6 MB, so 20–30 s.
5. Double-click the tab at the bottom and **rename it to exactly `sites`** (lowercase).
   The script looks the tab up by that name and refuses to run otherwise.

✅ Check: row 1 reads `site_key, queue_rank, sample_type, random_ord, gold_intent, …`, you
have 810 rows (809 + header), and columns E–L (`gold_intent` … `revision`) are empty.

### B. Install the app (5 min)

6. In the sheet: **Extensions > Apps Script**. A project opens containing an empty
   `Code.gs` with a stub `myFunction()`.
7. Select everything in `Code.gs` and replace it with the contents of
   `experiments/edge_quality/gold/appsscript/Code.gs`.
8. In the left sidebar next to **Files**, click **+ > HTML**. Name it exactly **`Index`**
   (no `.html` — Apps Script appends that itself). Select everything in the new file and
   replace it with the contents of `appsscript/Index.html`.
9. **Save** (💾 / Ctrl-S). You should now have exactly two files: `Code.gs` and `Index.html`.
10. **Deploy > New deployment**. Click the ⚙️ next to "Select type" → **Web app**.
    - Description: `gold labeller`
    - Execute as: **Me**
    - Who has access: **Only myself**
    - **Deploy**.
11. **Authorize access** → pick your account → you'll hit *"Google hasn't verified this
    app"*. Expected, it's your own script: **Advanced > Go to <project name> (unsafe) >
    Allow**. (Your code, your account, your sheet — nothing leaves it.)
12. Copy the **Web app URL** (ends in `/exec`). That's your labelling app — open it.

✅ Check: the app loads on site **#1** with a citing/cited pair, a claim with a highlighted
**[THIS CITATION]**, and `0 / 809 labelled` in the header.

**On your phone:** open the URL in Chrome/Safari signed into the same Google account →
share/menu → **Add to Home Screen**. It then behaves like an app.

> Changed the code later? **Deploy > Manage deployments > ✏️ > Version: New version >
> Deploy.** Same URL. (Just saving the editor is not enough for the deployed URL.)

---

## 4. Using it

The app opens at the first unlabelled site in queue order.

- **Three big buttons** = the intent decision. In **fast** mode (toggle top-right, on by
  default) one tap saves and advances — that's the whole loop for the common case.
- **`+ all three`** opens `supports_claim` (4 options), `priority` (2) and a notes box.
  Opening it turns off the one-tap path, so you finish with **Save & next**.
  Anything you leave blank is simply not labelled — intent alone is a valid row.
- **skip** writes `SKIP` (so it won't be served again; the scorer ignores it). Skipping a
  site you've already labelled does nothing but move on.
- **back** / **jump** to revisit. Re-opening a labelled site pre-loads your answer and
  the header says *already labelled (editing)*; saving bumps `revision`.
- Desktop keys: `1` `2` `3` = intent, `Enter` = save, `←` `→` = move.
- Abstracts are collapsed by default — tap **Cited paper abstract** (the evidence the
  judge saw) or **Citing paper abstract**.
- In the claim, `[CITED:TARGET]` renders as a highlighted **[THIS CITATION]** and other
  citations dim to `[other]` — same convention the judge was given.

**Decide the two forks consciously and note them** (§6C of the quickstart), because the
first one sits on the majority class:

1. a bare row in a comparison table → `background` or `compares_contrasts`?
2. a baseline you rerun → `uses_extends` or `compares_contrasts`?

---

## 5. Score it

In the sheet: **File > Download > Comma-separated values**. This downloads the tab you're
looking at, and Google names the file `<spreadsheet name> - <tab name>.csv` — so with the
names from §2 you get **`prior-gold-intent - sites.csv`** in `~/Downloads`. That is the
same single file coming back; there is nothing to combine.

PowerShell (one line — PowerShell has no `\` line-continuation, it would be passed to the
script as a stray argument):

```powershell
python experiments/edge_quality/gold/score_gold.py --sheet "$HOME\Downloads\prior-gold-intent - sites.csv"
```

bash/zsh:

```bash
python experiments/edge_quality/gold/score_gold.py \
    --sheet "$HOME/Downloads/prior-gold-intent - sites.csv"
```

Writes `out/gold_eval.md`: the unbiased random-sample accuracy with a Wilson CI, the
reweighted stratified estimate, per-class precision/recall/**macro-F1**, the
disagreement-block referee (ours vs Opus, broken down by fork), support/priority agreement
where labelled, accuracy split by `bibtex_valid`, and every miss with the judge's
justification for eyeballing. Safe to run at any point mid-labelling.

---

## 6. Refreshing the data without losing labels

Because it's one file, a re-import replaces the gold columns too — so the merge happens
**before** the import, in the exporter:

```powershell
# 1. download the current sheet: File > Download > CSV  (-> "prior-gold-intent - sites.csv")
# 2. rebuild from fixed upstream data, carrying your labels across by site_key (ONE line):
python experiments/edge_quality/gold/export_gold_sheet.py --merge-gold "$HOME\Downloads\prior-gold-intent - sites.csv"
# 3. re-import the regenerated out/gold_export/sheet.csv:
#    File > Import > Replace spreadsheet, untick "Convert text to numbers…"
# 4. rename the tab back to `sites`
```

It prints `merging N previously-labelled rows` — check N matches your progress before you
import.

Two things make this safe:

- **`queue_rank` is a hash of `(seed, site_key)`, not a positional shuffle.** Sites added
  or dropped upstream (e.g. the megablob re-resolve) don't reshuffle the ones you already
  labelled.
- If a labelled site *does* change block anyway, the exporter prints
  `⚠ N already-labelled sites changed sample_type` — that would quietly corrupt the
  accuracy split, so don't ignore it.

Keep `--seed 17` and the same block sizes across refreshes.

---

## 7. Notes

- **Second labeller?** Change `LABELLER` in `Code.gs`, and in the deployment set access to
  *Anyone with a Google account* (still "Execute as: Me", so they never need sheet
  access). Two people writing the same tab will overwrite each other — give the second
  person their own copy of the sheet if you want double-annotation and an IAA number.
- **Speed.** Each tap is a round-trip to Google (~0.3–1 s). The dock stays put and dims
  while saving.
- **`sheet.csv` is derived** — regenerate it rather than editing it; the Sheet is the copy
  that holds your labels.
- **Shell gotcha (PowerShell).** `\` is *not* a line-continuation in PowerShell — it gets
  passed to the script as a stray argument (`error: unrecognized arguments: \`) or breaks
  the parse outright (`Unexpected token 'sheet'`). Keep each command on one line, or use a
  backtick `` ` `` to continue. `$HOME` and forward slashes both work fine in PowerShell.
- **Nothing here is metered** — Apps Script is free, and no LLM is involved.
