/**
 * Prior — gold-set labelling app (Google Apps Script, bound to the labelling Sheet).
 *
 * ONE tab: `sites` — 809 rows sorted by queue_rank, header in row 1, created by importing
 * out/gold_export/sheet.csv. The app reads the context columns and writes the gold_* ones
 * back into the same row.
 *
 * The browser NEVER receives judge_*, edge_*, sj_* or sample_type — the payload is built
 * field by field in getSite(), so labelling stays blind.
 *
 * Deploy: Deploy > New deployment > Web app > Execute as ME, Access ONLY MYSELF.
 */

var TAB = 'sites';
var LABELLER = 'callum';          // stamped on every saved row
var SKIP = 'SKIP';                // gold_intent value meaning "passed on this one"

// ── plumbing ──────────────────────────────────────────────────────────────

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Prior — gold labelling')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1');
}

function sh_() {
  var s = SpreadsheetApp.getActive().getSheetByName(TAB);
  if (!s) throw new Error('Missing tab: ' + TAB + ' — import sheet.csv and rename the tab.');
  return s;
}

/** header name -> 1-based column index */
function cols_(sheet) {
  var head = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0], m = {};
  for (var i = 0; i < head.length; i++) m[String(head[i]).trim()] = i + 1;
  return m;
}

function colValues_(sheet, colIdx) {
  var n = sheet.getLastRow() - 1;
  return n < 1 ? [] : sheet.getRange(2, colIdx, n, 1).getValues().map(function (r) { return r[0]; });
}

/** Rows are exported in queue order, so row = rank + 1. Verify, else scan. */
function rowForRank_(sheet, c, rank) {
  var guess = rank + 1;
  if (guess >= 2 && guess <= sheet.getLastRow() &&
      Number(sheet.getRange(guess, c.queue_rank).getValue()) === Number(rank)) return guess;
  var vals = colValues_(sheet, c.queue_rank);
  for (var i = 0; i < vals.length; i++) if (Number(vals[i]) === Number(rank)) return i + 2;
  throw new Error('queue_rank ' + rank + ' not found');
}

// ── read API ──────────────────────────────────────────────────────────────

/** Progress + where to resume. */
function getState() {
  var s = sh_(), c = cols_(s);
  var intents = colValues_(s, c.gold_intent), ranks = colValues_(s, c.queue_rank);
  var done = 0, skipped = 0, firstOpen = 0;
  for (var i = 0; i < intents.length; i++) {
    var v = String(intents[i]).trim();
    if (v === SKIP) skipped++;
    else if (v) done++;
    else if (!firstOpen) firstOpen = Number(ranks[i]);
  }
  return { total: intents.length, labelled: done, skipped: skipped,
           firstOpen: firstOpen || intents.length };
}

/** Full payload for one queue rank. Judge fields are deliberately not included. */
function getSite(rank) {
  var s = sh_(), c = cols_(s);
  rank = Math.max(1, Math.min(Number(rank) || 1, s.getLastRow() - 1));
  var v = s.getRange(rowForRank_(s, c, rank), 1, 1, s.getLastColumn()).getValues()[0];
  var g = function (name) { return c[name] ? String(v[c[name] - 1]) : ''; };

  return {
    rank: rank,
    site_key: g('site_key'),
    cite_key: g('cite_key'),
    site_idx: Number(g('site_idx')) + 1,
    n_sites: Number(g('n_sites_on_edge')),
    claim: g('claim'),
    citing: { title: g('citing_title'), year: g('citing_year'),
              authors: g('citing_authors'), abstract: g('citing_abstract') },
    cited: { title: g('cited_title'), year: g('cited_year'),
             authors: g('cited_authors'), abstract: g('cited_abstract') },
    existing: { intent: g('gold_intent'), support: g('gold_support'),
                priority: g('gold_priority'), notes: g('gold_notes') },
    state: getState()
  };
}

/** First rank > afterRank with an empty gold_intent (SKIP counts as handled). */
function nextOpen(afterRank) {
  var s = sh_(), c = cols_(s);
  var intents = colValues_(s, c.gold_intent), ranks = colValues_(s, c.queue_rank);
  for (var i = 0; i < intents.length; i++) {
    if (Number(ranks[i]) > Number(afterRank) && !String(intents[i]).trim()) {
      return getSite(Number(ranks[i]));
    }
  }
  return getSite(Math.min(Number(afterRank) + 1, intents.length));
}

// ── write API ─────────────────────────────────────────────────────────────

/**
 * payload: {rank, site_key, intent, support, priority, notes, seconds}
 * Writes the gold columns of that row and returns the next open site.
 */
function saveLabel(p) {
  var lock = LockService.getScriptLock();
  lock.waitLock(20000);
  try {
    var s = sh_(), c = cols_(s);
    var row = rowForRank_(s, c, p.rank);
    if (String(s.getRange(row, c.site_key).getValue()) !== p.site_key) {
      throw new Error('row/site_key mismatch — reload the app');
    }
    var prev = Number(s.getRange(row, c.revision).getValue()) || 0;
    var set = function (name, val) { if (c[name]) s.getRange(row, c[name]).setValue(val); };
    set('gold_intent', p.intent || '');
    set('gold_support', p.support || '');
    set('gold_priority', p.priority || '');
    set('gold_notes', p.notes || '');
    set('labeller', LABELLER);
    set('labelled_at', new Date().toISOString());
    set('seconds', Math.round(Number(p.seconds) || 0));
    set('revision', prev + 1);
    SpreadsheetApp.flush();
  } finally {
    lock.releaseLock();
  }
  return nextOpen(p.rank);
}

/** Skip never clobbers a real label — skipping an already-labelled site just moves on. */
function skipSite(p) {
  var s = sh_(), c = cols_(s);
  var existing = String(s.getRange(rowForRank_(s, c, p.rank), c.gold_intent).getValue()).trim();
  if (existing && existing !== SKIP) return nextOpen(p.rank);
  return saveLabel({ rank: p.rank, site_key: p.site_key, intent: SKIP,
                     notes: p.notes || '', seconds: p.seconds });
}
